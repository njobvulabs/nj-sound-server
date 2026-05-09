import os
import queue
import subprocess
import threading
from collections import deque

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 48000
FRAME_SIZE = 960


def get_monitor_source_name():
    try:
        result = subprocess.run(
            ["pactl", "info"], capture_output=True, text=True
        )
        default_sink = None
        for line in result.stdout.splitlines():
            if "Default Sink" in line:
                default_sink = line.split(":", 1)[1].strip()
                break
        if default_sink:
            monitor_name = f"{default_sink}.monitor"
            sources = subprocess.run(
                ["pactl", "list", "sources", "short"],
                capture_output=True, text=True
            )
            for line in sources.stdout.splitlines():
                if monitor_name in line:
                    return monitor_name
    except Exception:
        pass
    return None


class AudioCapture:
    def __init__(self, device=None, channels=1):
        self.channels = channels
        self.pulse_source = device or get_monitor_source_name()
        self.queue = queue.Queue()
        self.stream = None
        self._old_pulse_source = None

    def _callback(self, indata, frames, time, status):
        if status:
            return
        if indata.shape[1] > self.channels:
            indata = np.mean(indata, axis=1, keepdims=True)
        np.clip(indata, -1.0, 1.0, out=indata)
        pcm = (indata * 32767).astype(np.int16)
        self.queue.put(pcm.tobytes())

    def read(self):
        return self.queue.get()

    def start(self):
        if isinstance(self.pulse_source, str) and ".monitor" in self.pulse_source:
            self._old_pulse_source = os.environ.get("PULSE_SOURCE")
            os.environ["PULSE_SOURCE"] = self.pulse_source
            dev = None
        else:
            dev = self.pulse_source
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=self.channels,
            blocksize=FRAME_SIZE,
            callback=self._callback,
            device=dev,
            dtype="float32",
        )
        self.stream.start()

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if self._old_pulse_source is not None:
            if self._old_pulse_source:
                os.environ["PULSE_SOURCE"] = self._old_pulse_source
            else:
                os.environ.pop("PULSE_SOURCE", None)


class AudioPlayback:
    def __init__(self, channels=1):
        self.channels = channels
        self.buffer = deque()
        self.lock = threading.Lock()
        self.stream = None

    def _callback(self, outdata, frames, time, status):
        with self.lock:
            if self.buffer:
                data = self.buffer.popleft()
                if data.shape[0] >= frames:
                    outdata[:frames, :] = data[:frames, :]
                    if data.shape[0] > frames:
                        self.buffer.appendleft(data[frames:])
                else:
                    outdata[:data.shape[0], :] = data[:, :]
                    outdata[data.shape[0]:, :] = 0.0
            else:
                outdata.fill(0.0)

    def write(self, pcm_bytes):
        arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32767.0
        with self.lock:
            if len(self.buffer) < 32:
                self.buffer.append(arr.reshape(-1, self.channels))

    def start(self):
        self.stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=self.channels,
            callback=self._callback,
            dtype="float32",
            blocksize=FRAME_SIZE,
        )
        self.stream.start()

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
