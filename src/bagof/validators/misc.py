"""Miscellaneous validators (forbidden values, etc.)."""

__all__ = [
    "IsNotOneOf",
    "IsNotOneOfValidator",
]

# dependencies
import typing_extensions as tx

# bags
from bagof.core.magic import UNSET, ishintstance
from bagof.hints.typevars.co import T

# locals
from .common import Validator


class IsNotOneOf(Validator[T]):
    """
    Validator for values not in a forbidden set.

    A value is forbidden only when it matches by **type as well as
    value**: forbidding `1` does not forbid `True`, even though the two
    compare equal.

    !!! example
        ```pycon
        >>> from bagof.validators.misc import IsNotOneOf
        >>> validate = IsNotOneOf(["", "null"])
        >>> validate("name")
        >>> validate("")
        ValueValidationError: IsNotOneOf(): Forbidden value.
        |> value = ''
        ```
    """

    def __init__(
        self,
        forbidden: tx.Iterable[T],
        hint: tx.Any = UNSET,
        compose: bool = False,
    ) -> None:
        """
        Parameters
        ----------
        forbidden : Iterable[T]
            The forbidden values. Need not be hashable.
        hint : Any, optional
            The type hint to validate against.
            If not provided, the default hint for the class is used.
        compose : bool
            Whether to compose this validator with others, when they are
            found in [`Annotated`][typing.Annotated] metadata.
        """
        super().__init__(hint, compose)
        # A tuple, not a set: membership is decided by type and value
        # below rather than by hashing, so an unhashable forbidden value
        # is perfectly usable.
        self.forbidden = tuple(forbidden)

    def __call__(self, value: T) -> None:
        super().__call__(value)
        for forbidden in self.forbidden:
            # `value in self.forbidden` compares with `==`, which
            # conflates `True` with `1` and `0` with `False`. Match the
            # rule `Literal` uses instead.
            if ishintstance(value, tx.Literal[forbidden]):
                raise self.value_error(value, "Forbidden value.")


IsNotOneOfValidator = IsNotOneOf
"""
Deprecated alias for [`IsNotOneOf`][].

Every other validator is named `IsXxx`; the suffix was dropped for
consistency.
"""
