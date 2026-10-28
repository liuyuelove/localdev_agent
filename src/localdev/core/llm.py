from __future__ import annotations

from typing import Any, Iterable

from anthropic.types import MessageParam

from localdev import config


def call_model(
    *,
    system: str | None,
    messages: list[MessageParam],
    tools: Iterable[dict[str, Any]] | None = None,
    max_tokens: int = 8000,
):
    """
    Thin wrapper around the Anthropic client used by the agent.
    Keeps the rest of the code independent from the client construction.
    """
    kwargs: dict[str, Any] = {
        "model": config.MODEL_ID,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if system is not None:
        kwargs["system"] = system
    if tools is not None:
        kwargs["tools"] = list(tools)
    return config.CLIENT.messages.create(**kwargs)

