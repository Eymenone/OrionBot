"""
OrionBot Backend — Conversations
Her sohbeti Vault'taki gibi kalıcı bir Markdown dosyası olarak saklar.
Sohbetler arası [[bağlantı]] sistemi (Obsidian wikilink mantığı) destekler —
bir sohbette bahsedilen konu başka bir sohbette/notta geçiyorsa otomatik
ilişkilendirilebilir.

Depo: ~/.orionbot/conversations/<sohbet_id>.md
Format:
    ---
    title: Klasör temizliği
    starred: true
    created: 2026-07-12 20:44
    updated: 2026-07-12 20:46
    links: [[Temizlik Listesi]]
    ---

    ## Sen (20:44)
    Masaüstümdeki eski proje klasörlerini temizler misin?

    ## OrionBot (20:44)
    Tabii, önce mevcut klasörleri listeleyeyim.

    ---KOMUT---
    $ ls ~/Desktop/eski_projeler
    deneme_2023/
    web-taslak/
    ---SONU---

Kullanım:
    conv = ConversationStore()
    cid = conv.yeni("Klasör temizliği")
    conv.mesaj_ekle(cid, "user", "Merhaba")
    conv.mesaj_ekle(cid, "ai", "Merhaba! Nasıl yardımcı olabilirim?")
    conv.listele()
    conv.mesajlari_oku(cid)
    conv.yildizla(cid, True)
    conv.bagli_notlari_bul(cid)   # -> Vault'taki ilişkili notlar
"""
import re
import time
import uuid
from pathlib import Path
from typing import List, Dict, Optional

DEFAULT_CONV_DIR = Path.home() / ".orionbot" / "conversations"

ROLE_LABELS = {
    "user": "Sen",
    "ai": "OrionBot",
    "command": "Terminal",
    "vault": "Vault",
}


class ConversationStore:
    def __init__(self, conv_dir: Optional[Path] = None, vault=None):
        self.d = Path(conv_dir) if conv_dir else DEFAULT_CONV_DIR
        self.d.mkdir(parents=True, exist_ok=True)
        self.vault = vault  # opsiyonel — bağlı notları bulmak için Vault referansı

    # ── Sohbet oluşturma / silme ─────────────────────────────────────

    def yeni(self, title: str = "Yeni sohbet") -> str:
        cid = str(uuid.uuid4())[:8]
        ts = time.strftime("%Y-%m-%d %H:%M")
        content = self._frontmatter(title, False, ts, ts, []) + "\n"
        (self.d / f"{cid}.md").write_text(content, encoding="utf-8")
        return cid

    def sil(self, cid: str) -> bool:
        f = self.d / f"{cid}.md"
        if f.exists():
            f.unlink()
            return True
        return False

    # ── Mesaj ekleme ─────────────────────────────────────────────────

    def mesaj_ekle(self, cid: str, role: str, text: str, output: str = "") -> bool:
        f = self.d / f"{cid}.md"
        if not f.exists():
            return False

        ts = time.strftime("%H:%M")
        label = ROLE_LABELS.get(role, role)

        if role == "command":
            block = f"\n## {label} ({ts})\n\n---KOMUT---\n$ {text}\n{output}\n---SONU---\n"
        else:
            block = f"\n## {label} ({ts})\n\n{text}\n"

        with f.open("a", encoding="utf-8") as fh:
            fh.write(block)

        self._touch_updated(cid)

        # İlk kullanıcı mesajından otomatik başlık üret (hâlâ "Yeni sohbet" ise)
        if role == "user":
            self._maybe_autotitle(cid, text)

        return True

    def _maybe_autotitle(self, cid: str, first_text: str):
        meta = self._meta_oku(cid)
        if meta.get("title") == "Yeni sohbet":
            baslik = first_text.strip()[:32]
            if len(first_text.strip()) > 32:
                baslik += "…"
            self.basligi_guncelle(cid, baslik or "Yeni sohbet")

    # ── Meta işlemleri ────────────────────────────────────────────────

    def basligi_guncelle(self, cid: str, title: str) -> bool:
        return self._update_meta_field(cid, "title", title)

    def yildizla(self, cid: str, starred: bool) -> bool:
        return self._update_meta_field(cid, "starred", "true" if starred else "false")

    def _update_meta_field(self, cid: str, field: str, value: str) -> bool:
        f = self.d / f"{cid}.md"
        if not f.exists():
            return False
        content = f.read_text(encoding="utf-8", errors="ignore")
        pattern = rf"^{field}:.*$"
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, f"{field}: {value}", content, count=1, flags=re.MULTILINE)
        f.write_text(content, encoding="utf-8")
        return True

    def _touch_updated(self, cid: str):
        self._update_meta_field(cid, "updated", time.strftime("%Y-%m-%d %H:%M"))

    # ── Okuma / listeleme ──────────────────────────────────────────────

    def _meta_oku(self, cid: str) -> Dict:
        f = self.d / f"{cid}.md"
        if not f.exists():
            return {}
        content = f.read_text(encoding="utf-8", errors="ignore")
        meta = {}
        fm_match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
        if fm_match:
            for line in fm_match.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
        return meta

    def listele(self) -> List[Dict]:
        sonuc = []
        for f in self.d.glob("*.md"):
            cid = f.stem
            meta = self._meta_oku(cid)
            sonuc.append({
                "id": cid,
                "title": meta.get("title", "Yeni sohbet"),
                "starred": meta.get("starred", "false") == "true",
                "updated": meta.get("updated", ""),
                "created": meta.get("created", ""),
            })
        # Yıldızlılar üstte, sonra son güncellenme sırasına göre
        sonuc.sort(key=lambda c: (not c["starred"], c["updated"]), reverse=False)
        sonuc.sort(key=lambda c: c["starred"], reverse=True)
        return sonuc

    def mesajlari_oku(self, cid: str) -> List[Dict]:
        """Sohbetin tam mesaj listesini (role, text, output) döndürür."""
        f = self.d / f"{cid}.md"
        if not f.exists():
            return []
        content = f.read_text(encoding="utf-8", errors="ignore")
        # frontmatter'ı at
        content = re.sub(r"^---\n.*?\n---\n", "", content, count=1, flags=re.DOTALL)

        mesajlar = []
        blocks = re.split(r"\n## ", content)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            header_match = re.match(r"(\w+) \(([\d:]+)\)\n?(.*)", block, re.DOTALL)
            if not header_match:
                continue
            label, ts, body = header_match.groups()
            role = next((k for k, v in ROLE_LABELS.items() if v == label), "ai")

            if "---KOMUT---" in body:
                cmd_match = re.search(r"---KOMUT---\n\$ (.+?)\n(.*?)\n---SONU---", body, re.DOTALL)
                if cmd_match:
                    mesajlar.append({"role": "command", "text": cmd_match.group(1).strip(),
                                     "output": cmd_match.group(2).strip(), "ts": ts})
            else:
                mesajlar.append({"role": role, "text": body.strip(), "ts": ts})
        return mesajlar

    def to_ai_history(self, cid: str) -> List[Dict]:
        """AI'a gönderilecek {'role': 'user'|'assistant', 'content': ...} formatına çevirir."""
        mesajlar = self.mesajlari_oku(cid)
        history = []
        for m in mesajlar:
            if m["role"] == "user":
                history.append({"role": "user", "content": m["text"]})
            elif m["role"] == "ai":
                history.append({"role": "assistant", "content": m["text"]})
        return history

    # ── Obsidian tarzı bağlantı sistemi ─────────────────────────────────

    def bagli_notlari_bul(self, cid: str, limit: int = 5) -> List[str]:
        """
        Bu sohbetin içeriğiyle Vault'taki notlar arasında basit kelime
        eşleşmesine dayalı ilişki kurar (gerçek [[wikilink]] olmasa da,
        otomatik bağlam bağlama işlevi görür).
        """
        if not self.vault:
            return []
        mesajlar = self.mesajlari_oku(cid)
        tum_metin = " ".join(m["text"] for m in mesajlar if m["role"] in ("user", "ai"))
        kelimeler = set(w.lower() for w in tum_metin.split() if len(w) > 3)

        sonuc = []
        for not_bilgisi in self.vault.listele():
            baslik_kelime = set(not_bilgisi["baslik"].lower().split())
            if kelimeler & baslik_kelime:
                sonuc.append(not_bilgisi["dosya"])
            if len(sonuc) >= limit:
                break
        return sonuc

    def sayim(self) -> int:
        return len(list(self.d.glob("*.md")))

    # ── Yardımcı ──────────────────────────────────────────────────────

    @staticmethod
    def _frontmatter(title: str, starred: bool, created: str, updated: str, links: List[str]) -> str:
        link_str = ", ".join(f"[[{l}]]" for l in links)
        return (
            f"---\n"
            f"title: {title}\n"
            f"starred: {'true' if starred else 'false'}\n"
            f"created: {created}\n"
            f"updated: {updated}\n"
            f"links: {link_str}\n"
            f"---\n"
        )
