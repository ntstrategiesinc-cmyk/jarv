"""Build the system prompt: who Jarvis is, how it sounds, and (later) what it knows.

Tier 1 carries identity + tone. Tier 4 appends durable memory facts here, and Tier 6
appends the safety posture. Keeping this in one place means the persona stays consistent
across text, voice, and heartbeat.
"""

from __future__ import annotations

from typing import Optional

from ..config import Config


def build_system_prompt(config: Config, memory_facts: Optional[list[str]] = None) -> str:
    name = config.persona_name
    tone = config.persona_tone

    lines = [
        f"You are {name}, a voice-first personal AI assistant for a single owner.",
        f"Tone: {tone}" if tone else "Tone: crisp and professional.",
        "Replies may be read aloud by text-to-speech, so keep them concise and direct;",
        "avoid markdown, long lists, and filler. Get to the point.",
    ]
    # Tier 4 will insert memory_facts here; Tier 6 will insert the safety posture.
    return "\n".join(lines)
