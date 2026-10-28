from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple

from localdev import config
from localdev.core.llm import call_model
from localdev.core import memory
from localdev.tools.base import run_bash, run_read, run_write, run_edit
from localdev.tools.system import BackgroundManager
from localdev.tools.skills import SkillLoader
from localdev.tools.registry import build_tools_and_handlers
from localdev.state.todo import TodoManager
from localdev.state.task import TaskManager
from localdev.multiagent.bus import MessageBus
from localdev.multiagent.team import TeammateManager


def run_subagent(prompt: str, agent_type: str = "Explore") -> str:
    """Subagent loop used by the main agent's `task` tool."""
    sub_tools = [
        {
            "name": "bash",
            "description": "Run command.",
            "input_schema": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
        {
            "name": "read_file",
            "description": "Read file.",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    ]
    if agent_type != "Explore":
        sub_tools += [
            {
                "name": "write_file",
                "description": "Write file.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            },
            {
                "name": "edit_file",
                "description": "Edit file.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old_text": {"type": "string"},
                        "new_text": {"type": "string"},
                    },
                    "required": ["path", "old_text", "new_text"],
                },
            },
        ]
    sub_handlers = {
        "bash": lambda **kw: run_bash(kw["command"]),
        "read_file": lambda **kw: run_read(kw["path"]),
        "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
        "edit_file": lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    }
    sub_msgs: List[Dict[str, Any]] = [{"role": "user", "content": prompt}]
    resp = None
    for _ in range(30):
        resp = call_model(
            system=None,
            messages=sub_msgs,
            tools=sub_tools,
            max_tokens=8000,
        )
        sub_msgs.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            break
        results = []
        for b in resp.content:
            if getattr(b, "type", None) == "tool_use":
                h = sub_handlers.get(b.name, lambda **kw: "Unknown tool")
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": b.id,
                        "content": str(h(**b.input))[:50000],
                    }
                )
        sub_msgs.append({"role": "user", "content": results})
    if resp:
        return (
            "".join(
                getattr(b, "text", "")
                for b in resp.content
                if hasattr(b, "text")
            )
            or "(no summary)"
        )
    return "(subagent failed)"


@dataclass
class AgentContext:
    todo: TodoManager
    skills: SkillLoader
    tasks: TaskManager
    bg: BackgroundManager
    bus: MessageBus
    team: TeammateManager
    tools: List[dict]
    handlers: Dict[str, Any]
    system_prompt: str


def create_agent_context() -> AgentContext:
    todo = TodoManager()
    tasks = TaskManager()
    bg = BackgroundManager()
    bus = MessageBus()
    team = TeammateManager(bus=bus, task_mgr=tasks)
    skills = SkillLoader(config.SKILLS_DIR)
    tools, handlers = build_tools_and_handlers(
        todo_mgr=todo,
        skill_loader=skills,
        task_mgr=tasks,
        bg_mgr=bg,
        bus=bus,
        team=team,
        run_subagent_func=run_subagent,
    )
    system_prompt = (
        f"You are a coding agent at {config.WORKDIR}. Use tools to solve tasks.\n"
        "Prefer task_create/task_update/task_list for multi-step work. "
        "Use TodoWrite for short checklists.\n"
        "Use task for subagent delegation. Use load_skill for specialized knowledge.\n"
        f"Skills: {skills.descriptions()}"
    )
    return AgentContext(
        todo=todo,
        skills=skills,
        tasks=tasks,
        bg=bg,
        bus=bus,
        team=team,
        tools=tools,
        handlers=handlers,
        system_prompt=system_prompt,
    )


def agent_loop(ctx: AgentContext, messages: List[Dict[str, Any]]) -> None:
    """
    Main agent loop: compression, background notifications, inbox, tools, and nagging.
    Mutates `messages` in place (same semantics as original s_full.agent_loop).
    """
    rounds_without_todo = 0
    while True:
        # compression pipeline
        memory.microcompact(messages)
        if memory.estimate_tokens(messages) > config.TOKEN_THRESHOLD:
            print("[auto-compact triggered]")
            messages[:] = memory.auto_compact(messages)
        # drain background notifications
        notifs = ctx.bg.drain()
        if notifs:
            txt = "\n".join(
                f"[bg:{n['task_id']}] {n['status']}: {n['result']}"
                for n in notifs
            )
            messages.append(
                {
                    "role": "user",
                    "content": f"<background-results>\n{txt}\n</background-results>",
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": "Noted background results.",
                }
            )
        # check lead inbox
        inbox = ctx.bus.read_inbox("lead")
        if inbox:
            messages.append(
                {
                    "role": "user",
                    "content": f"<inbox>{json.dumps(inbox, indent=2)}</inbox>",
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": "Noted inbox messages.",
                }
            )
        # LLM call
        response = call_model(
            system=ctx.system_prompt,
            messages=messages,
            tools=ctx.tools,
            max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return
        # Tool execution
        results: List[Dict[str, Any]] = []
        used_todo = False
        manual_compress = False
        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                if block.name == "compress":
                    manual_compress = True
                handler = ctx.handlers.get(block.name)
                try:
                    output = (
                        handler(**block.input)
                        if handler
                        else f"Unknown tool: {block.name}"
                    )
                except Exception as e:  # noqa: BLE001
                    output = f"Error: {e}"
                print(f"> {block.name}: {str(output)[:200]}")
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(output),
                    }
                )
                if block.name == "TodoWrite":
                    used_todo = True
        # nag reminder (only when todo workflow is active)
        rounds_without_todo = 0 if used_todo else rounds_without_todo + 1
        if ctx.todo.has_open_items() and rounds_without_todo >= 3:
            results.insert(
                0,
                {
                    "type": "text",
                    "text": "<reminder>Update your todos.</reminder>",
                },
            )
        messages.append({"role": "user", "content": results})
        # manual compress
        if manual_compress:
            print("[manual compact]")
            messages[:] = memory.auto_compact(messages)

