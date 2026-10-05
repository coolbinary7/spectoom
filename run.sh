#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
APP_VERSION="2.2.2-cloud"
PORT="${PORT:-8080}"

printf '\nSpectoom %s - demarrage\n\n' "$APP_VERSION"

running_version="$(python3 - "$PORT" <<'PY' 2>/dev/null || true
import json, sys, urllib.request
port=sys.argv[1]
try:
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=.8) as response:
        print(json.load(response).get('version',''))
except Exception:
    pass
PY
)"
if [ -n "$running_version" ]; then
  if [ "$running_version" = "$APP_VERSION" ]; then
    printf 'Spectoom %s est deja demarre sur le port %s.\n' "$APP_VERSION" "$PORT"
    exit 0
  fi
  printf 'Une ancienne version (%s) utilise le port %s. Arretez-la puis relancez.\n' "$running_version" "$PORT" >&2
  exit 2
fi

python3 -m pip install --disable-pip-version-check -r requirements.txt
python3 server.py
