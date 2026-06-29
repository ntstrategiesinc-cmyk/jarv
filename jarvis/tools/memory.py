"""Tools that let Jarvis manage its own long-term memory.

Remember/update are low-risk local writes and run freely. Forget deletes data, so it routes
through the confirmation gate. Memory is background knowledge, not a backdoor: a stored fact
never bypasses the gate — consequential actions still require the owner's confirmation.
"""

from __future__ import annotations

from ..config import Config
from ..memory.store import MemoryStore
from .base import Tool, ToolResult


def _ambiguous_message(query: str, matches: list[str]) -> str:
    if not matches:
        return f"Nothing in memory matches '{query}'."
    listed = "; ".join(matches)
    return f"That matches several facts ({listed}). Be more specific about which one."


def build_memory_tools(config: Config, store: MemoryStore) -> list[Tool]:
    def memory_remember(args: dict) -> ToolResult:
        fact = (args.get("fact") or "").strip()
        if not fact:
            return ToolResult.error("Provide the fact to remember.")
        added = store.add(fact)
        return ToolResult.success(f"Saved to memory: {fact}" if added else "Already in memory.")

    def memory_update(args: dict) -> ToolResult:
        find = (args.get("find") or "").strip()
        new_fact = (args.get("new_fact") or "").strip()
        if not find or not new_fact:
            return ToolResult.error("Provide both `find` (which fact) and `new_fact` (the new wording).")
        result = store.update(find, new_fact)
        if isinstance(result, list):
            return ToolResult.error(_ambiguous_message(find, result))
        old, new = result
        return ToolResult.success(f"Updated memory: '{old}' -> '{new}'.")

    def memory_forget(args: dict) -> ToolResult:
        find = (args.get("find") or "").strip()
        if not find:
            return ToolResult.error("Provide a phrase identifying the fact to forget.")
        result = store.remove(find)
        if isinstance(result, list):
            return ToolResult.error(_ambiguous_message(find, result))
        return ToolResult.success(f"Removed from memory: {result}")

    def memory_list(args: dict) -> ToolResult:
        facts = store.facts()
        if not facts:
            return ToolResult.success("Long-term memory is empty.")
        return ToolResult.success("\n".join(f"- {f}" for f in facts))

    return [
        Tool(
            name="memory_remember",
            description=(
                "Save a durable fact about the owner to long-term memory (a preference, an "
                "identity detail, a decision). Use when the owner shares something worth recalling "
                "in future sessions."
            ),
            input_schema={
                "type": "object",
                "properties": {"fact": {"type": "string", "description": "A single, clear statement to remember."}},
                "required": ["fact"],
            },
            handler=memory_remember,
            needs_confirmation=False,
        ),
        Tool(
            name="memory_update",
            description="Revise an existing remembered fact. Give a phrase to locate it and the new wording.",
            input_schema={
                "type": "object",
                "properties": {
                    "find": {"type": "string", "description": "Text identifying the fact to change."},
                    "new_fact": {"type": "string", "description": "The corrected statement."},
                },
                "required": ["find", "new_fact"],
            },
            handler=memory_update,
            needs_confirmation=False,
        ),
        Tool(
            name="memory_forget",
            description="Delete a fact from long-term memory. Give a phrase identifying it. Deletes data.",
            input_schema={
                "type": "object",
                "properties": {"find": {"type": "string", "description": "Text identifying the fact to remove."}},
                "required": ["find"],
            },
            handler=memory_forget,
            needs_confirmation=True,  # deleting data -> confirmation gate
        ),
        Tool(
            name="memory_list",
            description="List everything currently in long-term memory. Read-only.",
            input_schema={"type": "object", "properties": {}},
            handler=memory_list,
            needs_confirmation=False,
        ),
    ]
