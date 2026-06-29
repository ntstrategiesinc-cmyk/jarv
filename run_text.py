#!/usr/bin/env python
"""Tier 1/2/4/6 entry point: talk to Jarvis by typing.

    python run_text.py

Requires ANTHROPIC_API_KEY in .env (copy .env.example to .env first).
"""

from __future__ import annotations

import sys

from jarvis.app import build_core, force_utf8_console, missing_env
from jarvis.config import load_config
from jarvis.adapters.text_repl import run_repl


def main() -> int:
    force_utf8_console()
    config = load_config()

    missing = missing_env(["ANTHROPIC_API_KEY"])
    if missing:
        print(f"Missing in .env: {', '.join(missing)}. Copy .env.example to .env and fill it in.")
        return 1

    core = build_core(config)
    run_repl(core.agent, core.config, core.killswitch, core.audit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
