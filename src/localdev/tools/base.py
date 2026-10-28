from __future__ import annotations

import subprocess
from pathlib import Path

from localdev import config


def safe_path(p: str) -> Path:
    path = (config.WORKDIR / p).resolve()
    if not path.is_relative_to(config.WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str, timeout: int = 120) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    timeout = min(max(1, timeout), 600)  # clamp 1–600s
    try:
        r = subprocess.run(
            command,
            shell=True,
            cwd=config.WORKDIR,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return (
            f"Error: Timeout ({timeout}s). "
            "Commands that wait for user input (e.g. interactive games) cannot be run here; "
            "run them in your terminal instead."
        )


def run_list_dir(path: str = ".") -> str:
    """List directory contents (paths relative to WORKDIR)."""
    try:
        p = safe_path(path)
        if not p.is_dir():
            return f"Error: Not a directory: {path}"
        entries = sorted(p.iterdir())
        lines = []
        for e in entries:
            rel = e.relative_to(config.WORKDIR)
            lines.append(f"{rel}/" if e.is_dir() else str(rel))
        return "\n".join(lines)[:50000] if lines else "(empty)"
    except Exception as e:  # noqa: BLE001
        return f"Error: {e}"


def run_read(path: str, limit: int | None = None) -> str:
    try:
        lines = safe_path(path).read_text().splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
        return "\n".join(lines)[:50000]
    except Exception as e:  # noqa: BLE001
        return f"Error: {e}"


def run_write(path: str, content: str) -> str:
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:  # noqa: BLE001
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        fp = safe_path(path)
        c = fp.read_text()
        if old_text not in c:
            return f"Error: Text not found in {path}"
        fp.write_text(c.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:  # noqa: BLE001
        return f"Error: {e}"

