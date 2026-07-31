FROM python:3.11-slim AS base

WORKDIR /app

# System deps — Node.js for mcporter/Agent Reach, Playwright, git
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git build-essential gnupg ca-certificates pipx && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g mcporter && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY agent/ agent/
COPY gateway/ gateway/
COPY cli/ cli/
COPY workspace/ workspace/

# Install Python deps
RUN uv pip install --system -e ".[all]"

# Install Agent Reach into its own venv
RUN python -m venv /root/.agent-reach-venv && \
    /root/.agent-reach-venv/bin/pip install https://github.com/Panniantong/agent-reach/archive/main.zip
ENV PATH="/root/.agent-reach-venv/bin:$PATH"

# Install extra Python packages used by NexAlfa extensions
RUN uv pip install --system g4f graphifyy

# Install Playwright browsers
RUN playwright install chromium --with-deps

# Create storage directories
RUN mkdir -p storage/memory .nex/memory_raw

# Configure mcporter + Exa (user provides EXA key via env)
RUN mcporter config add exa https://mcp.exa.ai/mcp --scope home

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | \
    gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > \
    /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && apt-get install -y gh && rm -rf /var/lib/apt/lists/*

EXPOSE 18789

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://127.0.0.1:18789/health || exit 1

CMD ["/usr/local/bin/python", "-m", "gateway.server"]

# ── Web Frontend Build Stage ──────────────────────────────────
FROM node:20-alpine AS web-builder

WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web/ .

# The API URL will be set at build time for Next.js
ARG NEXT_PUBLIC_API_URL=http://localhost:18789
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# ── Web Runtime ───────────────────────────────────────────────
FROM node:20-alpine AS web

WORKDIR /web
COPY --from=web-builder /web/.next/standalone ./
COPY --from=web-builder /web/.next/static ./.next/static
COPY --from=web-builder /web/public ./public

EXPOSE 3000
ENV HOSTNAME="0.0.0.0"
CMD ["node", "server.js"]
