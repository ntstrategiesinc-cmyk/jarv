"""Content prep for the furniture pipeline (works with NO posting API set up).

Jarvis writes an Instagram/Facebook caption and a website product description for a furniture item,
then save_listing drops it as a ready-to-post text file in the Pending Approval folder, next to the
staged image. The owner copies it into Instagram / Facebook / Shopify by hand until the posting APIs
are connected — at which point the same content flows straight to those platforms.
"""

from __future__ import annotations

import re

from ..config import Config
from .base import Tool, ToolResult


def _safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", name).strip() or "listing"


def build_content_tools(config: Config) -> list[Tool]:
    def save_listing(args: dict) -> ToolResult:
        title = (args.get("title") or "").strip()
        if not title:
            return ToolResult.error("Provide a title for the listing.")
        price = (args.get("price") or "").strip()
        description = (args.get("description") or "").strip()
        caption = (args.get("caption") or "").strip()
        image_filename = (args.get("image_filename") or "").strip()

        out_dir = config.staging_dir  # the Pending Approval folder
        out_dir.mkdir(parents=True, exist_ok=True)

        lines = [f"===== {title} =====", ""]
        if price:
            lines.append(f"Price: {price}")
        if image_filename:
            lines.append(f"Staged photo: {image_filename}")
        lines.append("")
        if caption:
            lines += ["----- INSTAGRAM / FACEBOOK CAPTION (copy & paste) -----", caption, ""]
        if description:
            lines += ["----- WEBSITE / PRODUCT DESCRIPTION (for Shopify) -----", description, ""]

        path = out_dir / f"{_safe_filename(title)} - POST.txt"
        path.write_text("\n".join(lines), encoding="utf-8")
        return ToolResult.success(
            f"Saved ready-to-post content to {path}. The owner can copy the caption into Instagram/"
            f"Facebook and the description into Shopify."
        )

    return [
        Tool(
            name="save_listing",
            description=(
                "Save a ready-to-post furniture listing as a text file in the Pending Approval folder "
                "(next to the staged image), for the owner to copy-paste when posting manually. Use "
                "AFTER you've written an Instagram/Facebook caption (with hashtags) and a website "
                "product description for the item."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Product title."},
                    "price": {"type": "string", "description": "Price, e.g. '$900'."},
                    "description": {"type": "string", "description": "Product description for the website/Shopify."},
                    "caption": {"type": "string", "description": "Instagram/Facebook caption, including hashtags."},
                    "image_filename": {"type": "string", "description": "Filename of the staged image this pairs with."},
                },
                "required": ["title"],
            },
            handler=save_listing,
            needs_confirmation=False,
        )
    ]
