# NexAlfa — Your Personal AI Agent/Assistant

A custom-built personal AI assistant combining OpenClaw's infrastructure power, Hermes' self-improving intelligence, and Dev Mode's unrestricted philosophy. Built as a **monorepo** with a Python agent core, 7-channel messaging gateway, synchronized web + mobile apps, and a built-in learning loop.

## User Review Required

> [!IMPORTANT]
> **Naming**: I'm using "NexAlfa" based on your workspace name. Want a different name?

> [!IMPORTANT]
> **Model Providers**: Which LLM providers do you want to use? The plan includes LiteLLM for universal support (OpenAI, Anthropic, Google, Ollama, OpenRouter, etc.) — confirm which ones matter most to you so I prioritize their testing.

> [!IMPORTANT]
> **Deployment Target**: Where will this run?
> - Local machine (your PC)?
> - A VPS (like the dev-mode approach)?
> - Both (local dev + VPS prod)?

> [!IMPORTANT]
> **Mobile App**: 
> - **Option A**: React Native (Expo) — true native iOS + Android apps
> - **Option B**: PWA (Progressive Web App) — single web codebase, installable on phones, faster to build
> - **Option C**: Both (PWA first, native later)
> I recommend **Option C** — ship a PWA quickly, then go native.

## Open Questions

> [!WARNING]
> **WhatsApp**: WhatsApp Cloud API requires a Meta Business account and a dedicated phone number. Do you have those, or should I use a bridge approach (like what OpenClaw does)?

> [!WARNING]
> **Google Chat**: Google Chat API requires a Google Workspace account (not free Gmail). Do you have one?

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        NexAlfa                              │
├─────────────┬───────────────┬───────────────┬───────────────┤
│  Web App    │  Mobile App   │  CLI/TUI      │  Channel      │
│  (Next.js)  │  (Expo/PWA)   │  (Rich CLI)   │  Adapters     │
├─────────────┴───────────────┴───────────────┤               │
│              WebSocket Hub                   │  ┌──────────┐│
│         (Real-time Sync Layer)               │  │ Telegram ││
├──────────────────────────────────────────────┤  │ Discord  ││
│              FastAPI Gateway                 │  │ Slack    ││
│  ┌─────────┬──────────┬──────────┐          │  │ WhatsApp ││
│  │ Sessions│ Routing  │ Security │          │  │ GChat    ││
│  │ Manager │ Engine   │ (DevMode)│          │  │ Email    ││
│  └─────────┴──────────┴──────────┘          │  │ WebChat  ││
├──────────────────────────────────────────────┤  └──────────┘│
│              Agent Core                      │              │
│  ┌─────────┬──────────┬──────────┐          │              │
│  │ LiteLLM │ Learning │ Memory   │          │              │
│  │ (Models)│ Loop     │ (Vector) │          │              │
│  └─────────┴──────────┴──────────┘          │              │
│  ┌─────────┬──────────┬──────────┐          │              │
│  │ Skills  │ Tools    │ Cron     │          │              │
│  │ Engine  │ (Browser,│ Scheduler│          │              │
│  │         │  MCP...) │          │          │              │
│  └─────────┴──────────┴──────────┘          │              │
├──────────────────────────────────────────────┤              │
│              Storage Layer                   │              │
│  SQLite (conversations, config, history)     │              │
│  ChromaDB (vector memory, semantic search)   │              │
│  File System (skills, workspace, SOUL.md)    │              │
└──────────────────────────────────────────────┴──────────────┘
```

### Tech Stack

| Layer | Technology | Source Inspiration |
|---|---|---|
| **Agent Core** | Python 3.11+ / FastAPI | Hermes Agent |
| **Model Routing** | LiteLLM | Hermes (multi-provider) |
| **Gateway/API** | FastAPI + WebSocket | OpenClaw Gateway |
| **Channel Adapters** | python-telegram-bot, discord.py, slack-sdk, WhatsApp Cloud API, Google Chat API, SMTP/IMAP | OpenClaw channels |
| **Memory/Learning** | ChromaDB + SQLite | Hermes learning loop |
| **Skills Engine** | SKILL.md files + auto-creation | Both (OpenClaw format + Hermes auto-learn) |
| **Web App** | Next.js 15 + Socket.IO | New build |
| **Mobile App** | PWA → React Native (Expo) | New build |
| **CLI** | Rich (Python) | Hermes TUI |
| **Tools** | Playwright (browser), APScheduler (cron) | OpenClaw tools |
| **Config** | YAML + .env (dev-mode style) | Dev Mode approach |

### Monorepo Structure

```
NexAlfa/
├── agent/                    # Python — Agent core brain
│   ├── core/
│   │   ├── agent.py          # Main agent loop (from Hermes pattern)
│   │   ├── models.py         # LiteLLM multi-model router
│   │   ├── sessions.py       # Session management (from OpenClaw)
│   │   ├── router.py         # Multi-agent routing
│   │   └── thinking.py       # Reasoning/thinking levels
│   ├── memory/
│   │   ├── manager.py        # Memory manager (Hermes learning loop)
│   │   ├── vector_store.py   # ChromaDB vector memory
│   │   ├── user_model.py     # User modeling across sessions
│   │   └── conversation.py   # Conversation history + search
│   ├── skills/
│   │   ├── engine.py         # Skills loader (OpenClaw SKILL.md format)
│   │   ├── auto_create.py    # Auto-create skills from experience (Hermes)
│   │   └── registry.py       # Skill registry / marketplace
│   ├── tools/
│   │   ├── base.py           # Tool base class
│   │   ├── browser.py        # Browser automation (Playwright)
│   │   ├── cron.py           # Cron scheduler
│   │   ├── filesystem.py     # Read/write/edit tools
│   │   ├── process.py        # Shell/process execution
│   │   ├── mcp_client.py     # MCP integration (from Hermes)
│   │   └── webhooks.py       # Webhook handler
│   ├── personality/
│   │   ├── soul.py           # SOUL.md loader (OpenClaw)
│   │   ├── agents_md.py      # AGENTS.md loader
│   │   └── switcher.py       # Personality switching (Hermes /personality)
│   └── config/
│       ├── settings.py       # Dev-mode style config (no guardrails)
│       └── defaults.py       # Sensible defaults
│
├── gateway/                  # Python — Messaging Gateway
│   ├── server.py             # FastAPI + WebSocket hub
│   ├── auth.py               # DM pairing (relaxed dev-mode)
│   ├── message.py            # Normalized message model
│   ├── channels/
│   │   ├── base.py           # Base channel adapter
│   │   ├── telegram.py       # Telegram adapter
│   │   ├── discord.py        # Discord adapter
│   │   ├── slack.py          # Slack adapter
│   │   ├── whatsapp.py       # WhatsApp Cloud API adapter
│   │   ├── google_chat.py    # Google Chat adapter
│   │   ├── email.py          # Email (SMTP/IMAP) adapter
│   │   └── webchat.py        # WebChat (WebSocket) adapter
│   └── sync/
│       ├── hub.py            # Real-time sync hub (WebSocket)
│       └── state.py          # Shared state across clients
│
├── web/                      # Next.js — Web Application
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx          # Dashboard
│   │   ├── chat/             # Chat interface
│   │   ├── skills/           # Skills management
│   │   ├── channels/         # Channel configuration
│   │   ├── settings/         # Settings (raw config, dev-mode)
│   │   ├── memories/         # Memory browser
│   │   └── cron/             # Cron job manager
│   ├── components/
│   │   ├── Chat/             # Chat UI components
│   │   ├── Sidebar/          # Navigation
│   │   ├── Dashboard/        # Dashboard widgets
│   │   └── Settings/         # Config editor
│   ├── lib/
│   │   ├── socket.ts         # WebSocket client
│   │   ├── api.ts            # REST API client
│   │   └── store.ts          # State management
│   └── public/
│
├── mobile/                   # React Native (Expo) — Mobile App
│   ├── app/                  # Expo Router
│   │   ├── (tabs)/
│   │   │   ├── chat.tsx
│   │   │   ├── dashboard.tsx
│   │   │   └── settings.tsx
│   │   └── _layout.tsx
│   ├── components/
│   └── lib/
│       ├── socket.ts         # Shared WebSocket logic
│       └── api.ts            # Shared API client
│
├── cli/                      # Python — CLI/TUI
│   ├── main.py               # Entry point (`nexalfa` command)
│   ├── chat.py               # Interactive chat mode
│   ├── commands/             # Subcommands (model, tools, config, etc.)
│   └── tui.py                # Rich TUI interface
│
├── workspace/                # User workspace (created at runtime)
│   ├── SOUL.md               # Persona definition
│   ├── AGENTS.md             # Agent instructions
│   ├── MEMORY.md             # Auto-created memory (from Dev Mode)
│   ├── USER.md               # User model notes
│   ├── TOOLS.md              # Tool configuration
│   └── skills/               # User skills (SKILL.md files)
│
├── storage/                  # Local databases (created at runtime)
│   ├── nexalfa.db            # SQLite — conversations, config, history
│   └── memory/               # ChromaDB — vector embeddings
│
├── config/
│   ├── nexalfa.yaml          # Main config file
│   ├── .env.example          # Environment variables template
│   └── defaults.yaml         # Default configuration
│
├── docker-compose.yml        # Docker deployment
├── Dockerfile
├── pyproject.toml            # Python dependencies
├── package.json              # Root monorepo package.json
└── README.md
```

---

## Proposed Changes

### Phase 1 — Agent Core + WebChat (Foundation)
> **Goal**: Working AI agent you can chat with via WebChat in the browser. Self-improving memory from day one.

---

#### Agent Core (`agent/`)

##### [NEW] agent/core/agent.py
Main agent loop — pulled from Hermes Agent's `run_agent.py` pattern. Handles the conversation cycle: receive message → build context (personality + memory + skills) → call LLM → execute tools → learn → respond.

##### [NEW] agent/core/models.py
LiteLLM-based model router. Supports every provider (OpenAI, Anthropic, Google, Ollama, OpenRouter, etc.) with a single `hermes model`-style switching command. Includes streaming, thinking/reasoning levels, and model failover chains.

##### [NEW] agent/core/sessions.py
Session manager from OpenClaw's pattern — multi-session support, session history, spawn/send/list. Each channel conversation maps to a session.

##### [NEW] agent/core/thinking.py
Reasoning/thinking level control. Supports `none`, `low`, `medium`, `high` thinking levels that map to model-specific reasoning parameters. Outputs thinking with 💭 prefix (from Dev Mode).

---

#### Memory & Learning (`agent/memory/`)

##### [NEW] agent/memory/manager.py
Memory manager — the Hermes-style learning loop. After each conversation, evaluates what's worth remembering, creates/updates memory entries, and nudges the agent to persist important knowledge. Auto-creates `MEMORY.md`.

##### [NEW] agent/memory/vector_store.py
ChromaDB vector store for semantic search over conversation history, memories, and skills. Enables "search your own past conversations" feature from Hermes.

##### [NEW] agent/memory/user_model.py
Builds a deepening model of who you are across sessions — preferences, communication style, projects, recurring topics. Stored in `USER.md` and used to personalize responses.

##### [NEW] agent/memory/conversation.py
Full conversation history stored in SQLite (inspired by Dev Mode's WA history logger). Searchable, queryable by agents. Every message from every channel logged.

---

#### Skills (`agent/skills/`)

##### [NEW] agent/skills/engine.py
Skills loader using OpenClaw's `SKILL.md` format. Reads skill definitions from the workspace, injects them into agent context, and handles `/skill-name` invocation.

##### [NEW] agent/skills/auto_create.py
Hermes' key differentiator — auto-creates skills from experience. When the agent solves a novel problem, it extracts the approach into a reusable `SKILL.md` file. Skills improve on subsequent uses.

---

#### Tools (`agent/tools/`)

##### [NEW] agent/tools/base.py
Base tool class with OpenClaw's allow/deny pattern but in dev-mode style (everything allowed by default). Tools self-describe for the LLM.

##### [NEW] agent/tools/browser.py
Playwright-based browser automation tool.

##### [NEW] agent/tools/filesystem.py
File read/write/edit tools (from OpenClaw's toolset).

##### [NEW] agent/tools/process.py
Shell command execution — unrestricted (dev-mode philosophy).

##### [NEW] agent/tools/cron.py
APScheduler-based cron job system for scheduled tasks.

##### [NEW] agent/tools/mcp_client.py
MCP (Model Context Protocol) client from Hermes — connect to external MCP servers for additional tools.

##### [NEW] agent/tools/webhooks.py
Webhook endpoint handler for event-driven automation.

---

#### Personality (`agent/personality/`)

##### [NEW] agent/personality/soul.py
Loads `SOUL.md` — your agent's persona definition (from OpenClaw). Injected into every LLM call as system context.

##### [NEW] agent/personality/switcher.py
Personality switching from Hermes — `/personality <name>` to switch between different persona files.

---

#### Config (`agent/config/`)

##### [NEW] agent/config/settings.py
Dev-mode style configuration — everything visible, nothing blocked. Raw config always accessible. YAML-based with .env overrides.

---

### Phase 2 — Gateway + Channel Adapters

---

#### Gateway (`gateway/`)

##### [NEW] gateway/server.py
FastAPI server with WebSocket hub. Handles all inbound/outbound messaging, routes to the agent core, and syncs state to all connected clients (web, mobile, CLI).

##### [NEW] gateway/channels/base.py
Base channel adapter class. Normalizes messages from all platforms into a common `Message` model (the pro-tip from the research).

##### [NEW] gateway/channels/telegram.py
Telegram adapter using `python-telegram-bot`. Polling + webhook modes. Supports inline keyboards, media, thinking messages.

##### [NEW] gateway/channels/discord.py
Discord adapter using `discord.py`. Guild + DM support. Slash commands.

##### [NEW] gateway/channels/slack.py
Slack adapter using `slack-sdk`. Socket Mode (no public URL needed) + Web API.

##### [NEW] gateway/channels/whatsapp.py
WhatsApp Cloud API adapter. REST API for sending, webhook for receiving. Thinking messages with 💭 prefix (from Dev Mode).

##### [NEW] gateway/channels/google_chat.py
Google Chat adapter via Google Chat API.

##### [NEW] gateway/channels/email.py
Email adapter using SMTP (sending) + IMAP (receiving). Supports rich HTML responses.

##### [NEW] gateway/channels/webchat.py
Built-in WebChat via WebSocket. This is what the web app's chat connects to directly.

##### [NEW] gateway/sync/hub.py
WebSocket sync hub — ensures all connected clients (web, mobile, CLI, channels) see the same state in real-time. Message sent on Telegram → appears in web app instantly.

---

### Phase 3 — Web Application

---

#### Web App (`web/`)

##### [NEW] web/ (Next.js 15 app)
Full-featured web application with:
- **Dashboard** — agent status, recent conversations, memory insights, usage stats
- **Chat** — real-time chat interface synced with all channels. See and respond to messages from any channel.
- **Skills Manager** — browse, create, edit, toggle skills
- **Channel Config** — connect/disconnect channels, set per-channel routing
- **Memory Browser** — explore agent's memories, user model, conversation search
- **Cron Manager** — create/edit/view scheduled tasks
- **Settings** — raw config editor (dev-mode style), model selection, personality switching
- **Dark mode** — premium glassmorphism design

---

### Phase 4 — Mobile Application

---

#### Mobile App (`mobile/`)

##### [NEW] mobile/ (Expo + React Native)
Synchronized mobile app with:
- **Chat tab** — same real-time chat as web, all channels visible
- **Dashboard tab** — agent status, quick actions
- **Settings tab** — model switching, basic config
- Push notifications for agent messages
- Shares WebSocket logic with web app

---

### Phase 5 — CLI + Polish

---

#### CLI (`cli/`)

##### [NEW] cli/ (Python Rich CLI)
Terminal interface inspired by Hermes:
- `nexalfa` — interactive chat
- `nexalfa model` — switch model
- `nexalfa tools` — configure tools
- `nexalfa config` — view/edit config
- `nexalfa gateway` — start gateway
- `nexalfa doctor` — diagnose issues
- `nexalfa setup` — onboarding wizard
- Slash commands: `/new`, `/reset`, `/model`, `/personality`, `/skills`, `/compress`, `/usage`, `/think`

---

## Verification Plan

### Automated Tests
- **Agent core**: Unit tests for memory, skills, session management
- **Gateway**: Integration tests for each channel adapter with mocked APIs
- **Web app**: `npm run build` to verify no build errors, browser test for chat flow
- **Mobile**: Expo build check

### Manual Verification
1. Start gateway, send a message via WebChat → agent responds
2. Connect Telegram → send message → appears in web app chat
3. Agent learns from conversation → creates a skill → skill persists across sessions
4. Switch models mid-conversation → works seamlessly
5. Web + mobile show same state in real-time

### Build Commands
```bash
# Backend
cd agent && pip install -e ".[all]" && pytest

# Gateway
cd gateway && python server.py

# Web
cd web && npm install && npm run dev

# Mobile
cd mobile && npx expo start

# CLI
nexalfa doctor
```
