"""The push-to-talk voice session.

Wraps the existing agent core; it does NOT reimplement it. A spoken turn is: hold the key (record)
-> release (transcribe) -> feed the text into the SAME Agent.run_turn() the text REPL uses -> speak
the reply. Barge-in: press the key again while Jarvis is talking and playback stops so it listens.
The transcript is printed next to the reply so you can see what was heard.
"""

from __future__ import annotations

import queue
import sys
import threading

from pynput import keyboard

from ...config import Config
from ...core.agent import Agent
from ...core.conversation import Conversation
from .mic import MicRecorder
from .player import PcmPlayer
from .stt import SpeechToText
from .tts import TextToSpeech


def _resolve_key(name: str):
    return getattr(keyboard.Key, (name or "f9").lower(), keyboard.Key.f9)


class VoiceSession:
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
        self.ptt_key = _resolve_key(config.push_to_talk_key)
        self._recording = False
        self._busy = False
        self._queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()

    # --- key callbacks (kept cheap; heavy work happens in the worker) ---
    def _on_press(self, key):
        if key == keyboard.Key.esc:
            self._stop.set()
            self._queue.put(None)
            self.player.stop()
            return False  # stops the listener
        if key == self.ptt_key and not self._recording:
            if self._busy:
                self.player.stop()  # barge-in: cut off speech to listen
            self._recording = True
            self.mic.start()
            sys.stdout.write("\n[listening… release to send]\n")
            sys.stdout.flush()

    def _on_release(self, key):
        if key == self.ptt_key and self._recording:
            self._recording = False
            self._queue.put(self.mic.stop())

    # --- confirmation in voice mode: speak + print, read y/n from the console ---
    def _approver(self, tool, tool_input: dict, source: str = "spoken", timeout=None) -> bool:
        print(f"\n  [confirm] {self.name} wants to run '{tool.name}':")
        for k, v in tool_input.items():
            if v not in (None, "", []):
                print(f"      {k}: {v}")
        self._speak(f"I'm about to run {tool.name}. Type yes to confirm.")
        try:
            answer = input("  allow? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return answer in {"y", "yes"}

    def _speak(self, text: str) -> None:
        if not text or not text.strip():
            return
        try:
            self.player.play(self.tts.synthesize_stream(text))
        except Exception as e:
            print(f"  (tts error: {e})")

    def _worker(self) -> None:
        def on_text(delta: str) -> None:
            sys.stdout.write(delta)
            sys.stdout.flush()

        while not self._stop.is_set():
            pcm = self._queue.get()
            if pcm is None:
                return
            self._busy = True
            try:
                transcript = self.stt.transcribe(pcm)
            except Exception as e:
                print(f"  (stt error: {e})")
                self._busy = False
                continue
            if not transcript:
                print("  (didn't catch that — hold the key, speak, then release)")
                self._busy = False
                continue

            print(f"\nyou (heard) > {transcript}")
            self.conversation.add_user_text(transcript)
            print(f"{self.name.lower()} > ", end="", flush=True)
            reply = self.agent.run_turn(self.conversation, on_text=on_text, source="spoken", approver=self._approver)
            print()
            self._speak(reply)
            self._busy = False

    def run(self) -> None:
        keyname = self.config.push_to_talk_key.upper()
        print(f"{self.name} — voice mode.")
        print(f"Hold [{keyname}] to talk, release to send. Press [ESC] to quit.")
        print("(The text interface — run_text.py — still works for typing.)\n")

        worker = threading.Thread(target=self._worker, daemon=True)
        worker.start()
        with keyboard.Listener(on_press=self._on_press, on_release=self._on_release) as listener:
            listener.join()
        self._stop.set()
        self._queue.put(None)
        print("\nbye.")
