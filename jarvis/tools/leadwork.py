"""Working the leads that come in: read a saved lead file, and save a drafted reply/outreach.

Flow Jarvis follows: lead_inbox (see what's dropped) -> read_lead (pull the text out) -> extract the
name/contact/interest and log it with leads_add -> save_draft (a reply for the owner to send).
Lead file text is treated as untrusted data (it's fenced), so nothing inside it can act as a command.
"""

from __future__ import annotations

import email
import re
from email import policy
from pathlib import Path

from ..config import Config
from ..rails.sanitize import wrap_external
from .base import Tool, ToolResult


def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", name).strip() or "draft"


def _read_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".eml":
        msg = email.message_from_bytes(path.read_bytes(), policy=policy.default)
        body = msg.get_body(preferencelist=("plain", "html"))
        text = body.get_content() if body else ""
        return f"From: {msg.get('From', '')}\nSubject: {msg.get('Subject', '')}\nDate: {msg.get('Date', '')}\n\n{text}"
    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if ext in (".txt", ".md", ".csv", ".eml", ""):
        return path.read_text(encoding="utf-8", errors="replace")
    return ""


def build_leadwork_tools(config: Config) -> list[Tool]:
    def read_lead(args: dict) -> ToolResult:
        raw = (args.get("path") or "").strip().strip('"')
        if not raw:
            return ToolResult.error("Provide the file path to the lead (from lead_inbox).")
        p = Path(raw)
        if not p.exists():
            return ToolResult.error(f"No file at {raw}.")
        try:
            text = _read_text(p)
        except Exception as e:
            return ToolResult.error(f"Couldn't read {p.name}: {str(e)[:150]}")
        if not text.strip():
            return ToolResult.error(
                f"{p.name}: no readable text (it may be an image or a .msg file — open it and paste the text instead)."
            )
        return ToolResult.success(wrap_external(text[:4000], source=p.name))

    def save_draft(args: dict) -> ToolResult:
        content = (args.get("content") or "").strip()
        if not content:
            return ToolResult.error("Provide the draft content.")
        name = (args.get("name") or "draft").strip()
        business = (args.get("business") or "").strip().lower()

        base = None
        for b in config.businesses:
            if b["leads_folder"] and (not business or business in b["name"].lower()):
                base = b["leads_folder"]
                if business:
                    break
        if base is None:
            base = config.root
        drafts = Path(base) / "Drafts"
        drafts.mkdir(parents=True, exist_ok=True)
        path = drafts / f"{_safe(name)}.txt"
        path.write_text(content, encoding="utf-8")
        return ToolResult.success(f"Saved draft to {path}. The owner can review and send it.")

    def save_lead_content(args: dict) -> ToolResult:
        content = (args.get("content") or "").strip()
        name = (args.get("name") or "").strip()
        if not content or not name:
            return ToolResult.error("Provide a name and the content.")
        business = (args.get("business") or "").strip()
        out = config.lead_content_dir
        if business:
            out = out / _safe(business)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{_safe(name)}.txt"
        path.write_text(content, encoding="utf-8")
        return ToolResult.success(f"Saved lead-generation content to {path}.")

    return [
        Tool(
            name="save_lead_content",
            description=(
                "Save lead-generation marketing content (an ad, flyer, Marketplace listing, Google "
                "Business post, referral offer, email, or outreach template) to the Lead Content folder, "
                "optionally under a business. Use to build up ready-to-use content that brings in customers."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Short name, e.g. 'realtor-outreach' or 'marketplace-listing'."},
                    "business": {"type": "string", "description": "Which business (optional): Website & Sales, Solid Wood Builds & Sheds, or Furniture Staging."},
                    "content": {"type": "string", "description": "The full content to save."},
                },
                "required": ["name", "content"],
            },
            handler=save_lead_content,
            needs_confirmation=False,
        ),
        Tool(
            name="read_lead",
            description=(
                "Read the text of a saved lead file (a forwarded email .eml, a .pdf, or a .txt note) so "
                "you can pull out the person's name, contact info, and what they want. Pass the file path "
                "from lead_inbox. Read-only."
            ),
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Full path to the lead file."}},
                "required": ["path"],
            },
            handler=read_lead,
            needs_confirmation=False,
        ),
        Tool(
            name="save_draft",
            description=(
                "Save a drafted reply or outreach message as a text file in the business's Drafts folder, "
                "for the owner to review and send. Use after writing a reply to an incoming lead or a "
                "personalized outreach pitch."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Short name for the draft, e.g. 'reply-jane-doe'."},
                    "business": {"type": "string", "description": "Which business this is for (optional)."},
                    "content": {"type": "string", "description": "The full drafted message."},
                },
                "required": ["content"],
            },
            handler=save_draft,
            needs_confirmation=False,
        ),
    ]
