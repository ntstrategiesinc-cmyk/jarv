"""Keyboard-free voice session: press Enter to start recording, Enter again to stop.

A fallback for when pynput can't capture a global hotkey (some terminals/laptops). Same agent
core, same STT/TTS seams as the push-to-talk session — only the "when does a turn start/stop"
mechanism differs. Trade-off: no barge-in (a reply plays to completion before the next turn).
"""

from __future__ import annotations

import sys

from ...config import Config
from ...core.agent import Agent
from ...core.conversation import Conversation
from ..text_repl import make_console_approver
from .mic import MicRecorder
from .player import PcmPlayer
from .stt import SpeechToText
from .tts import TextToSpeech


class EnterVoiceSession:
    def __init__(self, agent: Agent, config: Config, stt: SpeechToText, tts: TextToSpeech, killswitch, audit):
        self.agent = agent
        self.config = config
        self.stt = stt
        self.tts = tts
        self.killswitch = killswitch
        self.audit = audit
        self.mic = MicRecorder(config.stt_sample_rate)
        self.player = PcmPlayer(config.tts_sample_rate)
        self.conversation = Conversation()
        self.name = config.persona_name
        self.approver = make_console_approver(self.name)

    def _speak(self, text: str) -> None:
        if not text or not text.strip():
            return
        try:
            self.player.play(self.tts.synthesize_stream(text))
        except Exception as e:
            print(f"  (tts error: {e})")

    def run(self) -> None:
        def on_text(delta: str) -> None:
            sys.stdout.write(delta)
            sys.stdout.flush()

        print(f"{self.name} — voice mode (keyboard-free).")
        print("Press [Enter] to start talking, [Enter] again to stop. Type q then [Enter] to quit.")
        print("(The text interface — run_text.py — still works.)\n")

        while True:
            try:
                cmd = input("[Enter]=talk   (q=quit) > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nbye.")
                return
            if cmd == "q":
                print("bye.")
                return

            self.mic.start()
            try:
                input("  recording… press [Enter] to stop ")
            except (EOFError, KeyboardInterrupt):
                self.mic.stop()
                print("\nbye.")
                return
            pcm = self.mic.stop()

            try:
                transcript = self.stt.transcribe(pcm)
            except Exception as e:
                print(f"  (stt error: {e})")
                continue
            if not transcript:
                print("  (didn't catch that — speak a bit louder/closer, then stop)")
                continue

            print(f"you (heard) > {transcript}")
            self.conversation.add_user_text(transcript)
            print(f"{self.name.lower()} > ", end="", flush=True)
            reply = self.agent.run_turn(self.conversation, on_text=on_text, source="spoken", approver=self.approver)
            print()
            self._speak(reply)
