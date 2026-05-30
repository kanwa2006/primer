"""Verify every declared runtime dependency imports successfully (Phase 0).

Importing docker/anthropic requires no daemon or API key.
"""
from __future__ import annotations

import importlib

import pytest

RUNTIME_DEPS = [
    "typer",
    "pydantic",
    "pydantic_settings",
    "rich",
    "anthropic",
    "docker",
    "requests",
    "tree_sitter",
    "tree_sitter_python",
    "tree_sitter_javascript",
]


@pytest.mark.parametrize("module_name", RUNTIME_DEPS)
def test_import_succeeds(module_name):
    """Each runtime dependency must be importable without error."""
    mod = importlib.import_module(module_name)
    assert mod is not None
