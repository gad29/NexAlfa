#!/bin/bash
# ============================================================
# NexAlfa — Kali Linux VPS Pre-Deployment Setup
# Run this ONCE before deploy.sh to install Docker & deps
# ============================================================

set -e

echo "🐉 NexAlfa — Kali Linux Setup"
echo "========================================"

# ── Update system ────────────────────────────────────────────
echo "📦 Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# ── Install Docker ───────────────────────────────────────────
if command -v docker &>/dev/null; then
    echo "✅ Docker already installed: $(docker --version)"
else
    echo "🐳 Installing Docker..."
    sudo apt-get install -y ca-certificates curl gnupg lsb-release

    # Add Docker's official GPG key
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    # Kali is based on Debian testing — use bookworm as the stable base
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Let current user run Docker without sudo
    sudo usermod -aG docker "$USER"
    echo "✅ Docker installed: $(docker --version)"
fi

# ── Verify Docker Compose ────────────────────────────────────
if docker compose version &>/dev/null; then
    echo "✅ Docker Compose: $(docker compose version --short)"
else
    echo "❌ Docker Compose plugin not found. Try: sudo apt-get install docker-compose-plugin"
    exit 1
fi

# ── Start Docker service ─────────────────────────────────────
sudo systemctl enable docker
sudo systemctl start docker
echo "✅ Docker service running"

# ── Install git if missing ───────────────────────────────────
if ! command -v git &>/dev/null; then
    sudo apt-get install -y git
fi

# ── Firewall (ufw) ──────────────────────────────────────────
if command -v ufw &>/dev/null; then
    echo "🔥 Configuring firewall..."
    sudo ufw allow 80/tcp    # HTTP
    sudo ufw allow 443/tcp   # HTTPS
    sudo ufw allow 22/tcp    # SSH (don't lock yourself out!)
    echo "✅ Ports 80, 443, 22 open"
fi

echo ""
echo "========================================"
echo "✅ Kali Linux setup complete!"
echo ""
echo "⚠️  If Docker was just installed, log out and back in"
echo "   (or run: newgrp docker) so you can use Docker without sudo."
echo ""
echo "Next steps:"
echo "  1. cd ~/NexAlfa"
echo "  2. cp .env.example .env && nano .env"
echo "  3. ./deploy.sh"
echo "========================================"
