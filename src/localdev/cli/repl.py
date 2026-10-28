from __future__ import annotations

import json
from typing import List, Dict, Any

from localdev.core.agent import create_agent_context, agent_loop


def run_repl() -> None:
    """Interactive REPL, mirroring the behavior of agents/s_full.py."""
    ctx = create_agent_context()
    history: List[Dict[str, Any]] = []
    while True:
        try:
            query = input("\033[36mlocaldev >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        if query.strip() == "/compact":
            if history:
                from localdev.core import memory

                print("[manual compact via /compact]")
                history[:] = memory.auto_compact(history)
            continue
        if query.strip() == "/tasks":
            print(ctx.tasks.list_all())
            continue
        if query.strip() == "/team":
            print(ctx.team.list_all())
            continue
        if query.strip() == "/inbox":
            print(json.dumps(ctx.bus.read_inbox("lead"), indent=2))
            continue
        history.append({"role": "user", "content": query})
        agent_loop(ctx, history)
        print()

