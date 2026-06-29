"""The long-term memory store: one durable fact per line in a plain markdown file.

Small, legible entries are easy to review, correct, and delete — a giant blob rots and can't be
audited. The file is loaded into the system prompt at the start of each turn, so Jarvis walks in
already knowing these facts. Edits made by hand are picked up on the next turn.
"""

from __future__ import annotations

from pathlib import Path

_HEADER = (
    "# Jarvis long-term memory\n"
    "# One durable fact per line (preferences, identity, decisions). Edit or delete freely.\n"
    "# Lines starting with '#' are comments.\n\n"
)


class MemoryStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def facts(self) -> list[str]:
        if not self.path.exists():
            return []
        out: list[str] = []
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("- "):
                line = line[2:].strip()
            if line:
                out.append(line)
        return out

    def _save(self, facts: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(f"- {f}" for f in facts)
        self.path.write_text(_HEADER + body + ("\n" if facts else ""), encoding="utf-8")

    def add(self, fact: str) -> bool:
        """Append a fact. Returns False if an identical one already exists."""
        fact = fact.strip()
        facts = self.facts()
        if any(f.lower() == fact.lower() for f in facts):
            return False
        facts.append(fact)
        self._save(facts)
        return True

    def find(self, query: str) -> list[str]:
        q = query.strip().lower()
        return [f for f in self.facts() if q in f.lower()]

    def remove(self, query: str):
        """Remove the single fact matching `query`. Returns the removed fact, or a list of
        candidates when the match is ambiguous (0 or >1) so the caller can clarify."""
        matches = self.find(query)
        if len(matches) != 1:
            return matches
        facts = [f for f in self.facts() if f != matches[0]]
        self._save(facts)
        return matches[0]

    def update(self, query: str, new_fact: str):
        """Replace the single fact matching `query`. Returns (old, new), or a list of candidates
        when ambiguous."""
        matches = self.find(query)
        if len(matches) != 1:
            return matches
        facts = self.facts()
        facts[facts.index(matches[0])] = new_fact.strip()
        self._save(facts)
        return (matches[0], new_fact.strip())
