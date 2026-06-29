"""The STT SEAM (Deepgram).

One responsibility: give me audio (raw 16-bit mono PCM) -> get back text. The mic PCM is wrapped
in a WAV container so Deepgram reads the sample rate/encoding from the header (the v7
transcribe_file has no sample_rate parameter). Swap the vendor by replacing this class; the voice
session only knows transcribe().
"""

from __future__ import annotations

import io
import wave

from deepgram import DeepgramClient


class SpeechToText:
    def __init__(self, api_key: str, model: str = "nova-3", sample_rate: int = 16000):
        self._client = DeepgramClient(api_key=api_key)
        self.model = model
        self.sample_rate = sample_rate

    def _to_wav(self, pcm: bytes) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)  # 16-bit
            w.setframerate(self.sample_rate)
            w.writeframes(pcm)
        return buf.getvalue()

    def transcribe(self, pcm: bytes) -> str:
        """Transcribe raw 16-bit mono PCM (from the desktop mic) by wrapping it in a WAV."""
        if not pcm:
            return ""
        resp = self._client.listen.v1.media.transcribe_file(
            request=self._to_wav(pcm), model=self.model, smart_format=True, punctuate=True, language="en"
        )
        return self._parse(resp)

    def transcribe_audio(self, data: bytes) -> str:
        """Transcribe a containerized audio file (webm/opus, mp3, wav, ...) as sent by a browser.
        Deepgram detects the container, so no encoding/sample_rate is needed."""
        if not data:
            return ""
        resp = self._client.listen.v1.media.transcribe_file(
            request=data, model=self.model, smart_format=True, punctuate=True, language="en"
        )
        return self._parse(resp)

    @staticmethod
    def _parse(resp) -> str:
        # Standard Deepgram shape: results.channels[0].alternatives[0].transcript.
        try:
            return (resp.results.channels[0].alternatives[0].transcript or "").strip()
        except (AttributeError, IndexError, TypeError):
            data = resp.model_dump() if hasattr(resp, "model_dump") else {}
            try:
                return (data["results"]["channels"][0]["alternatives"][0]["transcript"] or "").strip()
            except (KeyError, IndexError, TypeError):
                return ""
