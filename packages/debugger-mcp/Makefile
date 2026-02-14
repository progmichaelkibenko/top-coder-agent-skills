# debugger-mcp — build, publish, clean
# Run from this directory or via root: make -C packages/debugger-mcp <target>
# Publish top-coder-ai-skills-debugger to PyPI first (this package depends on it).

UV ?= uv
PYTHON ?= python3
OUT_DIR ?= dist/debugger-mcp

.PHONY: help build clean publish publish-test test-install

help:
	@echo "debugger-mcp targets:"
	@echo "  build        Build wheel + sdist (output in $(OUT_DIR)/)"
	@echo "  clean        Remove $(OUT_DIR)/ and build/"
	@echo "  publish      Publish to PyPI (requires auth; need top-coder-ai-skills-debugger on PyPI first)"
	@echo "  publish-test Publish to Test PyPI"
	@echo "  test-install Build and pip install from $(OUT_DIR)/ (verify wheel)"

build:
	$(UV) build . -o $(OUT_DIR)

clean:
	rm -rf $(OUT_DIR) build

publish: build
	$(UV) publish $(OUT_DIR)/*

publish-test: build
	$(UV) publish $(OUT_DIR)/* --repository test

test-install: build
	$(PYTHON) -m pip install --force-reinstall $(OUT_DIR)/*.whl
