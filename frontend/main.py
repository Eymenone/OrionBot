"""
OrionBot — Native Masaüstü Uygulaması
pywebview (edgechromium backend) ile Windows'ta zaten kurulu olan
Edge WebView2 motorunu kullanır. Tarayıcı açılmaz, localhost kullanılmaz,
HTTP server çalışmaz — her şey doğrudan Python <-> JS köprüsü üzerinden.

Kurulum:
    pip install pywebview requests psutil

Çalıştırma:
    python main.py
"""
import sys
import json
import threading
from pathlib import Path

# PyInstaller ile paketlendiğinde dosyalar geçici bir klasöre (_MEIPASS)
# çıkarılır. Normal çalıştırmada ise script'in bulunduğu klasör kullanılır.
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    BASE = Path(sys._MEIPASS)
    BACKEND_PATH = BASE  # exe içine backend modülleri de gömülü
else:
    BASE = Path(__file__).parent
    BACKEND_PATH = BASE.parent / "backend"

sys.path.insert(0, str(BACKEND_PATH))

import webview
from orion_engine import OrionEngine


class OrionAPI:
    """JS tarafından pywebview.api.<method>() ile çağrılan köprü sınıfı."""

    def __init__(self):
        self.engine = OrionEngine()

    # ── Config ────────────────────────────────────────────────────────

    def get_config(self):
        return self.engine.cfg

    def save_config(self, cfg):
        self.engine.configure(
            provider=cfg.get("provider", ""),
            api_key=cfg.get("api_key", ""),
            model=cfg.get("model", ""),
            base_url=cfg.get("base_url", ""),
        )
        return {"ok": True}

    def save_config_auto(self, api_key, model):
        """API key'den provider'ı otomatik tespit ederek kaydeder."""
        provider = self.engine.configure_auto(api_key, model)
        return {"ok": True, "provider": provider}

    def save_config_local(self, backend, model, base_url):
        """Yerel model (Ollama/LM Studio) için — key gerekmez."""
        self.engine.configure_local(backend, model, base_url)
        return {"ok": True}

    # ── Sohbet ────────────────────────────────────────────────────────

    def ask(self, text):
        result = {"reply": None, "command": None, "command_output": None,
                  "vault_file": None, "error": None}

        def on_reply(t):
            result["reply"] = t

        def on_command(cmd):
            result["command"] = cmd
            if self.engine.allow_all:
                r = self.engine.run_command(cmd)
                result["command_output"] = r["out"] or r["err"]

        def on_vault_write(fname):
            result["vault_file"] = fname

        def on_error(err):
            result["error"] = err

        self.engine.ask(
            text,
            on_reply=on_reply,
            on_command=on_command,
            on_vault_write=on_vault_write,
            on_error=on_error,
            blocking=True,  # senkron — JS zaten await ile bekliyor
        )
        return result

    def confirm_command(self, cmd):
        r = self.engine.run_command(cmd)
        return {"output": r["out"] or r["err"]}

    def toggle_allow(self):
        allow = self.engine.toggle_allow_all()
        return {"allow_all": allow}

    # ── Vault ─────────────────────────────────────────────────────────

    def get_vault(self):
        return {"notes": self.engine.vault.listele()}

    # ── Sohbetler (Conversations) ────────────────────────────────────

    def new_chat(self):
        cid = self.engine.yeni_sohbet()
        return {"id": cid}

    def select_chat(self, cid):
        self.engine.sohbet_sec(cid)
        return {"ok": True, "messages": self.engine.sohbet_mesajlari(cid)}

    def get_chats(self):
        return {"chats": self.engine.sohbet_listele()}

    def get_chat_messages(self, cid):
        return {"messages": self.engine.sohbet_mesajlari(cid)}

    def star_chat(self, cid, starred):
        ok = self.engine.sohbet_yildizla(cid, starred)
        return {"ok": ok}

    def remove_chat(self, cid):
        ok = self.engine.sohbet_sil(cid)
        return {"ok": ok}

    # ── Skills ────────────────────────────────────────────────────────

    def get_skills(self):
        return {"skills": self.engine.skill_listele()}

    def add_skill_repo(self, url):
        name = self.engine.skill_repodan_ekle(url)
        return {"ok": bool(name), "name": name}

    def toggle_skill(self, name, on):
        ok = self.engine.skill_ac_kapat(name, on)
        return {"ok": ok}

    def remove_skill(self, name):
        ok = self.engine.skill_sil(name)
        return {"ok": ok}

    def upload_skill_files(self, files):
        """files: [{"name": "...", "data": "<base64>"}] — JS'den drag-drop veya seçilen dosyalar."""
        import base64
        import tempfile

        eklenen = []
        for f in files:
            try:
                raw = base64.b64decode(f["data"])
                suffix = "_" + f["name"]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(raw)
                    tmp_path = tmp.name
                name = self.engine.skill_dosyadan_ekle(tmp_path)
                if name:
                    eklenen.append(name)
            except Exception:
                continue
        return {"ok": True, "added": eklenen}

    # ── Sistem ────────────────────────────────────────────────────────

    def get_stats(self):
        return self.engine.get_stats()


def _set_windows_icon(window, icon_path: Path):
    """
    pywebview/edgechromium, pencere title bar ve taskbar ikonunu kendiliğinden
    ayarlamaz — PyInstaller'ın --icon bayrağı sadece OrionBot.exe dosyasının
    Windows Gezgini'ndeki simgesini belirler, çalışan pencerenin ikonunu değil.
    Gerçek pencere ikonu için Win32 WM_SETICON mesajını elle göndermek gerekiyor.
    """
    if sys.platform != "win32" or not icon_path.exists():
        return

    def _apply():
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32

            # pywebview penceresinin gerçek Win32 handle'ını bul.
            # Farklı pywebview sürümlerinde farklı iç özelliklerde saklanabiliyor,
            # bu yüzden birkaç olası yolu sırayla deniyoruz.
            hwnd = None
            # pywebview surumune gore hwnd farkli yerlerde olabilir
            for attr in ("hwnd", "_hwnd"):
                hwnd = getattr(window, attr, None)
                if hwnd:
                    break
            if not hwnd:
                native = getattr(window, "native", None)
                if native is not None:
                    handle = getattr(native, "Handle", None)  # WinForms Form.Handle
                    if handle is not None:
                        hwnd = int(handle.ToInt64()) if hasattr(handle, "ToInt64") else int(handle)
            if not hwnd:
                gui = getattr(window, "gui", None)
                hwnd = getattr(gui, "hwnd", None) if gui else None
            if not hwnd:
                # Son çare: pencere başlığından FindWindowW ile bul
                hwnd = user32.FindWindowW(None, "OrionBot")

            if not hwnd:
                return

            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x00000010
            WM_SETICON = 0x0080
            ICON_SMALL = 0
            ICON_BIG = 1

            h_icon = user32.LoadImageW(
                None, str(icon_path), IMAGE_ICON, 0, 0, LR_LOADFROMFILE
            )
            if h_icon:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_icon)
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_icon)
        except Exception:
            pass  # ikon ayarlanamazsa uygulama yine de çalışmaya devam etsin

    # Pencere gerçekten oluşup handle'ı hazır olduktan kısa süre sonra dene
    threading.Timer(0.6, _apply).start()


def main():
    api = OrionAPI()
    index_path = BASE / "index.html"
    icon_path = BASE / "orion.ico"

    window = webview.create_window(
        title="OrionBot",
        url=str(index_path),
        js_api=api,
        width=1400,
        height=860,
        min_size=(900, 600),
        background_color="#121118",
        text_select=True,
        confirm_close=False,
    )

    _set_windows_icon(window, icon_path)

    try:
        webview.start(gui="edgechromium" if sys.platform == "win32" else None)
    except Exception:
        webview.start()


if __name__ == "__main__":
    main()
