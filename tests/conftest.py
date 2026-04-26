"""Shared pytest setup for legacy unit tests."""

from __future__ import annotations

import builtins

import pytest

builtins.pytest = pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "requirement(id): trace a test to a functional requirement")
