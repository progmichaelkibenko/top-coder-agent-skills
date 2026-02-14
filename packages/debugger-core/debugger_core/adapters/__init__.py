"""Debug adapter implementations for various runtimes.

Node.js uses CDP (Chrome DevTools Protocol) directly via
``cdp_client.py`` -- no adapter needed (just ``node`` on PATH).

Python uses DAP via the ``PythonAdapter`` (debugpy).
"""

from debugger_core.adapters.base import DebugAdapter
from debugger_core.adapters.python import PythonAdapter

__all__ = ["DebugAdapter", "PythonAdapter"]
