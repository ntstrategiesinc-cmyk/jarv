"""Tool + ToolResult: the shape every capability shares.

A ToolResult is what flows BACK to the model — success or a plain-language error. A tool that
fails returns ToolResult.error(...) so the model can reason over the failure and explain it,
rather than the harness crashing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class ToolResult:
    ok: bool
    content: str  # readable text fed back to the model (result or error)

    @classmethod
    def success(cls, content: str) -> "ToolResult":
        return cls(True, content)

    @classmethod
    def error(cls, content: str) -> "ToolResult":
        return cls(False, content)


@dataclass
class Tool:
    name: str
    description: str  # written for the model to read — say when to use it
    input_schema: dict  # JSON Schema; typed, named, validated inputs
    handler: Callable[[dict], ToolResult]
    # Consequential tools (send/post/spend/delete/change-a-setting) default to True.
    # Tier 6's gate also consults config.toml so this can be tuned without code edits.
    needs_confirmation: bool = False
    # True when the tool surfaces content from outside this conversation (stored notes, files,
    # web pages). Tier 6 fences such output as untrusted data to blunt prompt injection.
    returns_external_content: bool = False

    def to_api(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
