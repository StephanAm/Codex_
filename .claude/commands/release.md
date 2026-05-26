Run a full release for the specified app: build, commit pending changes, bump version, and push.

Usage: /release <app> [major|minor|patch]  (e.g. /release mnemo patch)

```bash
APP="$(echo "${ARGUMENTS:-}" | awk '{print $1}')"
BUMP="$(echo "${ARGUMENTS:-}" | awk '{print $2}')"
BUMP="${BUMP:-patch}"
if [ -z "$APP" ]; then
  echo "Error: app name required. Usage: /release <app> [major|minor|patch]" >&2
  exit 1
fi
./apps/$APP/scripts/release.sh "$BUMP"
```
