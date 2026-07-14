"""
OrionBot Backend — Vault
Obsidian tarzı, düz Markdown dosyalarına dayalı not deposu.

Kullanım:
    vault = Vault()  # varsayılan: ~/.orionbot/vault
    vault.yaz("Python Notu", "FastAPI async endpoint kullanımı...", ["python","fastapi"])
    notlar = vault.listele()
    sonuclar = vault.ara("fastapi")
"""
import re
import time
from pathlib import Path
from typing import List, Dict, Optional

DEFAULT_VAULT_DIR = Path.home() / ".orionbot" / "vault"


class Vault:
    def __init__(self, vault_dir: Optional[Path] = None):
        self.d = Path(vault_dir) if vault_dir else DEFAULT_VAULT_DIR
        self.d.mkdir(parents=True, exist_ok=True)

    def yaz(self, baslik: str, icerik: str, etiketler: Optional[List[str]] = None) -> str:
        """Yeni bir Markdown notu oluşturur. Oluşan dosya adını döndürür."""
        temiz = re.sub(r'[^\w\s-]', '', baslik)[:60].strip().replace(' ', '_')
        if not temiz:
            temiz = f"not_{int(time.time())}"

        dosya = self.d / f"{temiz}.md"
        ts = time.strftime("%Y-%m-%d %H:%M")
        etiket_str = " ".join(f"#{e}" for e in (etiketler or []))

        md = f"# {baslik}\n\n{etiket_str}\n\n{icerik}\n\n---\n*{ts}*\n"
        dosya.write_text(md, encoding="utf-8")
        return dosya.name

    def listele(self, limit: int = 20) -> List[Dict]:
        """Son değiştirilen notları döndürür (yeni → eski)."""
        sonuc = []
        dosyalar = sorted(self.d.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)
        for f in dosyalar[:limit]:
            txt = f.read_text(encoding="utf-8", errors="ignore")
            baslik = txt.split('\n')[0].lstrip('#').strip()
            etiketler = re.findall(r'#(\w+)', txt[:200])
            sonuc.append({"dosya": f.name, "baslik": baslik, "etiketler": etiketler})
        return sonuc

    def ara(self, sorgu: str, limit: int = 5) -> List[str]:
        """Basit metin araması — sorguyu içeren dosya adlarını döndürür."""
        q = sorgu.lower()
        sonuc = []
        for f in self.d.glob("*.md"):
            if q in f.read_text(encoding="utf-8", errors="ignore").lower():
                sonuc.append(f.name)
                if len(sonuc) >= limit:
                    break
        return sonuc

    def oku(self, dosya_adi: str) -> Optional[str]:
        """Bir notun tam içeriğini döndürür."""
        f = self.d / dosya_adi
        if f.exists():
            return f.read_text(encoding="utf-8", errors="ignore")
        return None

    def sil(self, dosya_adi: str) -> bool:
        f = self.d / dosya_adi
        if f.exists():
            f.unlink()
            return True
        return False

    def sayim(self) -> int:
        return len(list(self.d.glob("*.md")))
