"""AI photo staging for the furniture pipeline.

Takes a real furniture photo and produces a staged, marketing-ready version via an image-edit model
(OpenAI gpt-image-1 by default, behind a seam so it can be swapped). Guarded: with no OPENAI_API_KEY
it returns a plain-language "not configured" result and stages nothing.

Note: AI staging can subtly alter a product's appearance, so the staged image should be reviewed
before it's posted (the publish step is gated). Staging spends a little money per image; if you want
Jarvis to ask first, add "stage_photo" to [tools] needs_confirmation in config.toml.
"""

from __future__ import annotations

import base64
import os
from datetime import datetime
from pathlib import Path

from ..config import Config
from .base import Tool, ToolResult


class ImageStager:
    """The image-staging seam. Swap this class to change providers; callers only use stage()."""

    def __init__(self, api_key: str, model: str = "gpt-image-1", size: str = "1024x1024", quality: str = "medium"):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self.model = model
        self.size = size
        self.quality = quality

    def stage(self, image_path: str, prompt: str) -> bytes:
        """Edit an existing photo (e.g. stage a product). Returns PNG bytes."""
        with open(image_path, "rb") as f:
            resp = self._client.images.edit(
                model=self.model, image=f, prompt=prompt, size=self.size, quality=self.quality
            )
        return base64.b64decode(resp.data[0].b64_json)

    def generate(self, prompt: str) -> bytes:
        """Create a brand-new image from a text prompt (e.g. original Instagram content)."""
        resp = self._client.images.generate(
            model=self.model, prompt=prompt, size=self.size, quality=self.quality
        )
        return base64.b64decode(resp.data[0].b64_json)


def build_image_tools(config: Config) -> list[Tool]:
    def stage_photo(args: dict) -> ToolResult:
        image_path = (args.get("image_path") or "").strip().strip('"')
        if not image_path:
            return ToolResult.error("Provide image_path — the file path to the furniture photo to stage.")
        src = Path(image_path)
        if not src.exists():
            return ToolResult.error(f"No file found at {image_path}.")

        key = os.getenv("OPENAI_API_KEY")
        if not key:
            return ToolResult.error(
                "Photo staging isn't configured yet. Add OPENAI_API_KEY to .env (from "
                "platform.openai.com). Nothing was staged."
            )

        prompt = config.staging_prompt
        extra = (args.get("instructions") or "").strip()
        if extra:
            prompt = f"{prompt} Additional direction: {extra}"

        try:
            stager = ImageStager(key, config.staging_model, config.staging_size, config.staging_quality)
            png = stager.stage(str(src), prompt)
        except Exception as e:
            return ToolResult.error(f"Staging failed: {str(e)[:240]}")

        out_dir = config.staging_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out = out_dir / f"staged_{src.stem}_{stamp}.png"
        out.write_bytes(png)
        return ToolResult.success(
            f"Staged image created and saved to {out}. Review it; when you're happy, ask me to post it."
        )

    return [
        Tool(
            name="stage_photo",
            description=(
                "Turn a real furniture photo into a professionally staged marketing image. Use when "
                "the owner gives you a photo (a file path) to prepare for posting. Saves the result "
                "locally for review before any posting."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "File path to the source furniture photo."},
                    "instructions": {
                        "type": "string",
                        "description": "Optional extra direction, e.g. 'place in a modern living room' or 'white background'.",
                    },
                },
                "required": ["image_path"],
            },
            handler=stage_photo,
            needs_confirmation=False,
        )
    ]
