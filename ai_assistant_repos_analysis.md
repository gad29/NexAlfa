# 🔍 AI Assistant Repos — Deep Feature Analysis

Here's a clear breakdown of all three repositories. Read through, and tell me which features you want from each — I'll build your perfect assistant.

---

## 1️⃣ OpenClaw (Main) — `openclaw/openclaw`
> ⭐ 368k stars · TypeScript · "Your own personal AI assistant. Any OS. Any Platform."

This is the **mothership** — a massive, mature, production-grade personal AI assistant platform.

### 🏗️ Architecture
| Aspect | Details |
|---|---|
| **Language** | TypeScript (91.2%), Swift, Kotlin, JS |
| **Runtime** | Node.js 24 (or 22.14+) |
| **Package Manager** | pnpm (monorepo workspace) |
| **Install** | `npm install -g openclaw@latest` |
| **Config** | `~/.openclaw/openclaw.json` |
| **Workspace** | `~/.openclaw/workspace` |

### 📬 Multi-Channel Messaging (26+ Channels!)
- ✅ WhatsApp
- ✅ Telegram
- ✅ Slack
- ✅ Discord
- ✅ Google Chat
- ✅ Signal
- ✅ iMessage / BlueBubbles
- ✅ IRC
- ✅ Microsoft Teams
- ✅ Matrix
- ✅ Feishu / LINE / Mattermost
- ✅ Nextcloud Talk / Nostr / Synology Chat
- ✅ Tlon / Twitch / Zalo / WeChat / QQ
- ✅ WebChat (built-in web interface)

### 🧠 Core AI Features
- **Multi-model support** — OpenAI, Anthropic, any OpenAI-compatible API
- **Multi-agent routing** — route inbound channels/accounts to isolated agents with separate workspaces and sessions
- **Thinking/reasoning levels** — `/think <level>` command to control reasoning depth
- **Session management** — `sessions_list`, `sessions_history`, `sessions_send`, `sessions_spawn`
- **Context compaction** — `/compact` to compress conversation context
- **Model failover** — auth profile rotation + automatic fallback chains

### 🔧 Tools & Automation
- **Browser tool** — built-in browser automation
- **Canvas tool** — agent-driven visual workspace (A2UI)
- **Cron jobs** — scheduled automated tasks
- **Webhooks** — event-driven automation
- **Gmail Pub/Sub** — Gmail event integration
- **Skills system** — bundled/managed/workspace skills (`SKILL.md` files)
- **Skills registry** — [ClawHub](https://clawhub.ai) marketplace
- **First-class tools** — bash, process, read, write, edit, sessions, browser, canvas, nodes, cron, discord, gateway

### 🎙️ Voice & Companion Apps
- **Voice Wake** — wake word detection on macOS/iOS
- **Talk Mode** — continuous voice on Android (ElevenLabs + system TTS fallback)
- **macOS menu bar app** — gateway control, health, voice wake, push-to-talk, WebChat, debug tools
- **iOS node** — pairs as a WebSocket node, voice trigger forwarding, Canvas surface
- **Android node** — Connect/Chat/Voice tabs, Canvas, Camera, Screen capture

### 🔒 Security Model
- **DM pairing** — unknown senders get pairing codes, must be approved
- **Sandboxing** — Docker/SSH/OpenShell sandboxed sessions for non-main users
- **Per-tool allow/deny lists** — granular tool access control
- **`openclaw doctor`** — diagnoses risky/misconfigured DM policies

### 🎛️ Configuration & Operations
- **Onboarding wizard** — `openclaw onboard` step-by-step setup
- **Gateway daemon** — launchd/systemd service, stays running
- **Prompt files** — `AGENTS.md`, `SOUL.md`, `TOOLS.md` persona/config injection
- **Chat commands** — `/status`, `/new`, `/reset`, `/compact`, `/think`, `/verbose`, `/trace`, `/usage`, `/restart`, `/activation`
- **Development channels** — stable/beta/dev release tracks
- **Remote access** — Tailscale, SSH, web surfaces

---

## 2️⃣ Hermes Agent — `NousResearch/hermes-agent`
> ⭐ 131k stars · Python (88.2%) · "The agent that grows with you"

Built by **Nous Research**. The key differentiator: a **built-in learning loop** — it creates skills from experience, improves them, and builds a deepening model of who you are.

### 🏗️ Architecture
| Aspect | Details |
|---|---|
| **Language** | Python (88.2%), TypeScript (8.4%) |
| **Runtime** | Python 3.11+ (via `uv`) |
| **Install** | `curl -fsSL .../install.sh \| bash` |
| **Config** | `cli-config.yaml` |
| **CLI** | `hermes` command |

### 🧠 Self-Improving AI (THE Key Differentiator)
- **Skill creation from experience** — the agent creates reusable skills from conversations automatically
- **Skill improvement during use** — skills get refined as they're used
- **Knowledge persistence nudges** — the agent nudges itself to save important knowledge
- **Past conversation search** — can search its own conversation history
- **User modeling** — builds a deepening model of who you are across sessions
- **Honcho integration** — for user state/personalization across sessions
- **Trajectory compression** — compresses agent trajectories for efficient learning

### 🤖 Multi-Model Support (Massive Provider Coverage)
- Nous Portal
- OpenRouter (200+ models)
- NVIDIA NIM (Nemotron)
- Xiaomi MiMo
- z.ai/GLM
- Kimi/Moonshot
- MiniMax
- Hugging Face
- OpenAI
- Custom endpoints
- **Switch with `hermes model`** — no code changes, no lock-in

### 📬 Messaging Gateway
- ✅ Telegram
- ✅ Discord
- ✅ Slack
- ✅ WhatsApp
- ✅ Signal
- ✅ Email
- Gateway setup: `hermes gateway setup` → `hermes gateway start`

### 🔧 Tools & Skills
- **Configurable toolsets** — `hermes tools` to enable/disable tools
- **Skills system** — `/skills` command, invoke skills with `/<skill-name>`
- **Skills Hub** — [agentskills.io](https://agentskills.io) community marketplace
- **Optional skills** — modular `optional-skills/` directory
- **Plugins** — `plugins/` directory for extensions
- **MCP integration** — Model Context Protocol support
- **Cron scheduling** — built-in cron jobs
- **Context files** — inject context into conversations

### 🎛️ CLI & Slash Commands
| Command | Description |
|---|---|
| `hermes` | Interactive CLI chat |
| `hermes model` | Choose LLM provider and model |
| `hermes tools` | Configure enabled tools |
| `hermes config set` | Set individual config values |
| `hermes gateway` | Start messaging gateway |
| `hermes setup` | Full setup wizard |
| `hermes update` | Update to latest |
| `hermes doctor` | Diagnose issues |
| `hermes claw migrate` | Migrate from OpenClaw |
| `/new` / `/reset` | New conversation |
| `/model [provider:model]` | Switch model |
| `/personality [name]` | Change personality |
| `/retry` / `/undo` | Retry/undo last |
| `/compress` | Compress context |
| `/usage` | Token usage stats |
| `/insights [--days N]` | Usage insights |
| `/skills` | List skills |
| `/stop` | Stop agent (messaging) |
| `/platforms` | List platforms |
| `/status` | Agent status |
| `/sethome` | Set home directory |

### 🏋️ Advanced / Research Features
- **RL Training integration** — Atropos/Tinker reinforcement learning pipeline
- **Batch runner** — `batch_runner.py` for running agent on multiple inputs
- **Mini SWE runner** — `mini_swe_runner.py` for software engineering benchmarks
- **Data generation** — `datagen-config-examples/` for training data
- **Toolset distributions** — configurable tool probability distributions
- **ACP adapter/registry** — Agent Communication Protocol support
- **MCP server** — `mcp_serve.py` for serving as an MCP tool

### 🖥️ UI Options
- **TUI (Terminal UI)** — `ui-tui/` rich terminal interface
- **Web UI** — `web/` directory for web interface
- **TUI Gateway** — `tui_gateway/` bridging TUI and gateway

### 🚀 Deployment
- Works on Linux, macOS, WSL2, Android (Termux)
- Docker support
- Can run on a $5 VPS, GPU cluster, or serverless
- Nix support

---

## 3️⃣ OpenClaw Dev Mode — `bresleveloper/openclaw-dev-mode`
> ⭐ 3 stars · TypeScript · Fork of OpenClaw with security relaxations

This is a **personal fork** of OpenClaw that relaxes security restrictions for dev/power-user scenarios. It inherits ALL of OpenClaw's features and adds:

### 🔓 Security Easings (gated by `OPENCLAW_DEV_MODE=1`)
- **Always show raw config** in web GUI (no block)
- **Remove restrictive prompt sections** — strips internal restrictive initial prompts
- **Skip elevated permission gates** when dev-mode + Full profile active
- **Agent files and raw config secrets visible** by default in Control UI

### 📱 WhatsApp Power Features
- **Thinking/reasoning messages over WhatsApp** — shows model reasoning with 💭 prefix (`OPENCLAW_DEV_MODE_WA_THINKING_MESSAGES=1`)
- **Full WhatsApp history to SQLite** — saves all messages to `~/.openclaw/dev-mode/wa-history.db` for agents to passively query (`OPENCLAW_DEV_MODE_WA_SAVE_MESSAGES=1`)

### 🧠 Model Provider Tweaks
- **Ollama `think: true`** support with reasoning output level
- **`reasoning.summary: "auto"`** setting

### 📝 Other Additions
- **`MEMORY.md` written on agent creation** — auto-creates memory file
- **VPS-optimized** — designed to run on a personal VPS (uses JarvisHub directly)

### ⚙️ Configuration
```bash
# Add to ~/.openclaw/.env
OPENCLAW_DEV_MODE=1
OPENCLAW_DEV_MODE_CLEAR_UI=1
OPENCLAW_DEV_MODE_WA_THINKING_MESSAGES=1
OPENCLAW_DEV_MODE_WA_SAVE_MESSAGES=1
```

---

## 📊 Side-by-Side Comparison

| Feature | OpenClaw | Hermes Agent | OpenClaw Dev Mode |
|---|:---:|:---:|:---:|
| **Language** | TypeScript | Python | TypeScript |
| **Stars** | 368k | 131k | 3 |
| **Messaging channels** | 26+ | 6 | 26+ (inherited) |
| **Self-improving/learning** | ❌ | ✅ ⭐ | ❌ |
| **Skill creation from experience** | ❌ | ✅ ⭐ | ❌ |
| **User modeling across sessions** | ❌ | ✅ ⭐ | ❌ |
| **Past conversation search** | ❌ | ✅ | ❌ |
| **Skills system** | ✅ | ✅ | ✅ |
| **Multi-model support** | ✅ | ✅ (200+ via OpenRouter) | ✅ |
| **Voice (wake/talk)** | ✅ | ❌ | ✅ |
| **Canvas/visual workspace** | ✅ | ❌ | ✅ |
| **Companion apps (iOS/Android/macOS)** | ✅ | ❌ | ✅ |
| **Browser automation** | ✅ | ❌ | ✅ |
| **Cron jobs** | ✅ | ✅ | ✅ |
| **Webhooks** | ✅ | ❌ | ✅ |
| **Gmail integration** | ✅ | ❌ | ✅ |
| **Multi-agent routing** | ✅ | ❌ | ✅ |
| **Sandboxing** | ✅ | ❌ | ✅ (relaxed) |
| **DM pairing security** | ✅ | ❌ | ✅ (relaxed) |
| **MCP support** | ❌ | ✅ | ❌ |
| **RL training** | ❌ | ✅ | ❌ |
| **WhatsApp thinking messages** | ❌ | ❌ | ✅ |
| **WhatsApp history to SQLite** | ❌ | ❌ | ✅ |
| **Dev mode security bypass** | ❌ | ❌ | ✅ |
| **Personality switching** | ✅ (SOUL.md) | ✅ (/personality) | ✅ |
| **Docker support** | ✅ | ✅ | ✅ |
| **Web UI** | ✅ (Control UI) | ✅ | ✅ |
| **Terminal UI** | ❌ | ✅ (rich TUI) | ❌ |

---

## 🎯 What Should You Pick?

**Tell me which features from each repo you want, and I'll build your custom assistant.** Some example combos:

1. **"I want OpenClaw's channel coverage + Hermes' self-learning"** — I'd build a hybrid with OpenClaw's messaging layer and Hermes-style memory/skill evolution
2. **"I want Hermes but with more channels"** — Extend Hermes with additional channel adapters  
3. **"I want Dev Mode's unrestricted approach + Hermes' intelligence"** — Build a no-guardrails learning agent
4. **"Build me something completely new"** — Cherry-pick the best of all three

What features do you want? 🎯
