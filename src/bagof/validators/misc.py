"""Miscellaneous validators (forbidden values, etc.)."""

__all__ = [
    "IsNotOneOfValidator",
]

# dependencies
import typing_extensions as tx

# bags
from bagof.core.magic import UNSET
from bagof.hints.typevars.co import T

# locals
from .common import Validator


class IsNotOneOfValidator(Validator[T]):
    """Validator for values not in a forbidden set."""

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
            The set of forbidden values.
        hint : Any, optional
            The type hint to validate against.
            If not provided, the default hint for the class is used.
        compose : bool
            Whether to compose this validator with others, when they are
            found in [`Annotated`][typing.Annotated] metadata.
        """
        super().__init__(hint, compose)
        self.forbidden = set(forbidden)

    def __call__(self, value: T) -> None:
        super().__call__(value)
        if value in self.forbidden:
            raise self.value_error(value, "Forbidden value.")
