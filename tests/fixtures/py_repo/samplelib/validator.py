"""Input validation helpers for SampleLib."""


class ValidationError(Exception):
    """Raised when a value fails validation."""


def validate_number(value: object) -> None:
    """Raise ValidationError if value is not a real number."""
    if not isinstance(value, (int, float)):
        raise ValidationError(f"Expected a number, got {type(value).__name__!r}")
    if value != value:  # NaN check
        raise ValidationError("NaN is not a valid number")
