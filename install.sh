#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing scribe and cartographer to /usr/local/bin..."
sudo cp "$SCRIPT_DIR/apps/scribe/build/scribe"             /usr/local/bin/scribe
sudo cp "$SCRIPT_DIR/apps/cartographer/build/cartographer" /usr/local/bin/carto
sudo chmod +x /usr/local/bin/scribe /usr/local/bin/cartographer
echo "Done."
