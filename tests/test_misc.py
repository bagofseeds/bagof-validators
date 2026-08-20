# dependencies
import pytest
import typing_extensions as tx

# bags
from bagof.hints.typevars.co import INT

# locals
from bagof.validators import misc
from bagof.validators.exceptions import (
    TypeValidationError,
    ValueValidationError,
)


@pytest.mark.parametrize(
    "forbidden,value",
    [
        ([1, 2], 3),
        ([1, 2], 0),
        ((1, 2), 3),
        ({1, 2}, 3),
        ("ab", "c"),
        ([], 1),
        # The default hint is `Any`, so any type is accepted.
        ([1, 2], "a"),
        ([1, 2], None),
    ],
)
def test_is_not_one_of_valid(forbidden: tx.Any, value: tx.Any) -> None:
    validator = misc.IsNotOneOfValidator(forbidden)
    validator(value)


@pytest.mark.parametrize(
    "forbidden,value",
    [
        ([1, 2], 1),
        ([1, 2], 2),
        ((1, 2), 1),
        ({1, 2}, 1),
        ("ab", "a"),
        ([None], None),
    ],
)
def test_is_not_one_of_invalid(forbidden: tx.Any, value: tx.Any) -> None:
    validator = misc.IsNotOneOfValidator(forbidden)
    with pytest.raises(ValueValidationError):
        validator(value)


@pytest.mark.parametrize("hint", [int, INT])
def test_is_not_one_of_hint(hint: tx.Any) -> None:
    validator = misc.IsNotOneOfValidator([1, 2], hint)
    validator(3)
    with pytest.raises(ValueValidationError):
        validator(1)
    # The type is checked before the value.
    with pytest.raises(TypeValidationError):
        validator("a")


def test_is_not_one_of_materialises_the_forbidden_values() -> None:
    # Stored as a tuple rather than a set: membership is decided by type
    # and value, not by hashing, so an unhashable forbidden value works.
    validator = misc.IsNotOneOf([1, 2, 2])
    assert tuple(validator.forbidden) == (1, 2, 2)


def test_is_not_one_of_accepts_unhashable_forbidden_values() -> None:
    validator = misc.IsNotOneOf([[1], [2]], hint=tx.Any)
    validator([3])
    with pytest.raises(ValueValidationError):
        validator([1])


@pytest.mark.parametrize(
    "forbidden,value",
    [
        ([1], True),        # True is not 1
        ([0], False),       # False is not 0
        ([True], 1),
        ([1.0], 1),         # a float literal is not an int
    ],
)
def test_is_not_one_of_matches_by_type_as_well_as_value(
    forbidden: tx.Any, value: tx.Any
) -> None:
    # `value in set(forbidden)` conflated these pairs, so forbidding one
    # silently forbade the other.
    misc.IsNotOneOf(forbidden, hint=tx.Any)(value)


def test_is_not_one_of_alias_is_the_same_class() -> None:
    assert misc.IsNotOneOfValidator is misc.IsNotOneOf


def test_is_not_one_of_consumes_iterators() -> None:
    # The forbidden values are materialized at construction time, so an
    # iterator is not exhausted by the first call.
    validator = misc.IsNotOneOfValidator(iter([1, 2]))
    with pytest.raises(ValueValidationError):
        validator(1)
    with pytest.raises(ValueValidationError):
        validator(1)
