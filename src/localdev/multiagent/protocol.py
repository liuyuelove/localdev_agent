from __future__ import annotations

import uuid
from typing import Dict

from localdev.multiagent.bus import MessageBus


VALID_MSG_TYPES = {
    "message",
    "broadcast",
    "shutdown_request",
    "shutdown_response",
    "plan_approval_response",
}

shutdown_requests: Dict[str, dict] = {}
plan_requests: Dict[str, dict] = {}


def handle_shutdown_request(bus: MessageBus, teammate: str, sender: str = "lead") -> str:
    """Initiate a shutdown request for a teammate."""
    req_id = str(uuid.uuid4())[:8]
    shutdown_requests[req_id] = {"target": teammate, "status": "pending"}
    bus.send(sender, teammate, "Please shut down.", "shutdown_request", {"request_id": req_id})
    return f"Shutdown request {req_id} sent to '{teammate}'"


def handle_plan_review(bus: MessageBus, request_id: str, approve: bool, feedback: str = "", sender: str = "lead") -> str:
    """Approve or reject a teammate's plan."""
    req = plan_requests.get(request_id)
    if not req:
        return f"Error: Unknown plan request_id '{request_id}'"
    req["status"] = "approved" if approve else "rejected"
    bus.send(
        sender,
        req["from"],
        feedback,
        "plan_approval_response",
        {"request_id": request_id, "approve": approve, "feedback": feedback},
    )
    return f"Plan {req['status']} for '{req['from']}'"

