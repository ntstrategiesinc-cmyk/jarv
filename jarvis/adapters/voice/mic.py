"""Microphone capture while the push-to-talk key is held.

Push-to-talk means we never guess when speech starts or ends — recording runs between key-down and
key-up. Captures 16-bit mono PCM at the STT sample rate.
"""

from __future__ import annotations

import numpy as np
import sounddevice as sd


class MicRecorder:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=self.sample_rate, channels=1, dtype="int16", callback=self._callback
        )
        self._stream.start()

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001 (sd API)
        # Keep the callback cheap: just stash a copy of the frames.
        self._frames.append(indata.copy())

    def stop(self) -> bytes:
        """Stop capture and return the recorded PCM as raw 16-bit little-endian bytes."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if not self._frames:
            return b""
        audio = np.concatenate(self._frames, axis=0)
        self._frames = []
        return audio.tobytes()
