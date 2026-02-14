"""Node.js debug adapter using vscode-node-debug2.

vscode-node-debug2 is a standalone DAP adapter that speaks
JSON-RPC over stdin/stdout.  Despite the "vscode" prefix it
runs perfectly fine outside of VS Code.

The adapter is **auto-installed** on first use into a local cache
directory (~/.debugger-core/adapters/).  No manual ``npm install``
is required -- only ``node`` and ``npm`` must be on PATH.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Any

from debugger_core.adapters.base import DebugAdapter

logger = logging.getLogger(__name__)

# Where we auto-install the adapter when it is not found globally.
_CACHE_DIR = os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
    "debugger-core",
    "adapters",
)

_ADAPTER_ENTRY = os.path.join(
    "node_modules", "vscode-node-debug2", "out", "src", "nodeDebug.js"
)

# Well-known global install locations (checked first).
_GLOBAL_CANDIDATES = [
    "/usr/local/lib/node_modules/vscode-node-debug2/out/src/nodeDebug.js",
    "/usr/lib/node_modules/vscode-node-debug2/out/src/nodeDebug.js",
    "/opt/homebrew/lib/node_modules/vscode-node-debug2/out/src/nodeDebug.js",
]


# ---------------------------------------------------------------------------
# Locate or auto-install
# ---------------------------------------------------------------------------


def _find_in_global() -> str | None:
    """Check well-known global npm paths and ``npm root -g``."""
    for path in _GLOBAL_CANDIDATES:
        if os.path.isfile(path):
            return path

    npm = shutil.which("npm")
    if npm:
        result = subprocess.run(
            [npm, "root", "-g"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            candidate = os.path.join(
                result.stdout.strip(),
                "vscode-node-debug2",
                "out",
                "src",
                "nodeDebug.js",
            )
            if os.path.isfile(candidate):
                return candidate

    return None


def _find_in_cache() -> str | None:
    """Check our local cache directory."""
    candidate = os.path.join(_CACHE_DIR, _ADAPTER_ENTRY)
    return candidate if os.path.isfile(candidate) else None


def _auto_install() -> str:
    """Install vscode-node-debug2 into the local cache via npm."""
    npm = shutil.which("npm")
    if not npm:
        raise FileNotFoundError(
            "Cannot auto-install vscode-node-debug2: npm is not on PATH.  "
            "Install Node.js (https://nodejs.org) first."
        )

    os.makedirs(_CACHE_DIR, exist_ok=True)
    logger.info(
        "Auto-installing vscode-node-debug2 into %s (one-time setup)...",
        _CACHE_DIR,
    )

    result = subprocess.run(
        [npm, "install", "--no-save", "vscode-node-debug2"],
        cwd=_CACHE_DIR,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"npm install vscode-node-debug2 failed (exit {result.returncode}):\n"
            f"{result.stderr}"
        )

    entry = os.path.join(_CACHE_DIR, _ADAPTER_ENTRY)
    if not os.path.isfile(entry):
        raise FileNotFoundError(
            f"npm install succeeded but {entry} not found.  "
            "Try installing manually:  npm install -g vscode-node-debug2"
        )

    logger.info("vscode-node-debug2 installed successfully.")
    return entry


def _find_or_install_adapter() -> str:
    """Locate the adapter, auto-installing if necessary.

    Search order:
    1. Global npm installs (fast, no side-effects).
    2. Local cache (~/.cache/debugger-core/adapters/).
    3. Auto-install into the cache via ``npm install``.
    """
    path = _find_in_global()
    if path:
        return path

    path = _find_in_cache()
    if path:
        return path

    return _auto_install()


# ---------------------------------------------------------------------------
# Adapter class
# ---------------------------------------------------------------------------


class NodeAdapter(DebugAdapter):
    """Adapter for debugging Node.js applications via vscode-node-debug2.

    On first use, the adapter is automatically installed into
    ``~/.cache/debugger-core/adapters/`` if it is not already present
    globally.  Only ``node`` and ``npm`` need to be on PATH.
    """

    def __init__(self, adapter_path: str | None = None) -> None:
        self._adapter_path = adapter_path or _find_or_install_adapter()

    @property
    def adapter_id(self) -> str:
        return "node2"

    def get_spawn_command(self) -> list[str]:
        node = shutil.which("node")
        if not node:
            raise FileNotFoundError("node executable not found on PATH")
        return [node, self._adapter_path]

    def get_launch_args(
        self, program: str, cwd: str | None = None
    ) -> dict[str, Any]:
        return {
            "type": "node2",
            "request": "launch",
            "name": "Debug Node",
            "program": os.path.abspath(program),
            "cwd": self._resolve_cwd(program, cwd),
            "sourceMaps": False,
            "console": "internalConsole",
        }
