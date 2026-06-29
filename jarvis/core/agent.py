"""The agent core — the ONE brain every entry path flows through.

run_turn() drives a tool loop: the model may call several tools in a row before it's ready to
answer. Each tool call passes through _run_tool(), where consequential tools hit the
confirmation hook BEFORE running. Text, voice, and heartbeat all call run_turn() with their own
`approver` and `source`; none reimplements this logic.

Tier 2 wires a minimal confirmation hook (per-tool flag + approver callback). Tier 6 enriches
the same single point with the config-driven list, audit log, kill switch, sanitization, and the
heartbeat approval timeout — without moving where the check lives.
"""

from __future__ import annotations

from typing import Callable, Optional

from ..config import Config
from .conversation import Conversation
from .provider import ModelProvider, ToolCall
from .system_prompt import build_system_prompt

# An approver decides a single consequential action: (tool, tool_input) -> allow?
Approver = Callable[..., bool]


class Agent:
    def __init__(self, provider: ModelProvider, config: Config, registry=None):
        self.provider = provider
        self.config = config
        self.registry = registry

    def run_turn(
        self,
        conversation: Conversation,
        on_text: Optional[Callable[[str], None]] = None,
        source: str = "typed",
        approver: Optional[Approver] = None,
    ) -> str:
        """Run one turn to completion, including any number of tool calls. Returns the
        assistant's final text."""
        system = build_system_prompt(self.config)
        tools = self.registry.to_api() if self.registry else []

        while True:
            result = self.provider.send(
                system=system,
                messages=conversation.to_api(),
                tools=tools,
                on_text=on_text,
            )

            if result.error:
                msg = f"(I couldn't complete that — {result.error}. Try again?)"
                if on_text:
                    on_text(msg)
                return msg

            if not result.tool_calls:
                conversation.add_assistant_text(result.text)
                return result.text

            # The model wants tools. Record its turn (text + tool_use), run them, feed results back.
            assistant_blocks: list[dict] = []
            if result.text:
                assistant_blocks.append({"type": "text", "text": result.text})
            for tc in result.tool_calls:
                assistant_blocks.append(
                    {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input}
                )
            conversation.add_assistant_blocks(assistant_blocks)

            tool_results = [self._run_tool(tc, source, approver) for tc in result.tool_calls]
            conversation.add_tool_results(tool_results)
            # Loop: let the model react to the tool results (it may call more tools or answer).

    def _run_tool(self, tc: ToolCall, source: str, approver: Optional[Approver]) -> dict:
        """Run one tool call and return a tool_result block. Failures come back to the model
        as plain-language errors, never as crashes."""
        tool = self.registry.get(tc.name) if self.registry else None
        if tool is None:
            return self._result_block(tc.id, f"No such tool: '{tc.name}'.", is_error=True)

        if self._needs_confirmation(tool):
            allowed = self._confirm(tool, tc.input, source, approver)
            if not allowed:
                return self._result_block(
                    tc.id,
                    "The user did not approve this action, so it was not run. Do not retry it; "
                    "acknowledge and move on.",
                    is_error=False,
                )

        try:
            res = tool.handler(tc.input)
        except Exception as e:  # last-resort guard; tools should return ToolResult.error themselves
            return self._result_block(tc.id, f"{tc.name} failed unexpectedly: {e}", is_error=True)
        return self._result_block(tc.id, res.content, is_error=not res.ok)

    def _needs_confirmation(self, tool) -> bool:
        """Tier 2: the tool's own flag. Tier 6 also honors config.toml's needs_confirmation list."""
        if tool.name in self.config.confirm_tools:
            return True
        return tool.needs_confirmation

    def _confirm(self, tool, tool_input: dict, source: str, approver: Optional[Approver]) -> bool:
        """The single confirmation point. With no approver wired, default to DENY (safe)."""
        if approver is None:
            return False
        return bool(approver(tool, tool_input, source=source))

    @staticmethod
    def _result_block(tool_use_id: str, content: str, is_error: bool) -> dict:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": content,
            "is_error": is_error,
        }
