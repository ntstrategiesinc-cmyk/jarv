"""The PROVIDER SEAM.

Exactly one function's worth of responsibility: send a conversation (+ optional tools)
to the model and get back a streamed reply or a request to use tools. Everything else in
the harness calls ModelProvider.send() and never touches the Anthropic SDK directly, so the
provider can be swapped, retried, or cost-logged in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import anthropic


@dataclass
class ToolCall:
    """A model's request to run one tool. Resolved by the agent's tool loop (Tier 2)."""

    id: str
    name: str
    input: dict


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ProviderResult:
    """The outcome of one model call.

    `error` is set (and text/tool_calls empty) when the model was slow or unreachable, so
    callers can degrade calmly instead of crashing.
    """

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: Optional[str] = None
    usage: Usage = field(default_factory=Usage)
    error: Optional[str] = None


class ModelProvider:
    """Thin wrapper over the Anthropic SDK with streaming and graceful failure."""

    def __init__(self, api_key: str, model: str, max_tokens: int = 2048):
        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def send(
        self,
        system: str,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        on_text: Optional[Callable[[str], None]] = None,
    ) -> ProviderResult:
        """Stream a reply. Calls on_text(delta) as text arrives; returns the final result.

        Network/timeouts/5xx are caught and returned as a degraded ProviderResult (error set),
        never raised — a daily-driver assistant has to shrug those off.
        """
        tools = tools or []
        try:
            with self._client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=messages,
                tools=tools,
            ) as stream:
                for delta in stream.text_stream:
                    if on_text:
                        on_text(delta)
                final = stream.get_final_message()
        except (anthropic.APIConnectionError, anthropic.APITimeoutError):
            return ProviderResult(error="couldn't reach the model (network issue)")
        except anthropic.RateLimitError:
            return ProviderResult(error="rate limited by the model provider")
        except anthropic.APIStatusError as e:
            return ProviderResult(error=f"the model returned an error (HTTP {e.status_code})")
        except anthropic.AnthropicError as e:  # catch-all for SDK-level failures
            return ProviderResult(error=f"model error: {e.__class__.__name__}")

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in final.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=dict(block.input)))

        usage = Usage(
            input_tokens=getattr(final.usage, "input_tokens", 0) or 0,
            output_tokens=getattr(final.usage, "output_tokens", 0) or 0,
        )
        return ProviderResult(
            text="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=final.stop_reason,
            usage=usage,
        )
