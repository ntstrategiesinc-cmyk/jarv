#!/usr/bin/env python
"""Dead-simple speaker test: just makes Jarvis talk. No mic, no keys. If you HEAR a sentence,
your audio output works."""

import os

import numpy as np
import sounddevice as sd

from jarvis.app import force_utf8_console
from jarvis.config import load_config

force_utf8_console()
cfg = load_config()

print("Synthesizing speech... (this takes a second)")
from jarvis.adapters.voice.tts import TextToSpeech

tts = TextToSpeech(os.getenv("ELEVENLABS_API_KEY", ""), cfg.elevenlabs_voice_id,
                   cfg.elevenlabs_model_id, cfg.tts_sample_rate)
pcm = b"".join(tts.synthesize_stream(
    "Hello. This is Jarvis. If you can hear me speaking, your audio is working correctly."))
print(">>> PLAYING NOW — turn up your volume. You should hear a voice. <<<")
sd.play(np.frombuffer(pcm, dtype="int16"), samplerate=cfg.tts_sample_rate)
sd.wait()
print("Done. Did you hear the voice?")
