# Publishing to PyPI

This repo publishes two packages:

1. **top-coder-ai-skills-debugger** (`packages/debugger-core`) — shared debugger library (Node.js CDP, Python DAP). Publish this **first**.
2. **debugger-mcp** (`packages/debugger-mcp`) — MCP server that depends on top-coder-ai-skills-debugger. Publish after the debugger package is on PyPI.

## Auth (once)

1. Create a [PyPI account](https://pypi.org/account/register/) and an [API token](https://pypi.org/manage/account/token/) (scope: project or account).
2. Set the token before publishing:
   ```bash
   export UV_PUBLISH_TOKEN=pypi-YourTokenHere
   ```
   Or pass per run: `uv publish ... --token pypi-...`

## Publish order

```bash
# 1. Publish debugger library (must be on PyPI before debugger-mcp can install)
make -C packages/debugger-core publish
# or: cd packages/debugger-core && make publish

# 2. Publish MCP server (pulls top-coder-ai-skills-debugger from PyPI)
make -C packages/debugger-mcp publish
# or: cd packages/debugger-mcp && make publish
```

From repo root you can also run `make publish` to build and publish both in order.

## Per-package (from package dir)

**top-coder-ai-skills-debugger** (`packages/debugger-core`):

```bash
cd packages/debugger-core
make build          # → dist/debugger-core/*.whl, *.tar.gz
make publish        # upload to PyPI
make publish-test   # upload to Test PyPI
make test-install   # pip install from dist (sanity check)
```

**debugger-mcp** (`packages/debugger-mcp`):

```bash
cd packages/debugger-mcp
make build          # → dist/debugger-mcp/*.whl, *.tar.gz
make publish        # upload to PyPI (requires top-coder-ai-skills-debugger on PyPI)
make publish-test   # upload to Test PyPI
make test-install   # pip install from dist (sanity check)
```

## Versioning

- Bump `version` in the package’s `pyproject.toml` before each release.
- PyPI does not allow re-uploading the same version.

## Verify after publish

```bash
pip install top-coder-ai-skills-debugger
python -c "from debugger_core.session import DebugSession; print('ok')"

pip install debugger-mcp
python -c "import debugger_mcp; print('ok')"
```
