# justfile for agent-user-status
# Wrapper around Python tooling. See Taskfile.yml for the legacy task runner.
# Install: pip install -e ".[dev]"   (or: uv sync --extra dev)

set shell := ["bash", "-uc"]

# Default: list available recipes.
default:
    @just --list

# Start the dev runtime (statusd + bootstrap CLI in watch mode).
dev:
    PYTHONPATH=src python -m agent_user_status.bootstrap

# Produce a release wheel + sdist via setuptools.
build:
    python -m pip install --upgrade build
    python -m build

# Run the test suite (pytest, configured via pytest.ini).
test:
    PYTHONPATH=src pytest

# Run the linter (ruff check + ruff format --check + pyright).
lint:
    ruff check src tests
    ruff format --check src tests
    pyright src

# Apply formatter (ruff format).
fmt:
    ruff format src tests
    ruff check --fix src tests

# Remove build artifacts.
clean:
    rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache src/*.egg-info
    find . -type d -name __pycache__ -prune -exec rm -rf {} +
