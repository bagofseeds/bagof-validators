"""Exceptions raised by validators on validation error."""

__all__ = ["ValidationError", "ValueValidationError", "TypeValidationError"]

# bags
from bagof.core.magic import MagicError


class ValidationError(MagicError):
    """Base class for all validation errors."""

    def __init__(self, *args, **kwargs) -> None:
        if "validator" in kwargs:
            kwargs["this"] = kwargs.pop("validator")
        super().__init__(*args, **kwargs)


class ValueValidationError(ValidationError, ValueError):
    """Raised when validation fails because of the value of an object."""
    ...


class TypeValidationError(ValidationError, TypeError):
    """Raised when validation fails because of the type of an object."""
    ...
