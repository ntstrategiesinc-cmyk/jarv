#!/usr/bin/env python
"""Voice diagnostic — tests each stage of the voice pipeline separately so we can see exactly
where it breaks. Run:  .\.venv\\Scripts\\python.exe diagnose_voice.py
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
import sounddevice as sd

from jarvis.app import force_utf8_console
from jarvis.config import load_config

force_utf8_console()
cfg = load_config()


def hr(title):
    print("\n" + "=" * 60 + f"\n{title}\n" + "=" * 60)


# --- devices ---
hr("0) Audio devices")
print("default (input, output) indices:", sd.default.device)
try:
    di, do = sd.default.device
    print("input :", sd.query_devices(di)["name"])
    print("output:", sd.query_devices(do)["name"])
except Exception as e:
    print("device query error:", e)

# --- 1) TTS + playback ---
hr("1) SPEAKER TEST — you should HEAR Jarvis speak")
try:
    from jarvis.adapters.voice.tts import TextToSpeech
    tts = TextToSpeech(os.getenv("ELEVENLABS_API_KEY", ""), cfg.elevenlabs_voice_id,
                       cfg.elevenlabs_model_id, cfg.tts_sample_rate)
    pcm = b"".join(tts.synthesize_stream("If you can hear this, the speaker output is working."))
    print(f"synthesized {len(pcm)} bytes; playing now...")
    arr = np.frombuffer(pcm, dtype="int16")
    sd.play(arr, samplerate=cfg.tts_sample_rate); sd.wait()
    print(">> Did you HEAR that sentence? (if no sound: check Windows volume / output device)")
except Exception as e:
    print("TTS/playback ERROR:", type(e).__name__, e)

# --- 2) Mic + STT ---
hr("2) MIC TEST — speak for 3 seconds after the prompt")
try:
    from jarvis.adapters.voice.stt import SpeechToText
    stt = SpeechToText(os.getenv("DEEPGRAM_API_KEY", ""), cfg.deepgram_model, cfg.stt_sample_rate)
    for i in (3, 2, 1):
        print(f"  recording in {i}...", end="\r"); time.sleep(0.6)
    print("  >>> SPEAK NOW (3s): say 'testing one two three'        ")
    rec = sd.rec(int(cfg.stt_sample_rate * 3), samplerate=cfg.stt_sample_rate, channels=1, dtype="int16")
    sd.wait()
    level = int(np.abs(rec).mean())
    print(f"  captured, mean input level = {level}  (0 = silence/mic blocked; >50 = good)")
    heard = stt.transcribe(rec.tobytes())
    print(f"  Deepgram heard: {heard!r}")
    if level == 0:
        print("  !! Mic level 0 -> Windows mic privacy is likely blocking it. See note below.")
except Exception as e:
    print("Mic/STT ERROR:", type(e).__name__, e)

# --- 3) push-to-talk key: log EVERY key so we see what your F9 actually emits ---
hr("3) KEY TEST (12s) — press your intended talk key (try F9), then a couple of normal keys")
print(f"  configured key: {cfg.push_to_talk_key.upper()} "
      f"(resolves to: {getattr(__import__('pynput').keyboard.Key, cfg.push_to_talk_key.lower(), 'UNKNOWN')})")
print("  Press F9 a few times. Then press, say, the SPACEBAR and the letter J so we have a baseline.")
print("  (If NOTHING shows when you press ANY key, pynput is blocked entirely.)\n")
try:
    from pynput import keyboard
    events = []

    def on_press(k):
        name = getattr(k, "name", None) or getattr(k, "char", None) or str(k)
        events.append(name)
        print(f"  key pressed -> {name!r}")

    lis = keyboard.Listener(on_press=on_press)
    lis.start(); time.sleep(12); lis.stop()
    print(f"\n  total key events seen: {len(events)}")
    if not events:
        print("  !! No keys detected at all — pynput's listener isn't receiving input in this setup.")
    else:
        uniq = sorted(set(events))
        print("  distinct keys seen:", uniq)
        print("  >> Tell me which name appeared when you pressed your intended talk key;")
        print("     we'll set push_to_talk_key to a key that actually comes through.")
except Exception as e:
    print("Key test ERROR:", type(e).__name__, e)

hr("Done")
print("Tell me: (1) heard the sentence? (2) the mic level + what Deepgram heard, (3) key events seen?")
