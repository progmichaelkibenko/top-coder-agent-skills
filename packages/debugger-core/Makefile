# top-coder-ai-skills-debugger (packages/debugger-core) — build, publish, clean
# Run from this directory or via root: make -C packages/debugger-core <target>

UV ?= uv
PYTHON ?= python3
OUT_DIR ?= dist/debugger-core

.PHONY: help build clean publish publish-test test-install

help:
	@echo "debugger-core targets:"
	@echo "  build        Build wheel + sdist (output in $(OUT_DIR)/)"
	@echo "  clean        Remove $(OUT_DIR)/ and build/"
	@echo "  publish      Publish to PyPI (requires auth)"
	@echo "  publish-test Publish to Test PyPI"
	@echo "  test-install Build and pip install from $(OUT_DIR)/ (verify wheel)"

build:
	$(UV) build . -o $(OUT_DIR)

clean:
	rm -rf $(OUT_DIR) build

publish: build
	export UV_PUBLISH_TOKEN=pypi-YourTokenHere $(UV) publish $(OUT_DIR)/*

publish-test: build
	$(UV) publish $(OUT_DIR)/* --repository test

test-install: build
	$(PYTHON) -m pip install --force-reinstall $(OUT_DIR)/*.whl
