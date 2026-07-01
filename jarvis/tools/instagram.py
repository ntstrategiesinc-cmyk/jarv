"""Original Instagram content for growing followers — SEPARATE from product listings.

This is Jarvis making his OWN brand content: design tips, room inspiration, trends, "which would
you choose?" engagement posts — NOT the product photos that go to Facebook/Shopify. Jarvis writes
the concept + caption; create_instagram_post generates an original image (text->image) and saves the
image + caption into the Instagram folder for the owner to post from their phone.
"""

from __future__ import annotations

import os
import re
from datetime import datetime

from ..config import Config
from .base import Tool, ToolResult
from .imagegen import ImageStager


def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", name).strip() or "post"


def build_instagram_tools(config: Config) -> list[Tool]:
    def create_instagram_post(args: dict) -> ToolResult:
        name = (args.get("name") or "").strip()
        caption = (args.get("caption") or "").strip()
        image_prompt = (args.get("image_prompt") or "").strip()
        if not name or not caption:
            return ToolResult.error("Provide a short name and the Instagram caption.")

        out_dir = config.instagram_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = f"{_safe(name)} - {stamp}"

        image_note = ""
        if image_prompt:
            key = os.getenv("OPENAI_API_KEY")
            if not key:
                image_note = " (no image generated — OPENAI_API_KEY not set)"
            else:
                try:
                    gen = ImageStager(key, config.staging_model, config.staging_size, config.staging_quality)
                    png = gen.generate(image_prompt)
                    (out_dir / f"{base}.png").write_bytes(png)
                    image_note = f" with image {base}.png"
                except Exception as e:
                    image_note = f" (image generation failed: {str(e)[:150]})"

        (out_dir / f"{base} - caption.txt").write_text(caption, encoding="utf-8")
        return ToolResult.success(
            f"Saved an original Instagram post '{base}'{image_note} to {out_dir}. "
            f"The owner can post it from their phone."
        )

    def create_reel_pack(args: dict) -> ToolResult:
        name = (args.get("name") or "").strip()
        hook = (args.get("hook") or "").strip()
        if not name or not hook:
            return ToolResult.error("Provide a name and a hook for the reel.")
        script = (args.get("script") or "").strip()
        shot_list = (args.get("shot_list") or "").strip()
        audio = (args.get("audio") or "").strip()
        caption = (args.get("caption") or "").strip()

        out_dir = config.instagram_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        lines = [f"===== REEL: {name} =====", "", f"HOOK (first second on screen): {hook}", ""]
        if script:
            lines += ["ON-SCREEN TEXT / SCRIPT:", script, ""]
        if shot_list:
            lines += ["WHAT TO FILM:", shot_list, ""]
        if audio:
            lines += [f"TRENDING AUDIO IDEA: {audio}", ""]
        if caption:
            lines += ["CAPTION:", caption, ""]
        lines += ["HOW: film the clips (or use photos) in Instagram's Reel maker, add the audio, post."]

        path = out_dir / f"REEL - {_safe(name)} - {stamp}.txt"
        path.write_text("\n".join(lines), encoding="utf-8")
        return ToolResult.success(f"Saved a ready-to-film Reel pack to {path}.")

    return [
        Tool(
            name="create_reel_pack",
            description=(
                "Create a ready-to-film Instagram Reel pack to grow followers: a scroll-stopping hook, "
                "on-screen text/script, what to film, a trending-audio suggestion, and a caption. The "
                "owner films it on their phone in about a minute. Great for 'this or that', tips, and "
                "trend-based growth content."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Short slug for the reel."},
                    "hook": {"type": "string", "description": "The first-second hook that stops the scroll."},
                    "script": {"type": "string", "description": "On-screen text beats / short script."},
                    "shot_list": {"type": "string", "description": "What to film (or which photos to use)."},
                    "audio": {"type": "string", "description": "Trending audio suggestion."},
                    "caption": {"type": "string", "description": "Caption with hashtags and an engagement question."},
                },
                "required": ["name", "hook"],
            },
            handler=create_reel_pack,
            needs_confirmation=False,
        ),
        Tool(
            name="create_instagram_post",
            description=(
                "Create ORIGINAL Instagram content to grow the furniture brand's followers — design "
                "tips, room inspiration, trends, or engagement posts. This is NOT for product listings "
                "(those go to Facebook/Shopify). You write the caption (engaging, with hashtags and "
                "ideally a question to drive comments) and an image_prompt for an original image; the "
                "tool generates the image and saves both to the Instagram folder."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Short slug for the post files, e.g. 'small-space-tips'."},
                    "caption": {"type": "string", "description": "The Instagram caption: engaging, value/tip-driven, with hashtags and a question."},
                    "image_prompt": {
                        "type": "string",
                        "description": "Description of an ORIGINAL lifestyle/inspiration image to generate (not a real product). Optional.",
                    },
                },
                "required": ["name", "caption"],
            },
            handler=create_instagram_post,
            needs_confirmation=False,
        )
    ]
