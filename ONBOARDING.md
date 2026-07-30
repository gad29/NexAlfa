# NexAlfa Onboarding Guide

A step-by-step guide to get Nex up and running on your VPS. Covers connecting to a model provider, WhatsApp, and Email.

---

## Step 1: Prerequisites

Your VPS needs:
- **Python 3.11+** (`python3 --version`)
- **Node.js 20+** (`node --version`)
- **Git** (`git --version`)

If missing:
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y python3.11 python3-pip nodejs npm git

# Or use uv for Python (recommended — fast)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Step 2: Install NexAlfa

```bash
# Clone the repo
git clone <your-repo-url> ~/NexAlfa
cd ~/NexAlfa

# Install Python dependencies
pip install -e ".[all]"

# Install Playwright browsers (for browser tool)
playwright install chromium --with-deps

# Install web app dependencies
cd web && npm install && cd ..
```

---

## Step 3: Configure (.env)

```bash
cp .env.example .env
nano .env   # or vim, or any editor
```

### Minimum required — set at least ONE model provider:

```bash
# Option A: OpenAI
OPENAI_API_KEY=sk-your-key-here

# Option B: Google (Gemini)
GOOGLE_API_KEY=your-google-api-key

# Option C: OpenRouter (200+ models)
OPENROUTER_API_KEY=your-openrouter-key

# Option D: Ollama (local, free)
# Just make sure Ollama is running: ollama serve
OLLAMA_BASE_URL=http://localhost:11434
```

### Set the default model:

```bash
# Examples:
NEX_DEFAULT_MODEL=openai/gpt-4o
NEX_DEFAULT_MODEL=google/gemini-2.5-flash
NEX_DEFAULT_MODEL=openrouter/anthropic/claude-sonnet-4
NEX_DEFAULT_MODEL=ollama/llama3
```

### Set a gateway secret:

```bash
NEX_GATEWAY_SECRET=your-random-secret-string-here
```

---

## Step 4: Connect WhatsApp (Bridge Mode)

NexAlfa uses a WhatsApp Web bridge by default — similar to how OpenClaw does it. This connects via QR code scan, like WhatsApp Web.

### 4a. Ensure bridge mode is on:

In `.env`:
```bash
NEX_WHATSAPP_BRIDGE=true
```

### 4b. Start the gateway:

```bash
nexalfa gateway
```

### 4c. Scan QR code:

When the gateway starts, the WhatsApp bridge will display a QR code in the terminal. Scan it with your phone's WhatsApp (Settings → Linked Devices → Link a Device).

### 4d. Test:

Send a message to yourself or have someone message you. Nex will respond.

### 4e. (Optional) Switch to Meta Cloud API later:

When you're ready to use the official Meta Business API:

```bash
NEX_WHATSAPP_BRIDGE=false
WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id
WHATSAPP_BUSINESS_ACCOUNT_ID=your-business-account-id
WHATSAPP_ACCESS_TOKEN=your-permanent-access-token
WHATSAPP_VERIFY_TOKEN=your-verify-token
```

Then configure the webhook URL in Meta Developer Console:
- **URL**: `https://your-vps-domain:18789/webhook/whatsapp`
- **Verify Token**: same as `WHATSAPP_VERIFY_TOKEN` in `.env`
- **Subscribe to**: `messages`

---

## Step 5: Connect Email

### 5a. Configure SMTP/IMAP:

In `.env`:
```bash
# Gmail example:
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_IMAP_HOST=imap.gmail.com
EMAIL_IMAP_PORT=993
EMAIL_ADDRESS=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
```

> **Important**: For Gmail, you need an **App Password** (not your regular password).
> Go to: Google Account → Security → 2-Step Verification → App Passwords → Create one.

### 5b. Restart gateway:

```bash
# Stop current gateway (Ctrl+C) then:
nexalfa gateway
```

Now emails sent to your address will be processed by Nex, and replies will be sent automatically.

---

## Step 6: Start the Web App

```bash
# In a new terminal:
cd ~/NexAlfa/web
npm run dev
```

Open: `http://your-vps-ip:3000`

For production, build first:
```bash
npm run build
npm start
```

---

## Step 7: Run as a Service (Auto-start)

### Using systemd:

```bash
sudo tee /etc/systemd/system/nexalfa.service << 'EOF'
[Unit]
Description=NexAlfa Gateway
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/NexAlfa
ExecStart=/usr/local/bin/nexalfa gateway
Restart=always
RestartSec=5
Environment=PATH=/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable nexalfa
sudo systemctl start nexalfa
```

Check status:
```bash
sudo systemctl status nexalfa
sudo journalctl -u nexalfa -f   # live logs
```

---

## Step 8: Verify Everything

```bash
# Check health
curl http://localhost:18789/health

# Check status
curl http://localhost:18789/api/status

# Check channels
curl http://localhost:18789/api/channels

# Send a test message via API
curl -X POST http://localhost:18789/api/message \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello Nex!", "channel": "api"}'
```

---

## Docker Alternative

If you prefer Docker:

```bash
cd ~/NexAlfa
cp .env.example .env
nano .env  # fill in your keys

docker-compose up -d

# Check logs
docker-compose logs -f
```

---

## Troubleshooting

### "Connection refused" on port 18789
- Make sure the gateway is running: `nexalfa gateway`
- Check firewall: `sudo ufw allow 18789`

### WhatsApp QR code not appearing
- Ensure `NEX_WHATSAPP_BRIDGE=true` in `.env`
- Try restarting the gateway

### Model errors
- Run `nexalfa doctor` to check API key configuration
- Make sure at least one provider key is set in `.env`

### Web app not loading
- Check it's running: `cd web && npm run dev`
- Make sure `NEXT_PUBLIC_GATEWAY_URL` points to your gateway

---

## What's Next?

1. **Chat with Nex** via WhatsApp or the web app
2. **Watch it learn** — Nex auto-creates memories and skills
3. **Connect more channels** — Telegram, Discord, Slack, Google Chat
4. **Create skills** — write SKILL.md files in `workspace/skills/`
5. **Customize personality** — edit `workspace/SOUL.md`

Enjoy your personal AI agent! 🤖
