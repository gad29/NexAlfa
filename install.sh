#!/usr/bin/env bash
# NexAlfa Linux/macOS Installer
# Usage: curl -fsSL https://nexalfa.work/install.sh | bash

set -e

echo -e "\033[0;36m🚀 Installing NexAlfa — Your Autonomous AI Agent...\033[0m"

# Detect OS
OS="$(uname -s)"
case "${OS}" in
    Linux*)     MACHINE=Linux;;
    Darwin*)    MACHINE=Mac;;
    *)          MACHINE="UNKNOWN:${OS}"
esac

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "\033[0;33m⚠️ Python 3 not found. Installing Python 3...\033[0m"
    if [ "$MACHINE" == "Linux" ]; then
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv git nodejs npm
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y python3 python3-pip git nodejs npm
        fi
    elif [ "$MACHINE" == "Mac" ]; then
        brew install python node git
    fi
else
    echo -e "\033[0;32m✅ Python 3 detected: $(python3 --version)\033[0m"
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "\033[0;33m⚠️ Node.js not found. Installing Node.js...\033[0m"
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

# Install uv
echo -e "\033[0;36m📦 Installing uv package manager...\033[0m"
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# Clone repository
INSTALL_DIR="$HOME/NexAlfa"
if [ -d "$INSTALL_DIR" ]; then
    echo -e "\033[0;36m🔄 Updating existing NexAlfa installation...\033[0m"
    cd "$INSTALL_DIR"
    git pull origin main -q
else
    echo -e "\033[0;36m📥 Cloning NexAlfa repository...\033[0m"
    git clone https://github.com/gad29/NexAlfa.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Install dependencies
echo -e "\033[0;36m⚙️ Installing Python dependencies...\033[0m"
uv pip install --system -e ".[all]" pywebview

echo -e "\033[0;36m⚙️ Installing Node.js dependencies...\033[0m"
npm install --omit=dev

cd "$INSTALL_DIR/web"
npm install --omit=dev
cd "$INSTALL_DIR"

# Global symlinks
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

cat << 'EOF' > "$BIN_DIR/nexalfa"
#!/usr/bin/env bash
python3 -m cli.main "$@"
EOF

cat << 'EOF' > "$BIN_DIR/nex"
#!/usr/bin/env bash
python3 -m cli.main "$@"
EOF

chmod +x "$BIN_DIR/nexalfa" "$BIN_DIR/nex"

echo -e "\n\033[0;32m✅ NexAlfa installation complete!\033[0m"
echo -e "\033[0;36mStarting interactive onboarding setup...\033[0m\n"

# Run onboarding
python3 -m cli.main onboard
