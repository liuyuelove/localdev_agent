from __future__ import annotations

import json
import time
from dataclasses import dataclass

from pathlib import Path

from localdev import config


@dataclass
class MessageBus:
    """Simple JSONL-based message bus for teammates."""

    inbox_dir: Path = config.INBOX_DIR

    def __post_init__(self) -> None:
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

    def send(
        self,
        sender: str,
        to: str,
        content: str,
        msg_type: str = "message",
        extra: dict | None = None,
    ) -> str:
        msg = {
            "type": msg_type,
            "from": sender,
            "content": content,
            "timestamp": time.time(),
        }
        if extra:
            msg.update(extra)
        path = self.inbox_dir / f"{to}.jsonl"
        with open(path, "a") as f:
            f.write(json.dumps(msg) + "\n")
        return f"Sent {msg_type} to {to}"

    def read_inbox(self, name: str) -> list[dict]:
        path = self.inbox_dir / f"{name}.jsonl"
        if not path.exists():
            return []
        text = path.read_text().strip()
        if not text:
            return []
        msgs = [json.loads(l) for l in text.splitlines() if l]
        path.write_text("")
        return msgs

    def broadcast(self, sender: str, content: str, names: list[str]) -> str:
        count = 0
        for n in names:
            if n != sender:
                self.send(sender, n, content, "broadcast")
                count += 1
        return f"Broadcast to {count} teammates"

