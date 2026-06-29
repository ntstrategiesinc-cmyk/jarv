"""Quiet hours: non-urgent surfacing waits for waking hours.

Only something truly critical should interrupt late at night; everything else is held quietly in
the inbox until quiet hours end. The window is a setting (config.toml), and may cross midnight.
"""

from __future__ import annotations

from datetime import datetime, time


def _parse(hhmm: str) -> time:
    try:
        h, m = hhmm.split(":")
        return time(int(h), int(m))
    except Exception:
        return time(0, 0)


def is_quiet_now(start_hhmm: str, end_hhmm: str, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    start, end = _parse(start_hhmm), _parse(end_hhmm)
    t = now.time()
    if start == end:
        return False  # no quiet window
    if start < end:
        return start <= t < end
    # window crosses midnight (e.g. 22:00 -> 08:00)
    return t >= start or t < end
