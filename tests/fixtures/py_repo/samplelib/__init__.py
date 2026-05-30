"""SampleLib — a minimal Python library for fixture-based testing."""
from samplelib.calculator import add, subtract, multiply
from samplelib.validator import validate_number

__all__ = ["add", "subtract", "multiply", "validate_number"]
