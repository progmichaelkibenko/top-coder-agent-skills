"""
Chrome DevTools Protocol (CDP) client for Node.js debugging.

Spawns ``node --inspect-brk`` and communicates with V8's built-in
inspector over WebSocket.  Zero npm dependencies required -- only
``node`` on PATH.

Implements the :class:`~debugger_core.protocol.DebugClient` protocol
(same public API as ``DAPClient``), so ``DebugSession`` can use
either client transparently.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
from typing import Any

import websockets

from debugger_core.protocol import (
    TIMEOUT_DISCONNECT,
    TIMEOUT_LAUNCH,
    TIMEOUT_READLINE,
    DebugMessage,
    wait_for_stop_or_terminate,
)

logger = logging.getLogger(__name__)

# CDPMessage is kept as a local alias for readability in this file.
CDPMessage = DebugMessage

# ---------------------------------------------------------------------------
# CDP Client
# ---------------------------------------------------------------------------


class CDPClient:
    """Async CDP client that debugs Node.js via ``--inspect-brk``.

    Lifecycle (same as DAPClient)::

        client = CDPClient()
        await client.start()
        await client.launch(program)
        await client.set_breakpoints(file, [10, 20])
        await client.continue_()
        ...
        await client.disconnect()
    """

    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._ws: websockets.ClientConnection | None = None
        self._msg_id: int = 1
        self._pending: dict[int, asyncio.Future[CDPMessage]] = {}
        self._reader_task: asyncio.Task[None] | None = None

        # Public surface (satisfies DebugClient protocol):
        self.stopped_event: asyncio.Future[CDPMessage] | None = None
        self.terminated_event: asyncio.Future[None] | None = None
        self.on_event = None
        self.output_lines: list[str] = []

        # Internal CDP state
        self._scripts: dict[str, str] = {}  # scriptId -> url
        self._breakpoint_ids: dict[str, list[str]] = {}  # file -> [breakpointId]

        # Frame / variable state -- per-instance, NOT class-level.
        self._last_call_frames: list[CDPMessage] = []
        self._last_stack_frames: list[CDPMessage] = []
        self._object_ids: dict[int, str] = {}
        self._next_var_ref: int = 1

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> CDPMessage:
        """No-op for CDP (adapter == node itself). Returns empty dict."""
        return {}

    async def launch(self, program: str, cwd: str | None = None) -> CDPMessage:
        """Spawn ``node --inspect-brk=0 <program>`` and connect via WS."""
        node = shutil.which("node")
        if not node:
            raise FileNotFoundError("node executable not found on PATH")

        resolved_cwd = cwd or os.path.dirname(os.path.abspath(program)) or os.getcwd()

        self._process = await asyncio.create_subprocess_exec(
            node,
            "--inspect-brk=0",
            os.path.abspath(program),
            cwd=resolved_cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Parse the WebSocket URL from stderr.
        ws_url = await self._read_ws_url()
        logger.info("Connecting to Node inspector at %s", ws_url)

        self._ws = await websockets.connect(
            ws_url,
            max_size=10 * 1024 * 1024,
            ping_interval=None,  # Node inspector doesn't respond to WS pings.
        )
        self._reader_task = asyncio.create_task(self._read_loop())

        # Enable debugger and runtime domains.
        await self._send("Debugger.enable", {})
        await self._send("Runtime.enable", {})

        # --inspect-brk pauses before the first line.  Wait for the
        # initial Debugger.paused event so we are in a known state.
        self.stopped_event = asyncio.get_running_loop().create_future()
        await self._send("Runtime.runIfWaitingForDebugger", {})
        await asyncio.wait_for(self.stopped_event, timeout=TIMEOUT_LAUNCH)
        self.stopped_event = None  # consumed; ready for breakpoints

        return {}

    async def disconnect(self) -> None:
        """Kill the node process and close the WebSocket."""
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=TIMEOUT_DISCONNECT)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None

        self._pending.clear()

    # ------------------------------------------------------------------
    # Debugger commands (same signatures as DAPClient)
    # ------------------------------------------------------------------

    async def set_breakpoints(
        self, file_path: str, lines: list[int]
    ) -> CDPMessage:
        """Set breakpoints for *file_path*. Returns DAP-shaped response.

        Only removes previous breakpoints for *this* file, leaving
        breakpoints in other files untouched (mirrors DAP semantics).
        """
        abs_path = os.path.abspath(file_path)

        # Remove old breakpoints for THIS file only.
        for bp_id in self._breakpoint_ids.get(abs_path, []):
            try:
                await self._send("Debugger.removeBreakpoint", {"breakpointId": bp_id})
            except Exception:
                pass
        self._breakpoint_ids[abs_path] = []

        results = []
        file_url = f"file://{abs_path}"

        for line in lines:
            try:
                resp = await self._send(
                    "Debugger.setBreakpointByUrl",
                    {
                        "lineNumber": line - 1,  # CDP is 0-based
                        "url": file_url,
                    },
                )
                bp_id = resp.get("breakpointId", "")
                self._breakpoint_ids[abs_path].append(bp_id)
                locations = resp.get("locations", [])
                actual_line = locations[0]["lineNumber"] + 1 if locations else line
                results.append({"verified": True, "line": actual_line})
            except Exception as exc:
                logger.warning("Failed to set breakpoint at %s:%d: %s", file_path, line, exc)
                results.append({"verified": False, "line": line})

        return {"breakpoints": results}

    async def continue_(self, thread_id: int = 1) -> CDPMessage:
        """Resume execution. Blocks until the next pause or termination."""
        self.stopped_event = asyncio.get_running_loop().create_future()
        self.terminated_event = asyncio.get_running_loop().create_future()
        await self._send("Debugger.resume", {})
        return await wait_for_stop_or_terminate(
            self.stopped_event, self.terminated_event,
        )

    async def next_(self, thread_id: int = 1) -> CDPMessage:
        """Step over."""
        self.stopped_event = asyncio.get_running_loop().create_future()
        self.terminated_event = asyncio.get_running_loop().create_future()
        await self._send("Debugger.stepOver", {})
        return await wait_for_stop_or_terminate(
            self.stopped_event, self.terminated_event,
        )

    async def step_in(self, thread_id: int = 1) -> CDPMessage:
        """Step into."""
        self.stopped_event = asyncio.get_running_loop().create_future()
        self.terminated_event = asyncio.get_running_loop().create_future()
        await self._send("Debugger.stepInto", {})
        return await wait_for_stop_or_terminate(
            self.stopped_event, self.terminated_event,
        )

    async def stack_trace(
        self, thread_id: int = 1, levels: int = 20
    ) -> CDPMessage:
        """Get call stack. Returns DAP-shaped ``stackFrames``."""
        # We don't have a callFrameId stored; we need to get it from
        # the last paused event. We'll re-request via Debugger.getStackTrace
        # or use the cached frames from the last Debugger.paused event.
        # For simplicity, we cache frames on every paused event.
        return {"stackFrames": self._last_stack_frames}

    async def scopes(self, frame_id: int) -> CDPMessage:
        """Get scopes for a frame. Returns DAP-shaped scopes."""
        # frame_id in our CDP mapping is the index into _last_call_frames
        if frame_id < 0 or frame_id >= len(self._last_call_frames):
            return {"scopes": []}

        frame = self._last_call_frames[frame_id]
        scope_chain = frame.get("scopeChain", [])

        scopes = []
        for scope in scope_chain:
            scope_type = scope.get("type", "")
            obj = scope.get("object", {})
            scopes.append({
                "name": scope_type.capitalize(),
                "variablesReference": self._store_object_id(obj.get("objectId", "")),
                "expensive": scope_type == "global",
            })

        return {"scopes": scopes}

    async def variables(self, variables_reference: int) -> CDPMessage:
        """Get variables for a reference. Returns DAP-shaped variables."""
        object_id = self._get_object_id(variables_reference)
        if not object_id:
            return {"variables": []}

        try:
            resp = await self._send(
                "Runtime.getProperties",
                {
                    "objectId": object_id,
                    "ownProperties": True,
                    "generatePreview": True,
                },
            )
        except Exception:
            return {"variables": []}

        variables = []
        for prop in resp.get("result", []):
            name = prop.get("name", "?")
            value_obj = prop.get("value", {})
            var_type = value_obj.get("type", "")
            # Get a string representation.
            if "value" in value_obj:
                value_str = str(value_obj["value"])
            elif "description" in value_obj:
                value_str = value_obj["description"]
            elif value_obj.get("subtype") == "null":
                value_str = "null"
            else:
                value_str = value_obj.get("unserializableValue", str(value_obj))

            child_ref = 0
            child_object_id = value_obj.get("objectId")
            if child_object_id:
                child_ref = self._store_object_id(child_object_id)

            variables.append({
                "name": name,
                "value": value_str,
                "type": var_type,
                "variablesReference": child_ref,
            })

        return {"variables": variables}

    async def evaluate(
        self,
        expression: str,
        frame_id: int | None = None,
        context: str = "repl",
    ) -> CDPMessage:
        """Evaluate an expression. Returns DAP-shaped result."""
        # If we have a frame, evaluate in that frame's context.
        if frame_id is not None and 0 <= frame_id < len(self._last_call_frames):
            call_frame_id = self._last_call_frames[frame_id].get("callFrameId")
            if call_frame_id:
                resp = await self._send(
                    "Debugger.evaluateOnCallFrame",
                    {"callFrameId": call_frame_id, "expression": expression},
                )
                return self._format_eval_result(resp)

        resp = await self._send("Runtime.evaluate", {"expression": expression})
        return self._format_eval_result(resp)

    @staticmethod
    def _format_eval_result(resp: CDPMessage) -> CDPMessage:
        """Convert a CDP evaluate response to DAP-shaped result."""
        result_obj = resp.get("result", {})
        value = result_obj.get(
            "description",
            result_obj.get("value", str(result_obj)),
        )
        return {"result": value, "type": result_obj.get("type", "")}

    async def threads(self) -> CDPMessage:
        """Node is single-threaded. Return one thread."""
        return {"threads": [{"id": 1, "name": "main"}]}

    # ------------------------------------------------------------------
    # Internal: WebSocket URL parsing
    # ------------------------------------------------------------------

    async def _read_ws_url(self) -> str:
        """Read the inspector WebSocket URL from node's stderr."""
        assert self._process and self._process.stderr
        loop = asyncio.get_running_loop()
        deadline = loop.time() + TIMEOUT_LAUNCH

        while loop.time() < deadline:
            line_bytes = await asyncio.wait_for(
                self._process.stderr.readline(), timeout=TIMEOUT_READLINE,
            )

            # Empty read means node exited before printing the WS URL.
            if not line_bytes:
                exit_code = self._process.returncode
                raise RuntimeError(
                    f"Node process exited (code={exit_code}) before "
                    f"printing the inspector WebSocket URL."
                )

            line = line_bytes.decode("utf-8", errors="replace").strip()
            logger.debug("node stderr: %s", line)

            match = re.search(r"ws://[^\s]+", line)
            if match:
                return match.group(0)

        raise RuntimeError(
            "Timed out waiting for Node inspector WebSocket URL.  "
            "Is node --inspect-brk working?"
        )

    # ------------------------------------------------------------------
    # Internal: WebSocket read loop
    # ------------------------------------------------------------------

    async def _read_loop(self) -> None:
        """Read CDP messages from the WebSocket."""
        assert self._ws
        try:
            async for raw in self._ws:
                msg: CDPMessage = json.loads(raw)

                if "id" in msg:
                    # Response to a request.
                    msg_id = msg["id"]
                    fut = self._pending.pop(msg_id, None)
                    if fut and not fut.done():
                        if "error" in msg:
                            fut.set_exception(
                                RuntimeError(f"CDP error: {msg['error'].get('message', msg['error'])}")
                            )
                        else:
                            fut.set_result(msg.get("result", {}))
                else:
                    # Event.
                    await self._handle_event(msg)

        except websockets.ConnectionClosed:
            logger.debug("WebSocket connection closed.")
        except asyncio.CancelledError:
            return  # don't touch futures on intentional cancel
        except Exception:
            logger.exception("Error in CDP read loop")

        # Reject any in-flight requests so callers don't hang.
        self._fail_pending("Connection lost.")

    async def _handle_event(self, msg: CDPMessage) -> None:
        method = msg.get("method", "")
        params = msg.get("params", {})

        if method == "Debugger.paused":
            call_frames = params.get("callFrames", [])
            self._last_call_frames = call_frames
            self._last_stack_frames = self._convert_frames(call_frames)

            reason = params.get("reason", "other")
            # Map CDP reason to DAP reason.
            dap_reason = {
                "breakpoint": "breakpoint",
                "exception": "exception",
                "other": "step",
            }.get(reason, reason)

            body = {"reason": dap_reason, "threadId": 1}

            if self.stopped_event and not self.stopped_event.done():
                self.stopped_event.set_result(body)

        elif method == "Debugger.scriptParsed":
            script_id = params.get("scriptId", "")
            url = params.get("url", "")
            if url:
                self._scripts[script_id] = url

        elif method == "Runtime.consoleAPICalled":
            args = params.get("args", [])
            text = " ".join(
                a.get("description", a.get("value", "")) for a in args
            )
            self.output_lines.append(text)

        elif method == "Runtime.exceptionThrown":
            # Uncaught exception -- capture the error text for output.
            exception_details = params.get("exceptionDetails", {})
            exc_obj = exception_details.get("exception", {})
            text = exc_obj.get(
                "description",
                exception_details.get("text", "Uncaught exception"),
            )
            self.output_lines.append(text)

        elif method in ("Inspector.detached", "Runtime.executionContextDestroyed"):
            if self.terminated_event and not self.terminated_event.done():
                self.terminated_event.set_result(None)

    # ------------------------------------------------------------------
    # Internal: CDP request/response
    # ------------------------------------------------------------------

    def _fail_pending(self, reason: str) -> None:
        """Reject all in-flight request futures so callers don't hang."""
        err = ConnectionError(reason)
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(err)
        self._pending.clear()

    async def _send(self, method: str, params: dict[str, Any]) -> CDPMessage:
        """Send a CDP command and wait for the response."""
        assert self._ws
        msg_id = self._msg_id
        self._msg_id += 1

        msg = {"id": msg_id, "method": method, "params": params}
        await self._ws.send(json.dumps(msg))

        logger.debug("-> CDP %s (id=%d)", method, msg_id)

        loop = asyncio.get_running_loop()
        fut: asyncio.Future[CDPMessage] = loop.create_future()
        self._pending[msg_id] = fut
        return await fut

    # ------------------------------------------------------------------
    # Internal: CDP -> DAP frame conversion
    # ------------------------------------------------------------------

    def _store_object_id(self, object_id: str) -> int:
        """Store a CDP objectId and return a numeric variablesReference."""
        if not object_id:
            return 0
        ref = self._next_var_ref
        self._next_var_ref += 1
        self._object_ids[ref] = object_id
        return ref

    def _get_object_id(self, var_ref: int) -> str | None:
        return self._object_ids.get(var_ref)

    def _convert_frames(self, call_frames: list[CDPMessage]) -> list[CDPMessage]:
        """Convert CDP callFrames to DAP-shaped stackFrames."""
        dap_frames = []
        for i, cf in enumerate(call_frames):
            location = cf.get("location", {})
            script_id = location.get("scriptId", "")
            url = cf.get("url", "") or self._scripts.get(script_id, "")

            # Convert file:// URL to path.
            file_path = url
            if url.startswith("file://"):
                file_path = url[7:]

            dap_frames.append({
                "id": i,  # frame index as ID
                "name": cf.get("functionName", "(anonymous)") or "(anonymous)",
                "source": {
                    "path": file_path,
                    "name": os.path.basename(file_path) if file_path else "?",
                },
                "line": location.get("lineNumber", 0) + 1,  # CDP is 0-based
                "column": location.get("columnNumber", 0) + 1,
            })
        return dap_frames
