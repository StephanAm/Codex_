#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${1:-$SCRIPT_DIR/bulletins}"
mkdir -p "$OUTPUT_DIR"

START="2026-05-01"
END="$(date +%Y-%m-%d)"

current="$START"
while [[ ! "$current" > "$END" ]]; do
    echo "▶ $current"
    "$SCRIPT_DIR/scribe.sh" bulletin \
        --date "$current" \
        --output "$OUTPUT_DIR/bulletin-$current.md" \
        2>&1 | sed 's/^/  /'
    current="$(date -d "$current + 1 day" +%Y-%m-%d)"
done

echo "Done → $OUTPUT_DIR"
