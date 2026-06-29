"""The inbox — the one durable place surfaced items land.

Persisted to state/inbox.json so a notice raised while the owner's interface is closed is HELD,
not lost — they catch up on it when they return. Every item is dismissible; dismissed items are
kept (marked) for the audit trail but no longer shown as pending.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class Inbox:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _load(self) -> dict:
        if not self.path.exists():
            return {"next_id": 1, "items": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            data.setdefault("next_id", 1)
            data.setdefault("items", [])
            return data
        except Exception:
            return {"next_id": 1, "items": []}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, *, source: str, title: str, body: str = "", severity: str = "notice") -> int:
        data = self._load()
        item_id = data["next_id"]
        data["next_id"] += 1
        data["items"].append({
            "id": item_id,
            "ts": datetime.now().isoformat(timespec="seconds"),
            "source": source,
            "severity": severity,
            "title": title,
            "body": body,
            "dismissed": False,
        })
        self._save(data)
        return item_id

    def pending(self) -> list[dict]:
        return [i for i in self._load()["items"] if not i.get("dismissed")]

    def dismiss(self, item_id) -> int:
        """Dismiss one item by id, or all pending when item_id == 'all'. Returns count dismissed."""
        data = self._load()
        n = 0
        for i in data["items"]:
            if not i.get("dismissed") and (item_id == "all" or i["id"] == item_id):
                i["dismissed"] = True
                n += 1
        if n:
            self._save(data)
        return n
