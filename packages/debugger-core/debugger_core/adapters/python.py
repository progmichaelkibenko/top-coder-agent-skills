"""Python debug adapter using debugpy.

debugpy is Microsoft's DAP-compliant debug adapter for Python.
It ships as a regular pip package and can run as a standalone
DAP adapter over stdin/stdout.

Install:  pip install debugpy
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import Any

from debugger_core.adapters.base import DebugAdapter


def _find_debugpy_adapter() -> str:
    """Locate the debugpy adapter entry-point.

    debugpy exposes a DAP adapter via ``python -m debugpy.adapter``.
    We just need to verify the module is importable.
    """
    # Quick check: try to find the package without importing it.
    import importlib.util

    spec = importlib.util.find_spec("debugpy")
    if spec is None:
        raise FileNotFoundError(
            "Cannot find debugpy.  Install it with:  pip install debugpy"
        )
    return "debugpy.adapter"


class PythonAdapter(DebugAdapter):
    """Adapter for debugging Python applications via debugpy."""

    def __init__(self, python_path: str | None = None) -> None:
        self._python = python_path or sys.executable or shutil.which("python3") or "python3"
        # Verify debugpy is available at construction time.
        self._module = _find_debugpy_adapter()

    @property
    def adapter_id(self) -> str:
        return "debugpy"

    def get_spawn_command(self) -> list[str]:
        return [self._python, "-m", self._module]

    def get_launch_args(
        self, program: str, cwd: str | None = None
    ) -> dict[str, Any]:
        return {
            "type": "debugpy",
            "request": "launch",
            "name": "Debug Python",
            "program": os.path.abspath(program),
            "cwd": self._resolve_cwd(program, cwd),
            "console": "internalConsole",
            "justMyCode": True,
        }
