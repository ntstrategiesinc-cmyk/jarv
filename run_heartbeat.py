#!/usr/bin/env python
"""Tier 5 entry point: the proactive heartbeat loop.

    python run_heartbeat.py

Runs separately from the conversation (own process, relocatable to an always-on host later). It
needs no API keys for the built-in checks — it surfaces items into the shared inbox, which the
text interface shows via /inbox. Stop with Ctrl-C.
"""

from __future__ import annotations

import sys

from jarvis.app import force_utf8_console
from jarvis.config import load_config
from jarvis.heartbeat.inbox import Inbox
from jarvis.heartbeat.runner import HeartbeatRunner
from jarvis.rails.audit import AuditLog
from jarvis.rails.killswitch import KillSwitch


def main() -> int:
    force_utf8_console()
    config = load_config()

    killswitch = KillSwitch(config.state_dir / "killswitch.json")
    audit = AuditLog(
        config.state_dir / "audit.log",
        input_price_per_mtok=config.input_price_per_mtok,
        output_price_per_mtok=config.output_price_per_mtok,
    )
    inbox = Inbox(config.state_dir / "inbox.json")

    HeartbeatRunner(config, inbox, killswitch, audit).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
