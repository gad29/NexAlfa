# NexAlfa 🤖

**Your personal AI agent. No guardrails. Self-improving. Always on.**

NexAlfa is a personal AI assistant that combines the best of OpenClaw's infrastructure, Hermes Agent's self-improving intelligence, and a dev-mode philosophy where everything is visible and nothing is blocked.

## Features

### 🧠 Agent Core
- **Multi-model support** — OpenAI, Google (Gemini), OpenRouter (200+ models), Ollama (local) via LiteLLM
- **Automatic failover** — if one provider fails, seamlessly switches to the next
- **Thinking/reasoning levels** — control reasoning depth (none/low/medium/high)
- **Self-improving memory** — learns from every conversation, extracts patterns, builds a model of you
- **Auto-skill creation** — creates reusable skills from novel problem-solving
- **Semantic search** — search past conversations by meaning (ChromaDB)
- **Full conversation history** — every message from every channel stored in SQLite with full-text search

### 📡 7 Channel Adapters
- **WhatsApp** — dual mode: bridge (whatsapp-web.js) + Meta Cloud API
- **Telegram** — full Bot API with polling
- **Discord** — DM and mention handling
- **Slack** — Socket Mode (no public URL needed)
- **Google Chat** — Workspace API + webhook
- **Email** — SMTP sending + IMAP receiving
- **WebChat** — built-in web interface (Socket.IO)

### 🔧 Tools
- **Shell** — execute any command, unrestricted
- **Files** — read, write, list directories
- **Browser** — Playwright-based web automation + search
- **Cron** — scheduled recurring tasks
- **MCP** — connect to external Model Context Protocol servers
- **Webhooks** — register custom webhook endpoints

### 🌐 Web & Mobile App
- **Next.js web dashboard** — real-time chat, skills manager, memory browser, settings
- **PWA-ready** — installable on mobile devices
- **Real-time sync** — all channels synced via Socket.IO

### 🎛️ CLI
- `nexalfa` — interactive chat
- `nexalfa gateway` — start the gateway server
- `nexalfa status` — agent status
- `nexalfa doctor` — diagnose issues

## Quick Start

### 1. Clone & Install

```bash
git clone <your-repo-url>
cd NexAlfa

# Install Python dependencies
pip install -e ".[all]"

# Install web dependencies
cd web && npm install && cd ..
```

### 2. Configure

```bash
# Copy the example config
cp .env.example .env

# Edit .env — at minimum, set one API key:
# OPENAI_API_KEY=sk-...
# or GOOGLE_API_KEY=...
# or OPENROUTER_API_KEY=...
```

### 3. Start

```bash
# Start the gateway (serves API + WebSocket + all channels)
nexalfa gateway

# In another terminal, start the web app
cd web && npm run dev
```

### 4. Open

- **Web App**: http://localhost:3000
- **Gateway API**: http://localhost:18789
- **Health check**: http://localhost:18789/health

## Docker

```bash
cp .env.example .env
# Edit .env with your API keys
docker-compose up -d
```

## Project Structure

```
NexAlfa/
├── agent/           # Python — Agent core (brain)
│   ├── core/        # Main loop, model router, sessions
│   ├── memory/      # SQLite + ChromaDB + learning loop
│   ├── skills/      # SKILL.md loader + auto-creation
│   ├── tools/       # Shell, files, browser, cron, MCP, webhooks
│   ├── personality/ # SOUL.md + personality switching
│   └── config/      # Settings (pydantic-settings, .env)
├── gateway/         # Python — Messaging gateway
│   ├── channels/    # 7 channel adapters
│   ├── sync/        # WebSocket sync hub
│   └── server.py    # FastAPI + Socket.IO server
├── web/             # Next.js — Web application
├── cli/             # Python — CLI interface
├── workspace/       # Agent workspace (SOUL.md, AGENTS.md, skills/)
└── storage/         # SQLite DB + ChromaDB vectors
```

## Slash Commands

| Command | Description |
|---|---|
| `/new` / `/reset` | Clear current session |
| `/model [provider/model]` | Switch or show model |
| `/think [none\|low\|medium\|high]` | Set thinking level |
| `/personality [name]` | Switch personality |
| `/skills` | List available skills |
| `/status` | Agent status |
| `/usage` | Token usage |
| `/compact` | Compress context |
| `/search <query>` | Search past conversations |
| `/memories` | Memory statistics |

## License

MIT
