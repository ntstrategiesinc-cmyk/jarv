"""The TTS SEAM (ElevenLabs).

One responsibility: give me text -> get a stream of raw PCM chunks to play. We request
output_format="pcm_<rate>" and play the bytes ourselves via sounddevice, deliberately avoiding the
SDK's play()/stream() helper (which shells out to mpv/ffmpeg — the #1 Windows first-voice break).
Because ElevenLabs streams, playback can start before the whole sentence is synthesized.
"""

from __future__ import annotations

from typing import Iterator

from elevenlabs import ElevenLabs


class TextToSpeech:
    def __init__(self, api_key: str, voice_id: str, model_id: str = "eleven_flash_v2_5", sample_rate: int = 24000):
        self._client = ElevenLabs(api_key=api_key)
        self.voice_id = voice_id
        self.model_id = model_id
        self.sample_rate = sample_rate

    def synthesize_stream(self, text: str) -> Iterator[bytes]:
        """Yield raw little-endian 16-bit PCM chunks at self.sample_rate (for desktop playback)."""
        return self._client.text_to_speech.stream(
            self.voice_id,
            text=text,
            model_id=self.model_id,
            output_format=f"pcm_{self.sample_rate}",
        )

    def synthesize_mp3(self, text: str) -> bytes:
        """Return the whole reply as MP3 bytes — what a browser <audio> element can play directly."""
        chunks = self._client.text_to_speech.convert(
            self.voice_id, text=text, model_id=self.model_id, output_format="mp3_44100_128"
        )
        return b"".join(chunks)
