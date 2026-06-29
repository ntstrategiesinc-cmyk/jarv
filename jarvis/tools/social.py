"""post_photo — publish a photo to Instagram and/or a Facebook Page via the Meta Graph API.

A consequential, outward-facing action: always needs_confirmation. The network calls are real,
but guarded — with no Meta credentials in .env the tool returns a plain-language "not configured"
result and posts nothing, so it's safe to exercise before the one-time Meta setup is done.

One-time setup (see AGENT.md / README): a Meta app (Business), a Facebook Page, an Instagram
Business account linked to that Page, and a long-lived Page token. Then set META_PAGE_TOKEN,
META_PAGE_ID, META_IG_USER_ID in .env.

Note: Instagram requires a PUBLIC image URL (it cannot take a local file); Facebook accepts a URL.
"""

from __future__ import annotations

import os

import requests

from ..config import Config
from .base import Tool, ToolResult

_TIMEOUT = 30


def _graph_error(resp: requests.Response) -> str:
    try:
        return str(resp.json().get("error", {}).get("message", resp.text))[:300]
    except Exception:
        return resp.text[:300]


def _post_facebook(version: str, page_id: str, token: str, image_url: str, caption: str) -> str:
    url = f"https://graph.facebook.com/{version}/{page_id}/photos"
    try:
        resp = requests.post(
            url, data={"url": image_url, "caption": caption, "access_token": token}, timeout=_TIMEOUT
        )
    except requests.RequestException as e:
        return f"Facebook: error reaching the Graph API ({e})."
    if resp.status_code == 200:
        return f"Facebook: posted (id {resp.json().get('id', '?')})."
    return f"Facebook: error {resp.status_code} — {_graph_error(resp)}"


def _post_instagram(version: str, ig_id: str, token: str, image_url: str, caption: str) -> str:
    base = f"https://graph.facebook.com/{version}"
    # Step 1: create a media container.
    try:
        c = requests.post(
            f"{base}/{ig_id}/media",
            data={"image_url": image_url, "caption": caption, "access_token": token},
            timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        return f"Instagram: error creating the media container ({e})."
    if c.status_code != 200:
        return f"Instagram: error {c.status_code} creating container — {_graph_error(c)}"
    creation_id = c.json().get("id")
    # Step 2: publish it.
    try:
        p = requests.post(
            f"{base}/{ig_id}/media_publish",
            data={"creation_id": creation_id, "access_token": token},
            timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        return f"Instagram: error publishing ({e})."
    if p.status_code != 200:
        return f"Instagram: error {p.status_code} publishing — {_graph_error(p)}"
    return f"Instagram: posted (id {p.json().get('id', '?')})."


def build_social_tools(config: Config) -> list[Tool]:
    version = config.graph_api_version

    def post_photo(args: dict) -> ToolResult:
        image_url = (args.get("image_url") or "").strip()
        caption = args.get("caption") or ""
        targets = args.get("targets") or ["instagram", "facebook"]
        if not image_url:
            return ToolResult.error("image_url is required: a public https URL to a JPEG image.")

        token = os.getenv("META_PAGE_TOKEN")
        page_id = os.getenv("META_PAGE_ID")
        ig_id = os.getenv("META_IG_USER_ID")
        if not token:
            return ToolResult.error(
                "Meta isn't configured yet, so nothing was posted. After the one-time Meta app "
                "setup, set META_PAGE_TOKEN (and META_PAGE_ID / META_IG_USER_ID) in .env."
            )

        results: list[str] = []
        if "facebook" in targets:
            if not page_id:
                results.append("Facebook: skipped (META_PAGE_ID not set).")
            else:
                results.append(_post_facebook(version, page_id, token, image_url, caption))
        if "instagram" in targets:
            if not ig_id:
                results.append("Instagram: skipped (META_IG_USER_ID not set).")
            else:
                results.append(_post_instagram(version, ig_id, token, image_url, caption))
        if not results:
            return ToolResult.error(f"No valid targets in {targets}. Use 'instagram' and/or 'facebook'.")

        ok = not any("error" in r.lower() for r in results)
        return ToolResult(ok=ok, content="\n".join(results))

    return [
        Tool(
            name="post_photo",
            description=(
                "Publish a photo to Instagram and/or a Facebook Page. Use only when the user "
                "asks to post or publish an image. Consequential, public action."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "image_url": {
                        "type": "string",
                        "description": "Public https URL to a JPEG. Instagram cannot use a local file path.",
                    },
                    "caption": {"type": "string", "description": "Caption / message for the post."},
                    "targets": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["instagram", "facebook"]},
                        "description": "Platforms to post to. Defaults to both.",
                    },
                },
                "required": ["image_url"],
            },
            handler=post_photo,
            needs_confirmation=True,
        ),
    ]
