"""Shared assembly: build the one agent core that every entry path uses.

run_text.py and run_voice.py both call build_core() so the brain, tools, rails, and memory are
assembled identically — the adapters differ only at the edges (typed vs spoken I/O).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from .config import Config, load_config
from .core.agent import Agent
from .core.provider import ModelProvider
from .memory.store import MemoryStore
from .rails.audit import AuditLog
from .rails.gate import ConfirmationGate
from .rails.killswitch import KillSwitch
from .tools.content import build_content_tools
from .tools.imagegen import build_image_tools
from .tools.intake import build_intake_tools, build_workspace_tools
from .tools.leads import build_leads_tools
from .tools.memory import build_memory_tools
from .tools.registry import ToolRegistry
from .tools.social import build_social_tools


@dataclass
class Core:
    config: Config
    agent: Agent
    killswitch: KillSwitch
    audit: AuditLog
    memory: MemoryStore


def force_utf8_console() -> None:
    """Windows consoles default to cp1252; streamed model/voice output would crash on Unicode,
    and piped stdin would mis-decode a leading BOM. Force UTF-8 on all three streams."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    try:
        # utf-8-sig auto-strips a leading BOM (e.g. from PowerShell-piped input).
        sys.stdin.reconfigure(encoding="utf-8-sig", errors="replace")
    except (AttributeError, ValueError):
        pass


def missing_env(names: list[str]) -> list[str]:
    return [n for n in names if not os.getenv(n)]


def build_core(config: Config | None = None) -> Core:
    config = config or load_config()

    provider = ModelProvider(
        api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        model=config.model_name,
        max_tokens=config.max_tokens,
    )
    killswitch = KillSwitch(config.state_dir / "killswitch.json")
    audit = AuditLog(
        config.state_dir / "audit.log",
        input_price_per_mtok=config.input_price_per_mtok,
        output_price_per_mtok=config.output_price_per_mtok,
    )
    gate = ConfirmationGate(config, killswitch, audit)
    memory = MemoryStore(config.memory_path)

    registry = ToolRegistry()
    registry.register_all(build_leads_tools(config))
    registry.register_all(build_social_tools(config))
    registry.register_all(build_memory_tools(config, memory))
    registry.register_all(build_image_tools(config))
    registry.register_all(build_intake_tools(config))
    registry.register_all(build_workspace_tools(config))
    registry.register_all(build_content_tools(config))

    agent = Agent(provider, config, registry=registry, gate=gate, audit=audit, memory=memory)
    return Core(config=config, agent=agent, killswitch=killswitch, audit=audit, memory=memory)
