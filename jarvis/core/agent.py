"""The agent core — the ONE brain every entry path flows through.

Tier 1: a single model call per turn (no tools). Tier 2 extends run_turn() into a tool loop
that drives multiple sequential tool calls, with the Tier 6 confirmation gate sitting between
the model choosing a tool and the tool running. Text, voice, and heartbeat all call run_turn();
none of them reimplements this logic.
"""

from __future__ import annotations

from typing import Callable, Optional

from ..config import Config
from .conversation import Conversation
from .provider import ModelProvider
from .system_prompt import build_system_prompt


class Agent:
    def __init__(self, provider: ModelProvider, config: Config):
        self.provider = provider
        self.config = config

    def run_turn(
        self,
        conversation: Conversation,
        on_text: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Run one turn: send history to the model, stream the reply, record it. Returns
        the assistant's text (also useful to non-text callers like voice)."""
        system = build_system_prompt(self.config)
        result = self.provider.send(
            system=system,
            messages=conversation.to_api(),
            tools=[],
            on_text=on_text,
        )

        if result.error:
            # Degrade calmly: surface the problem, don't poison history with a failed turn.
            msg = f"(I couldn't complete that — {result.error}. Try again?)"
            if on_text:
                on_text(msg)
            return msg

        conversation.add_assistant_text(result.text)
        return result.text
