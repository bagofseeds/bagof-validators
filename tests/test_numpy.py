# dependencies
import pytest
import typing_extensions as tx

# locals
from bagof.validators import numpy as validators_numpy
from bagof.validators.base import Validator
from bagof.validators.exceptions import TypeValidationError

np = pytest.importorskip("numpy", reason="numpy is an optional dependency")


def test_is_dtype_is_exported() -> None:
    assert "IsDType" in validators_numpy.__all__
    assert validators_numpy.IsDType.DEFAULT is np.dtype


@pytest.mark.parametrize(
    "hint,value",
    [
        # Default hint (`np.dtype`)
        (np.dtype, np.dtype("float32")),
        (np.dtype, np.dtype(int)),
        (np.dtype, np.dtype("S1")),
        # Scalar types
        (np.generic, np.float32(1)),
        (np.generic, np.int64(1)),
        (np.float32, np.float32(1)),
    ],
)
def test_dtype_valid(hint: tx.Any, value: tx.Any) -> None:
    validator = validators_numpy.IsDType(hint)
    validator(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        # A scalar is not a dtype, and vice versa.
        (np.dtype, np.float32(1)),
        (np.generic, np.dtype("float32")),
        # Not a numpy value at all.
        (np.dtype, 1),
        (np.dtype, "float32"),
        (np.dtype, None),
        (np.generic, 1.5),
        (np.float32, np.int64(1)),
    ],
)
def test_dtype_invalid(hint: tx.Any, value: tx.Any) -> None:
    validator = validators_numpy.IsDType(hint)
    with pytest.raises(TypeValidationError):
        validator(value)


def test_dtype_default_hint() -> None:
    validator = validators_numpy.IsDType()
    validator(np.dtype("float32"))
    with pytest.raises(TypeValidationError):
        validator(1)


@pytest.mark.parametrize("hint", [np.dtype, np.generic])
def test_dtype_is_registered(hint: tx.Any) -> None:
    assert Validator.get_class(hint) is validators_numpy.IsDType
    assert isinstance(Validator.get(hint), validators_numpy.IsDType)
