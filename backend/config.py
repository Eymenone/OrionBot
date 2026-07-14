"""
OrionBot Backend — Config
Ayarları ~/.orionbot/config.json dosyasında saklar.

Kullanım:
    cfg = load_cfg()
    cfg["provider"] = "custom"
    save_cfg(cfg)
"""
import json
from pathlib import Path
from typing import Dict

CONFIG_DIR = Path.home() / ".orionbot"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Bilinen provider'ların bilgileri — UI'da seçim listesi ve varsayılan URL için
PROVIDERS = {
    "openrouter": {
        "label": "OpenRouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "hint": "sk-or-v1-...",
        "models": [
            "qwen/qwen3-coder:free",
            "deepseek/deepseek-v4-flash:free",
            "minimax/minimax-m2.5:free",
            "meta-llama/llama-3.3-70b-instruct:free",
        ],
        "needs_url": False,
    },
    "anthropic": {
        "label": "Anthropic",
        "url": "https://api.anthropic.com/v1/messages",
        "hint": "sk-ant-...",
        "models": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"],
        "needs_url": False,
    },
    "ollama": {
        "label": "Ollama",
        "url": "http://localhost:11434/api/chat",
        "hint": "(gerekmez)",
        "models": ["llama3.2", "qwen2.5:7b", "phi3", "mistral"],
        "needs_url": True,
    },
    "lmstudio": {
        "label": "LM Studio",
        "url": "http://localhost:1234/v1/chat/completions",
        "hint": "(gerekmez)",
        "models": ["local-model"],
        "needs_url": True,
    },
    "nvidia": {
        "label": "NVIDIA NIM",
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "hint": "nvapi-...",
        "models": ["z-ai/glm-5.2"],
        "needs_url": False,
    },
    "custom": {
        "label": "Özel",
        "url": "",
        "hint": "opsiyonel",
        "models": [],
        "needs_url": True,
    },
}


def load_cfg() -> Dict:
    """Kayıtlı config'i döndürür, yoksa boş dict."""
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_cfg(data: Dict) -> None:
    """Config'i diske yazar."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def reset_cfg() -> None:
    """Config dosyasını tamamen siler (kurulum ekranını tekrar tetiklemek için)."""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
