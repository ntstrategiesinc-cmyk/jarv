#!/usr/bin/env python
"""Tier 3 entry point: talk to Jarvis by voice (push-to-talk).

    python run_voice.py

Wraps the SAME agent core as run_text.py. Requires ANTHROPIC_API_KEY, DEEPGRAM_API_KEY, and
ELEVENLABS_API_KEY in .env, plus voice.elevenlabs_voice_id in config.toml. The text interface
stays available — run_text.py is untouched.
"""

from __future__ import annotations

import sys

from jarvis.app import build_core, force_utf8_console, missing_env
from jarvis.config import load_config


def main() -> int:
    force_utf8_console()
    config = load_config()

    missing = missing_env(["ANTHROPIC_API_KEY", "DEEPGRAM_API_KEY", "ELEVENLABS_API_KEY"])
    if missing:
        print(f"Missing in .env: {', '.join(missing)}. Voice needs all three. See .env.example.")
        return 1
    if not config.elevenlabs_voice_id:
        print("Set voice.elevenlabs_voice_id in config.toml to your chosen ElevenLabs voice id.")
        return 1

    core = build_core(config)

    # Import voice deps lazily so the text path never depends on audio libraries being importable.
    import os

    from jarvis.adapters.voice.stt import SpeechToText
    from jarvis.adapters.voice.tts import TextToSpeech

    stt = SpeechToText(os.getenv("DEEPGRAM_API_KEY", ""), config.deepgram_model, config.stt_sample_rate)
    tts = TextToSpeech(
        os.getenv("ELEVENLABS_API_KEY", ""),
        config.elevenlabs_voice_id,
        config.elevenlabs_model_id,
        config.tts_sample_rate,
    )

    # Pick the input mechanism. "enter" needs no global hotkey (most reliable); "ptt" holds a key.
    if config.voice_input_mode == "ptt":
        from jarvis.adapters.voice.session import VoiceSession
        session = VoiceSession(core.agent, config, stt, tts, core.killswitch, core.audit)
    else:
        from jarvis.adapters.voice.console_session import EnterVoiceSession
        session = EnterVoiceSession(core.agent, config, stt, tts, core.killswitch, core.audit)
    session.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
