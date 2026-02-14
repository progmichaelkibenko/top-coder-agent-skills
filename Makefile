# Top Coder Agent Skills — build and publish
# Uses uv (preferred) or hatch for Python packages.

PACKAGES := packages/debugger-core packages/debugger-mcp
UV ?= uv
PYTHON ?= python3

.PHONY: help build build-core build-mcp clean publish publish-core publish-mcp test-install install-dev

help:
	@echo "Targets:"
	@echo "  build          Build all packages (wheels + sdists in each package's dist/)"
	@echo "  build-core     Build debugger-core only"
	@echo "  build-mcp      Build debugger-mcp only"
	@echo "  clean          Remove dist/ and build/ under packages"
	@echo "  publish        Publish debugger-core then debugger-mcp to PyPI (requires auth)"
	@echo "  publish-core   Publish debugger-core to PyPI only"
	@echo "  publish-mcp    Publish debugger-mcp to PyPI only"
	@echo "  publish-test   Publish both to Test PyPI (for dry-run)"
	@echo "  test-install   Install top-coder-ai-skills-debugger from local dist (pip install --force-reinstall)"
	@echo "  install-dev    Install all packages editable from workspace (uv sync)"

build: build-core build-mcp

build-core:
	$(MAKE) -C packages/debugger-core build

build-mcp:
	$(UV) build packages/debugger-mcp

clean:
	$(MAKE) -C packages/debugger-core clean
	rm -rf packages/debugger-mcp/dist packages/debugger-mcp/build

# Publish to production PyPI. Set HATCH_INDEX_USER / HATCH_INDEX_AUTH or use keyring.
publish: build-core publish-core build-mcp publish-mcp

publish-core:
	$(MAKE) -C packages/debugger-core publish

publish-mcp:
	$(UV) publish packages/debugger-mcp

# Publish to Test PyPI: make publish-test REPO=test
REPO ?= test
publish-test:
	$(MAKE) -C packages/debugger-core publish-test
	$(UV) build packages/debugger-mcp && $(UV) publish packages/debugger-mcp --repository $(REPO)

# Install debugger-core from local dist (verifies the wheel/sdist).
test-install:
	$(MAKE) -C packages/debugger-core test-install

install-dev:
	$(UV) sync
