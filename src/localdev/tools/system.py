from __future__ import annotations

import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from queue import Queue
from typing import Dict, Any

from localdev import config


@dataclass
class BackgroundManager:
    tasks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    notifications: Queue = field(default_factory=Queue)

    def run(self, command: str, timeout: int = 120) -> str:
        tid = str(uuid.uuid4())[:8]
        self.tasks[tid] = {
            "status": "running",
            "command": command,
            "result": None,
        }
        threading.Thread(
            target=self._exec,
            args=(tid, command, timeout),
            daemon=True,
        ).start()
        return f"Background task {tid} started: {command[:80]}"

    def _exec(self, tid: str, command: str, timeout: int) -> None:
        try:
            r = subprocess.run(
                command,
                shell=True,
                cwd=config.WORKDIR,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = (r.stdout + r.stderr).strip()[:50000]
            self.tasks[tid].update(
                {
                    "status": "completed",
                    "result": output or "(no output)",
                }
            )
        except Exception as e:  # noqa: BLE001
            self.tasks[tid].update({"status": "error", "result": str(e)})
        self.notifications.put(
            {
                "task_id": tid,
                "status": self.tasks[tid]["status"],
                "result": (self.tasks[tid]["result"] or "")[:500],
            }
        )

    def check(self, tid: str | None = None) -> str:
        if tid:
            t = self.tasks.get(tid)
            if not t:
                return f"Unknown: {tid}"
            return f"[{t['status']}] {t.get('result', '(running)')}"
        if not self.tasks:
            return "No bg tasks."
        return "\n".join(
            f"{k}: [{v['status']}] {v['command'][:60]}"
            for k, v in self.tasks.items()
        )

    def drain(self) -> list[dict]:
        notifs: list[dict] = []
        while not self.notifications.empty():
            notifs.append(self.notifications.get_nowait())
        return notifs

