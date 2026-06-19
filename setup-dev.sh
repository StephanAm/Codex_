#!/usr/bin/env bash
# setup-dev.sh — Install Codex build dependencies on Debian / Ubuntu / Mint.
# Safe to re-run: each dependency is checked before installing.

set -euo pipefail

ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
info() { printf '  \033[33m→\033[0m %s\n' "$*"; }
step() { printf '\n\033[1m── %s\033[0m\n' "$*"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

apt_installed() { dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q "install ok installed"; }

# ── apt packages ──────────────────────────────────────────────────────────────
step "System packages"

APT_PKGS=(
    curl
    build-essential
    pkg-config
    libwebkit2gtk-4.1-dev
    librsvg2-dev
    squashfs-tools
)

MISSING=()
for pkg in "${APT_PKGS[@]}"; do
    if apt_installed "$pkg"; then
        ok "$pkg"
    else
        MISSING+=("$pkg")
        info "$pkg (missing)"
    fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
    info "Running: sudo apt install ${MISSING[*]}"
    sudo apt-get update -qq
    sudo apt-get install -y "${MISSING[@]}"
fi

# ── uv ────────────────────────────────────────────────────────────────────────
step "uv (Python package manager)"
export PATH="$HOME/.local/bin:$PATH"

if command -v uv >/dev/null 2>&1; then
    ok "uv $(uv --version | awk '{print $2}')"
else
    info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ok "uv installed — added to ~/.local/bin"
fi

# ── nvm ───────────────────────────────────────────────────────────────────────
step "nvm (Node version manager)"
export NVM_DIR="$HOME/.nvm"

if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    ok "nvm already installed"
else
    info "Installing nvm..."
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
    ok "nvm installed"
fi

# Load nvm into this shell session
# shellcheck source=/dev/null
source "$NVM_DIR/nvm.sh"

# ── Node.js 24 ────────────────────────────────────────────────────────────────
step "Node.js 24"

if nvm ls 24 2>/dev/null | grep -q "v24"; then
    NODE_VER="$(node --version 2>/dev/null || nvm run 24 --silent node --version)"
    ok "Node.js 24 already installed ($NODE_VER)"
else
    info "Installing Node.js 24 via nvm..."
    nvm install 24
    nvm alias default 24
    ok "Node.js 24 installed"
fi

nvm use 24 --silent

# ── pnpm ──────────────────────────────────────────────────────────────────────
step "pnpm"

if command -v pnpm >/dev/null 2>&1; then
    ok "pnpm $(pnpm --version)"
else
    info "Installing pnpm..."
    npm install -g pnpm
    ok "pnpm installed"
fi

# ── Rust + Cargo ──────────────────────────────────────────────────────────────
step "Rust + Cargo"
export PATH="$HOME/.cargo/bin:$PATH"

if command -v cargo >/dev/null 2>&1; then
    ok "cargo $(cargo --version | awk '{print $2}')"
else
    info "Installing Rust via rustup..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path
    # shellcheck source=/dev/null
    source "$HOME/.cargo/env"
    ok "Rust installed"
fi

# ── done ──────────────────────────────────────────────────────────────────────
printf '\n\033[1;32mAll build dependencies installed.\033[0m\n'
printf '\nNext steps:\n'
printf '  uv sync --all-packages   # Python workspace\n'
printf '  pnpm install             # Node workspace\n'
printf '\n'
printf 'If this was a fresh install of nvm or Rust, open a new terminal first\n'
printf 'so their shell integrations are active.\n'
