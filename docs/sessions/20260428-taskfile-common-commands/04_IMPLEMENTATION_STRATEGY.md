# Implementation Strategy

Use the existing Python packaging and Ruff configuration as the source of truth.
Prefer `uv`-backed commands so the tasks do not depend on a manually activated shell environment.
Add a lightweight repository-language detector so the common task names stay stable even if the repo layout changes later.
