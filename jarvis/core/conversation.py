"""Short-term memory: the running list of turns in one session.

The Anthropic API is stateless, so we hold the history and pass it back every turn. This is
distinct from long-term memory (Tier 4), which survives restarts. Content is stored in the
API's message shape so tool_use / tool_result blocks (Tier 2) slot in without reshaping.
"""

from __future__ import annotations


class Conversation:
    def __init__(self) -> None:
        self._messages: list[dict] = []

    def add_user_text(self, text: str) -> None:
        self._messages.append({"role": "user", "content": text})

    def add_assistant_text(self, text: str) -> None:
        self._messages.append({"role": "assistant", "content": text})

    def add_assistant_blocks(self, blocks: list[dict]) -> None:
        """Append a full assistant turn (text and/or tool_use blocks). Used by Tier 2."""
        self._messages.append({"role": "assistant", "content": blocks})

    def add_tool_results(self, results: list[dict]) -> None:
        """Append tool_result blocks as a user turn so the model can react. Used by Tier 2."""
        self._messages.append({"role": "user", "content": results})

    def to_api(self) -> list[dict]:
        return list(self._messages)

    def __len__(self) -> int:
        return len(self._messages)
