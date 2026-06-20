# justfile — Phenotype org standard recipes
# Run `just` to list available recipes.

set shell := ["bash", "-uc"]

# Default: list available recipes.
default:
    @just --list

# Build the project for the detected language.
build:
    @if [ -f pyproject.toml ] || [ -f setup.py ]; then \
        uv build; \
    elif [ -f package.json ]; then \
        if [ -f pnpm-lock.yaml ]; then pnpm build; \
        elif [ -f yarn.lock ]; then yarn build; \
        else npm run build; fi; \
    elif [ -f go.mod ]; then \
        go build ./...; \
    elif [ -f Cargo.toml ]; then \
        cargo build; \
    else \
        echo "No build task configured for this repository"; \
        exit 1; \
    fi

# Run the test suite.
test:
    @if [ -f pyproject.toml ] || [ -f setup.py ]; then \
        PYTHONPATH=src python -m pytest tests/unit -q; \
    elif [ -f package.json ]; then \
        if [ -f pnpm-lock.yaml ]; then pnpm test; \
        elif [ -f yarn.lock ]; then yarn test; \
        else npm test; fi; \
    elif [ -f go.mod ]; then \
        go test ./...; \
    elif [ -f Cargo.toml ]; then \
        cargo test; \
    else \
        echo "No test task configured for this repository"; \
        exit 1; \
    fi

# Run the linter.
lint:
    @if [ -f pyproject.toml ] || [ -f setup.py ]; then \
        PYTHONPATH=src python -m ruff check .; \
    elif [ -f package.json ]; then \
        if [ -f pnpm-lock.yaml ]; then pnpm lint; \
        elif [ -f yarn.lock ]; then yarn lint; \
        else npm run lint; fi; \
    elif [ -f go.mod ]; then \
        go vet ./...; \
    elif [ -f Cargo.toml ]; then \
        cargo clippy --all-targets --all-features; \
    else \
        echo "No lint task configured for this repository"; \
        exit 1; \
    fi

# Apply the formatter.
fmt:
    @if [ -f pyproject.toml ] || [ -f setup.py ]; then \
        PYTHONPATH=src python -m ruff format .; \
    elif [ -f package.json ]; then \
        if [ -f pnpm-lock.yaml ]; then pnpm format; \
        elif [ -f yarn.lock ]; then yarn format; \
        else npm run format --if-present; fi; \
    elif [ -f go.mod ]; then \
        gofmt -w .; \
    elif [ -f Cargo.toml ]; then \
        cargo fmt --all; \
    else \
        echo "No format task configured for this repository"; \
        exit 1; \
    fi

# Run the dependency-audit gate (pip-audit + OSV Scanner).
audit:
    @if [ -f .github/workflows/audit.yml ]; then \
        if [ -f pyproject.toml ] || [ -f setup.py ]; then \
            python -m pip install --upgrade pip pip-audit tomli; \
            python -m pip install -e .[eye] || python -m pip install -e .; \
            python -m pip_audit --strict; \
        else \
            echo "Audit gate is wired for Python surfaces only."; \
        fi; \
    else \
        echo "No audit workflow configured"; \
        exit 1; \
    fi

# Run the supply-chain deny gate (cargo-deny + pip-licenses).
deny:
    @if [ -f .github/workflows/deny.yml ]; then \
        if [ -f Cargo.toml ] || [ -f deny.toml ]; then \
            if command -v cargo-deny >/dev/null 2>&1; then \
                cargo deny check; \
            else \
                echo "cargo-deny not installed locally; CI gate covers it"; \
            fi; \
        fi; \
        if [ -f pyproject.toml ] || [ -f setup.py ]; then \
            python -m pip install --upgrade pip pip-licenses; \
            python -m piplicenses \
                --format=markdown \
                --with-system \
                --allow-only=MIT;Apache-2.0;BSD-2-Clause;BSD-3-Clause;ISC;MPL-2.0;Python-2.0;PSF-2.0;Zlib;HPND;LGPL-2.1-or-later;LGPL-3.0-or-later;LGPL-2.1-only;LGPL-3.0-only;Unlicense;CC0-1.0;0BSD \
                --ignore-packages=agent-user-status; \
        fi; \
    else \
        echo "No deny workflow configured"; \
        exit 1; \
    fi

# Run the repository grade report.
grade:
    @if [ -f grade.sh ]; then \
        ./grade.sh; \
    elif [ -f Taskfile.yml ]; then \
        task grade; \
    else \
        echo "No grade runner found"; \
        exit 1; \
    fi

# Run the full CI gate locally (lint + test + grade).
ci: lint test grade
    @echo "Local CI gate passed"

# Remove build artifacts.
clean:
    @if [ -d .venv ]; then rm -rf .venv; fi
    @find . -type d -name __pycache__ -prune -exec rm -rf {} +
    @rm -rf .pytest_cache .ruff_cache .mypy_cache build dist htmlcov .coverage coverage.xml
    @echo "Build artifacts removed"

# Run the full local quality gate.
quality: lint test
    @echo "Quality gate passed"
