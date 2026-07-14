"""
OrionBot Backend — Skill Sistemi
Claude Skills'e benzer: her skill bir klasör, içinde SKILL.md (talimatlar)
ve opsiyonel destek dosyaları (scripts/, references/) bulunur.

Üç kaynaktan skill eklenebilir:
  - dosya   : kullanıcı .zip/.md/.py yükler
  - repo    : bir GitHub repo linkinden çekilir
  - yerel   : elle oluşturulmuş, diskte hazır bulunan skill

Skill deposu: ~/.orionbot/skills/<skill_adi>/SKILL.md

Kullanım:
    mgr = SkillManager()
    mgr.olustur("web-arastirma", "Web'de arama yapıp özet çıkarır...", tags=["arastirma"])
    mgr.listele()
    mgr.ac_kapat("web-arastirma", False)
    mgr.sil("web-arastirma")
    mgr.aktif_sistem_promptu()   # -> AI'a eklenecek metin
"""
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import List, Dict, Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

DEFAULT_SKILLS_DIR = Path.home() / ".orionbot" / "skills"
META_FILE = "_meta.json"  # her skill klasöründe: {"source": "repo", "on": true, "url": "..."}


class Skill:
    def __init__(self, name: str, path: Path, source: str = "yerel",
                 on: bool = True, url: str = ""):
        self.name = name
        self.path = path
        self.source = source  # "dosya" | "repo" | "yerel"
        self.on = on
        self.url = url

    @property
    def skill_md_path(self) -> Path:
        return self.path / "SKILL.md"

    def icerik_oku(self) -> str:
        if self.skill_md_path.exists():
            return self.skill_md_path.read_text(encoding="utf-8", errors="ignore")
        return ""

    def frontmatter_oku(self) -> Dict[str, str]:
        """
        Claude Skills formatındaki YAML frontmatter'ı okur:
            ---
            name: skill-adi
            description: "Ne zaman kullanılacağını anlatan metin..."
            ---
        Bulamazsa boş dict döner.
        """
        icerik = self.icerik_oku()
        m = re.match(r'^---\s*\n(.*?)\n---\s*\n', icerik, re.DOTALL)
        if not m:
            return {}
        meta = {}
        for line in m.group(1).splitlines():
            if ':' not in line:
                continue
            key, _, val = line.partition(':')
            val = val.strip().strip('"').strip("'")
            meta[key.strip()] = val
        return meta

    def ozet(self) -> str:
        """
        Claude Skills uyumlu: önce YAML frontmatter'daki 'description' alanını
        kullanır (gerçek Claude Skills bu şekilde çalışır — model, description'a
        bakarak skill'i ne zaman tetikleyeceğine karar verir). Frontmatter yoksa
        SKILL.md'nin ilk anlamlı paragrafına düşer.
        """
        meta = self.frontmatter_oku()
        if meta.get('description'):
            return meta['description'][:300]

        icerik = self.icerik_oku()
        satirlar = [s.strip() for s in icerik.splitlines() if s.strip() and not s.strip().startswith('#')]
        return satirlar[0][:200] if satirlar else ""

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "source": self.source,
            "on": self.on,
            "url": self.url,
            "ozet": self.ozet(),
        }


class SkillManager:
    def __init__(self, skills_dir: Optional[Path] = None):
        self.dir = Path(skills_dir) if skills_dir else DEFAULT_SKILLS_DIR
        self.dir.mkdir(parents=True, exist_ok=True)

    # ── Listeleme ────────────────────────────────────────────────────

    def listele(self) -> List[Dict]:
        """Diskteki tüm skill'leri tarar ve metadata ile birlikte döndürür."""
        sonuc = []
        for skill_dir in sorted(self.dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill = self._skill_yukle(skill_dir)
            if skill:
                sonuc.append(skill.to_dict())
        return sonuc

    def _skill_yukle(self, skill_dir: Path) -> Optional[Skill]:
        if not (skill_dir / "SKILL.md").exists():
            return None
        meta = self._meta_oku(skill_dir)
        return Skill(
            name=skill_dir.name,
            path=skill_dir,
            source=meta.get("source", "yerel"),
            on=meta.get("on", True),
            url=meta.get("url", ""),
        )

    def _meta_oku(self, skill_dir: Path) -> Dict:
        meta_path = skill_dir / META_FILE
        if meta_path.exists():
            try:
                return json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _meta_yaz(self, skill_dir: Path, meta: Dict):
        (skill_dir / META_FILE).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    # ── Temizle ───────────────────────────────────────────────────────

    @staticmethod
    def _temiz_isim(ad: str) -> str:
        ad = re.sub(r'\.(zip|md|json|py|js|txt)$', '', ad, flags=re.IGNORECASE)
        ad = re.sub(r'[^\w\-]', '_', ad.strip())
        return ad[:60] or "skill"

    # ── Oluşturma — manuel/yerel skill ──────────────────────────────

    def olustur(self, name: str, icerik_md: str, tags: Optional[List[str]] = None,
                description: str = "") -> str:
        """
        Elle bir skill oluşturur. Claude Skills uyumlu YAML frontmatter ile
        (name + description) — gerçek Claude ortamındaki SKILL.md formatının aynısı.
        """
        clean = self._temiz_isim(name)
        skill_dir = self.dir / clean
        skill_dir.mkdir(parents=True, exist_ok=True)

        # description verilmemişse içerikten kısa bir özet türet
        desc = description.strip() or icerik_md.strip().split('\n')[0][:200]
        desc = desc.replace('"', "'")

        md = (
            f"---\n"
            f"name: {clean}\n"
            f'description: "{desc}"\n'
            f"---\n\n"
            f"# {name}\n\n"
            f"{icerik_md}\n"
        )
        (skill_dir / "SKILL.md").write_text(md, encoding="utf-8")

        self._meta_yaz(skill_dir, {"source": "yerel", "on": True, "url": ""})
        return clean

    # ── Dosyadan ekleme (.zip / .md / .py) ───────────────────────────

    def dosyadan_ekle(self, dosya_yolu: Path) -> Optional[str]:
        """
        .zip  -> içinde SKILL.md olan bir klasör bekler, açılır
        .md   -> tek başına SKILL.md olarak kabul edilir
        .py   -> scripts/ altına konur, basit bir SKILL.md oluşturulur
        """
        dosya_yolu = Path(dosya_yolu)
        if not dosya_yolu.exists():
            return None

        clean = self._temiz_isim(dosya_yolu.stem)
        skill_dir = self.dir / clean

        if dosya_yolu.suffix.lower() == ".zip":
            skill_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(dosya_yolu) as z:
                z.extractall(skill_dir)
            # Eğer zip içinde tek bir alt klasör varsa, içeriği yukarı taşı
            alt_klasorler = [p for p in skill_dir.iterdir() if p.is_dir()]
            if len(alt_klasorler) == 1 and not (skill_dir / "SKILL.md").exists():
                for item in alt_klasorler[0].iterdir():
                    shutil.move(str(item), str(skill_dir / item.name))
                alt_klasorler[0].rmdir()
            if not (skill_dir / "SKILL.md").exists():
                # SKILL.md yoksa otomatik oluştur
                (skill_dir / "SKILL.md").write_text(
                    f"# {dosya_yolu.stem}\n\nZip'ten yüklenen skill.\n", encoding="utf-8")

        elif dosya_yolu.suffix.lower() == ".md":
            skill_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dosya_yolu, skill_dir / "SKILL.md")

        elif dosya_yolu.suffix.lower() in (".py", ".js"):
            skill_dir.mkdir(parents=True, exist_ok=True)
            scripts_dir = skill_dir / "scripts"
            scripts_dir.mkdir(exist_ok=True)
            shutil.copy2(dosya_yolu, scripts_dir / dosya_yolu.name)
            (skill_dir / "SKILL.md").write_text(
                f"# {dosya_yolu.stem}\n\n"
                f"Bu skill, scripts/{dosya_yolu.name} dosyasını içerir.\n"
                f"Gerektiğinde bu scripti çalıştırabilirsin.\n",
                encoding="utf-8")
        else:
            return None

        self._meta_yaz(skill_dir, {"source": "dosya", "on": True, "url": ""})
        return clean

    # ── Repo'dan ekleme ───────────────────────────────────────────────

    def repodan_ekle(self, url: str) -> Optional[str]:
        """
        GitHub repo linkinden skill çeker.
        Repo'da SKILL.md varsa onu, yoksa README.md'yi SKILL.md olarak kaydeder.
        """
        if not HAS_REQUESTS:
            return None

        url = url.strip().rstrip("/")
        if not url.startswith("http"):
            url = "https://" + url

        # github.com/kullanici/repo -> raw.githubusercontent.com/kullanici/repo/main/...
        m = re.search(r'github\.com/([^/]+)/([^/]+)', url)
        if not m:
            return None
        owner, repo = m.group(1), m.group(2).replace(".git", "")

        clean = self._temiz_isim(repo)
        skill_dir = self.dir / clean
        skill_dir.mkdir(parents=True, exist_ok=True)

        icerik = None
        for branch in ("main", "master"):
            for dosya in ("SKILL.md", "README.md"):
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{dosya}"
                try:
                    r = requests.get(raw_url, timeout=10)
                    if r.status_code == 200:
                        icerik = r.text
                        break
                except Exception:
                    continue
            if icerik:
                break

        if icerik is None:
            icerik = f"# {repo}\n\nRepo: {url}\n\n(İçerik otomatik çekilemedi, manuel düzenleyin.)\n"

        (skill_dir / "SKILL.md").write_text(icerik, encoding="utf-8")
        self._meta_yaz(skill_dir, {"source": "repo", "on": True, "url": url})
        return clean

    # ── Aç/kapat/sil ─────────────────────────────────────────────────

    def ac_kapat(self, name: str, on: bool) -> bool:
        skill_dir = self.dir / name
        if not skill_dir.exists():
            return False
        meta = self._meta_oku(skill_dir)
        meta["on"] = on
        self._meta_yaz(skill_dir, meta)
        return True

    def sil(self, name: str) -> bool:
        skill_dir = self.dir / name
        if skill_dir.exists() and skill_dir.is_dir():
            shutil.rmtree(skill_dir)
            return True
        return False

    # ── AI için sistem promptu üretme ────────────────────────────────

    def aktif_skill_ozeti(self) -> str:
        """
        Aktif (on=True) tüm skill'lerin kısa özetini birleştirip
        AI'ın system promptuna eklenecek metni üretir.
        """
        aktifler = [s for s in self.listele() if s["on"]]
        if not aktifler:
            return ""
        satirlar = ["Yüklü ve aktif yeteneklerin (skills):"]
        for s in aktifler:
            satirlar.append(f"  - {s['name']}: {s['ozet']}")
        satirlar.append(
            "Bir skill'in tam içeriğine ihtiyacın olursa, "
            "SKILL_OKU: <skill_adi> formatını kullanabilirsin.")
        return "\n".join(satirlar)

    def skill_tam_icerik(self, name: str) -> Optional[str]:
        """Bir skill'in tam SKILL.md içeriğini döndürür (AI istediğinde)."""
        skill_dir = self.dir / name
        skill = self._skill_yukle(skill_dir) if skill_dir.exists() else None
        return skill.icerik_oku() if skill else None

    def sayim(self) -> int:
        return len(self.listele())

    def aktif_sayim(self) -> int:
        return len([s for s in self.listele() if s["on"]])
