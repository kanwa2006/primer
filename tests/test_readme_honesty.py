"""Verify README.md contains none of the forbidden substrings (P0.2.9)."""
from __future__ import annotations

from pathlib import Path

import pytest

README = Path(__file__).parent.parent / "README.md"

FORBIDDEN = [
    "41%",
    "68%",
    "$0 end-to-end",
    "$0 end to end",
]


def test_readme_exists():
    assert README.exists(), "README.md must exist"


@pytest.mark.parametrize("forbidden", FORBIDDEN)
def test_readme_does_not_contain_forbidden(forbidden):
    content = README.read_text(encoding="utf-8").lower()
    assert forbidden.lower() not in content, (
        f"README.md must not contain {forbidden!r} — see positioning honesty rules."
    )
