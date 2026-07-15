# OrionBot

Get up and running with Claude, GPT, Gemini, Llama, and other models through a native Windows desktop app —

> **Note:** This is a demo / preview build, not the final product. Things will change. NVIDIA NIM and OpenRouter have been tested; the local-model (Ollama / LM Studio) path has not been tested yet — use it at your own discretion for now.

![License](https://img.shields.io/badge/license-MIT-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![Linux/macOS](https://img.shields.io/badge/Linux%20%2F%20macOS-coming%20soon-yellow)

---

## Download

Grab `OrionBot.exe` from [Releases](../../releases) and run it. No Python, no dependencies, nothing else to install.

---

## Quickstart

1. Run `OrionBot.exe`
2. On first launch, pick a connection method:
   - **API Key** — paste your key, the provider is auto-detected (`sk-ant-` → Anthropic, `sk-or-` → OpenRouter, `nvapi-` → NVIDIA)
   - **Local model** — point it at Ollama, LM Studio, or your own OpenAI-compatible endpoint
3. Start chatting

No config files to touch by hand.

---

## Features

- **Auto-detected providers** — paste a key, OrionBot figures out which service it belongs to
- **Local model support** — Ollama, LM Studio, or any custom endpoint, no key required
- **Persistent, multi-chat** — every conversation is saved as a linked Markdown file (Obsidian-style), can be starred, browsed, and revisited
- **Vault** — a persistent, Markdown-based memory the assistant can write notes into
- **Skills, Claude Skills–compatible** — drop in a `SKILL.md` folder, a `.zip`, or a GitHub repo link and OrionBot picks up the new capability
- **Terminal integration** — the assistant can run shell commands, gated by a confirm dialog (or an "allow all" toggle if you trust it)
- **Optional Home Assistant integration** — control lights, switches, and thermostats from chat
- Single `.exe`, no Python install required

---

## Skills

OrionBot's skill system speaks the same format as [Anthropic's Claude Skills](https://docs.claude.com) — a folder with a `SKILL.md` file:

```
my-skill/
├── SKILL.md          required
├── scripts/          optional
└── references/       optional
```

```markdown
---
name: pdf-summarizer
description: "Use this when the user wants a PDF read or summarized."
---

# PDF Summarizer

...
```

The `description` field is what OrionBot feeds to the model as context, so it can decide when the skill is relevant and ask for the full file with `SKILL_OKU: <skill-name>` if needed.

Add a skill three ways, right from the app:
- **Drag and drop** a `.zip`, `.md`, or `.py` file
- **Paste a GitHub repo link** — OrionBot pulls `SKILL.md` or `README.md` automatically
- **Write one by hand** (see `backend/skills.py` if you're scripting it)

This has been tested against real skills from Anthropic's own skill collection (`docx`, `pdf`, etc.) — they load and parse without modification.

---

## Connection methods

| Method | Description |
|---|---|
| **API Key** | Paste a key, provider is auto-detected |
| **Local model** | Ollama, LM Studio, or any OpenAI-compatible endpoint — *not yet tested, use with caution* |
| **Kortex** | *Coming soon* — OrionAGI's own model. Currently a disabled placeholder in the UI |

---

## Building from source

The `.exe` on the Releases page is built from this repo with:

```bash
cd frontend
pip install pywebview requests psutil pyinstaller
python build_exe.py
```

This produces `dist/OrionBot.exe`.

If you just want to run it from source without packaging:

```bash
cd frontend
python main.py
```

This works fine for development, but the title bar may briefly show the default Python/Windows icon instead of OrionBot's before the app applies its own — a `pywebview` quirk, not a bug. The packaged `.exe` sets it directly.

---

## Architecture

```
orionbot/
├── backend/
│   ├── orion_engine.py     the engine tying everything together
│   ├── ai_client.py        multi-provider AI client + key auto-detection
│   ├── vault.py             Obsidian-style persistent notes
│   ├── conversations.py     persistent, multi-chat history
│   ├── skills.py            Claude Skills–compatible skill system
│   ├── terminal.py          command runner
│   └── home_assistant.py    home automation integration (optional)
└── frontend/
    ├── index.html           the entire UI (single file)
    ├── main.py               pywebview bridge (native window, no localhost)
    └── build_exe.py          .exe packager
```

The frontend runs on `pywebview`'s `edgechromium` backend (the WebView2 runtime already on most Windows machines) — a direct Python↔JavaScript bridge, no HTTP server, no browser tab.

---

## Roadmap

- [ ] Test and stabilize the Ollama / local-model path
- [ ] Linux and macOS builds
- [ ] Kortex — a lightweight local model built for this app specifically

---

## License

MIT
