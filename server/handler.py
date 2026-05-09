import asyncio
import logging

import websockets

logger = logging.getLogger(__name__)


class ClientHandler:
    def __init__(self, capture, playback):
        self.capture = capture
        self.playback = playback

    async def handle(self, websocket):
        remote = websocket.remote_address
        logger.info("Client connected: %s", remote)
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._send_audio(websocket))
                tg.create_task(self._receive_audio(websocket))
        except Exception as e:
            logger.info("Client disconnected: %s  reason=%s", remote, e)

    async def _send_audio(self, websocket):
        loop = asyncio.get_running_loop()
        while True:
            try:
                pcm = await loop.run_in_executor(None, self.capture.read)
                await websocket.send(pcm)
            except websockets.ConnectionClosed:
                break
            except Exception as e:
                logger.warning("Send error: %s", e)

    async def _receive_audio(self, websocket):
        loop = asyncio.get_running_loop()
        async for message in websocket:
            if not isinstance(message, bytes):
                continue
            try:
                await loop.run_in_executor(None, self.playback.write, message)
            except Exception as e:
                logger.warning("Receive error: %s", e)
