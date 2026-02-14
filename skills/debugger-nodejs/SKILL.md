---
name: debugger-nodejs
description: Debug Node.js applications at runtime using DAP breakpoints and variable inspection. Use when the user reports a runtime bug in Node.js, a silent failure, unexpected variable values, race conditions, or when console.log debugging is insufficient. Also use proactively when you encounter a bug you cannot diagnose from static analysis alone.
---

# Debugger (Node.js)

**Why:** Runtime bugs -- silent failures, wrong variable values, race conditions -- cannot always be diagnosed from code alone. This skill gives you a real debugger (breakpoints, variable inspection, expression evaluation) instead of scattering `console.log` and guessing. You use the Debug Adapter Protocol (DAP) via `vscode-node-debug2` to pause execution and inspect actual state.

**Hard constraints:** Requires the `top-coder-ai-skills-debugger` Python package. All commands go through `scripts/debug.py`. Never leave a debug session running after you are done -- always call `stop`.

---

## Setup (before first use)

**Install the package** in the environment used to run the script (globally or in the project):

- **Global (recommended for skills):**  
  `pip install top-coder-ai-skills-debugger`  
  or for the current user only: `pip install --user top-coder-ai-skills-debugger`

- **Project (if using uv):**  
  `uv add top-coder-ai-skills-debugger`

- **Project (if using Poetry):**  
  `poetry add top-coder-ai-skills-debugger`

**Check that it works:** Run `python scripts/debug.py` with no arguments. If you see "top-coder-ai-skills-debugger is not installed", run one of the install commands above and retry. The script checks for the package and exits with a clear message when it is missing.

---

## When to use

- **Runtime errors:** A function returns the wrong result and you cannot see why from the source.
- **Silent failures:** A button does nothing, data is not saved, but there is no crash or error message.
- **Unexpected values:** A variable is `undefined`, `NaN`, or `"[object Object]"` when it should be a number.
- **Race conditions / async bugs:** Timing-dependent failures where execution order matters.
- **Static analysis is not enough:** You have read the code but cannot determine the root cause.

Do **not** use for: syntax errors, missing imports, or type errors that the linter already catches.

---

## Available commands

All commands run via `python scripts/debug.py <action> [args]`. If the script reports that `top-coder-ai-skills-debugger` is not installed, run the install command from **Setup** above, then retry.

| Command | Usage | Description |
|---------|-------|-------------|
| **start** | `start <file.js>` | Launch the Node.js debugger for the given file. |
| **breakpoint** | `breakpoint <file.js> <line>` | Set a breakpoint at a specific file and line. |
| **continue** | `continue` | Resume execution until the next breakpoint or termination. |
| **step** | `step` | Step over the current line. |
| **evaluate** | `evaluate <expression>` | Evaluate an expression in the current scope (e.g. `evaluate total`). |
| **stack** | `stack` | Print the current call stack. |
| **variables** | `variables` | Print all local variables in the current frame. |
| **probe** | `probe <file.js>:<line>` | One-shot: run to the line, dump all variables and stack, then stop. |
| **stop** | `stop` | End the debug session and clean up. |

---

## Workflows

### Interactive debugging (multi-turn)

Use when you need to set multiple breakpoints, step through code, and inspect different variables across turns.

```
1. start app.js
2. breakpoint app.js 15
3. continue                     # runs until line 15
4. evaluate someVariable        # inspect the value
5. step                         # step to next line
6. variables                    # dump all locals
7. stop                         # always clean up
```

### One-shot probe (single turn)

Use when you have a hypothesis about a specific line and want to see all state at that point in one go.

```
1. probe app.js:15              # runs to line 15, dumps everything, stops
```

The probe returns: source context (with `>>>` marking the line), full stack trace, and all local variables. This is usually enough to confirm or reject a hypothesis.

---

## Code contrast

### Anti-pattern: Guess-and-log

```javascript
// Scattered console.logs that you must add, run, read, and remove.
function calculateTotal(items) {
    let total = 0;
    console.log("items:", items);          // added for debugging
    for (let i = 0; i < items.length; i++) {
        total = total + items[i];
        console.log("total so far:", total);  // added for debugging
    }
    console.log("final total:", total);    // added for debugging
    return total;
}
// Problems: pollutes code, must remember to clean up, cannot inspect
// complex objects or step through logic interactively.
```

### Top-coder pattern: Probe at the suspect line

```
$ python scripts/debug.py probe app.js:8

Stopped (breakpoint) at app.js:8
     5 |     let total = 0;
     6 |     for (let i = 0; i < items.length; i++) {
     7 |         const item = items[i];
  >>>  8 |         total = total + item;
     9 |         console.log(`Adding item ${i}`);
    10 |     }

--- Stack Trace ---
#0   calculateTotal                 (app.js:8)
#1   main                           (app.js:22)

--- Local Variables ---
  total: number = 0
  i: number = 0
  item: object = { name: "Apple", price: 1.2 }

# Immediately see: total + item is adding an object, not item.price.
# Fix the bug, no console.log cleanup needed.
```

---

## Prerequisites

1. **Node.js** must be on PATH.
2. **vscode-node-debug2**: `npm install -g vscode-node-debug2`
3. **top-coder-ai-skills-debugger** Python package: `pip install -e packages/debugger-core` or `uv sync` (from the repo root).

---

## Tips

- **Probe first.** Start with a one-shot probe at the suspicious line. If that gives enough info, you are done.
- **Breakpoint before continue.** Always set at least one breakpoint before calling `continue`, or execution will run to completion without stopping.
- **Always stop.** Call `stop` when finished. Do not leave zombie debug processes.
- **Evaluate complex expressions.** `evaluate` accepts any valid JS expression, not just variable names -- e.g. `evaluate items.map(i => i.price)`.
- **Check the stack.** If you are unsure how the code reached a point, use `stack` to see the full call chain.
