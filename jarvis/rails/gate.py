"""The confirmation gate — the ONE place a consequential action is approved or denied.

The agent calls gate.decide() between the model choosing a tool and the tool running, so the
same check covers typed, spoken, and heartbeat-initiated actions. It honors the kill switch,
the config-driven confirmation list, per-action approval (never generalizes), and the heartbeat
approval timeout (so a background action can't block forever waiting on a human).
"""

from __future__ import annotations

from typing import Callable, Optional

from ..config import Config
from .audit import AuditLog
from .killswitch import KillSwitch

Approver = Callable[..., bool]


class ConfirmationGate:
    def __init__(self, config: Config, killswitch: KillSwitch, audit: AuditLog):
        self.config = config
        self.killswitch = killswitch
        self.audit = audit

    def needs_confirmation(self, tool) -> bool:
        # config.toml's list wins (tunable without code); else the tool's own default.
        if tool.name in self.config.confirm_tools:
            return True
        return tool.needs_confirmation

    def decide(self, tool, tool_input: dict, source: str, approver: Optional[Approver]) -> bool:
        # Kill switch halts proactive (heartbeat) actions outright; conversation still works.
        if source == "heartbeat" and self.killswitch.is_paused():
            self.audit.record_decision(tool.name, source, "denied-killswitch", tool_input)
            return False

        if not self.needs_confirmation(tool):
            return True  # read-only / safe tools flow freely

        if approver is None:
            decision = False  # no one to ask -> safe default is deny
        else:
            # Heartbeat approvals time out to a safe default; typed/spoken wait for the human.
            timeout = self.config.confirm_timeout_seconds if source == "heartbeat" else None
            try:
                decision = bool(approver(tool, tool_input, source=source, timeout=timeout))
            except Exception:
                decision = False

        self.audit.record_decision(tool.name, source, "allowed" if decision else "denied", tool_input)
        return decision
