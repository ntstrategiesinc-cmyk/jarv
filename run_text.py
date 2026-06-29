#!/usr/bin/env python
"""Tier 1/2/4/6 entry point: talk to Jarvis by typing.

    python run_text.py

Requires ANTHROPIC_API_KEY in .env (copy .env.example to .env first).
"""

from __future__ import annotations

import os
import sys

from jarvis.config import load_config
from jarvis.core.agent import Agent
from jarvis.core.provider import ModelProvider
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.leads import build_leads_tools
from jarvis.tools.social import build_social_tools
from jarvis.adapters.text_repl import run_repl


def build_registry(config) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register_all(build_leads_tools(config))
    registry.register_all(build_social_tools(config))
    return registry


def _force_utf8_console() -> None:
    """Windows consoles default to cp1252; streamed model output (em-dashes, smart quotes,
    emoji) would raise UnicodeEncodeError and crash mid-reply. Force UTF-8 on the streams."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main() -> int:
    _force_utf8_console()
    config = load_config()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.")
        return 1

    provider = ModelProvider(
        api_key=api_key,
        model=config.model_name,
        max_tokens=config.max_tokens,
    )
    agent = Agent(provider, config, registry=build_registry(config))
    run_repl(agent, config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
