from __future__ import annotations

import json
import time
from typing import List, Dict, Any

from localdev import config
from .llm import call_model


def estimate_tokens(messages: List[Dict[str, Any]]) -> int:
    """Very rough token estimation based on JSON length."""
    return len(json.dumps(messages, default=str)) // 4


def microcompact(messages: List[Dict[str, Any]]) -> None:
    """
    Clear older tool_result payloads to keep context small.
    Mutates messages in place.
    """
    indices = []
    for msg in messages:
        if msg.get("role") == "user" and isinstance(msg.get("content"), list):
            for part in msg["content"]:
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    indices.append(part)
    if len(indices) <= 3:
        return
    for part in indices[:-3]:
        if isinstance(part.get("content"), str) and len(part["content"]) > 100:
            part["content"] = "[cleared]"


def auto_compact(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Persist the full transcript to disk and return a compressed summary conversation.
    """
    config.TRANSCRIPT_DIR.mkdir(exist_ok=True)
    path = config.TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"
    with open(path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg, default=str) + "\n")
    conv_text = json.dumps(messages, default=str)[:80000]
    resp = call_model(
        system=None,
        messages=[
            {
                "role": "user",
                "content": f"Summarize for continuity:\n{conv_text}",
            }
        ],
        max_tokens=2000,
    )
    summary = resp.content[0].text
    return [
        {
            "role": "user",
            "content": f"[Compressed. Transcript: {path}]\n{summary}",
        },
        {
            "role": "assistant",
            "content": "Understood. Continuing with summary context.",
        },
    ]

