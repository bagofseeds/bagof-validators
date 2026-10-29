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


# --- IsNDArray --------------------------------------------------------

hints_numpy = pytest.importorskip("bagof.hints.numpy")
ndarray, NDArray, hints_dtype = (
    hints_numpy.ndarray, hints_numpy.NDArray, hints_numpy.dtype
)
L = tx.Literal


def _shaped(*shape: tx.Any) -> tx.Any:
    return ndarray[tx.Tuple[shape], hints_dtype[tx.Any]]


def test_ndarray_is_registered() -> None:
    assert Validator.get_class(np.ndarray) is validators_numpy.IsNDArray
    assert Validator.get_class(NDArray[np.float64]) is (
        validators_numpy.IsNDArray
    )
    assert "IsNDArray" in validators_numpy.__all__


@pytest.mark.parametrize(
    "hint,value",
    [
        (np.ndarray, np.zeros(3)),
        (np.ndarray, np.zeros((2, 3), dtype=int)),
        (NDArray, np.zeros(3)),
        (NDArray[np.float64], np.zeros(3)),
        (NDArray[float], np.zeros(3, dtype=np.float32)),
        (NDArray[int], np.zeros(3, dtype=np.int8)),
        (NDArray[np.number], np.zeros(3, dtype=np.complex64)),
        (ndarray[tx.Any, hints_dtype[tx.Any]], np.zeros(())),
        (ndarray[tx.Any, np.dtype], np.zeros(3, dtype=int)),
        (_shaped(L[3]), np.zeros(3)),
        (_shaped(L[4], L[4]), np.eye(4)),
        (_shaped(int, L[1, 3]), np.zeros((5, 1))),
        (_shaped(L[3], ...), np.zeros((3, 3, 3))),
        (_shaped(tx.Unpack[tx.Tuple[int, ...]], L[3]), np.zeros((2, 4, 3))),
        (_shaped(), np.zeros(())),
    ],
)
def test_ndarray_valid(hint: tx.Any, value: tx.Any) -> None:
    Validator.get(hint)(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        (np.ndarray, [1, 2, 3]),
        (np.ndarray, 1.0),
        (np.ndarray, np.float64(1)),
        (NDArray[np.float64], np.zeros(3, dtype=np.float32)),
        (NDArray[float], np.zeros(3, dtype=int)),
        (NDArray[int], [1, 2]),
    ],
)
def test_ndarray_invalid_type(hint: tx.Any, value: tx.Any) -> None:
    with pytest.raises(TypeValidationError):
        Validator.get(hint)(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        # a validator neither pads nor broadcasts
        (_shaped(L[4], L[4]), np.zeros(4)),
        (_shaped(L[4], L[4]), np.zeros((1, 4))),
        (_shaped(L[4], L[4]), np.zeros((1, 4, 4))),
        (_shaped(int, int), np.zeros(3)),
        (_shaped(L[3], ...), np.zeros((3, 2))),
        (_shaped(tx.Unpack[tx.Tuple[int, ...]], L[3]), np.zeros(())),
        (_shaped(), np.zeros(1)),
    ],
)
def test_ndarray_invalid_shape(hint: tx.Any, value: tx.Any) -> None:
    from bagof.validators.exceptions import ValueValidationError

    with pytest.raises(ValueValidationError, match="shape"):
        Validator.get(hint)(value)


def test_ndarray_subclass() -> None:
    class MyArray(np.ndarray):
        pass

    validator = Validator.get(MyArray)
    validator(np.zeros(3).view(MyArray))
    with pytest.raises(TypeValidationError):
        validator(np.zeros(3))


def test_ndarray_rejects_device_arrays() -> None:
    # Unlike the converter, a validator does not move arrays: an array of
    # another library is not a numpy array.
    class FakeCupyArray:
        __cuda_array_interface__: dict = {}
        shape = (3,)
        dtype = np.dtype("float64")

    with pytest.raises(TypeValidationError):
        Validator.get(np.ndarray)(FakeCupyArray())
