# Implementation Strategy

Use the existing Python packaging and Ruff configuration as the source of truth.
Prefer `uv`-backed commands so the tasks do not depend on a manually activated shell environment.
