from __future__ import annotations

"""
Simple entrypoint for the localdev agent.

Usage (from repository root or this directory):
    python3 run.py

This file adds the local `src` directory to sys.path so that the
`localdev` package can be imported without installation.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from localdev.cli.repl import run_repl  # noqa: E402


def main() -> None:
    run_repl()


if __name__ == "__main__":
    main()

