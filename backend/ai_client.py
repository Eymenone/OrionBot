"""
OrionBot Backend — AI Client
OpenRouter, Anthropic, Ollama, LM Studio, NVIDIA NIM, Custom (OpenAI-uyumlu) destekler.

Kullanım:
    client = AIClient(provider="custom", api_key="...", model="z-ai/glm-5.2",
                      base_url="https://integrate.api.nvidia.com/v1/chat/completions")
    reply = client.chat(system="Sen yardımsever bir asistansın.",
                        messages=[{"role":"user","content":"Merhaba"}])
"""
from typing import List, Dict

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# Bilinen provider'ların varsayılan endpoint'leri
PROVIDER_URLS = {
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "anthropic":  "https://api.anthropic.com/v1/messages",
    "ollama":     "http://localhost:11434/api/chat",
    "lmstudio":   "http://localhost:1234/v1/chat/completions",
    "nvidia":     "https://integrate.api.nvidia.com/v1/chat/completions",
}

# API key önekinden otomatik provider tespiti
KEY_PREFIX_MAP = [
    ("sk-ant-",   "anthropic"),
    ("sk-or-v1-", "openrouter"),
    ("nvapi-",    "nvidia"),
]


def detect_provider(api_key: str) -> str:
    """
    API key'in önekine bakarak hangi provider'a ait olduğunu tahmin eder.
    Eşleşme bulunamazsa 'openrouter' varsayılan olarak döner
    (OpenRouter en geniş model yelpazesine sahip olduğu için).
    """
    key = (api_key or "").strip()
    for prefix, provider in KEY_PREFIX_MAP:
        if key.startswith(prefix):
            return provider
    return "openrouter"

# OpenRouter üzerinden erişilebilen bilinen ücretsiz modeller (referans amaçlı)
FREE_MODELS = [
    "qwen/qwen3-coder:free",
    "deepseek/deepseek-v4-flash:free",
    "minimax/minimax-m2.5:free",
    "meta-llama/llama-3.3-70b-instruct:free",
]


class AIClient:
    """
    Tüm provider'lar için tek arayüz.

    provider: "openrouter" | "anthropic" | "ollama" | "lmstudio" | "nvidia" | "custom"
    api_key:  provider'ın API anahtarı (ollama/lmstudio için boş bırakılabilir)
    model:    modelin tam adı (örn. "qwen/qwen3-coder:free", "z-ai/glm-5.2")
    base_url: özel/nvidia/ollama/lmstudio için endpoint URL'si.
              Boş bırakılırsa provider'ın PROVIDER_URLS'teki varsayılanı kullanılır.
    """

    def __init__(self, provider: str, api_key: str, model: str, base_url: str = ""):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        given = (base_url or "").strip()
        self.base_url = given if given else PROVIDER_URLS.get(provider, "")

    def chat(self, system: str, messages: List[Dict], max_tokens: int = 1024) -> str:
        """
        system:   system prompt metni
        messages: [{"role": "user"|"assistant", "content": "..."}] formatında geçmiş
        """
        if not HAS_REQUESTS:
            raise RuntimeError("requests kütüphanesi yok: pip install requests")
        if not self.base_url:
            raise RuntimeError(f"Bu provider için URL bulunamadı: {self.provider}")

        if self.provider == "anthropic":
            return self._anthropic(system, messages, max_tokens)
        if self.provider == "ollama":
            return self._ollama(system, messages)
        # openrouter, lmstudio, nvidia, custom — hepsi OpenAI-uyumlu chat/completions formatı
        return self._openai_compat(system, messages, max_tokens)

    # ── OpenAI-uyumlu format (OpenRouter, LM Studio, NVIDIA NIM, Custom) ──

    def _openai_compat(self, system: str, messages: List[Dict], max_tokens: int) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://orion-agi.com"
            headers["X-Title"] = "OrionBot"

        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}] + messages,
            "max_tokens": max_tokens,
            "temperature": 1,
            "top_p": 1,
        }

        r = requests.post(self.base_url, headers=headers, json=body, timeout=90)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()

    # ── Anthropic Messages API ────────────────────────────────────────────

    def _anthropic(self, system: str, messages: List[Dict], max_tokens: int) -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        r = requests.post(self.base_url, headers=headers, json=body, timeout=90)
        r.raise_for_status()
        return r.json()["content"][0]["text"].strip()

    # ── Ollama /api/chat ───────────────────────────────────────────────────

    def _ollama(self, system: str, messages: List[Dict]) -> str:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}] + messages,
            "stream": False,
        }
        r = requests.post(self.base_url, json=body, timeout=120)
        r.raise_for_status()
        return r.json()["message"]["content"].strip()

    # ── Streaming destekli versiyon (opsiyonel, ileride kullanılabilir) ────

    def chat_stream(self, system: str, messages: List[Dict], max_tokens: int = 1024):
        """
        Generator — parça parça (chunk) metin döndürür.
        Sadece OpenAI-uyumlu provider'lar için (openrouter, lmstudio, nvidia, custom).
        """
        if self.provider in ("anthropic", "ollama"):
            # Bu iki provider için streaming henüz eklenmedi, tam yanıtı tek seferde döndür
            yield self.chat(system, messages, max_tokens)
            return

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://orion-agi.com"
            headers["X-Title"] = "OrionBot"

        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}] + messages,
            "max_tokens": max_tokens,
            "stream": True,
        }

        with requests.post(self.base_url, headers=headers, json=body, timeout=90, stream=True) as r:
            r.raise_for_status()
            import json as _json
            for line in r.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    line = line[6:]
                if line.strip() == "[DONE]":
                    break
                try:
                    chunk = _json.loads(line)
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
                except Exception:
                    continue
