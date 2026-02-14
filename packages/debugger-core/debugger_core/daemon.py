"""Background session daemon for interactive skill-script debugging.

Holds the debugger connection (CDP or DAP) alive between separate CLI
invocations.  Skill scripts communicate with the daemon over a TCP
socket on ``127.0.0.1``.

Launched automatically by :pymethod:`DebugSession.start` when the
session is file-backed.  Not used by the MCP server (which keeps its
own long-lived ``DebugSession`` in-process).

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
from typing import Any

logger = logging.getLogger(__name__)


class SessionDaemon:
    """TCP server that wraps a live :class:`DebugSession`."""

    def __init__(self, port: int) -> None:
        self.port = port
        self._session: Any = None  # DebugSession (imported lazily)
        self._shutdown = asyncio.Event()

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    async def start_and_serve(self, program: str, language: str) -> None:
        """Launch the debugger and start accepting commands over TCP."""
        # Import here to avoid circular import (session imports daemon path).
        from debugger_core.session import DebugSession  # noqa: PLC0415

        self._session = DebugSession()
        result = await self._session.start(program, language)

        if result.startswith("Error"):
            # Signal failure to the parent process that spawned us.
            print(json.dumps({"error": result}), flush=True)
            sys.exit(1)

        server = await asyncio.start_server(
            self._handle_client, "127.0.0.1", self.port,
        )

        # Tell the parent we're ready (it reads this line from stdout).
        addr = server.sockets[0].getsockname()
        print(json.dumps({"ready": True, "port": addr[1]}), flush=True)

        async with server:
            await self._shutdown.wait()

        # Graceful teardown -- stop the debugger & node/python process.
        try:
            await self._session.stop()
        except Exception:
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
            raw = await asyncio.wait_for(reader.readline(), timeout=120)
            if not raw:
                return

            cmd: dict[str, Any] = json.loads(raw.decode())
            result = await self._dispatch(cmd)

            writer.write(json.dumps({"result": result}).encode() + b"\n")
            await writer.drain()
        except Exception as exc:
            try:
                writer.write(
                    json.dumps({"error": str(exc)}).encode() + b"\n"
                )
                await writer.drain()
            except Exception:
                pass
        finally:
            writer.close()
            await writer.wait_closed()

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, cmd: dict[str, Any]) -> str:
        action = cmd.get("action", "")

        if action == "breakpoint":
            return await self._session.add_breakpoint(
                file=cmd["file"], line=int(cmd["line"]),
            )

        if action == "resume":
            return await self._session.resume()

        if action == "step":
            return await self._session.step(cmd.get("step_action", "next"))

        if action == "inspect":
            return await self._session.inspect(cmd["expression"])

        if action == "variables":
            return await self._session.get_local_variables()

        if action == "stack":
            return await self._session.get_stack()

        if action == "stop":
            self._shutdown.set()
            return "Debug session ended."

        return f"Unknown daemon action: {action}"


# ---------------------------------------------------------------------------
# CLI entry-point (launched by DebugSession._start_daemon)
# ---------------------------------------------------------------------------


async def _amain() -> None:
    parser = argparse.ArgumentParser(description="debugger-core session daemon")
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
