# stdlib
import sys

# dependencies
import pytest
import typing_extensions as tx

# bags
from bagof.hints.typevars.co import INT, STR, NoneType, T

# locals
from bagof.validators import common
from bagof.validators.base import Validator
from bagof.validators.exceptions import (
    TypeValidationError,
    ValidationError,
    ValueValidationError,
)

# `X | Y` unions only exist from python 3.10 onwards.
HAS_UNION_TYPE = sys.version_info >= (3, 10)
requires_union_type = pytest.mark.skipif(
    not HAS_UNION_TYPE, reason="requires python >= 3.10"
)


# ----------------------------------------------------------------------
# IsAny
# ----------------------------------------------------------------------


@pytest.mark.parametrize("value", [1, "a", None, [1], object(), Ellipsis])
def test_any_accepts_everything(value: tx.Any) -> None:
    common.IsAny()(value)
    common.IsAny(tx.Any)(value)
    # `Any` is registered, so it is also reachable through the dispatcher.
    Validator.get(tx.Any)(value)


# ----------------------------------------------------------------------
# IsNone
# ----------------------------------------------------------------------


@pytest.mark.parametrize("hint", [NoneType, None])
def test_none_valid(hint: tx.Any) -> None:
    common.IsNone()(None)
    Validator.get(NoneType)(None)


@pytest.mark.parametrize("value", [1, "a", 0, False, [], object()])
def test_none_invalid(value: tx.Any) -> None:
    validator = common.IsNone()
    with pytest.raises(TypeValidationError):
        validator(value)


def test_none_is_registered() -> None:
    assert isinstance(Validator.get(NoneType), common.IsNone)


# ----------------------------------------------------------------------
# IsUnion
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "hint,value",
    [
        (tx.Union[int, str], 1),
        (tx.Union[int, str], "a"),
        (tx.Optional[int], 1),
        (tx.Optional[int], None),
        (tx.Union[int, str, None], None),
        (tx.Union[INT, STR], 1),
        (tx.Union[INT, STR], "a"),
        # Annotated unions are unwrapped.
        (tx.Annotated[tx.Union[int, str], "meta"], 1),
    ],
)
def test_union_valid(hint: tx.Any, value: tx.Any) -> None:
    validator = common.IsUnion(hint)
    validator(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        (tx.Union[int, str], None),
        (tx.Union[int, str], [1]),
        (tx.Optional[int], "a"),
        (tx.Union[INT, STR], None),
        (tx.Annotated[tx.Union[int, str], "meta"], None),
    ],
)
def test_union_invalid(hint: tx.Any, value: tx.Any) -> None:
    validator = common.IsUnion(hint)
    with pytest.raises(ValidationError):
        validator(value)


def test_union_error_collects_causes() -> None:
    validator = common.IsUnion(tx.Union[int, str])
    with pytest.raises(TypeValidationError) as info:
        validator(None)
    # Each failed member contributes a cause. The `MultipleCauses` wrapper
    # is transparent, so the members show up directly.
    causes = info.value.causes
    assert len(causes) == 2
    assert all(isinstance(c, ValidationError) for c in causes)


def test_union_error_reports_causes_in_its_message() -> None:
    validator = common.IsUnion(tx.Union[int, str])
    with pytest.raises(TypeValidationError) as info:
        validator(None)
    message = info.value._make_message()
    # Both member failures are visible, each on its own line.
    assert message.count("\n?>") == 2
    assert info.value.depth == 2


@pytest.mark.parametrize("hint", [int, str, tx.List[int], tx.Literal[1]])
def test_union_rejects_non_union_hints(hint: tx.Any) -> None:
    with pytest.raises(TypeError, match="not a Union"):
        common.IsUnion(hint)


def test_union_rejects_bare_union() -> None:
    # The default hint is a bare `Union`, which has no arguments.
    with pytest.raises(TypeError, match="No arguments"):
        common.IsUnion()


def test_union_is_registered() -> None:
    assert isinstance(Validator.get(tx.Union[int, str]), common.IsUnion)


@requires_union_type
def test_union_type_valid() -> None:
    hint = int | str
    common.IsUnion(hint)(1)
    common.IsUnion(hint)("a")
    with pytest.raises(ValidationError):
        common.IsUnion(hint)(None)


@requires_union_type
def test_union_type_is_registered() -> None:
    assert isinstance(Validator.get(int | str), common.IsUnion)


def test_union_of_unregistered_types() -> None:

    class Foo:
        pass

    # Unregistered members fall back to the base validator instead of
    # blowing up.
    common.IsUnion(tx.Union[Foo, int])(Foo())
    common.IsUnion(tx.Union[Foo, int])(1)
    with pytest.raises(ValidationError):
        common.IsUnion(tx.Union[Foo, int])("a")


# ----------------------------------------------------------------------
# IsLiteral
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "hint,value",
    [
        (tx.Literal["a"], "a"),
        (tx.Literal["a", "b"], "b"),
        (tx.Literal[1, 2], 1),
        (tx.Literal[None], None),
        (tx.Literal[1, "a", None], None),
    ],
)
def test_literal_valid(hint: tx.Any, value: tx.Any) -> None:
    validator = common.IsLiteral(hint)
    validator(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        (tx.Literal["a"], "b"),
        (tx.Literal["a", "b"], "c"),
        (tx.Literal[1, 2], 3),
        (tx.Literal[1, 2], None),
        (tx.Literal[None], 1),
    ],
)
def test_literal_invalid(hint: tx.Any, value: tx.Any) -> None:
    validator = common.IsLiteral(hint)
    with pytest.raises(TypeValidationError):
        validator(value)


def test_literal_bare_hint_accepts_nothing() -> None:
    # A bare `Literal` has no arguments, so nothing is valid.
    with pytest.raises(TypeValidationError):
        common.IsLiteral()(1)


def test_literal_is_registered() -> None:
    assert isinstance(Validator.get(tx.Literal[1]), common.IsLiteral)


# ----------------------------------------------------------------------
# IsTypeVar
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "hint,value",
    [
        (INT, 1),
        (STR, "a"),
        # An unbound typevar accepts anything.
        (T, 1),
        (T, "a"),
        (T, None),
    ],
)
def test_typevar_valid(hint: tx.Any, value: tx.Any) -> None:
    validator = common.IsTypeVar(hint)
    validator(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        (INT, "a"),
        (INT, None),
        (STR, 1),
    ],
)
def test_typevar_invalid(hint: tx.Any, value: tx.Any) -> None:
    validator = common.IsTypeVar(hint)
    with pytest.raises(ValidationError):
        validator(value)


@pytest.mark.parametrize("hint,expected", [(INT, int), (STR, str)])
def test_typevar_unwrapped(hint: tx.Any, expected: tx.Any) -> None:
    assert common.IsTypeVar(hint).unwrapped is expected
    # `Annotated` wrappers are unwrapped too.
    assert common.IsTypeVar(tx.Annotated[hint, "meta"]).unwrapped is expected


def test_typevar_is_registered() -> None:
    assert isinstance(Validator.get(INT), common.IsTypeVar)


# ----------------------------------------------------------------------
# IsAnnotated
# ----------------------------------------------------------------------


class _Marker:
    """Metadata that no validator is registered for."""


@pytest.mark.parametrize(
    "hint,value",
    [
        # Metadata with no validator falls back to the wrapped type.
        (tx.Annotated[int, "meta"], 1),
        (tx.Annotated[int, _Marker()], 1),
        (tx.Annotated[str, "meta"], "a"),
        (tx.Annotated[tx.List[int], "meta"], [1, 2]),
    ],
)
def test_annotated_falls_back_to_wrapped_type_valid(
    hint: tx.Any, value: tx.Any
) -> None:
    common.IsAnnotated(hint)(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        (tx.Annotated[int, "meta"], "a"),
        (tx.Annotated[str, "meta"], 1),
        (tx.Annotated[tx.List[int], "meta"], ["a"]),
    ],
)
def test_annotated_falls_back_to_wrapped_type_invalid(
    hint: tx.Any, value: tx.Any
) -> None:
    with pytest.raises(ValidationError):
        common.IsAnnotated(hint)(value)


def test_annotated_with_validator_instance() -> None:
    # bags
    from bagof.validators.numbers import IsPositive

    hint = tx.Annotated[int, IsPositive(int)]
    validator = common.IsAnnotated(hint)
    # A non-composable validator replaces the type check entirely.
    assert len(validator.validators) == 1
    validator(1)
    with pytest.raises(ValueValidationError):
        validator(-1)


def test_annotated_with_validator_class() -> None:
    # bags
    from bagof.validators.numbers import IsPositive

    # A validator class is instantiated with the wrapped type.
    hint = tx.Annotated[int, IsPositive]
    validator = common.IsAnnotated(hint)
    assert len(validator.validators) == 1
    assert isinstance(validator.validators[0], IsPositive)
    assert validator.validators[0].hint is int
    validator(1)
    with pytest.raises(ValueValidationError):
        validator(-1)


def test_annotated_composable_validator_keeps_type_check() -> None:
    # bags
    from bagof.validators.numbers import IsPositive

    hint = tx.Annotated[int, IsPositive(compose=True)]
    validator = common.IsAnnotated(hint)
    # A composable validator is applied *after* the wrapped type check.
    assert len(validator.validators) == 2
    validator(1)
    with pytest.raises(ValidationError):
        validator(-1)
    with pytest.raises(ValidationError):
        validator("a")


def test_annotated_composes_several_validators() -> None:
    # bags
    from bagof.validators.numbers import IsGreaterThan, IsLessThan

    hint = tx.Annotated[
        int, IsGreaterThan(0, compose=True), IsLessThan(10, compose=True)
    ]
    validator = common.IsAnnotated(hint)
    assert len(validator.validators) == 3
    validator(5)
    for value in (0, 10):
        with pytest.raises(ValueValidationError):
            validator(value)


def test_annotated_validators_are_cached() -> None:
    validator = common.IsAnnotated(tx.Annotated[int, "meta"])
    assert validator.validators is validator.validators


def test_annotated_registry() -> None:

    class Marker:
        pass

    class IsMarked(Validator[tx.Any]):
        DEFAULT = tx.Any

        def __init__(self, marker: tx.Any = None) -> None:
            super().__init__(int)
            self.marker = marker

        def __call__(self, value: tx.Any) -> None:
            if value != 42:
                raise self.value_error(value, "Not marked.")

    common.IsAnnotated.register(Marker)(IsMarked)
    try:
        validator = common.IsAnnotated(tx.Annotated[int, Marker()])
        assert len(validator.validators) == 1
        assert isinstance(validator.validators[0], IsMarked)
        validator(42)
        with pytest.raises(ValueValidationError):
            validator(1)
    finally:
        common.IsAnnotated._REGISTRY.pop(Marker, None)


def test_annotated_is_registered() -> None:
    hint = tx.Annotated[int, "meta"]
    assert isinstance(Validator.get(hint), common.IsAnnotated)
