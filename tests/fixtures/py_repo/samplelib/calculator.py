"""Basic arithmetic operations for SampleLib."""
from samplelib.validator import validate_number


def add(a: float, b: float) -> float:
    """Return the sum of two numbers."""
    validate_number(a)
    validate_number(b)
    return a + b


def subtract(a: float, b: float) -> float:
    """Return the difference of two numbers."""
    validate_number(a)
    validate_number(b)
    return a - b


def multiply(a: float, b: float) -> float:
    """Return the product of two numbers."""
    validate_number(a)
    validate_number(b)
    return a * b


class Calculator:
    """Stateful calculator that remembers the last result."""

    def __init__(self) -> None:
        self.last_result: float = 0.0

    def compute(self, op: str, a: float, b: float) -> float:
        """Dispatch an arithmetic operation by name."""
        ops = {"add": add, "subtract": subtract, "multiply": multiply}
        if op not in ops:
            raise ValueError(f"Unknown operation: {op!r}")
        self.last_result = ops[op](a, b)
        return self.last_result
