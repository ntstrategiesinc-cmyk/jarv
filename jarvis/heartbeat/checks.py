"""Scheduled checks: each inspects something and decides whether the result is worth surfacing.

A check returns a dict (severity/title/body) when it has something noteworthy, or None when it
doesn't — quiet by default. New check types are added here and enabled in config.toml; the runner
never changes. Checks are read-only: surfacing is the action. (A consequential follow-up would go
through the confirmation gate with source="heartbeat", which safely denies when no human answers.)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from ..config import Config


@dataclass
class CheckContext:
    config: Config
    state_dir: Path


def check_watch_file(cfg: dict, ctx: CheckContext) -> Optional[dict]:
    """Surface (once) when a trigger file exists; the file is consumed so it fires a single item."""
    fname = cfg.get("file", "heartbeat_trigger.txt")
    path = ctx.state_dir / fname
    if not path.exists():
        return None
    try:
        # utf-8-sig so a BOM (e.g. from a file made by PowerShell) is stripped.
        body = path.read_text(encoding="utf-8-sig").strip()[:300]
    except Exception:
        body = ""
    try:
        path.unlink()  # consume so it surfaces once, not every tick
    except OSError:
        pass
    return {
        "severity": cfg.get("severity", "alert"),
        "title": cfg.get("title", f"Trigger file '{fname}' detected"),
        "body": body or "(empty trigger file)",
    }


def check_stale_leads(cfg: dict, ctx: CheckContext) -> Optional[dict]:
    """Surface leads still marked 'new' older than N days — they likely need follow-up."""
    from ..tools.leads import LeadsStore

    store = LeadsStore(ctx.config.leads_workbook_path, ctx.config.leads_sheet_name)
    try:
        leads = store.all()
    except Exception:
        return None
    days = int(cfg.get("older_than_days", 7))
    cutoff = datetime.now() - timedelta(days=days)
    stale: list[str] = []
    for lead in leads:
        if str(lead.get("status", "")).lower() != "new":
            continue
        try:
            created = datetime.fromisoformat(str(lead.get("created_at", "")))
        except ValueError:
            continue
        if created < cutoff:
            stale.append(str(lead.get("name", "?")))
    if not stale:
        return None
    return {
        "severity": cfg.get("severity", "notice"),
        "title": f"{len(stale)} lead(s) need follow-up (new > {days}d)",
        "body": ", ".join(stale),
    }


# Registry: config `type` -> check function.
CHECKS: dict[str, Callable[[dict, CheckContext], Optional[dict]]] = {
    "watch_file": check_watch_file,
    "stale_leads": check_stale_leads,
}


def run_check(cfg: dict, ctx: CheckContext) -> Optional[dict]:
    fn = CHECKS.get(cfg.get("type", ""))
    if fn is None:
        return {"severity": "notice", "title": f"unknown check type '{cfg.get('type')}'", "body": ""}
    try:
        return fn(cfg, ctx)
    except Exception as e:  # a broken check shouldn't kill the loop
        return {"severity": "notice", "title": f"check '{cfg.get('name')}' errored", "body": str(e)[:200]}
