"""The text adapter: a plain REPL over the agent core.

Primary debugging surface and permanent fallback. Supplies a console approver for the
confirmation gate, and slash-commands to drive the Tier 6 rails: pause/resume the kill switch,
check session cost, and tail the audit log.
"""

from __future__ import annotations

import sys

from ..config import Config
from ..core.agent import Agent
from ..core.conversation import Conversation
from ..heartbeat.inbox import Inbox
from ..rails.audit import AuditLog
from ..rails.killswitch import KillSwitch


def make_console_approver(name: str):
    """Prompt on the console, stating plainly what's about to happen. Returns allow/deny.
    Accepts (and ignores) `timeout` so it matches the gate's approver signature; the heartbeat
    approver (Tier 5) is where the timeout actually applies."""

    def approver(tool, tool_input: dict, source: str = "typed", timeout=None) -> bool:
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


def _handle_command(cmd: str, killswitch: KillSwitch, audit: AuditLog, inbox: Inbox) -> bool:
    """Handle a /slash command. Returns True if it was a command (and was handled)."""
    parts = cmd.split()
    head = parts[0].lower()
    if head in {"/pause", "/stop"}:
        killswitch.pause()
        audit.record_event("killswitch", state="paused", source="typed")
        print("  proactive behavior PAUSED (you can still chat). /resume to re-enable.")
    elif head in {"/resume", "/start"}:
        killswitch.resume()
        audit.record_event("killswitch", state="resumed", source="typed")
        print("  proactive behavior RESUMED.")
    elif head == "/status":
        paused = "PAUSED" if killswitch.is_paused() else "active"
        print(f"  proactive: {paused}")
        print(
            f"  session cost: ${audit.session_cost_usd:.4f} "
            f"({audit.session_input_tokens} in / {audit.session_output_tokens} out tokens)"
        )
    elif head == "/inbox":
        items = inbox.pending()
        if not items:
            print("  inbox empty.")
        else:
            print(f"  {len(items)} item(s) waiting:")
            for i in items:
                line = f"    #{i['id']} [{i.get('severity', 'notice')}] {i.get('title', '')}"
                if i.get("body"):
                    line += f" — {i['body']}"
                print(line + f"   ({i.get('ts', '')})")
            print("  dismiss with /dismiss <id> or /dismiss all")
    elif head == "/dismiss":
        if len(parts) < 2:
            print("  usage: /dismiss <id> | /dismiss all")
        else:
            target = "all" if parts[1].lower() == "all" else int(parts[1]) if parts[1].isdigit() else None
            if target is None:
                print("  give a numeric id or 'all'.")
            else:
                n = inbox.dismiss(target)
                print(f"  dismissed {n} item(s).")
    elif head == "/audit":
        lines = audit.tail(10)
        print("  last audit entries:" if lines else "  (audit log empty)")
        for line in lines:
            print(f"    {line}")
    elif head == "/help":
        print("  commands: /pause  /resume  /status  /inbox  /dismiss <id|all>  /audit  /help  exit")
    else:
        return False
    return True


def run_repl(agent: Agent, config: Config, killswitch: KillSwitch, audit: AuditLog) -> None:
    name = config.persona_name
    inbox = Inbox(config.state_dir / "inbox.json")

    conversation = Conversation()
    approver = make_console_approver(name)

    pending = inbox.pending()
    print(f"{name} — text mode. Type a message, /help for commands, or 'exit' to quit.")
    if pending:
        print(f"[heartbeat] {len(pending)} item(s) waiting — type /inbox to see them.")
    print()

    def on_text(delta: str) -> None:
        sys.stdout.write(delta)
        sys.stdout.flush()

    while True:
        try:
            # lstrip a stray BOM (escape form) so slash-commands are recognized even if piped.
            user = input("you > ").lstrip("﻿").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye.")
            return

        if not user:
            continue
        if user.lower() in {"exit", "quit"}:
            print("bye.")
            return
        if user.startswith("/"):
            if not _handle_command(user, killswitch, audit, inbox):
                print("  unknown command. /help for the list.")
            continue

        conversation.add_user_text(user)
        print(f"{name.lower()} > ", end="", flush=True)
        agent.run_turn(conversation, on_text=on_text, source="typed", approver=approver)
        print("\n")
