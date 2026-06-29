"""A plain, append-only audit log + running model-cost tally.

Every model call (tokens/cost), every confirmation decision, and every tool run is recorded as
one JSON line in state/audit.log. When something surprises you, this is how you find out what
happened — and a runaway loop shows up immediately as climbing cost.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class AuditLog:
    def __init__(self, path: Path, input_price_per_mtok: float = 0.0, output_price_per_mtok: float = 0.0):
        self.path = Path(path)
        self.input_price = input_price_per_mtok
        self.output_price = output_price_per_mtok
        self.session_cost_usd = 0.0
        self.session_input_tokens = 0
        self.session_output_tokens = 0

    def _write(self, record: dict) -> None:
        record = {"ts": datetime.now().isoformat(timespec="seconds"), **record}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def record_usage(self, input_tokens: int, output_tokens: int) -> None:
        self.session_input_tokens += input_tokens
        self.session_output_tokens += output_tokens
        cost = (input_tokens / 1_000_000) * self.input_price + (output_tokens / 1_000_000) * self.output_price
        self.session_cost_usd += cost
        self._write({
            "kind": "usage",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 6),
            "session_cost_usd": round(self.session_cost_usd, 6),
        })

    def record_decision(self, tool: str, source: str, decision: str, tool_input: Optional[dict] = None) -> None:
        self._write({"kind": "confirmation", "tool": tool, "source": source, "decision": decision, "input": tool_input})

    def record_tool_run(self, tool: str, source: str, ok: bool) -> None:
        self._write({"kind": "tool_run", "tool": tool, "source": source, "ok": ok})

    def record_event(self, event: str, **fields) -> None:
        self._write({"kind": "event", "event": event, **fields})

    def tail(self, n: int = 10) -> list[str]:
        if not self.path.exists():
            return []
        return self.path.read_text(encoding="utf-8").splitlines()[-n:]
