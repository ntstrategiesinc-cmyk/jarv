"""Load configuration (config.toml) and secrets (.env) into one frozen Config.

config.toml holds human-editable settings; .env holds secrets (gitignored). Mutable
runtime state (kill switch, schedules, inbox) lives in jarvis/state/*.json instead,
because tomllib is read-only.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Repo root = the directory containing config.toml (parent of the jarvis package).
ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    """Parsed config.toml plus the repo root. Read-only.

    Accessors are added per-tier as settings are needed; `data` exposes the raw tree
    and `section()` is a safe getter for optional tables.
    """

    data: dict
    root: Path

    def section(self, name: str) -> dict:
        return self.data.get(name, {})

    @property
    def state_dir(self) -> Path:
        """Durable runtime state (kill switch, schedules, inbox, audit log). Gitignored."""
        d = self.root / "jarvis" / "state"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # --- model / provider (Tier 1) ---
    @property
    def model_name(self) -> str:
        return self.data["model"]["name"]

    @property
    def max_tokens(self) -> int:
        return int(self.data["model"].get("max_tokens", 2048))

    @property
    def input_price_per_mtok(self) -> float:
        return float(self.data["model"].get("input_price_per_mtok", 0.0))

    @property
    def output_price_per_mtok(self) -> float:
        return float(self.data["model"].get("output_price_per_mtok", 0.0))

    # --- persona (Tier 1) ---
    @property
    def persona_name(self) -> str:
        return self.section("persona").get("name", "Jarvis")

    @property
    def persona_tone(self) -> str:
        return self.section("persona").get("tone", "")

    # --- tools / leads / social (Tier 2) ---
    @property
    def leads_workbook_path(self) -> Path:
        rel = self.section("leads").get("workbook_path", "leads.xlsx")
        return self.root / rel

    @property
    def leads_sheet_name(self) -> str:
        return self.section("leads").get("sheet_name", "Leads")

    @property
    def graph_api_version(self) -> str:
        return self.section("social").get("graph_api_version", "v22.0")

    # --- memory (Tier 4) ---
    @property
    def memory_path(self) -> Path:
        rel = self.section("memory").get("path", "jarvis/memory/memory.md")
        return self.root / rel

    # --- staging (furniture pipeline) ---
    @property
    def staging_model(self) -> str:
        return self.section("staging").get("model", "gpt-image-1")

    @property
    def staging_size(self) -> str:
        return self.section("staging").get("size", "1024x1024")

    @property
    def staging_quality(self) -> str:
        return self.section("staging").get("quality", "medium")

    @property
    def staging_dir(self) -> Path:
        return self.root / self.section("staging").get("output_dir", "media/staged")

    @property
    def staging_prompt(self) -> str:
        return self.section("staging").get("prompt", "Make this a clean, professional product photo.")

    # --- voice (Tier 3) ---
    @property
    def stt_sample_rate(self) -> int:
        return int(self.section("voice").get("stt_sample_rate", 16000))

    @property
    def tts_sample_rate(self) -> int:
        return int(self.section("voice").get("tts_sample_rate", 24000))

    @property
    def deepgram_model(self) -> str:
        return self.section("voice").get("deepgram_model", "nova-3")

    @property
    def elevenlabs_voice_id(self) -> str:
        return self.section("voice").get("elevenlabs_voice_id", "")

    @property
    def elevenlabs_model_id(self) -> str:
        return self.section("voice").get("elevenlabs_model_id", "eleven_flash_v2_5")

    @property
    def push_to_talk_key(self) -> str:
        return self.section("voice").get("push_to_talk_key", "f9")

    @property
    def voice_input_mode(self) -> str:
        return self.section("voice").get("input_mode", "enter")

    # --- heartbeat (Tier 5) ---
    @property
    def heartbeat_tick_seconds(self) -> int:
        return int(self.section("heartbeat").get("tick_seconds", 60))

    @property
    def heartbeat_misfire_seconds(self) -> int:
        return int(self.section("heartbeat").get("misfire_grace_seconds", 300))

    @property
    def quiet_hours_start(self) -> str:
        return self.section("heartbeat").get("quiet_hours_start", "22:00")

    @property
    def quiet_hours_end(self) -> str:
        return self.section("heartbeat").get("quiet_hours_end", "08:00")

    @property
    def heartbeat_checks(self) -> list[dict]:
        return list(self.section("heartbeat").get("checks", []))

    # --- rails (Tier 6 reads these; defined early so the gate has them) ---
    @property
    def confirm_tools(self) -> list[str]:
        return list(self.section("tools").get("needs_confirmation", []))

    @property
    def confirm_timeout_seconds(self) -> int:
        return int(self.section("tools").get("confirm_timeout_seconds", 120))


def load_config(root: Path = ROOT) -> Config:
    """Load .env (so os.getenv sees secrets) then parse config.toml."""
    load_dotenv(root / ".env")
    with open(root / "config.toml", "rb") as f:
        data = tomllib.load(f)
    return Config(data=data, root=root)


def require_env(name: str) -> str | None:
    """Return an env var or None. Callers decide how to handle a missing secret."""
    return os.getenv(name)
