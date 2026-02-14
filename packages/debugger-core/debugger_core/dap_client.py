"""
Core DAP (Debug Adapter Protocol) client.

Speaks the DAP JSON-RPC protocol over stdin/stdout to any DAP-compliant
debug adapter (vscode-node-debug2, debugpy, delve, etc.).

This is the lowest-level building block -- higher-level orchestration
lives in session.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine

from debugger_core.adapters.base import DebugAdapter
from debugger_core.protocol import (
    TIMEOUT_DISCONNECT,
    TIMEOUT_LAUNCH,
    DebugMessage,
    wait_for_stop_or_terminate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

DAPMessage = DebugMessage
EventCallback = Callable[[DAPMessage], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# DAP Client
# ---------------------------------------------------------------------------


class DAPClient:
    """Async DAP client that communicates with a debug adapter subprocess.

    Lifecycle::

        client = DAPClient(adapter)
        await client.start()          # spawns adapter, sends 'initialize'
        await client.launch(...)      # sends 'launch' + 'configurationDone'
        await client.set_breakpoints(...)
        await client.continue_()      # blocks until next stop event
        ...
        await client.disconnect()     # tears down
    """

    def __init__(self, adapter: DebugAdapter) -> None:
        self._adapter = adapter
        self._process: asyncio.subprocess.Process | None = None
        self._seq: int = 1
        self._pending: dict[int, asyncio.Future[DAPMessage]] = {}
        self._reader_task: asyncio.Task[None] | None = None

        # Resolves when the debuggee pauses (breakpoint / step / exception).
        self.stopped_event: asyncio.Future[DAPMessage] | None = None

        # Resolves when the adapter fires 'terminated'.
        self.terminated_event: asyncio.Future[None] | None = None

        # Resolves when the adapter fires 'initialized' (ready for breakpoints).
        self._initialized_event: asyncio.Future[None] | None = None

        # Task for the in-flight ``launch`` request (completed after configurationDone).
        self._launch_task: asyncio.Task[DAPMessage] | None = None

        # Optional external listener for *all* events.
        self.on_event: EventCallback | None = None

        # Collected stdout/stderr from the debuggee (via 'output' events).
        self.output_lines: list[str] = []

        # Track whether configurationDone has been sent.
        self._configured: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> DAPMessage:
        """Spawn the adapter subprocess and send ``initialize``."""
        cmd = self._adapter.get_spawn_command()
        logger.info("Spawning adapter: %s", " ".join(cmd))

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._reader_task = asyncio.create_task(self._read_loop())

        return await self._request(
            "initialize",
            {
                "adapterID": self._adapter.adapter_id,
                "clientID": "top-coder-ai-skills-debugger",
                "clientName": "top-coder-ai-skills-debugger",
                "linesStartAt1": True,
                "columnsStartAt1": True,
                "pathFormat": "path",
                "supportsRunInTerminalRequest": False,
            },
        )

    async def launch(self, program: str, cwd: str | None = None) -> DAPMessage:
        """Send ``launch`` and wait for the adapter to be ready.

        Per the DAP spec the adapter sends an ``initialized`` event
        after receiving ``launch``.  At that point breakpoints can be
        set.  ``configurationDone`` is deferred until the first
        ``continue_()`` call so breakpoints are registered before the
        debuggee starts running.
        """
        launch_args = self._adapter.get_launch_args(program, cwd)

        # Prepare to catch the 'initialized' event.
        self._initialized_event = asyncio.get_running_loop().create_future()

        # Send launch (don't await -- adapter won't respond until
        # configurationDone for some adapters like debugpy).
        launch_task = asyncio.ensure_future(self._request("launch", launch_args))

        # Wait for the 'initialized' event (adapter is ready for breakpoints).
        await asyncio.wait_for(self._initialized_event, timeout=TIMEOUT_LAUNCH)

        # Store the launch task -- it will complete after configurationDone.
        self._launch_task = launch_task
        return {}

    async def _ensure_configured(self) -> None:
        """Send ``configurationDone`` once, completing the launch sequence."""
        if self._configured:
            return
        self._configured = True
        await self._request("configurationDone", {})
        # Now the launch response should come back.
        if self._launch_task is not None and not self._launch_task.done():
            await asyncio.wait_for(self._launch_task, timeout=TIMEOUT_LAUNCH)

    async def disconnect(self) -> None:
        """Gracefully disconnect and kill the adapter."""
        if self._process and self._process.returncode is None:
            try:
                await asyncio.wait_for(
                    self._request(
                        "disconnect", {"restart": False, "terminateDebuggee": True}
                    ),
                    timeout=TIMEOUT_DISCONNECT,
                )
            except Exception:
                pass  # best-effort
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=TIMEOUT_DISCONNECT)
            except asyncio.TimeoutError:
                self._process.kill()

        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        self._pending.clear()
        self._process = None

    # ------------------------------------------------------------------
    # DAP requests
    # ------------------------------------------------------------------

    async def set_breakpoints(
        self, file_path: str, lines: list[int]
    ) -> DAPMessage:
        """Set breakpoints for *file_path*. Replaces any previous set."""
        return await self._request(
            "setBreakpoints",
            {
                "source": {"path": file_path},
                "lines": lines,
                "breakpoints": [{"line": ln} for ln in lines],
            },
        )

    async def continue_(self, thread_id: int = 1) -> DAPMessage:
        """Resume execution. Blocks until the next ``stopped`` event.

        On the first call, sends ``configurationDone`` which starts
        the debuggee (breakpoints should already be set).

        If the program terminates before hitting a breakpoint, returns
        a synthetic stopped body with ``reason: "terminated"``.
        """
        self.stopped_event = asyncio.get_running_loop().create_future()
        self.terminated_event = asyncio.get_running_loop().create_future()

        if not self._configured:
            await self._ensure_configured()
        else:
            await self._request("continue", {"threadId": thread_id})

        return await wait_for_stop_or_terminate(
            self.stopped_event, self.terminated_event,
        )

    async def next_(self, thread_id: int = 1) -> DAPMessage:
        """Step over. Blocks until the next ``stopped`` event."""
        self.stopped_event = asyncio.get_running_loop().create_future()
        self.terminated_event = asyncio.get_running_loop().create_future()
        await self._request("next", {"threadId": thread_id})
        return await wait_for_stop_or_terminate(
            self.stopped_event, self.terminated_event,
        )

    async def step_in(self, thread_id: int = 1) -> DAPMessage:
        """Step into. Blocks until the next ``stopped`` event."""
        self.stopped_event = asyncio.get_running_loop().create_future()
        self.terminated_event = asyncio.get_running_loop().create_future()
        await self._request("stepIn", {"threadId": thread_id})
        return await wait_for_stop_or_terminate(
            self.stopped_event, self.terminated_event,
        )

    async def stack_trace(
        self, thread_id: int = 1, levels: int = 20
    ) -> DAPMessage:
        """Return the current stack trace."""
        return await self._request(
            "stackTrace",
            {"threadId": thread_id, "startFrame": 0, "levels": levels},
        )

    async def scopes(self, frame_id: int) -> DAPMessage:
        """Return scopes for a given stack frame."""
        return await self._request("scopes", {"frameId": frame_id})

    async def variables(self, variables_reference: int) -> DAPMessage:
        """Return variables for a given variables reference."""
        return await self._request(
            "variables", {"variablesReference": variables_reference}
        )

    async def evaluate(
        self,
        expression: str,
        frame_id: int | None = None,
        context: str = "repl",
    ) -> DAPMessage:
        """Evaluate an expression in the given frame."""
        args: dict[str, Any] = {
            "expression": expression,
            "context": context,
        }
        if frame_id is not None:
            args["frameId"] = frame_id
        return await self._request("evaluate", args)

    async def threads(self) -> DAPMessage:
        """Return active threads."""
        return await self._request("threads", {})

    # ------------------------------------------------------------------
    # Protocol internals
    # ------------------------------------------------------------------

    def _fail_pending(self, reason: str) -> None:
        """Reject all in-flight request futures so callers don't hang."""
        err = ConnectionError(reason)
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(err)
        self._pending.clear()

    async def _request(self, command: str, arguments: dict[str, Any]) -> DAPMessage:
        """Send a DAP request and wait for the matching response."""
        seq = self._seq
        self._seq += 1

        msg: DAPMessage = {
            "seq": seq,
            "type": "request",
            "command": command,
            "arguments": arguments,
        }

        payload = json.dumps(msg)
        header = f"Content-Length: {len(payload)}\r\n\r\n"

        assert self._process and self._process.stdin
        self._process.stdin.write((header + payload).encode("utf-8"))
        await self._process.stdin.drain()

        logger.debug("-> DAP request seq=%d cmd=%s", seq, command)

        loop = asyncio.get_running_loop()
        fut: asyncio.Future[DAPMessage] = loop.create_future()
        self._pending[seq] = fut
        return await fut

    async def _read_loop(self) -> None:
        """Background task that reads DAP messages from adapter stdout."""
        assert self._process and self._process.stdout
        reader = self._process.stdout

        try:
            while True:
                # -- Read header ------------------------------------------
                raw_header = await reader.readuntil(b"\r\n\r\n")
                header_str = raw_header.decode("utf-8")
                content_length = _parse_content_length(header_str)

                # -- Read body --------------------------------------------
                body_bytes = await reader.readexactly(content_length)
                msg: DAPMessage = json.loads(body_bytes.decode("utf-8"))

                msg_type = msg.get("type")

                if msg_type == "response":
                    await self._handle_response(msg)
                elif msg_type == "event":
                    await self._handle_event(msg)
                else:
                    logger.debug("Ignoring DAP message type=%s", msg_type)

        except asyncio.CancelledError:
            return  # don't touch futures on intentional cancel
        except asyncio.IncompleteReadError:
            logger.debug("Adapter closed the stream.")
        except Exception:
            logger.exception("Error in DAP read loop")

        # Reject any in-flight requests so callers don't hang.
        self._fail_pending("Adapter connection lost.")

    async def _handle_response(self, msg: DAPMessage) -> None:
        req_seq: int = msg.get("request_seq", -1)
        fut = self._pending.pop(req_seq, None)
        if fut is None or fut.done():
            return

        if msg.get("success"):
            fut.set_result(msg.get("body", {}))
        else:
            error_msg = msg.get("message", "Unknown DAP error")
            fut.set_exception(RuntimeError(f"DAP error: {error_msg}"))

    async def _handle_event(self, msg: DAPMessage) -> None:
        event = msg.get("event", "")
        body = msg.get("body", {})
        logger.debug("<- DAP event: %s", event)

        if event == "initialized":
            if self._initialized_event and not self._initialized_event.done():
                self._initialized_event.set_result(None)

        elif event == "stopped":
            if self.stopped_event and not self.stopped_event.done():
                self.stopped_event.set_result(body)

        elif event == "terminated":
            if self.terminated_event and not self.terminated_event.done():
                self.terminated_event.set_result(None)

        elif event == "output":
            category = body.get("category", "")
            output_text = body.get("output", "")
            if category in ("stdout", "stderr", "console"):
                self.output_lines.append(output_text.rstrip("\n"))

        if self.on_event:
            try:
                await self.on_event(msg)
            except Exception:
                logger.exception("Error in on_event callback")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_content_length(header: str) -> int:
    """Extract Content-Length from a DAP header block."""
    for line in header.strip().splitlines():
        if line.lower().startswith("content-length:"):
            return int(line.split(":", 1)[1].strip())
    raise ValueError(f"No Content-Length in header: {header!r}")
