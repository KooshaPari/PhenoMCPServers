# justfile for agent-user-status
# Python project. Uses uv for dependency management.

set shell := ["bash", "-uc"]

# Default: list available recipes.
default:
    @just --list

# Start the dev runtime (placeholder — agent-user-statusd / agent-imessage entrypoints).
dev:
    uv run agent-user-status

# Produce release artifacts (sdist + wheel via build).
build:
    uv run python -m build

# Run the test suite (pytest).
test:
    uv run pytest -v

# Run the linter (ruff check).
lint:
    uv run ruff check src tests

# Apply the formatter (ruff format).
fmt:
    uv run ruff format src tests

# Remove build artifacts.
clean:
    rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache
