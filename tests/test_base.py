# dependencies
import pytest
import typing_extensions as tx

# bags
from bagof.core.magic import UNSET

# locals
from bagof.validators import base, collections, misc, numbers, strings
from bagof.validators.base import (
    Validator,
    get_validator,
    get_validator_class,
    register_validator,
)
from bagof.validators.exceptions import (
    TypeValidationError,
    ValidationError,
    ValueValidationError,
)


class Foo:
    """A type that no validator is registered for."""


@pytest.fixture
def registry() -> base.ValidatorRegistry:
    """An isolated registry, so that the global one is left untouched."""
    return {}


@pytest.mark.parametrize(
    "hint,value",
    [
        (tx.Any, 1),
        (tx.Any, "a"),
        (tx.Any, None),
        (int, 1),
        (str, "a"),
        (Foo, Foo()),
    ],
)
def test_default_validator_valid(hint: tx.Any, value: tx.Any) -> None:
    Validator(hint)(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        (int, "a"),
        (str, 1),
        (Foo, 1),
        (Foo, None),
    ],
)
def test_default_validator_invalid(hint: tx.Any, value: tx.Any) -> None:
    with pytest.raises(TypeValidationError):
        Validator(hint)(value)


def test_default_hint_is_any() -> None:
    assert Validator().hint is tx.Any
    assert Validator(UNSET).hint is tx.Any


def test_compose_flag() -> None:
    assert Validator(int).compose is False
    assert Validator(int, compose=True).compose is True


@pytest.mark.parametrize(
    "factory",
    [
        # Every validator with extra constructor arguments must still
        # forward `hint` and `compose` to the base class.
        lambda **k: numbers.IsLessThan(10, **k),
        lambda **k: numbers.IsLessEqual(10, **k),
        lambda **k: numbers.IsGreaterThan(10, **k),
        lambda **k: numbers.IsGreaterEqual(10, **k),
        lambda **k: numbers.IsInRange(0, 10, **k),
        lambda **k: strings.MatchesRegex(r"^a", **k),
        lambda **k: misc.IsNotOneOfValidator([1], **k),
        lambda **k: collections.HasLength(1, **k),
    ],
)
def test_compose_is_forwarded(factory: tx.Any) -> None:
    assert factory().compose is False
    assert factory(compose=True).compose is True
    assert factory(hint=int, compose=True).hint is int


# ----------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "type,expected",
    [
        (UNSET, ValidationError),
        ("value", ValueValidationError),
        ("type", TypeValidationError),
        (ValueValidationError, ValueValidationError),
        (TypeValidationError, TypeValidationError),
    ],
)
def test_error_types(type: tx.Any, expected: tx.Any) -> None:
    validator = Validator(int)
    kwargs = {} if type is UNSET else {"type": type}
    error = validator.make_error(1, "message", **kwargs)
    assert isinstance(error, expected)
    assert error.this is validator
    assert error.value == 1
    assert error.message == "message"


def test_error_raises_what_make_error_builds() -> None:
    # `make_error` builds, `error` raises - the two are never the same
    # verb, so neither can be mistaken for the other.
    validator = Validator(int)
    with pytest.raises(ValidationError) as info:
        validator.error("message", 1)
    assert info.value.this is validator
    assert info.value.value == 1
    assert info.value.message == "message"


def test_error_raises_the_subclass_error_type() -> None:
    # `error` is inherited from `MagicHint`, but it must raise the type
    # this class's `make_error` builds, not a bare `MagicError`.
    with pytest.raises(TypeValidationError):
        Validator(int).error("message", 1, type="type")


@pytest.mark.parametrize(
    "method,expected",
    [
        ("make_error", ValidationError),
        ("type_error", TypeValidationError),
        ("value_error", ValueValidationError),
    ],
)
def test_error_default_messages(method: str, expected: tx.Any) -> None:
    validator = Validator(int)
    error = getattr(validator, method)("a")
    assert isinstance(error, expected)
    assert error.message


def test_type_error_default_message_mentions_type() -> None:
    error = Validator(int).type_error("a")
    assert str(str) in error.message


# ----------------------------------------------------------------------
# Registration
# ----------------------------------------------------------------------


def test_register_via_class_kwarg(registry: base.ValidatorRegistry) -> None:

    class IsFoo(Validator[tx.Any]):
        DEFAULT = Foo

    Validator.register(IsFoo, Foo, registry=registry)
    assert registry == {Foo: IsFoo}


def test_register_default_hint(registry: base.ValidatorRegistry) -> None:

    class IsFoo(Validator[tx.Any]):
        DEFAULT = Foo

    # With no explicit hint, the class' DEFAULT is used.
    Validator.register(IsFoo, registry=registry)
    assert registry == {Foo: IsFoo}


def test_register_multiple_hints(registry: base.ValidatorRegistry) -> None:

    class IsFoo(Validator[tx.Any]):
        DEFAULT = Foo

    Validator.register(IsFoo, Foo, int, registry=registry)
    assert registry == {Foo: IsFoo, int: IsFoo}


def test_register_as_decorator(registry: base.ValidatorRegistry) -> None:

    @Validator.register(Foo, registry=registry)
    class IsFoo(Validator[tx.Any]):
        DEFAULT = Foo

    assert registry == {Foo: IsFoo}


def test_register_metaclass_kwarg_true() -> None:
    # `register=True` registers the class for its own DEFAULT.
    registry: base.ValidatorRegistry = {}

    class IsFoo(Validator[tx.Any], register=True):
        DEFAULT = Foo

    # `register=True` uses the global registry, so clean up after ourselves.
    try:
        assert base.VALIDATORS[Foo] is IsFoo
        assert Validator.get_class(Foo) is IsFoo
    finally:
        base.VALIDATORS.pop(Foo, None)
    assert registry == {}


def test_register_metaclass_kwarg_tuple() -> None:

    class IsFoo(Validator[tx.Any], register=(Foo,)):
        DEFAULT = Foo

    try:
        assert base.VALIDATORS[Foo] is IsFoo
    finally:
        base.VALIDATORS.pop(Foo, None)


def test_register_metaclass_kwarg_single_hint() -> None:

    class IsFoo(Validator[tx.Any], register=Foo):
        DEFAULT = tx.Any

    try:
        assert base.VALIDATORS[Foo] is IsFoo
    finally:
        base.VALIDATORS.pop(Foo, None)


def test_no_register_kwarg_leaves_registry_untouched() -> None:

    class IsFoo(Validator[tx.Any]):
        DEFAULT = Foo

    assert Foo not in base.VALIDATORS


# ----------------------------------------------------------------------
# Lookup
# ----------------------------------------------------------------------


def test_get_class(registry: base.ValidatorRegistry) -> None:

    class IsFoo(Validator[tx.Any]):
        DEFAULT = Foo

    registry[Foo] = IsFoo
    assert Validator.get_class(Foo, registry=registry) is IsFoo


def test_get_returns_an_instance(registry: base.ValidatorRegistry) -> None:

    class IsFoo(Validator[tx.Any]):
        DEFAULT = Foo

    registry[Foo] = IsFoo
    validator = Validator.get(Foo, registry=registry)
    assert isinstance(validator, IsFoo)
    assert validator.hint is Foo


def test_get_falls_back_to_validator(
    registry: base.ValidatorRegistry
) -> None:
    # By default, an unregistered hint falls back to the base `Validator`,
    # so that container validators can validate arbitrary item types.
    assert Validator.get_class(Foo, registry=registry) is Validator
    assert type(Validator.get(Foo, registry=registry)) is Validator


def test_get_explicit_none_fallback(registry: base.ValidatorRegistry) -> None:
    assert Validator.get_class(Foo, registry=registry, fallback=None) is None
    assert Validator.get(Foo, registry=registry, fallback=None) is None


def test_get_explicit_fallback(registry: base.ValidatorRegistry) -> None:

    class IsFallback(Validator[tx.Any]):
        DEFAULT = tx.Any

    assert Validator.get_class(
        Foo, registry=registry, fallback=IsFallback
    ) is IsFallback
    assert isinstance(
        Validator.get(Foo, registry=registry, fallback=IsFallback), IsFallback
    )


def test_get_uses_global_registry_by_default() -> None:
    # `int` resolves to the number validator registered by `numbers`.
    from bagof.validators.numbers import IsNumber
    assert Validator.get_class(int) is IsNumber
    assert isinstance(Validator.get(int), IsNumber)


def test_aliases() -> None:
    assert register_validator is Validator.register
    assert get_validator is Validator.get
    assert get_validator_class is Validator.get_class


# ----------------------------------------------------------------------
# Wrapped validators
# ----------------------------------------------------------------------


@pytest.mark.parametrize("exception", [TypeError, ValueError])
def test_wrap_validator_converts_errors(exception: tx.Any) -> None:

    def failing(value: tx.Any) -> None:
        raise exception("boom")

    wrapped = Validator(int)._wrap_validator(failing)
    with pytest.raises(ValueValidationError) as info:
        wrapped(1)
    assert isinstance(info.value.__cause__, exception)
    assert info.value.value == 1


def test_wrap_validator_passes_through() -> None:
    calls = []
    wrapped = Validator(int)._wrap_validator(calls.append)
    wrapped(1)
    assert calls == [1]


def test_wrap_validator_does_not_catch_other_errors() -> None:

    def failing(value: tx.Any) -> None:
        raise KeyError("boom")

    wrapped = Validator(int)._wrap_validator(failing)
    with pytest.raises(KeyError):
        wrapped(1)


@pytest.mark.parametrize(
    "error",
    [
        ValueValidationError,             # a class
        ValueValidationError("instance"),  # an instance
    ],
)
def test_trywrap_validator_error_kinds(error: tx.Any) -> None:

    def failing(value: tx.Any) -> None:
        raise ValueError("boom")

    wrapped = base._trywrap_validator(failing, error)
    with pytest.raises(ValueValidationError):
        wrapped(1)
