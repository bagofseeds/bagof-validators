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
    """Validator for [`Number`][numbers.Number]."""

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

    def __init__(self, threshold: NUMBER, hint: tx.Any = UNSET) -> None:
        super().__init__(hint)
        self.threshold = threshold


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
    """Validator for numbers in a range."""

    def __init__(
        self,
        min_value: NUMBER,
        max_value: NUMBER,
        hint: tx.Any = UNSET,
    ) -> None:
        super().__init__(hint)
        self.min_value = min_value
        self.max_value = max_value

    def __call__(self, value: NUMBER) -> None:
        super().__call__(value)
        mn, mx = self.min_value, self.max_value
        if not (mn <= value <= mx):
            raise self.value_error(value, f"Not in range [{mn!r}, {mx!r}].")
