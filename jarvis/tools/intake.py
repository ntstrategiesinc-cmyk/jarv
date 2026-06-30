"""The intake folder: drop product photos named "Title - Price.ext" and Jarvis reads them.

A simple, no-typing way for the owner to hand Jarvis furniture listings: the filename carries the
title and price. Jarvis lists what's waiting, and the staging/publish steps pull photos from here.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..config import Config
from .base import Tool, ToolResult

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def parse_listing(filename: str) -> tuple[str, str | None]:
    """Pull a title and price from a filename. Tolerant of many formats:
    'Oak Dining Table - 499', 'sofa-$900', 'Velvet Chair $249.99', 'Bookshelf 179'.
    The price is taken as the last number in the name; the title is what comes before it."""
    stem = Path(filename).stem
    matches = list(re.finditer(r"\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)", stem))
    if matches:
        m = matches[-1]
        price = m.group(1).replace(",", "")
        title = stem[: m.start()].rstrip(" -–—_$").strip()
        if not title:  # price was at the very front
            title = stem[m.end():].strip()
        return (title or stem.strip()), price
    return stem.strip(), None


def list_intake(intake_dir: Path) -> list[dict]:
    intake_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    for p in sorted(intake_dir.iterdir()):
        if p.suffix.lower() in IMAGE_EXTS:
            title, price = parse_listing(p.name)
            items.append({"title": title, "price": price, "filename": p.name, "path": str(p)})
    return items


def build_intake_tools(config: Config) -> list[Tool]:
    def intake_list(args: dict) -> ToolResult:
        items = list_intake(config.intake_dir)
        if not items:
            return ToolResult.success(
                f"The intake folder is empty ({config.intake_dir}). Drop product photos there, each "
                f"named like 'Oak Dining Table - 499.jpg'."
            )
        lines = []
        for i, it in enumerate(items, 1):
            price = f"${it['price']}" if it["price"] else "no price in filename"
            lines.append(f"{i}. {it['title']} — {price}   [file: {it['filename']}]   path: {it['path']}")
        return ToolResult.success(f"{len(items)} item(s) waiting in the intake folder:\n" + "\n".join(lines))

    return [
        Tool(
            name="intake_list",
            description=(
                "List furniture product photos waiting in the intake folder, with the title and price "
                "parsed from each filename ('Title - Price.jpg'). Use this to see what's ready to stage "
                "or post, and to get a photo's file path. Read-only."
            ),
            input_schema={"type": "object", "properties": {}},
            handler=intake_list,
            needs_confirmation=False,
        )
    ]


def build_workspace_tools(config: Config) -> list[Tool]:
    def pending_approvals(args: dict) -> ToolResult:
        d = config.pending_dir
        d.mkdir(parents=True, exist_ok=True)
        files = [p for p in sorted(d.iterdir()) if p.suffix.lower() in IMAGE_EXTS]
        if not files:
            return ToolResult.success(f"Nothing is pending approval ({d}).")
        lines = [f"{i}. {p.name}   path: {p}" for i, p in enumerate(files, 1)]
        return ToolResult.success(f"{len(files)} staged item(s) awaiting your approval to post:\n" + "\n".join(lines))

    def lead_inbox(args: dict) -> ToolResult:
        filt = (args.get("business") or "").strip().lower()
        out: list[str] = []
        for b in config.businesses:
            if filt and filt not in b["name"].lower():
                continue
            folder = b["leads_folder"]
            if folder is None:
                continue
            folder.mkdir(parents=True, exist_ok=True)
            names = [p.name for p in sorted(folder.iterdir()) if p.is_file() and p.name.lower() != "readme.txt"]
            line = f"- {b['name']}: {len(names)} file(s)"
            if names:
                line += " — " + ", ".join(names)
            out.append(line)
        if not out:
            return ToolResult.success("No matching business found.")
        return ToolResult.success("Lead inboxes:\n" + "\n".join(out))

    return [
        Tool(
            name="pending_approvals",
            description="List furniture items that are staged and waiting for the owner's approval before posting (the Pending Approval folder). Read-only.",
            input_schema={"type": "object", "properties": {}},
            handler=pending_approvals,
            needs_confirmation=False,
        ),
        Tool(
            name="lead_inbox",
            description=(
                "List files the owner dropped in their business lead folders (sales emails, leads). "
                "Optionally filter to one business: 'Website & Sales', 'Solid Wood Builds & Sheds', or "
                "'Furniture Staging'. Read-only."
            ),
            input_schema={
                "type": "object",
                "properties": {"business": {"type": "string", "description": "Optional business name to filter to."}},
            },
            handler=lead_inbox,
            needs_confirmation=False,
            returns_external_content=True,
        ),
    ]
