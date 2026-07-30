#!/bin/bash
# ============================================================
# NexAlfa VPS Deployment Script
# Run this on your VPS after cloning the repo
# ============================================================

set -e

echo "🚀 NexAlfa VPS Deployment"
echo "========================================"

# ── Check prerequisites ──────────────────────────────────────
command -v docker >/dev/null 2>&1 || { echo "❌ Docker not found. Install: https://docs.docker.com/engine/install/"; exit 1; }
command -v docker compose >/dev/null 2>&1 || { echo "❌ Docker Compose not found."; exit 1; }

# ── Config ───────────────────────────────────────────────────
if [ ! -f .env ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env with your API keys before continuing!"
    echo "   nano .env"
    echo ""
    echo "At minimum, set one of these:"
    echo "   OPENAI_API_KEY=sk-..."
    echo "   GOOGLE_API_KEY=..."
    echo "   OPENROUTER_API_KEY=..."
    echo ""
    echo "Also set:"
    echo "   NEX_GATEWAY_SECRET=<random-string>"
    echo "   NEX_DOMAIN=your-domain.com (for SSL)"
    echo "   NEX_PUBLIC_URL=https://your-domain.com"
    echo ""
    echo "Then re-run this script."
    exit 0
fi

# ── Read domain from .env ────────────────────────────────────
DOMAIN=$(grep -E "^NEX_DOMAIN=" .env | cut -d= -f2)

# ── SSL Setup ────────────────────────────────────────────────
if [ -n "$DOMAIN" ] && [ "$DOMAIN" != "localhost" ]; then
    echo "🔒 Setting up SSL for $DOMAIN..."
    mkdir -p deploy/certbot/conf deploy/certbot/www

    if [ ! -d "deploy/certbot/conf/live/$DOMAIN" ]; then
        echo "Getting initial SSL certificate..."
        # Start nginx temporarily for the ACME challenge
        docker compose up -d nginx
        sleep 5

        docker compose run --rm certbot certonly \
            --webroot \
            --webroot-path=/var/www/certbot \
            -d "$DOMAIN" \
            --email "admin@$DOMAIN" \
            --agree-tos \
            --no-eff-email

        docker compose down
        echo "✅ SSL certificate obtained for $DOMAIN"
    else
        echo "✅ SSL certificate already exists for $DOMAIN"
    fi
else
    echo "⚠️  No NEX_DOMAIN set in .env — running without SSL (HTTP only)"
    echo "   Set NEX_DOMAIN=your-domain.com for HTTPS"
fi

# ── Build & Deploy ───────────────────────────────────────────
echo ""
echo "🔨 Building containers..."
docker compose build

echo ""
echo "🚀 Starting NexAlfa..."
docker compose up -d

echo ""
echo "========================================"
echo "✅ NexAlfa is running!"
echo ""
echo "  📡 Gateway API:  http://localhost:18789"
echo "  🌐 Web App:      http://localhost:3000"

if [ -n "$DOMAIN" ] && [ "$DOMAIN" != "localhost" ]; then
    echo "  🔒 HTTPS:        https://$DOMAIN"
fi

echo ""
echo "  📋 Logs:          docker compose logs -f"
echo "  🛑 Stop:          docker compose down"
echo "  🔄 Restart:       docker compose restart"
echo "  📦 Rebuild:       docker compose up -d --build"
echo "========================================"
