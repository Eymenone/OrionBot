"""
OrionBot Backend — Ana Motor (Engine)
Tüm backend parçalarını (AI, Vault, Terminal, Config) birleştirip
tek bir basit arayüz sunar. Herhangi bir frontend (Claude Design, Tkinter,
web UI, her ne olursa) bu sınıfı çağırarak OrionBot'un tüm işlevlerine erişir.

Kullanım (frontend tarafında):

    from orion_engine import OrionEngine

    engine = OrionEngine()

    # Kurulum kontrolü
    if not engine.is_configured():
        engine.configure(provider="custom", api_key="...", model="z-ai/glm-5.2",
                         base_url="https://integrate.api.nvidia.com/v1/chat/completions")

    # Mesaj gönder — callback'ler UI'ı güncellemek için kullanılır
    engine.ask(
        "Merhaba, bana Python'da hızlı sıralama algoritması yaz",
        on_thinking=lambda: print("Düşünüyor..."),
        on_reply=lambda text: print("Cevap:", text),
        on_command=lambda cmd: print("Komut isteniyor:", cmd),
        on_vault_write=lambda fname: print("Not kaydedildi:", fname),
        on_error=lambda err: print("Hata:", err),
    )

    # Terminal komutu onaylandıysa çalıştır
    engine.run_command("dir")

    # Vault'a direkt erişim
    engine.vault.listele()
"""
import re
import threading
from typing import Callable, Optional, List, Dict

from ai_client import AIClient
from vault import Vault
from terminal import Runner
from conversations import ConversationStore
from config import load_cfg, save_cfg, PROVIDERS
from home_assistant import HomeAssistant
from skills import SkillManager


SYSTEM_PROMPT_TEMPLATE = """Sen OrionBot'sun — kullanıcının AI asistanısın.
Kısa ve net yanıtla. Türkçe kullan.

Eğer bir terminal komutu çalıştırman gerekiyorsa şu formatı kullan (satırın başında):
ÇALIŞTIR: <komut>

Eğer önemli, kalıcı bir bilgiyi not olarak kaydetmen gerekiyorsa:
NOT: <başlık> | <içerik> | <etiket1,etiket2>

Eğer bir ev cihazını (ışık, priz, termostat, kilit) kontrol etmen gerekiyorsa:
EV: <domain>.<servis>.<entity_id>.<opsiyonel_deger>
örnekler:
  EV: light.turn_on.light.salon
  EV: light.turn_on.light.salon.200        (200 = parlaklık)
  EV: switch.turn_off.switch.priz1
  EV: climate.set_temperature.climate.salon.22.5

{skills_ctx}

allow_all={allow_all}
{allow_note}

Model: {model}
{vault_ctx}
{ha_ctx}"""


class OrionEngine:
    def __init__(self):
        self.cfg: Dict = load_cfg()
        self.vault = Vault()
        self.runner = Runner()
        self.skills = SkillManager()
        self.conversations = ConversationStore(vault=self.vault)
        self.ai: Optional[AIClient] = None
        self.history: List[Dict] = []
        self.allow_all: bool = self.cfg.get("allow_all", False)
        self._pending_cmd: Optional[str] = None
        self._pending_ha: Optional[Dict] = None
        self.ha: Optional[HomeAssistant] = None
        self.active_chat_id: Optional[str] = None

        if self.is_configured():
            self._init_ai()
        self._init_ha()

    # ── Kurulum ────────────────────────────────────────────────────────

    def is_configured(self) -> bool:
        return bool(self.cfg.get("provider") and self.cfg.get("model"))

    def configure(self, provider: str, api_key: str, model: str, base_url: str = ""):
        """Yeni ayarları kaydet ve AI client'ı yeniden başlat."""
        if not base_url:
            base_url = PROVIDERS.get(provider, {}).get("url", "")
        self.cfg = {
            "provider": provider,
            "api_key": api_key,
            "model": model,
            "base_url": base_url,
            "allow_all": self.allow_all,
        }
        save_cfg(self.cfg)
        self._init_ai()

    def configure_auto(self, api_key: str, model: str) -> str:
        """
        API key'in formatından provider'ı otomatik tespit edip yapılandırır.
        Kullanıcı provider seçmek zorunda kalmaz. Tespit edilen provider'ı döndürür.
        """
        from ai_client import detect_provider
        provider = detect_provider(api_key)
        self.configure(provider=provider, api_key=api_key, model=model, base_url="")
        return provider

    def configure_local(self, backend: str, model: str, base_url: str = "") -> None:
        """
        Yerel model (Ollama/LM Studio) için — key gerekmez, otomatik tespit edilemez,
        kullanıcı açıkça 'yerel' seçmiş olur.
        backend: 'ollama' | 'lmstudio' | 'custom'
        """
        self.configure(provider=backend, api_key="", model=model, base_url=base_url)

    def _init_ai(self):
        self.ai = AIClient(
            provider=self.cfg.get("provider", ""),
            api_key=self.cfg.get("api_key", ""),
            model=self.cfg.get("model", ""),
            base_url=self.cfg.get("base_url", ""),
        )

    def _init_ha(self):
        """Home Assistant bağlantısı varsa kur."""
        ha_url = self.cfg.get("ha_url", "")
        ha_token = self.cfg.get("ha_token", "")
        if ha_url and ha_token:
            self.ha = HomeAssistant(ha_url, ha_token)
        else:
            self.ha = None

    def configure_home_assistant(self, url: str, token: str) -> bool:
        """
        Home Assistant bağlantısını kaydet. Bağlantı testi başarılıysa True döner.
        url: örn. "http://192.168.1.100:8123"
        token: Home Assistant Long-Lived Access Token
        """
        test_client = HomeAssistant(url, token)
        basarili = test_client.baglanti_testi()
        if basarili:
            self.cfg["ha_url"] = url
            self.cfg["ha_token"] = token
            save_cfg(self.cfg)
            self.ha = test_client
        return basarili

    def is_home_assistant_configured(self) -> bool:
        return self.ha is not None

    # ── Sohbet (Conversation) yönetimi ──────────────────────────────────

    def yeni_sohbet(self) -> str:
        cid = self.conversations.yeni()
        self.active_chat_id = cid
        self.history = []
        return cid

    def sohbet_sec(self, cid: str):
        self.active_chat_id = cid
        self.history = self.conversations.to_ai_history(cid)

    def sohbet_listele(self) -> List[Dict]:
        return self.conversations.listele()

    def sohbet_mesajlari(self, cid: str) -> List[Dict]:
        return self.conversations.mesajlari_oku(cid)

    def sohbet_yildizla(self, cid: str, starred: bool) -> bool:
        return self.conversations.yildizla(cid, starred)

    def sohbet_sil(self, cid: str) -> bool:
        return self.conversations.sil(cid)

    def _ensure_active_chat(self):
        """Aktif sohbet yoksa otomatik bir tane oluşturur."""
        if not self.active_chat_id:
            self.active_chat_id = self.conversations.yeni()

    # ── Skill yönetimi ───────────────────────────────────────────────

    def skill_listele(self) -> List[Dict]:
        return self.skills.listele()

    def skill_dosyadan_ekle(self, dosya_yolu: str) -> Optional[str]:
        from pathlib import Path as _P
        return self.skills.dosyadan_ekle(_P(dosya_yolu))

    def skill_repodan_ekle(self, url: str) -> Optional[str]:
        return self.skills.repodan_ekle(url)

    def skill_ac_kapat(self, name: str, on: bool) -> bool:
        return self.skills.ac_kapat(name, on)

    def skill_sil(self, name: str) -> bool:
        return self.skills.sil(name)

    def toggle_allow_all(self) -> bool:
        self.allow_all = not self.allow_all
        self.cfg["allow_all"] = self.allow_all
        save_cfg(self.cfg)
        return self.allow_all

    # ── Mesajlaşma ─────────────────────────────────────────────────────

    def ask(
        self,
        text: str,
        on_thinking: Optional[Callable[[], None]] = None,
        on_reply: Optional[Callable[[str], None]] = None,
        on_command: Optional[Callable[[str], None]] = None,
        on_command_run: Optional[Callable[[str], None]] = None,
        on_vault_write: Optional[Callable[[str], None]] = None,
        on_ha_action: Optional[Callable[[str, str, str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
        blocking: bool = False,
    ):
        """
        Kullanıcı mesajını AI'a gönderir. Varsayılan olarak arka planda
        (thread içinde) çalışır — UI donmaz. blocking=True verirsen
        aynı thread'de senkron çalışır (script/test amaçlı).

        on_ha_action(domain, servis, entity_id): Home Assistant komutu çalıştırıldığında çağrılır.

        Callback'ler frontend'in ihtiyacına göre opsiyoneldir.
        """
        def _work():
            if on_thinking:
                on_thinking()

            self._ensure_active_chat()

            vault_ctx = ""
            hits = self.vault.ara(text)
            if hits:
                vault_ctx = f"Vault'ta ilgili notlar: {', '.join(hits)}"

            skills_ctx = self.skills.aktif_skill_ozeti()

            ha_ctx = ""
            if self.ha:
                try:
                    ozet = self.ha.ozet()
                    ha_ctx = (f"Home Assistant bağlı — {ozet['toplam_isik']} ışık "
                             f"({ozet['acik_isik']} açık), {ozet['toplam_switch']} priz/switch var.")
                except Exception:
                    ha_ctx = "Home Assistant bağlantısı var ama şu an erişilemiyor."
            else:
                ha_ctx = "Home Assistant bağlı değil."

            system = SYSTEM_PROMPT_TEMPLATE.format(
                allow_all=self.allow_all,
                allow_note=("Onay sormadan direkt çalıştır." if self.allow_all
                           else "Kullanıcı onayını bekle, komutu hemen çalıştırma."),
                model=self.cfg.get("model", "?"),
                vault_ctx=vault_ctx,
                ha_ctx=ha_ctx,
                skills_ctx=skills_ctx,
            )

            self.history.append({"role": "user", "content": text})
            self.conversations.mesaj_ekle(self.active_chat_id, "user", text)

            if not self.ai:
                if on_error:
                    on_error("AI yapılandırılmamış. Önce configure() çağır.")
                if on_done:
                    on_done()
                return

            try:
                reply = self.ai.chat(system, self.history)

                # AI bir skill'in tam içeriğini istedi mi? (SKILL_OKU: <isim>)
                skill_match = re.search(r'SKILL_OKU:\s*(\S+)', reply)
                if skill_match:
                    skill_name = skill_match.group(1).strip()
                    skill_content = self.skills.skill_tam_icerik(skill_name)
                    if skill_content:
                        # Skill içeriğini geçmişe ekleyip AI'ı tekrar çağır
                        self.history.append({"role": "assistant", "content": reply})
                        self.history.append({
                            "role": "user",
                            "content": f"[Sistem: '{skill_name}' skill içeriği]\n{skill_content[:3000]}"
                        })
                        reply = self.ai.chat(system, self.history)

                self.history.append({"role": "assistant", "content": reply})
                self._handle_reply(reply, on_reply, on_command, on_vault_write, on_ha_action)
            except Exception as e:
                if on_error:
                    on_error(str(e))

            if on_done:
                on_done()

        if blocking:
            _work()
        else:
            threading.Thread(target=_work, daemon=True).start()

    def _handle_reply(self, reply, on_reply, on_command, on_vault_write, on_ha_action=None):
        # Terminal komutu var mı?
        m = re.search(r'ÇALIŞTIR:\s*(.+)', reply)
        clean_text = reply
        cmd = None
        if m:
            cmd = m.group(1).strip()
            clean_text = reply[:m.start()].strip()

        if clean_text:
            self.conversations.mesaj_ekle(self.active_chat_id, "ai", clean_text)
            if on_reply:
                on_reply(clean_text)

        if cmd:
            self._pending_cmd = cmd
            if self.allow_all:
                if on_command:
                    on_command(cmd)
                self.run_command(cmd)
            else:
                if on_command:
                    on_command(cmd)  # frontend onay diyaloğu göstermeli

        # Vault notu var mı?
        for nm in re.finditer(r'NOT:\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+)', reply):
            baslik, icerik, etiket_str = nm.group(1), nm.group(2), nm.group(3)
            etiketler = [e.strip() for e in etiket_str.split(',')]
            dosya = self.vault.yaz(baslik, icerik, etiketler)
            self.conversations.mesaj_ekle(self.active_chat_id, "vault", f"Not kaydedildi: {dosya}")
            if on_vault_write:
                on_vault_write(dosya)

        # Home Assistant komutu var mı?
        # Format: EV: <domain>.<servis>.<entity_domain>.<entity_name>[.<deger>]
        for ha_match in re.finditer(r'EV:\s*(\S+)', reply):
            self._handle_ha_command(ha_match.group(1), on_ha_action)

    def _handle_ha_command(self, komut_str: str, on_ha_action=None):
        """'light.turn_on.light.salon.200' gibi bir string'i parse edip çalıştırır."""
        if not self.ha:
            return
        parcalar = komut_str.split(".")
        if len(parcalar) < 4:
            return
        domain, servis, entity_domain, entity_name = parcalar[0], parcalar[1], parcalar[2], parcalar[3]
        entity_id = f"{entity_domain}.{entity_name}"
        deger = parcalar[4] if len(parcalar) > 4 else None

        ekstra = None
        if deger is not None:
            try:
                deger_num = float(deger)
                if domain == "light":
                    ekstra = {"brightness": int(deger_num)}
                elif domain == "climate":
                    ekstra = {"temperature": deger_num}
            except ValueError:
                pass

        try:
            self.ha.servis_cagir(domain, servis, entity_id, ekstra)
            if on_ha_action:
                on_ha_action(domain, servis, entity_id)
        except Exception:
            pass  # sessizce başarısız ol, sohbet akışını bozmasın

    # ── Terminal ───────────────────────────────────────────────────────

    def confirm_pending_command(self) -> Optional[str]:
        """Bekleyen komutu onayla ve çalıştır. Çalıştırılan komutu döndürür."""
        cmd = self._pending_cmd
        self._pending_cmd = None
        if cmd:
            self.run_command(cmd)
        return cmd

    def reject_pending_command(self):
        self._pending_cmd = None

    def run_command(self, cmd: str) -> Dict[str, str]:
        out, err = self.runner.run(cmd)
        self._ensure_active_chat()
        self.conversations.mesaj_ekle(self.active_chat_id, "command", cmd, out or err)
        return {"cmd": cmd, "out": out, "err": err}

    # ── Sistem bilgisi ───────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, float]:
        try:
            import psutil
            return {
                "cpu": psutil.cpu_percent(),
                "ram": psutil.virtual_memory().percent,
                "disk": psutil.disk_usage("/").percent,
            }
        except Exception:
            return {"cpu": 0.0, "ram": 0.0, "disk": 0.0}
