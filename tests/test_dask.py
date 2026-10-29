# dependencies
import pytest
import typing_extensions as tx

# locals
from bagof.validators.base import Validator
from bagof.validators.exceptions import (
    TypeValidationError,
    ValueValidationError,
)

np = pytest.importorskip("numpy")
da = pytest.importorskip("dask.array")

validators_dask = pytest.importorskip("bagof.validators.dask")
hints_dask = pytest.importorskip("bagof.hints.dask")
L = tx.Literal


def test_dask_is_registered() -> None:
    assert Validator.get_class(da.Array) is validators_dask.IsDaskArray
    assert Validator.get_class(hints_dask.NDArray[np.float64]) is (
        validators_dask.IsDaskArray
    )


def test_dask_valid() -> None:
    hint = hints_dask.Array[tx.Tuple[L[2], int], hints_dask.dtype[float]]
    Validator.get(hint)(da.zeros((2, 5)))


@pytest.mark.parametrize("value", [np.zeros((2, 5)), [[0.0] * 5] * 2])
def test_dask_rejects_other_arrays(value: tx.Any) -> None:
    with pytest.raises(TypeValidationError):
        Validator.get(da.Array)(value)


def test_dask_invalid_dtype() -> None:
    with pytest.raises(TypeValidationError, match="dtype"):
        Validator.get(hints_dask.NDArray[np.float64])(da.zeros(3, dtype=int))


def test_dask_invalid_shape() -> None:
    hint = hints_dask.Array[tx.Tuple[L[2], int], hints_dask.dtype[tx.Any]]
    with pytest.raises(ValueValidationError, match="shape"):
        Validator.get(hint)(da.zeros((3, 5)))


def test_dask_unknown_size_is_accepted() -> None:
    hint = hints_dask.Array[tx.Tuple[L[2]], hints_dask.dtype[tx.Any]]
    arr = da.from_array(np.arange(4), chunks=2)
    arr = arr[arr > 1]
    Validator.get(hint)(arr)
