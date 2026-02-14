"""Background session daemon for interactive skill-script debugging.

Holds the debugger connection (CDP or DAP) alive between separate CLI
invocations.  Skill scripts communicate with the daemon over a TCP
socket on ``127.0.0.1``.

Launched automatically by :meth:`DebugSession.start` when the session
is file-backed.  Not used by the MCP server (which keeps its own
long-lived ``DebugSession`` in-process).

CLI (used by session.py -- not called directly)::

    python -m debugger_core.daemon \\
        --port PORT --language LANG --program FILE
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import TYPE_CHECKING, Any, Callable, Awaitable

from debugger_core.protocol import TIMEOUT_DAEMON_CMD

if TYPE_CHECKING:
    from debugger_core.session import DebugSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Daemon action type
# ---------------------------------------------------------------------------

DaemonAction = Callable[["SessionDaemon", dict[str, Any]], Awaitable[str]]


# ---------------------------------------------------------------------------
# SessionDaemon
# ---------------------------------------------------------------------------


class SessionDaemon:
    """TCP server that wraps a live :class:`DebugSession`.

    Actions are dispatched via ``_ACTION_TABLE`` (strategy pattern),
    keeping the handler logic small and extensible.
    """

    def __init__(self, port: int) -> None:
        self.port = port
        self.session: DebugSession | None = None
        self.shutdown_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    async def start_and_serve(self, program: str, language: str) -> None:
        """Launch the debugger and start accepting commands over TCP."""
        # Import here to avoid circular import (session imports daemon path).
        from debugger_core.session import DebugSession  # noqa: PLC0415

        self.session = DebugSession()
        result = await self.session.start(program, language)

        if result.startswith("Error"):
            print(json.dumps({"error": result}), flush=True)
            sys.exit(1)

        tcp_server = await asyncio.start_server(
            self._handle_client, "127.0.0.1", self.port,
        )

        # Signal readiness to the parent process (reads this from stdout).
        addr = tcp_server.sockets[0].getsockname()
        print(json.dumps({"ready": True, "port": addr[1]}), flush=True)

        async with tcp_server:
            await self.shutdown_event.wait()

        # Graceful teardown.
        try:
            await self.session.stop()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # TCP client handler
    # ------------------------------------------------------------------

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            raw = await asyncio.wait_for(reader.readline(), timeout=TIMEOUT_DAEMON_CMD)
            if not raw:
                return

            cmd: dict[str, Any] = json.loads(raw.decode())
            result = await self._dispatch(cmd)

            writer.write(json.dumps({"result": result}).encode() + b"\n")
            await writer.drain()
        except Exception as exc:  # noqa: BLE001 - daemon must not crash on bad input
            try:
                writer.write(
                    json.dumps({"error": str(exc)}).encode() + b"\n"
                )
                await writer.drain()
            except Exception:  # noqa: BLE001
                pass
        finally:
            writer.close()
            await writer.wait_closed()

    # ------------------------------------------------------------------
    # Command dispatch (strategy table)
    # ------------------------------------------------------------------

    async def _dispatch(self, cmd: dict[str, Any]) -> str:
        action_name = cmd.get("action", "")
        handler = _ACTION_TABLE.get(action_name)
        if handler is None:
            return f"Unknown daemon action: {action_name}"
        return await handler(self, cmd)


# ---------------------------------------------------------------------------
# Action strategies
# ---------------------------------------------------------------------------


async def _do_breakpoint(daemon: SessionDaemon, cmd: dict[str, Any]) -> str:
    assert daemon.session is not None
    return await daemon.session.add_breakpoint(
        file=cmd["file"], line=int(cmd["line"]),
    )


async def _do_resume(daemon: SessionDaemon, _cmd: dict[str, Any]) -> str:
    assert daemon.session is not None
    return await daemon.session.resume()


async def _do_step(daemon: SessionDaemon, cmd: dict[str, Any]) -> str:
    assert daemon.session is not None
    return await daemon.session.step(cmd.get("step_action", "next"))


async def _do_inspect(daemon: SessionDaemon, cmd: dict[str, Any]) -> str:
    assert daemon.session is not None
    return await daemon.session.inspect(cmd["expression"])


async def _do_variables(daemon: SessionDaemon, _cmd: dict[str, Any]) -> str:
    assert daemon.session is not None
    return await daemon.session.get_local_variables()


async def _do_stack(daemon: SessionDaemon, _cmd: dict[str, Any]) -> str:
    assert daemon.session is not None
    return await daemon.session.get_stack()


async def _do_stop(daemon: SessionDaemon, _cmd: dict[str, Any]) -> str:
    daemon.shutdown_event.set()
    return "Debug session ended."


_ACTION_TABLE: dict[str, DaemonAction] = {
    "breakpoint": _do_breakpoint,
    "resume":     _do_resume,
    "step":       _do_step,
    "inspect":    _do_inspect,
    "variables":  _do_variables,
    "stack":      _do_stack,
    "stop":       _do_stop,
}


# ---------------------------------------------------------------------------
# CLI entry-point (launched by DebugSession._start_daemon)
# ---------------------------------------------------------------------------


async def _amain() -> None:
    parser = argparse.ArgumentParser(description="top-coder-ai-skills-debugger session daemon")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--language", required=True)
    parser.add_argument("--program", required=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

    daemon = SessionDaemon(port=args.port)
    await daemon.start_and_serve(
        program=args.program, language=args.language,
    )


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
