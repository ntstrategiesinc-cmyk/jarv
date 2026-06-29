#!/usr/bin/env python
"""Dead-simple mic test: records you for 4 seconds, shows how loud it heard you, and what
Deepgram transcribed. No keys."""

import os
import time

import numpy as np
import sounddevice as sd

from jarvis.app import force_utf8_console
from jarvis.config import load_config

force_utf8_console()
cfg = load_config()

print("Input device Windows will use:", end=" ")
try:
    print(sd.query_devices(sd.default.device[0])["name"])
except Exception as e:
    print("(could not read)", e)

print("\nGet ready to speak. Recording starts in:")
for i in (3, 2, 1):
    print(f"   {i}...")
    time.sleep(1)
print(">>> SPEAK NOW for 4 seconds — say: 'testing one two three' <<<")

rec = sd.rec(int(cfg.stt_sample_rate * 4), samplerate=cfg.stt_sample_rate, channels=1, dtype="int16")
sd.wait()
print("...done recording.\n")

level = int(np.abs(rec).mean())
peak = int(np.abs(rec).max())
print(f"Microphone level: average={level}, peak={peak}")
if level == 0:
    print("  -> Level is 0 = the mic gave pure silence. Windows is blocking it or using the")
    print("     wrong input device. (Settings > Privacy > Microphone, or pick the right mic.)")
else:
    print("  -> Good, the mic captured sound.")

print("\nSending to Deepgram to transcribe...")
from jarvis.adapters.voice.stt import SpeechToText

stt = SpeechToText(os.getenv("DEEPGRAM_API_KEY", ""), cfg.deepgram_model, cfg.stt_sample_rate)
heard = stt.transcribe(rec.tobytes())
print(f"\nDeepgram heard:  {heard!r}")
print("\nTell me: the mic level numbers above, and what Deepgram heard.")
