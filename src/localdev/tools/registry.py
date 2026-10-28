from __future__ import annotations

import json
from typing import Tuple, Dict, Callable, Any, List

from localdev.tools.base import run_bash, run_read, run_write, run_edit, run_list_dir
from localdev.tools.system import BackgroundManager
from localdev.tools.skills import SkillLoader
from localdev.state.todo import TodoManager
from localdev.state.task import TaskManager
from localdev.multiagent.bus import MessageBus
from localdev.multiagent.team import TeammateManager
from localdev.multiagent import protocol


ToolHandler = Callable[..., str]


def build_tools_and_handlers(
    *,
    todo_mgr: TodoManager,
    skill_loader: SkillLoader,
    task_mgr: TaskManager,
    bg_mgr: BackgroundManager,
    bus: MessageBus,
    team: TeammateManager,
    run_subagent_func: Callable[..., str],
) -> Tuple[List[dict], Dict[str, ToolHandler]]:
    """
    Build the TOOLS spec list and TOOL_HANDLERS dispatch table.

    This replaces the hard-coded global TOOL_HANDLERS in s_full.py and
    allows dependency injection for easier testing and reuse.
    """

    handlers: Dict[str, ToolHandler] = {
        "bash": lambda **kw: run_bash(kw["command"], kw.get("timeout", 120)),
        "list_dir": lambda **kw: run_list_dir(kw.get("path", ".")),
        "read_file": lambda **kw: run_read(kw["path"], kw.get("limit")),
        "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
        "edit_file": lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
        "TodoWrite": lambda **kw: todo_mgr.update(kw["items"]),
        "task": lambda **kw: run_subagent_func(
            kw["prompt"], kw.get("agent_type", "Explore")
        ),
        "load_skill": lambda **kw: skill_loader.load(kw["name"]),
        "compress": lambda **kw: "Compressing...",
        "background_run": lambda **kw: bg_mgr.run(
            kw["command"], kw.get("timeout", 120)
        ),
        "check_background": lambda **kw: bg_mgr.check(kw.get("task_id")),
        "task_create": lambda **kw: task_mgr.create(
            kw["subject"], kw.get("description", "")
        ),
        "task_get": lambda **kw: task_mgr.get(kw["task_id"]),
        "task_update": lambda **kw: task_mgr.update(
            kw["task_id"],
            kw.get("status"),
            kw.get("add_blocked_by"),
            kw.get("add_blocks"),
        ),
        "task_list": lambda **kw: task_mgr.list_all(),
        "spawn_teammate": lambda **kw: team.spawn(
            kw["name"], kw["role"], kw["prompt"]
        ),
        "list_teammates": lambda **kw: team.list_all(),
        "send_message": lambda **kw: bus.send(
            "lead", kw["to"], kw["content"], kw.get("msg_type", "message")
        ),
        "read_inbox": lambda **kw: json.dumps(bus.read_inbox("lead"), indent=2),
        "broadcast": lambda **kw: bus.broadcast(
            "lead", kw["content"], team.member_names()
        ),
        "shutdown_request": lambda **kw: protocol.handle_shutdown_request(
            bus, kw["teammate"]
        ),
        "plan_approval": lambda **kw: protocol.handle_plan_review(
            bus, kw["request_id"], kw["approve"], kw.get("feedback", "")
        ),
        "idle": lambda **kw: "Lead does not idle.",
        "claim_task": lambda **kw: task_mgr.claim(kw["task_id"], "lead"),
    }

    tools: List[dict] = [
        {
            "name": "bash",
            "description": "Run a non-interactive shell command. For interactive programs (e.g. games with input()), use timeout≤10 to get a short preview, or tell the user to run in their terminal.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer", "description": "Seconds (1–600), default 120. Use a small value for commands that may block on input."},
                },
                "required": ["command"],
            },
        },
        {
            "name": "list_dir",
            "description": "List directory contents. Use before read_file to see what exists.",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative path, default '.'"}},
            },
        },
        {
            "name": "read_file",
            "description": "Read file contents.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["path"],
            },
        },
        {
            "name": "write_file",
            "description": "Write content to file.",
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
            "description": "Replace exact text in file.",
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
        {
            "name": "TodoWrite",
            "description": "Update task tracking list.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string"},
                                "status": {
                                    "type": "string",
                                    "enum": [
                                        "pending",
                                        "in_progress",
                                        "completed",
                                    ],
                                },
                                "activeForm": {"type": "string"},
                            },
                            "required": ["content", "status", "activeForm"],
                        },
                    }
                },
                "required": ["items"],
            },
        },
        {
            "name": "task",
            "description": "Spawn a subagent for isolated exploration or work.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "agent_type": {
                        "type": "string",
                        "enum": ["Explore", "general-purpose"],
                    },
                },
                "required": ["prompt"],
            },
        },
        {
            "name": "load_skill",
            "description": "Load specialized knowledge by name.",
            "input_schema": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
        {
            "name": "compress",
            "description": "Manually compress conversation context.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "background_run",
            "description": "Run command in background thread.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer"},
                },
                "required": ["command"],
            },
        },
        {
            "name": "check_background",
            "description": "Check background task status.",
            "input_schema": {
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
            },
        },
        {
            "name": "task_create",
            "description": "Create a persistent file task.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["subject"],
            },
        },
        {
            "name": "task_get",
            "description": "Get task details by ID.",
            "input_schema": {
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
            },
        },
        {
            "name": "task_update",
            "description": "Update task status or dependencies.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "status": {
                        "type": "string",
                        "enum": [
                            "pending",
                            "in_progress",
                            "completed",
                            "deleted",
                        ],
                    },
                    "add_blocked_by": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "add_blocks": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                },
                "required": ["task_id"],
            },
        },
        {
            "name": "task_list",
            "description": "List all tasks.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "spawn_teammate",
            "description": "Spawn a persistent autonomous teammate.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "prompt": {"type": "string"},
                },
                "required": ["name", "role", "prompt"],
            },
        },
        {
            "name": "list_teammates",
            "description": "List all teammates.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "send_message",
            "description": "Send a message to a teammate.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "content": {"type": "string"},
                    "msg_type": {
                        "type": "string",
                        "enum": list(protocol.VALID_MSG_TYPES),
                    },
                },
                "required": ["to", "content"],
            },
        },
        {
            "name": "read_inbox",
            "description": "Read and drain the lead's inbox.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "broadcast",
            "description": "Send message to all teammates.",
            "input_schema": {
                "type": "object",
                "properties": {"content": {"type": "string"}},
                "required": ["content"],
            },
        },
        {
            "name": "shutdown_request",
            "description": "Request a teammate to shut down.",
            "input_schema": {
                "type": "object",
                "properties": {"teammate": {"type": "string"}},
                "required": ["teammate"],
            },
        },
        {
            "name": "plan_approval",
            "description": "Approve or reject a teammate's plan.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string"},
                    "approve": {"type": "boolean"},
                    "feedback": {"type": "string"},
                },
                "required": ["request_id", "approve"],
            },
        },
        {
            "name": "idle",
            "description": "Enter idle state.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "claim_task",
            "description": "Claim a task from the board.",
            "input_schema": {
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
            },
        },
    ]

    return tools, handlers

