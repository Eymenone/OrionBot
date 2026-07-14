"""
OrionBot Backend — Home Assistant Entegrasyonu
Açık kaynak Home Assistant'ın REST API'sine bağlanır.
Işıkları, prizleri, termostatları, sensörleri kontrol eder/okur.

Kurulum (kullanıcı tarafında):
    1. Home Assistant arayüzünde: Profil (sol alt) → Uzun Süreli Erişim Anahtarları
       → "Anahtar Oluştur" → tokenı kopyala
    2. OrionBot Ayarlar'da Home Assistant URL + token gir

Kullanım:
    ha = HomeAssistant(base_url="http://192.168.1.100:8123", token="...")
    ha.baglanti_testi()               # -> bool
    ha.tum_varliklar()                # -> [{"entity_id": "...", "state": "...", ...}, ...]
    ha.durum_al("light.salon")        # -> {"state": "on", "attributes": {...}}
    ha.servis_cagir("light", "turn_on", "light.salon", {"brightness": 200})
    ha.isik_ac("light.salon")
    ha.isik_kapat("light.salon")
    ha.sicaklik_ayarla("climate.salon", 22.5)
"""
from typing import Optional, List, Dict, Any

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class HomeAssistant:
    def __init__(self, base_url: str, token: str):
        """
        base_url: örn. "http://192.168.1.100:8123" veya "http://homeassistant.local:8123"
                  (sonunda /api olmadan, otomatik eklenir)
        token:    Home Assistant'tan alınan Long-Lived Access Token
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/{path.lstrip('/')}"

    # ── Bağlantı ─────────────────────────────────────────────────────────

    def baglanti_testi(self) -> bool:
        """API'nin erişilebilir olup olmadığını kontrol eder."""
        if not HAS_REQUESTS:
            return False
        try:
            r = requests.get(self._url(""), headers=self._headers, timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    # ── Varlıklar (entities) ─────────────────────────────────────────────

    def tum_varliklar(self) -> List[Dict[str, Any]]:
        """Tüm cihaz/sensör durumlarını döndürür."""
        r = requests.get(self._url("states"), headers=self._headers, timeout=10)
        r.raise_for_status()
        return r.json()

    def durum_al(self, entity_id: str) -> Dict[str, Any]:
        """Tek bir varlığın durumunu döndürür. örn: 'light.salon', 'sensor.oda_sicakligi'"""
        r = requests.get(self._url(f"states/{entity_id}"), headers=self._headers, timeout=10)
        r.raise_for_status()
        return r.json()

    def varliklari_filtrele(self, domain: str) -> List[Dict[str, Any]]:
        """Belirli bir tür (domain) varlıkları döndürür. örn: 'light', 'switch', 'climate', 'sensor'"""
        tum = self.tum_varliklar()
        return [e for e in tum if e["entity_id"].startswith(f"{domain}.")]

    # ── Servis çağırma (genel amaçlı kontrol) ────────────────────────────

    def servis_cagir(self, domain: str, servis: str, entity_id: str,
                     ekstra: Optional[Dict] = None) -> Dict:
        """
        Genel servis çağırma fonksiyonu.
        örn: servis_cagir("light", "turn_on", "light.salon", {"brightness": 200})
        """
        body = {"entity_id": entity_id}
        if ekstra:
            body.update(ekstra)
        r = requests.post(self._url(f"services/{domain}/{servis}"),
                          headers=self._headers, json=body, timeout=10)
        r.raise_for_status()
        return r.json()

    # ── Kısayol fonksiyonlar — sık kullanılan işlemler ───────────────────

    def isik_ac(self, entity_id: str, parlaklik: Optional[int] = None):
        ekstra = {"brightness": parlaklik} if parlaklik is not None else None
        return self.servis_cagir("light", "turn_on", entity_id, ekstra)

    def isik_kapat(self, entity_id: str):
        return self.servis_cagir("light", "turn_off", entity_id)

    def priz_ac(self, entity_id: str):
        return self.servis_cagir("switch", "turn_on", entity_id)

    def priz_kapat(self, entity_id: str):
        return self.servis_cagir("switch", "turn_off", entity_id)

    def sicaklik_ayarla(self, entity_id: str, derece: float):
        return self.servis_cagir("climate", "set_temperature", entity_id,
                                 {"temperature": derece})

    def kilit_ac(self, entity_id: str):
        return self.servis_cagir("lock", "unlock", entity_id)

    def kilit_kapat(self, entity_id: str):
        return self.servis_cagir("lock", "lock", entity_id)

    def sensor_oku(self, entity_id: str) -> str:
        """Bir sensörün mevcut değerini (state) döndürür. örn: sıcaklık, nem, vs."""
        durum = self.durum_al(entity_id)
        return durum.get("state", "bilinmiyor")

    def ozet(self) -> Dict[str, int]:
        """Ev genelinde kısa özet — kaç ışık açık, kaç cihaz var vs."""
        tum = self.tum_varliklar()
        isiklar = [e for e in tum if e["entity_id"].startswith("light.")]
        acik_isik = [e for e in isiklar if e["state"] == "on"]
        switchler = [e for e in tum if e["entity_id"].startswith("switch.")]
        return {
            "toplam_varlik": len(tum),
            "toplam_isik": len(isiklar),
            "acik_isik": len(acik_isik),
            "toplam_switch": len(switchler),
        }
