#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv"

if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV"
fi

echo "Installing dependencies..."
"$VENV/bin/pip" install -q -r "$DIR/server/requirements.txt"

echo "Starting Sound Bridge server (HTTPS if cert.pem/key.pem found)..."
exec "$VENV/bin/python" "$DIR/server/main.py" "$@"
