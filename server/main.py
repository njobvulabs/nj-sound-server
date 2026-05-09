import argparse
import asyncio
import logging
import os
import signal
import socket
import ssl

import sounddevice as sd
import websockets

from audio import AudioCapture, AudioPlayback
from handler import ClientHandler

__version__ = "1.0.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logging.getLogger("websockets").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


async def process_request(connection, request):
    if request.path == "/" and "Upgrade" not in request.headers:
        index_path = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_path):
            with open(index_path, "r") as f:
                body = f.read()
            response = connection.respond(200, body)
            response.headers["Content-Type"] = "text/html; charset=utf-8"
            response.headers["Cache-Control"] = "no-cache"
            return response
        return connection.respond(404, "Not Found")
    return None


def build_parser():
    parser = argparse.ArgumentParser(
        prog="nj-sound-server",
        description="Use your Android phone as a wireless speaker and microphone for your PC.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    conn = parser.add_argument_group("Connection")
    conn.add_argument("--host", default="0.0.0.0", help="Bind address (default: %(default)s)")
    conn.add_argument("--port", type=int, default=8765, help="Server port (default: %(default)s)")

    audio = parser.add_argument_group("Audio")
    audio.add_argument("--stereo", action="store_true", help="Enable stereo PC→Phone audio")
    audio.add_argument("--device", type=int, help="PulseAudio source device index")
    audio.add_argument("--list-devices", action="store_true", help="Show available audio devices and exit")

    sec = parser.add_argument_group("Security")
    sec.add_argument("--cert", help="SSL certificate path (auto-detects cert.pem)")
    sec.add_argument("--key", help="SSL private key path (auto-detects key.pem)")

    other = parser.add_argument_group("Other")
    other.add_argument("--version", action="store_true", help="Show version and exit")

    return parser


def detect_local_ip():
    for fam in (socket.AF_INET,):
        for name in (socket.gethostname(), "localhost", "hostname"):
            try:
                addrs = socket.getaddrinfo(name, None, fam, socket.SOCK_STREAM)
                for addr in addrs:
                    ip = addr[4][0]
                    if ip != "127.0.0.1":
                        return ip
            except OSError:
                break
    return "localhost"


def resolve_ssl(args):
    cert_path = args.cert
    key_path = args.key
    if cert_path or key_path:
        if not cert_path or not key_path:
            raise SystemExit("--cert and --key must be used together")
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert_path, key_path)
        return ctx
    server_dir = os.path.dirname(os.path.abspath(__file__))
    auto_cert = os.path.join(server_dir, "cert.pem")
    auto_key = os.path.join(server_dir, "key.pem")
    if os.path.exists(auto_cert) and os.path.exists(auto_key):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(auto_cert, auto_key)
        return ctx
    return None


async def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        print(f"nj-sound-server v{__version__}")
        return

    if args.list_devices:
        print(sd.query_devices())
        return

    ssl_context = resolve_ssl(args)
    channels = 2 if args.stereo else 1
    proto = "https" if ssl_context else "http"

    logger.info("")
    logger.info("  NJ Sound Server v%s", __version__)
    logger.info("  %s://%s:%d  (%s, %s)", proto, detect_local_ip(), args.port,
                "stereo" if args.stereo else "mono", "SSL" if ssl_context else "no SSL")
    logger.info("")

    capture = AudioCapture(device=args.device, channels=channels)
    playback = AudioPlayback(channels=channels)
    handler = ClientHandler(capture, playback)

    capture.start()
    playback.start()

    stop = asyncio.Future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(
            sig, lambda: stop.set_result(None)
        )

    async with websockets.serve(
        handler.handle,
        args.host,
        args.port,
        process_request=process_request,
        ssl=ssl_context,
    ):
        logger.info("Ready — open %s://%s:%d in your phone browser", proto, detect_local_ip(), args.port)
        try:
            await stop
        except asyncio.CancelledError:
            pass

    capture.stop()
    playback.stop()
    logger.info("Goodbye")


if __name__ == "__main__":
    asyncio.run(main())
