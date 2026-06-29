"""The text adapter: a plain REPL over the agent core.

This is the primary debugging surface and the permanent fallback. It supplies a console
approver so consequential tools (Tier 2 flag / Tier 6 gate) prompt for an explicit yes before
running. Voice (Tier 3) wraps the same Agent.run_turn() with its own approver.
"""

from __future__ import annotations

import sys

from ..config import Config
from ..core.agent import Agent
from ..core.conversation import Conversation


def make_console_approver(name: str):
    """Prompt on the console, stating plainly what's about to happen. Returns allow/deny."""

    def approver(tool, tool_input: dict, source: str = "typed") -> bool:
        print()  # break from any streamed text
        print(f"  [confirm] {name} wants to run '{tool.name}':")
        for k, v in tool_input.items():
            if v not in (None, "", []):
                print(f"      {k}: {v}")
        try:
            answer = input("  allow? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return answer in {"y", "yes"}

    return approver


def run_repl(agent: Agent, config: Config) -> None:
    name = config.persona_name
    print(f"{name} — text mode. Type a message; 'exit' or Ctrl-C to quit.\n")

    conversation = Conversation()
    approver = make_console_approver(name)

    def on_text(delta: str) -> None:
        sys.stdout.write(delta)
        sys.stdout.flush()

    while True:
        try:
            user = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye.")
            return

        if not user:
            continue
        if user.lower() in {"exit", "quit"}:
            print("bye.")
            return

        conversation.add_user_text(user)
        print(f"{name.lower()} > ", end="", flush=True)
        agent.run_turn(conversation, on_text=on_text, source="typed", approver=approver)
        print("\n")
