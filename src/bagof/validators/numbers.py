"""Validators for numeric types (int, float, etc.)."""

__all__ = [
    "IsNumber",
    "IsPositive",
    "IsNegative",
    "IsNonNegative",
    "IsNonPositive",
    "IsLessThan",
    "IsLessEqual",
    "IsGreaterThan",
    "IsGreaterEqual",
    "IsInRange",
]

# stdlib
import numbers

# dependencies
import typing_extensions as tx

# bags
from bagof.core.magic import UNSET
from bagof.hints.typevars.co import NUMBER

# locals
from .base import Validator


class IsNumber(Validator[NUMBER], register=numbers.Number):
    """
    Validator for [`Number`][numbers.Number].

    !!! note
        Numeric widening is accepted: an [`int`][] passes a [`float`][]
        hint, and an [`int`][] or [`float`][] passes a [`complex`][] hint.
    """

    DEFAULT = numbers.Number

    def __call__(self, value: NUMBER) -> None:
        # Deal with int / float / complex differently
        # (i.e., accept int for float, and float for complex)
        if self.origin is float and isinstance(value, int):
            return
        if self.origin is complex and isinstance(value, (int, float)):
            return
        super().__call__(value)  # check type


class IsPositive(IsNumber[NUMBER]):
    """Validator for positive numbers."""

    def __call__(self, value: NUMBER) -> None:
        super().__call__(value)
        if value <= 0:
            raise self.value_error(value, "Not a positive value.")


class IsNegative(IsNumber[NUMBER]):
    """Validator for negative numbers."""

    def __call__(self, value: NUMBER) -> None:
        super().__call__(value)
        if value >= 0:
            raise self.value_error(value, "Not a negative value.")


class IsNonNegative(IsNumber[NUMBER]):
    """Validator for non-negative numbers."""

    def __call__(self, value: NUMBER) -> None:
        super().__call__(value)
        if value < 0:
            raise self.value_error(value, "Not a non-negative value.")


class IsNonPositive(IsNumber[NUMBER]):
    """Validator for non-positive numbers."""

    def __call__(self, value: NUMBER) -> None:
        super().__call__(value)
        if value > 0:
            raise self.value_error(value, "Not a non-positive value.")


class _ComparatorValidator(IsNumber[NUMBER]):

    def __init__(
        self,
        threshold: NUMBER,
        hint: tx.Any = UNSET,
        compose: bool = False,
    ) -> None:
        """
        Parameters
        ----------
        threshold : NUMBER
            The threshold value to compare against.
        hint : Any, optional
            The type hint to validate against.
        compose : bool
            Whether to compose this validator with others, when they are
            found in [`Annotated`][typing.Annotated] metadata.
        """
        super().__init__(hint, compose)
        self.threshold = threshold

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.threshold!r})"


class IsLessThan(_ComparatorValidator[NUMBER]):
    """Validator for numbers less than a threshold."""

    def __call__(self, value: NUMBER) -> None:
        super().__call__(value)
        if value >= self.threshold:
            raise self.value_error(value, f"Not less than {self.threshold!r}")


class IsLessEqual(_ComparatorValidator[NUMBER]):
    """Validator for numbers less than or equal to a threshold."""

    def __call__(self, value: NUMBER) -> None:
        super().__call__(value)
        if value > self.threshold:
            raise self.value_error(
                value, f"Not less than or equal to {self.threshold!r}"
            )


class IsGreaterThan(_ComparatorValidator[NUMBER]):
    """Validator for numbers greater than a threshold."""

    def __call__(self, value: NUMBER) -> None:
        super().__call__(value)
        if value <= self.threshold:
            raise self.value_error(
                value, f"Not greater than {self.threshold!r}."
            )


class IsGreaterEqual(_ComparatorValidator[NUMBER]):
    """Validator for numbers greater than or equal to a threshold."""

    def __call__(self, value: NUMBER) -> None:
        super().__call__(value)
        if value < self.threshold:
            raise self.value_error(
                value, f"Not greater than or equal to {self.threshold!r}."
            )


class IsInRange(IsNumber[NUMBER]):
    """
    Validator for numbers in a range.

    !!! example
        ```pycon
        >>> from bagof.validators.numbers import IsInRange
        >>> validate = IsInRange(0, 1)
        >>> validate(0.5)
        >>> validate(2)
        ValueValidationError: IsInRange(0, 1): Not in range [0, 1].
        |> value = 2
        ```
    """

    def __init__(
        self,
        min_value: NUMBER,
        max_value: NUMBER,
        inclusive: tx.Union[bool, tx.Tuple[bool, bool]] = True,
        hint: tx.Any = UNSET,
        compose: bool = False,
    ) -> None:
        """
        Parameters
        ----------
        min_value : NUMBER
            The minimum value of the range.
        max_value : NUMBER
            The maximum value of the range.
        inclusive : bool | (bool, bool), optional
            Whether the range is inclusive on both ends.
            If a single boolean is provided, it applies to both ends.
        hint : Any, optional
            The type hint to validate against.
        compose : bool
            Whether to compose this validator with others, when they are
            found in [`Annotated`][typing.Annotated] metadata.
        """
        super().__init__(hint, compose)
        if isinstance(inclusive, bool):
            inclusive = (inclusive, inclusive)
        self.min_value = min_value
        self.max_value = max_value
        self.inclusive = inclusive

    def __repr__(self) -> str:
        args = f"{self.min_value!r}, {self.max_value!r}"
        if self.inclusive != (True, True):
            args += f", inclusive={self.inclusive!r}"
        return f"{type(self).__name__}({args})"

    def __call__(self, value: NUMBER) -> None:
        super().__call__(value)
        mn, mx = self.min_value, self.max_value
        if all(self.inclusive):
            test = (mn <= value <= mx)
            lb, ub = "[", "]"
        elif not any(self.inclusive):
            test = (mn < value < mx)
            lb, ub = "(", ")"
        elif not self.inclusive[0]:
            test = (mn < value <= mx)
            lb, ub = "(", "]"
        else:
            test = (mn <= value < mx)
            lb, ub = "[", ")"
        if not test:
            raise self.value_error(
                value, f"Not in range {lb}{mn!r}, {mx!r}{ub}."
            )
