#!/usr/bin/env bash
# One-time migration: moves existing data to the new ~/.codex_/ layout.
set -euo pipefail

CODEX="$HOME/.codex_"
mkdir -p "$CODEX/mnemo_" "$CODEX/cartographer"

# Mnemo data
if [[ -d "$HOME/.note_taker" ]]; then
    echo "▶ Migrating ~/.note_taker/ → ~/.codex_/mnemo_/"
    cp -an "$HOME/.note_taker/." "$CODEX/mnemo_/"
    echo "  done (original kept at ~/.note_taker — remove manually once happy)"
fi

# Cartographer data
if [[ -d "$HOME/.cartographer" ]]; then
    echo "▶ Migrating ~/.cartographer/ → ~/.codex_/cartographer/"
    cp -an "$HOME/.cartographer/." "$CODEX/cartographer/"

    # Credentials move up to ~/.codex_/ root
    for f in credentials.json token.json; do
        if [[ -f "$CODEX/cartographer/$f" && ! -f "$CODEX/$f" ]]; then
            echo "  moving $f → ~/.codex_/$f"
            mv "$CODEX/cartographer/$f" "$CODEX/$f"
        fi
    done
    echo "  done (original kept at ~/.cartographer — remove manually once happy)"
fi

# Credentials from old Mnemo location
for f in credentials.json token.json; do
    if [[ -f "$HOME/.note_taker/$f" && ! -f "$CODEX/$f" ]]; then
        echo "▶ Moving ~/.note_taker/$f → ~/.codex_/$f"
        cp "$HOME/.note_taker/$f" "$CODEX/$f"
    fi
done

echo "Migration complete → $CODEX"
