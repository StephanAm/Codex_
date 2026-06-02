#!/usr/bin/env bash
# Wrapper for `scribe`. Edit the variables below to match your environment,
# then run this script instead of `scribe` directly.

# ── Cartographer ──────────────────────────────────────────────────────────────
export CARTOGRAPHER_DB="${CARTOGRAPHER_DB:-$HOME/.cartographer/index.db}"
export CARTOGRAPHER_BIN="/home/stephan/Code/codex/apps/cartographer/cartographer.sh"

# ── LLM ───────────────────────────────────────────────────────────────────────
export SCRIBE_MODEL="${SCRIBE_MODEL:-llama3.2:3b}"
export SCRIBE_OLLAMA_URL="${SCRIBE_OLLAMA_URL:-http://localhost:11434}"
export SCRIBE_TOP_K="${SCRIBE_TOP_K:-10}"

# ── Run ───────────────────────────────────────────────────────────────────────
exec uv run --package scribe scribe "$@"
