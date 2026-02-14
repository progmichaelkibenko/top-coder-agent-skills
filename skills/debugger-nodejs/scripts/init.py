#!/usr/bin/env python3
"""Ensure top-coder-ai-skills-debugger is installed for this skill.

Run once before using the debugger (e.g. after installing the skill).
Uses the same Python that will run debug.py, so the package is available
when you run debug commands.

Usage: python scripts/init.py
"""

from __future__ import annotations

import subprocess
import sys

PACKAGE = "top-coder-ai-skills-debugger"


def _have_package() -> bool:
    try:
        __import__("debugger_core")
        return True
    except ModuleNotFoundError:
        return False


def main() -> int:
    if _have_package():
        print(f"{PACKAGE} is already installed.")
        return 0

    print(f"Installing {PACKAGE}...")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", PACKAGE],
        capture_output=False,
    )
    if r.returncode != 0:
        print(
            f"Install failed. You can install manually:\n"
            f"  pip install {PACKAGE}\n"
            f"  uv add {PACKAGE}   (in a uv project)\n"
            f"  poetry add {PACKAGE}   (in a Poetry project)",
            file=sys.stderr,
        )
        return 1

    if not _have_package():
        print("Install completed but package still not found. Try restarting your shell.", file=sys.stderr)
        return 1

    print(f"{PACKAGE} is ready. You can run debug.py now.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
