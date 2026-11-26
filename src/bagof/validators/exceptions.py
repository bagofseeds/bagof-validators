"""Exceptions raised by validators on validation error."""

__all__ = ["ValidationError", "ValueValidationError", "TypeValidationError"]

# dependencies
import typing_extensions as tx

# bags
from bagof.core.magic import MagicError


def _rebuild_validation_error(
    cls: tx.Type["ValidationError"],
    message: str,
    args: tx.Tuple[tx.Any, ...],
    this: tx.Any,
    value: tx.Any,
    fix: tx.Optional[str],
) -> "ValidationError":
    """Reconstruct a [`ValidationError`][] that carries a fix hint."""
    return cls(message, *args, this=this, value=value, fix=fix)


class ValidationError(MagicError):
    """
    Base class for all validation errors.

    !!! note
        The concrete [`ValueValidationError`][] and
        [`TypeValidationError`][] subclasses also inherit from the built-in
        [`ValueError`][] and [`TypeError`][], so they can be caught as
        either.

    Other Parameters
    ----------------
    fix : str, optional
        How to fix the failure, shown in a
        [`Report`][bagof.validators.reports.Report].
    """

    fix: tx.Optional[str]
    """How to fix the failure, when the validator can say."""

    problems: tx.Tuple[tx.Any, ...] = ()
    """
    Inside a [`collect`][bagof.validators.reports.collect] block, every
    [`Problem`][bagof.validators.reports.Problem] that the failing
    validator call found; empty otherwise.
    """

    def __init__(self, *args, **kwargs) -> None:
        if "validator" in kwargs:
            kwargs["this"] = kwargs.pop("validator")
        self.fix = kwargs.pop("fix", None)
        super().__init__(*args, **kwargs)

    def __reduce__(self) -> tx.Tuple[tx.Any, ...]:
        if self.fix is None:
            return super().__reduce__()
        rest = tuple(self.args[1:])
        state = (
            type(self), self.message, rest, self.this, self.value, self.fix
        )
        return (_rebuild_validation_error, state)


class ValueValidationError(ValidationError, ValueError):
    """Raised when validation fails because of the value of an object."""
    ...


class TypeValidationError(ValidationError, TypeError):
    """Raised when validation fails because of the type of an object."""
    ...
