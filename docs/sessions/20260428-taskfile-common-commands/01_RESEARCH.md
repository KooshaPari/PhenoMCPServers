# Research

Repo-local findings:
- `pyproject.toml` identifies the project as Python and uses setuptools packaging.
- The repo already uses `ruff` configuration in `pyproject.toml`.
- No existing `Taskfile.yml` was present in the checkout.

Command choices:
- Build: `uv build`
- Test: `uv run pytest`
- Lint: `uv run ruff check .`
- Clean: remove build artifacts and common local caches
