# Research

Repo-local findings:
- `pyproject.toml` identifies the project as Python and uses setuptools packaging.
- The repo already uses `ruff` configuration in `pyproject.toml`.
- A root `Taskfile.yml` was already present in the checkout, so the work became a normalization pass rather than a fresh add.

Command choices:
- Build: `uv build`
- Test: `uv run pytest`
- Lint: `uv run ruff check .`
- Clean: remove build artifacts and common local caches
