# dependencies
import pytest
import typing_extensions as tx

# bags
from bagof.core.magic import MagicError

# locals
from bagof.validators import exceptions
from bagof.validators.base import Validator


@pytest.mark.parametrize(
    "cls,bases",
    [
        (exceptions.ValidationError, (MagicError,)),
        (exceptions.ValueValidationError, (exceptions.ValidationError,
                                          ValueError)),
        (exceptions.TypeValidationError, (exceptions.ValidationError,
                                          TypeError)),
    ],
)
def test_hierarchy(cls: tx.Any, bases: tx.Tuple[type, ...]) -> None:
    for base in bases:
        assert issubclass(cls, base)


@pytest.mark.parametrize(
    "cls",
    [
        exceptions.ValidationError,
        exceptions.ValueValidationError,
        exceptions.TypeValidationError,
    ],
)
def test_validator_kwarg_is_aliased_to_this(cls: tx.Any) -> None:
    # `validator=` is a backward-compatible alias for `this=`.
    validator = Validator(int)
    error = cls("message", validator=validator)
    assert error.this is validator
    assert error.message == "message"


@pytest.mark.parametrize(
    "cls",
    [
        exceptions.ValidationError,
        exceptions.ValueValidationError,
        exceptions.TypeValidationError,
    ],
)
def test_this_kwarg(cls: tx.Any) -> None:
    validator = Validator(int)
    error = cls("message", this=validator, value=1)
    assert error.this is validator
    assert error.value == 1


def test_raisable() -> None:
    with pytest.raises(exceptions.ValidationError):
        raise exceptions.ValueValidationError("message")
    # Value/type errors are also catchable as builtin exceptions.
    with pytest.raises(ValueError):
        raise exceptions.ValueValidationError("message")
    with pytest.raises(TypeError):
        raise exceptions.TypeValidationError("message")
