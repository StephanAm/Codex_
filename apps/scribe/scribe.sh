#!/usr/bin/env bash
# Wrapper for `scribe`.
#
# Config lives in ~/.codex_/scribe/config.toml — run `scribe config init`
# to create it. Environment variables below override the config file if set.

# ── Optional overrides ────────────────────────────────────────────────────────
# export CARTOGRAPHER_DB=""
# export CARTOGRAPHER_BIN=""
# export SCRIBE_BACKEND=""
# export SCRIBE_CLAUDE_BIN=""
# export SCRIBE_MODEL=""
# export SCRIBE_OLLAMA_URL=""
# export SCRIBE_TOP_K=""

# ── Run ───────────────────────────────────────────────────────────────────────
exec uv run --package scribe scribe "$@"
