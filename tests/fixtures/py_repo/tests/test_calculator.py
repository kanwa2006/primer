"""Tests for samplelib.calculator."""
import pytest
from samplelib.calculator import add, subtract, multiply, Calculator
from samplelib.validator import ValidationError


def test_add_integers():
    assert add(2, 3) == 5


def test_add_floats():
    assert abs(add(1.1, 2.2) - 3.3) < 1e-9


def test_subtract():
    assert subtract(10, 4) == 6


def test_multiply():
    assert multiply(3, 4) == 12


def test_add_rejects_non_number():
    with pytest.raises(ValidationError):
        add("a", 1)


def test_calculator_compute():
    calc = Calculator()
    assert calc.compute("add", 5, 3) == 8
    assert calc.last_result == 8


def test_calculator_unknown_op():
    calc = Calculator()
    with pytest.raises(ValueError):
        calc.compute("modulo", 5, 3)
