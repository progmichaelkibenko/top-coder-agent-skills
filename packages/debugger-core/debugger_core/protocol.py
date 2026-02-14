"""Shared protocol and utilities for debug clients.

Defines :class:`DebugClient` -- the formal contract that both
:class:`DAPClient` and :class:`CDPClient` must satisfy.  Having an
explicit Protocol means the type checker will catch API drift between
the two implementations at lint time, not at runtime.

Also provides :func:`wait_for_stop_or_terminate`, the single shared
implementation of the "race stopped vs. terminated" pattern used by
both clients.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

DebugMessage = dict[str, Any]

# ---------------------------------------------------------------------------
# Timeout constants (seconds)
# ---------------------------------------------------------------------------

TIMEOUT_RESUME: float = 30.0
"""How long ``continue_``/``next_``/``step_in`` wait for the debuggee to
pause again before raising :class:`asyncio.TimeoutError`."""

TIMEOUT_LAUNCH: float = 10.0
"""How long to wait for the debug adapter to initialise / launch."""

TIMEOUT_DISCONNECT: float = 3.0
"""Grace period for the adapter subprocess to exit before being killed."""

TIMEOUT_READLINE: float = 5.0
"""Per-line read timeout when parsing adapter output (e.g. WS URL)."""

TIMEOUT_DAEMON_CMD: float = 120.0
"""How long a skill-script invocation waits for a daemon response."""


# ---------------------------------------------------------------------------
# DebugClient protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class DebugClient(Protocol):
    """Contract shared by :class:`DAPClient` and :class:`CDPClient`.

    ``DebugSession`` depends on this interface, not on concrete classes.
    """

    stopped_event: asyncio.Future[DebugMessage] | None
    terminated_event: asyncio.Future[None] | None
    output_lines: list[str]

    async def start(self) -> DebugMessage: ...
    async def launch(self, program: str, cwd: str | None = None) -> DebugMessage: ...
    async def disconnect(self) -> None: ...

    async def set_breakpoints(self, file_path: str, lines: list[int]) -> DebugMessage: ...
    async def continue_(self, thread_id: int = 1) -> DebugMessage: ...
    async def next_(self, thread_id: int = 1) -> DebugMessage: ...
    async def step_in(self, thread_id: int = 1) -> DebugMessage: ...

    async def stack_trace(self, thread_id: int = 1, levels: int = 20) -> DebugMessage: ...
    async def scopes(self, frame_id: int) -> DebugMessage: ...
    async def variables(self, variables_reference: int) -> DebugMessage: ...
    async def evaluate(
        self,
        expression: str,
        frame_id: int | None = None,
        context: str = "repl",
    ) -> DebugMessage: ...
    async def threads(self) -> DebugMessage: ...


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

_TERMINATED_BODY: DebugMessage = {
    "reason": "terminated",
    "description": "Program exited.",
}


async def wait_for_stop_or_terminate(
    stopped: asyncio.Future[DebugMessage],
    terminated: asyncio.Future[None],
    timeout: float = TIMEOUT_RESUME,
) -> DebugMessage:
    """Wait for either a *stopped* or *terminated* event.

    Returns the stopped body if the debuggee paused, or a synthetic
    ``{"reason": "terminated"}`` body if the program exited.

    Raises :class:`asyncio.TimeoutError` if neither event fires within
    *timeout* seconds.
    """
    done, pending = await asyncio.wait(
        [stopped, terminated],
        timeout=timeout,
        return_when=asyncio.FIRST_COMPLETED,
    )

    for fut in pending:
        fut.cancel()

    if not done:
        raise asyncio.TimeoutError("No stop or terminate within timeout.")

    winner = done.pop()
    if winner is stopped:
        return winner.result()

    return dict(_TERMINATED_BODY)  # return a fresh copy each time
