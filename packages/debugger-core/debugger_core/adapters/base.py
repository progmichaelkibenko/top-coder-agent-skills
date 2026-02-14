"""Abstract base for debug adapters."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any


class DebugAdapter(ABC):
    """Base class for runtime-specific debug adapters.

    Each subclass knows how to:
    * Locate the adapter binary on disk.
    * Build the command to spawn it.
    * Build the ``launch`` arguments that the DAP client sends.
    """

    @property
    @abstractmethod
    def adapter_id(self) -> str:
        """Short identifier used in the DAP ``initialize`` request."""

    @abstractmethod
    def get_spawn_command(self) -> list[str]:
        """Return the command + args to start the adapter subprocess."""

    @abstractmethod
    def get_launch_args(
        self, program: str, cwd: str | None = None
    ) -> dict[str, Any]:
        """Return the ``arguments`` dict for the DAP ``launch`` request."""

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_cwd(program: str, cwd: str | None) -> str:
        if cwd:
            return os.path.abspath(cwd)
        return os.path.dirname(os.path.abspath(program)) or os.getcwd()
