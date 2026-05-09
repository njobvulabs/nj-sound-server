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

CERT="$DIR/server/cert.pem"
KEY="$DIR/server/key.pem"
if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
    echo "Generating self-signed SSL certificate..."
    openssl req -x509 -newkey rsa:4096 -keyout "$KEY" -out "$CERT" \
        -days 365 -nodes -subj '/CN=SoundBridge' 2>/dev/null
fi

echo ""
echo "Setup complete!"
echo ""
echo "To start the server:"
echo "  bash server.sh"
echo ""
echo "Then open https://YOUR_SERVER_IP:8765 in your phone browser."
