"""The heartbeat runner: an APScheduler loop that wakes on an interval and runs due checks.

Discipline baked in:
- Persisted next-due times (state/next_due.json) so a restart resumes the schedule instead of
  refiring everything at once.
- One tick job with max_instances=1 + coalesce, so slow checks don't stack and a wake-from-sleep
  backlog collapses into a single catch-up tick.
- Kill-switch aware: while paused, ticks do nothing (proactive behavior halts).
- Quiet hours: "alert" items only interrupt outside quiet hours; everything is still held in the
  inbox to catch up on later.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from ..config import Config
from ..rails.audit import AuditLog
from ..rails.killswitch import KillSwitch
from .checks import CheckContext, run_check
from .inbox import Inbox
from .quiet_hours import is_quiet_now


class HeartbeatRunner:
    def __init__(self, config: Config, inbox: Inbox, killswitch: KillSwitch, audit: AuditLog):
        self.config = config
        self.inbox = inbox
        self.killswitch = killswitch
        self.audit = audit
        self.next_due_path = config.state_dir / "next_due.json"
        self.ctx = CheckContext(config=config, state_dir=config.state_dir)
        self.name = config.persona_name

    # --- durable schedule ---
    def _load_next_due(self) -> dict:
        if not self.next_due_path.exists():
            return {}
        try:
            return json.loads(self.next_due_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_next_due(self, data: dict) -> None:
        self.next_due_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # --- one wake-up ---
    def tick(self) -> None:
        if self.killswitch.is_paused():
            return  # proactive behavior halted; conversation still works elsewhere

        now = time.time()
        next_due = self._load_next_due()
        for check in self.config.heartbeat_checks:
            if not check.get("enabled"):
                continue
            name = check.get("name", check.get("type", "unnamed"))
            if now < next_due.get(name, 0.0):
                continue  # not due yet
            item = run_check(check, self.ctx)
            # Reschedule once even if it surfaced nothing (coalesce: at most one run per due time).
            next_due[name] = now + max(1, int(check.get("every_minutes", 60))) * 60
            if item:
                self._surface(name, item)
        self._save_next_due(next_due)

    def _surface(self, source: str, item: dict) -> None:
        severity = item.get("severity", "notice")
        title = item.get("title", "(untitled)")
        body = item.get("body", "")
        # Always hold it in the durable inbox so nothing is lost.
        item_id = self.inbox.add(source=source, title=title, body=body, severity=severity)
        self.audit.record_event("heartbeat_surface", source=source, severity=severity, title=title, id=item_id)

        quiet = is_quiet_now(self.config.quiet_hours_start, self.config.quiet_hours_end)
        if severity == "alert" and not quiet:
            print(f"\n[heartbeat] {title}" + (f" — {body}" if body else ""))
            print(f"  (inbox #{item_id}; view with /inbox in run_text.py)")
        elif severity == "alert" and quiet:
            print(f"\n[heartbeat] held until morning (quiet hours): {title} (inbox #{item_id})")
        # "notice" severity stays silent — it just waits in the inbox.

    def run(self) -> None:
        pending = self.inbox.pending()
        print(f"{self.name} heartbeat — tick every {self.config.heartbeat_tick_seconds}s. Ctrl-C to stop.")
        print(f"{len(pending)} item(s) already waiting in the inbox.")
        if self.killswitch.is_paused():
            print("(proactive behavior is PAUSED via the kill switch)")

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            self.tick,
            "interval",
            seconds=self.config.heartbeat_tick_seconds,
            id="heartbeat-tick",
            max_instances=1,           # don't stack overlapping runs
            coalesce=True,             # collapse missed runs into one
            misfire_grace_time=self.config.heartbeat_misfire_seconds,
        )
        scheduler.start()
        self.tick()  # immediate catch-up tick so restarts surface due items without waiting

        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown(wait=False)
            print("\nheartbeat stopped.")
