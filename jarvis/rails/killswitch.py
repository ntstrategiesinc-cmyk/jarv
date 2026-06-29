"""The kill switch: one obvious way to pause all proactive behavior at once.

Backed by a state file so it survives restarts. The heartbeat (Tier 5) checks is_paused() before
acting, and the gate denies any heartbeat-initiated consequential action while paused — but you
can still talk to Jarvis in text/voice. You want this the first time it does something unexpected.
"""

from __future__ import annotations

import json
from pathlib import Path


class KillSwitch:
    def __init__(self, path: Path):
        self.path = Path(path)

    def is_paused(self) -> bool:
        if not self.path.exists():
            return False
        try:
            return bool(json.loads(self.path.read_text(encoding="utf-8")).get("paused", False))
        except Exception:
            return False

    def pause(self) -> None:
        self._set(True)

    def resume(self) -> None:
        self._set(False)

    def _set(self, value: bool) -> None:
        self.path.write_text(json.dumps({"paused": value}), encoding="utf-8")
