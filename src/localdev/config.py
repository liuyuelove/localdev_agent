import os
from pathlib import Path

from dotenv import load_dotenv
from anthropic import Anthropic


load_dotenv(override=True)


def get_workdir() -> Path:
    """Root workspace directory for the agent."""
    return Path.cwd()


WORKDIR = get_workdir()

TEAM_DIR = WORKDIR / ".team"
INBOX_DIR = TEAM_DIR / "inbox"
TASKS_DIR = WORKDIR / ".tasks"
SKILLS_DIR = WORKDIR / "skills"
TRANSCRIPT_DIR = WORKDIR / ".transcripts"

TOKEN_THRESHOLD = 100000
POLL_INTERVAL = 5
IDLE_TIMEOUT = 300  # 5 minutes; teammate stays alive during short user pauses


def make_client() -> Anthropic:
    """Create an Anthropic client using environment configuration."""
    # Mirror s_full.py behavior: if base URL is set, clear default token env
    if os.getenv("ANTHROPIC_BASE_URL"):
        os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
    return Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))


MODEL_ID = os.environ["MODEL_ID"]
CLIENT = make_client()

