"""High-level debug session that wraps the DAP client.

``DebugSession`` is the single entry-point consumed by both:

* **MCP server** -- keeps the session in memory (long-running process).
* **Skill scripts** -- persist session state to a JSON file so that
  sequential CLI invocations can reconnect to the same adapter.

All public methods return **plain-text strings** ready to hand to an LLM.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from debugger_core.adapters.python import PythonAdapter
from debugger_core.cdp_client import CDPClient
from debugger_core.dap_client import DAPClient
from debugger_core.formatters import (
    format_probe_result,
    format_stack_trace,
    format_stopped_at,
    format_variables,
)

logger = logging.getLogger(__name__)

_SESSION_FILE = ".debug_session.json"

# Languages that use CDP (direct Node.js inspector, zero deps).
_CDP_LANGUAGES = {"node"}
# Languages that use DAP (external debug adapter).
_DAP_LANGUAGES = {"python"}
_ALL_LANGUAGES = _CDP_LANGUAGES | _DAP_LANGUAGES


# ---------------------------------------------------------------------------
# DebugSession
# ---------------------------------------------------------------------------


class DebugSession:
    """Manages a single debug session against a DAP adapter.

    Usage (in-memory, e.g. from MCP server)::

        session = DebugSession()
        print(await session.start("app.js", "node"))
        print(await session.add_breakpoint("app.js", 10))
        print(await session.resume())
        print(await session.inspect("myVar"))
        print(await session.stop())

    Usage (file-based, e.g. from skill scripts)::

        session = DebugSession.from_file_or_new(language="node")
        # session.start(...)  on first invocation
        # session.resume()    on subsequent invocations
        # session.stop()      to clean up
    """

    def __init__(self) -> None:
        self._client: DAPClient | CDPClient | None = None
        self._language: str | None = None
        self._program: str | None = None
        self._breakpoints: dict[str, list[int]] = {}  # file -> lines
        self._persist_file: str | None = None

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_file_or_new(
        cls,
        language: str | None = None,
        session_file: str = _SESSION_FILE,
    ) -> DebugSession:
        """Restore a session from a JSON file, or create a fresh one.

        Used by skill CLI scripts where each invocation is a new process.
        """
        session = cls()
        session._persist_file = os.path.abspath(session_file)

        if os.path.isfile(session._persist_file):
            try:
                with open(session._persist_file, encoding="utf-8") as f:
                    data = json.load(f)
                session._language = data.get("language", language)
                session._program = data.get("program")
                session._breakpoints = data.get("breakpoints", {})
                logger.info("Restored session from %s", session._persist_file)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to restore session file: %s", exc)

        if language:
            session._language = language

        return session

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def start(self, program: str, language: str | None = None) -> str:
        """Launch the debugger for *program*.

        Returns a human-readable status string.
        """
        lang = language or self._language
        if not lang:
            return "Error: language must be specified (node | python)"

        if lang not in _ALL_LANGUAGES:
            return f"Error: unsupported language '{lang}'. Choose: {', '.join(sorted(_ALL_LANGUAGES))}"

        # Pick the right client based on language.
        if lang in _CDP_LANGUAGES:
            self._client = CDPClient()
        else:
            adapter = PythonAdapter()
            self._client = DAPClient(adapter)

        self._language = lang
        self._program = os.path.abspath(program)
        self._breakpoints = {}

        try:
            await self._client.start()
            await self._client.launch(self._program)
        except Exception as exc:
            return f"Error launching debugger: {exc}"

        self._save()
        return f"Debugger started for {os.path.basename(program)} ({lang}). Ready for breakpoints."

    async def stop(self) -> str:
        """Disconnect and clean up."""
        if self._client:
            await self._client.disconnect()
            self._client = None

        self._delete_session_file()
        return "Debug session ended."

    # ------------------------------------------------------------------
    # Breakpoints
    # ------------------------------------------------------------------

    async def add_breakpoint(self, file: str, line: int) -> str:
        """Set a breakpoint at *file*:*line*."""
        if not self._client:
            return "Error: no active debug session. Call start() first."

        file = os.path.abspath(file)
        existing = self._breakpoints.get(file, [])
        if line not in existing:
            existing.append(line)
        self._breakpoints[file] = existing

        try:
            resp = await self._client.set_breakpoints(file, existing)
        except Exception as exc:
            return f"Error setting breakpoint: {exc}"

        bps = resp.get("breakpoints", [])
        verified = [b for b in bps if b.get("verified")]
        self._save()
        return (
            f"Breakpoint at {os.path.basename(file)}:{line} "
            f"({'verified' if len(verified) == len(bps) else 'pending'})"
        )

    # ------------------------------------------------------------------
    # Execution control
    # ------------------------------------------------------------------

    async def resume(self) -> str:
        """Continue execution until the next breakpoint or termination."""
        if not self._client:
            return "Error: no active debug session."

        try:
            stop_info = await self._client.continue_()
        except asyncio.TimeoutError:
            return "Execution resumed but no breakpoint hit within 30 s."
        except Exception as exc:
            return f"Error resuming: {exc}"

        return await self._describe_stop(stop_info)

    async def step(self, action: str = "next") -> str:
        """Step over (``next``) or into (``step_in``)."""
        if not self._client:
            return "Error: no active debug session."

        try:
            if action == "step_in":
                stop_info = await self._client.step_in()
            else:
                stop_info = await self._client.next_()
        except asyncio.TimeoutError:
            return "Step timed out (30 s)."
        except Exception as exc:
            return f"Error stepping: {exc}"

        return await self._describe_stop(stop_info)

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    async def inspect(self, expression: str) -> str:
        """Evaluate *expression* in the current top frame."""
        if not self._client:
            return "Error: no active debug session."

        frame_id = await self._top_frame_id()
        if frame_id is None:
            return "Error: could not determine current frame."

        try:
            resp = await self._client.evaluate(expression, frame_id=frame_id)
        except Exception as exc:
            return f"Error evaluating '{expression}': {exc}"

        result = resp.get("result", str(resp))
        var_type = resp.get("type", "")
        prefix = f"({var_type}) " if var_type else ""
        return f"{prefix}{result}"

    async def get_stack(self) -> str:
        """Return the current stack trace as formatted text."""
        if not self._client:
            return "Error: no active debug session."

        try:
            resp = await self._client.stack_trace()
        except Exception as exc:
            return f"Error fetching stack: {exc}"

        frames = resp.get("stackFrames", [])
        return format_stack_trace(frames)

    async def get_local_variables(self) -> str:
        """Return local variables of the top frame as formatted text."""
        if not self._client:
            return "Error: no active debug session."

        variables = await self._fetch_locals()
        return format_variables(variables)

    # ------------------------------------------------------------------
    # Probe (one-shot)
    # ------------------------------------------------------------------

    async def probe(
        self,
        program: str,
        file: str,
        line: int,
        language: str | None = None,
    ) -> str:
        """One-shot: start, break at *line*, dump state, stop.

        Returns a comprehensive probe report (location + stack + vars).
        """
        # 1. Start
        start_msg = await self.start(program, language)
        if start_msg.startswith("Error"):
            return start_msg

        # 2. Set breakpoint
        bp_msg = await self.add_breakpoint(file, line)
        if bp_msg.startswith("Error"):
            await self.stop()
            return bp_msg

        # 3. Run to breakpoint
        try:
            stop_info = await self.resume()
        except Exception as exc:
            await self.stop()
            return f"Error during probe run: {exc}"

        if "Error" in stop_info or "no breakpoint" in stop_info.lower():
            await self.stop()
            return stop_info

        # 4. Collect data
        try:
            stack_resp = await self._client.stack_trace()  # type: ignore[union-attr]
            frames = stack_resp.get("stackFrames", [])
            local_vars = await self._fetch_locals()
        except Exception as exc:
            await self.stop()
            return f"Error collecting probe data: {exc}"

        # 5. Stop
        await self.stop()

        reason = stop_info.split("(")[1].split(")")[0] if "(" in stop_info else "breakpoint"
        return format_probe_result(
            os.path.abspath(file), line, frames, local_vars, reason
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _top_frame_id(self) -> int | None:
        """Return the frameId of the top stack frame, or None."""
        if not self._client:
            return None
        try:
            resp = await self._client.stack_trace()
            frames = resp.get("stackFrames", [])
            return frames[0]["id"] if frames else None
        except Exception:
            return None

    async def _fetch_locals(self) -> list[dict[str, Any]]:
        """Fetch local-scope variables from the top frame."""
        if not self._client:
            return []

        frame_id = await self._top_frame_id()
        if frame_id is None:
            return []

        try:
            scopes_resp = await self._client.scopes(frame_id)
            scopes = scopes_resp.get("scopes", [])
            # Find the "Locals" scope (usually the first one).
            local_scope = next(
                (s for s in scopes if s.get("name", "").lower() in ("locals", "local")),
                scopes[0] if scopes else None,
            )
            if local_scope is None:
                return []

            vars_resp = await self._client.variables(
                local_scope["variablesReference"]
            )
            return vars_resp.get("variables", [])
        except Exception:
            return []

    async def _describe_stop(self, stop_info: dict[str, Any] | str) -> str:
        """Build a human-readable description of why we stopped."""
        # stop_info may already be a formatted string (from resume error paths).
        if isinstance(stop_info, str):
            return stop_info

        reason = stop_info.get("reason", "unknown")

        # Try to get the current location from the stack.
        if self._client:
            try:
                stack_resp = await self._client.stack_trace()
                frames = stack_resp.get("stackFrames", [])
                if frames:
                    top = frames[0]
                    source = top.get("source", {})
                    file_path = source.get("path", source.get("name", "?"))
                    line = top.get("line", 0)
                    return format_stopped_at(file_path, line, reason)
            except Exception:
                pass

        return f"Stopped ({reason})."

    # ------------------------------------------------------------------
    # Persistence (file-based state for skill scripts)
    # ------------------------------------------------------------------

    def _save(self) -> None:
        """Persist minimal session state to disk."""
        if not self._persist_file:
            return
        data = {
            "language": self._language,
            "program": self._program,
            "breakpoints": self._breakpoints,
        }
        try:
            with open(self._persist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            logger.warning("Could not save session file %s", self._persist_file)

    def _delete_session_file(self) -> None:
        if self._persist_file and os.path.isfile(self._persist_file):
            try:
                os.remove(self._persist_file)
            except OSError:
                pass
