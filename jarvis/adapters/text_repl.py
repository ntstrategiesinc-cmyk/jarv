"""The text adapter: a plain REPL over the agent core.

This is the primary debugging surface and the permanent fallback. Voice (Tier 3) wraps the
same Agent.run_turn() at the edges; it never replaces this path.
"""

from __future__ import annotations

import sys

from ..config import Config
from ..core.agent import Agent
from ..core.conversation import Conversation


def run_repl(agent: Agent, config: Config) -> None:
    name = config.persona_name
    print(f"{name} — text mode. Type a message; 'exit' or Ctrl-C to quit.\n")

    conversation = Conversation()

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
        agent.run_turn(conversation, on_text=on_text)
        print("\n")
