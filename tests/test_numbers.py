# stdlib
import numbers as std_numbers

# dependencies
import pytest
import typing_extensions as tx

# bags
from bagof.hints.typevars.co import FLOAT, INT

# locals
from bagof.validators import numbers
from bagof.validators.base import Validator
from bagof.validators.exceptions import (
    TypeValidationError,
    ValueValidationError,
)


@pytest.mark.parametrize(
    "hint,value",
    [
        # Default hint (`numbers.Number`)
        (std_numbers.Number, 1),
        (std_numbers.Number, 1.5),
        (std_numbers.Number, 1j),
        # int
        (int, 1),
        (int, -1),
        (int, 0),
        # float accepts int
        (float, 1.5),
        (float, 1),
        # complex accepts int and float
        (complex, 1j),
        (complex, 1),
        (complex, 1.5),
        # typevars validate exactly like the hint they are bound to,
        # widening included.
        (INT, 1),
        (FLOAT, 1.5),
        (FLOAT, 1),
    ],
)
def test_number_valid(hint: tx.Any, value: tx.Any) -> None:
    default_validator = numbers.IsNumber()
    default_validator(value)
    validator = numbers.IsNumber(hint)
    validator(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        (std_numbers.Number, "a"),
        (std_numbers.Number, None),
        (std_numbers.Number, [1]),
        # int does not accept float or complex
        (int, 1.5),
        (int, 1j),
        # float does not accept complex
        (float, 1j),
        (float, "1.5"),
        # typevars
        (INT, 1.5),
        (FLOAT, 1j),
    ],
)
def test_number_invalid(hint: tx.Any, value: tx.Any) -> None:
    validator = numbers.IsNumber(hint)
    with pytest.raises(TypeValidationError):
        validator(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        (INT, 1),
        (FLOAT, 1.5),
        (FLOAT, 1),
    ],
)
def test_number_typevar_dispatch_valid(hint: tx.Any, value: tx.Any) -> None:
    # Dispatching through the registry gives the same result as building
    # the validator directly with the typevar.
    Validator.get(hint)(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        (INT, 1.5),
        (FLOAT, 1j),
        (INT, "a"),
    ],
)
def test_number_typevar_dispatch_invalid(hint: tx.Any, value: tx.Any) -> None:
    with pytest.raises(TypeValidationError):
        Validator.get(hint)(value)


@pytest.mark.parametrize(
    "cls,valid,invalid",
    [
        (numbers.IsPositive, [1, 1.5], [0, -1, -1.5]),
        (numbers.IsNegative, [-1, -1.5], [0, 1, 1.5]),
        (numbers.IsNonNegative, [0, 1, 1.5], [-1, -1.5]),
        (numbers.IsNonPositive, [0, -1, -1.5], [1, 1.5]),
    ],
)
def test_sign_validators(
    cls: tx.Any, valid: tx.List[tx.Any], invalid: tx.List[tx.Any]
) -> None:
    validator = cls()
    for value in valid:
        validator(value)
    for value in invalid:
        with pytest.raises(ValueValidationError):
            validator(value)


@pytest.mark.parametrize(
    "cls",
    [
        numbers.IsPositive,
        numbers.IsNegative,
        numbers.IsNonNegative,
        numbers.IsNonPositive,
    ],
)
def test_sign_validators_type_check(cls: tx.Any) -> None:
    # The type is checked before the value.
    validator = cls(int)
    with pytest.raises(TypeValidationError):
        validator("a")


@pytest.mark.parametrize(
    "cls,threshold,valid,invalid",
    [
        (numbers.IsLessThan, 10, [9, 9.5, -1], [10, 11]),
        (numbers.IsLessEqual, 10, [9, 10], [11, 10.5]),
        (numbers.IsGreaterThan, 10, [11, 10.5], [10, 9]),
        (numbers.IsGreaterEqual, 10, [10, 11], [9, 9.5]),
    ],
)
def test_comparator_validators(
    cls: tx.Any,
    threshold: tx.Any,
    valid: tx.List[tx.Any],
    invalid: tx.List[tx.Any],
) -> None:
    validator = cls(threshold)
    assert validator.threshold == threshold
    for value in valid:
        validator(value)
    for value in invalid:
        with pytest.raises(ValueValidationError):
            validator(value)


@pytest.mark.parametrize(
    "cls",
    [
        numbers.IsLessThan,
        numbers.IsLessEqual,
        numbers.IsGreaterThan,
        numbers.IsGreaterEqual,
    ],
)
def test_comparator_validators_type_check(cls: tx.Any) -> None:
    validator = cls(10, int)
    with pytest.raises(TypeValidationError):
        validator("a")


@pytest.mark.parametrize(
    "inclusive,value",
    [
        # Inclusive on both ends (default)
        (True, 0),
        (True, 5),
        (True, 10),
        # Exclusive on both ends
        (False, 5),
        # Exclusive lower bound only
        ((False, True), 5),
        ((False, True), 10),
        # Exclusive upper bound only
        ((True, False), 0),
        ((True, False), 5),
    ],
)
def test_in_range_valid(inclusive: tx.Any, value: tx.Any) -> None:
    validator = numbers.IsInRange(0, 10, inclusive)
    validator(value)


@pytest.mark.parametrize(
    "inclusive,value",
    [
        # Inclusive on both ends (default)
        (True, -1),
        (True, 11),
        # Exclusive on both ends
        (False, 0),
        (False, 10),
        (False, -1),
        (False, 11),
        # Exclusive lower bound only
        ((False, True), 0),
        ((False, True), 11),
        # Exclusive upper bound only
        ((True, False), 10),
        ((True, False), -1),
    ],
)
def test_in_range_invalid(inclusive: tx.Any, value: tx.Any) -> None:
    validator = numbers.IsInRange(0, 10, inclusive)
    with pytest.raises(ValueValidationError):
        validator(value)


def test_in_range_attributes() -> None:
    validator = numbers.IsInRange(0, 10)
    assert validator.min_value == 0
    assert validator.max_value == 10
    # A single boolean is expanded to both ends.
    assert validator.inclusive == (True, True)
    assert numbers.IsInRange(0, 10, (True, False)).inclusive == (True, False)


def test_in_range_type_check() -> None:
    validator = numbers.IsInRange(0, 10, hint=int)
    with pytest.raises(TypeValidationError):
        validator("a")
