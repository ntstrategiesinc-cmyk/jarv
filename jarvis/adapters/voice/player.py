"""Stream PCM playback with barge-in.

Plays raw 16-bit mono PCM chunks as they arrive (so the assistant starts speaking before the whole
reply is synthesized). A shared stop flag lets another thread interrupt playback the instant the
owner presses push-to-talk again — so you can always cut Jarvis off.
"""

from __future__ import annotations

import threading
from typing import Iterable

import numpy as np
import sounddevice as sd


class PcmPlayer:
    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate
        self._stop = threading.Event()

    def stop(self) -> None:
        """Signal any in-progress playback to halt (barge-in)."""
        self._stop.set()

    def play(self, pcm_chunks: Iterable[bytes]) -> bool:
        """Play a stream of PCM chunks. Returns True if it finished, False if interrupted."""
        self._stop.clear()
        stream = sd.OutputStream(samplerate=self.sample_rate, channels=1, dtype="int16")
        stream.start()
        finished = True
        try:
            for chunk in pcm_chunks:
                if self._stop.is_set():
                    finished = False
                    break
                if not chunk:
                    continue
                stream.write(np.frombuffer(chunk, dtype="int16"))
        finally:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        return finished
