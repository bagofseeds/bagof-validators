"""
Shared base for the array validators (numpy / cupy / dask).

The three array libraries validate identically: check that the value is
one of the library's arrays (of the requested subclass), that its dtype
is the one named in the hint, and that its shape matches the shape named
in the hint. This module factors that out so the per-library modules stay
a few lines each.
"""

__all__ = ["ArrayValidator", "scalar_maps"]

# stdlib
import numbers

# dependencies
import typing_extensions as tx

# bags
from bagof.core.magic import get_args_uw, safe_isinstance, safe_issubclass

# locals
from ._shapes import ShapeSpec, shape_spec
from .base import Validator


def scalar_maps(xp: tx.Any) -> dict:
    """
    Build the dtype lookup table for a scalar namespace ``xp``.

    Returns
    -------
    py_to_scalar : dict
        Maps Python (and [`numbers`][]) types to the namespace's scalar
        type, e.g. ``float -> xp.floating``.
    """
    return {
        object: xp.object_,
        str: xp.str_,
        bool: xp.bool_,
        int: xp.integer,
        float: xp.floating,
        complex: xp.complexfloating,
        numbers.Number: xp.number,
        numbers.Complex: xp.complexfloating,
        numbers.Real: xp.floating,
        numbers.Rational: xp.floating,
        numbers.Integral: xp.integer,
    }


class ArrayValidator(Validator[tx.Any]):
    """
    Base for array validators.

    A subclass sets the class attributes below; it does not override
    ``__call__``. An optional library's namespaces may be given lazily
    (see [`lazy_import`][bagof.core.magic.lazy_import]) so the class body
    never imports it.

    Unlike the converters, a validator never moves nor reshapes a value:
    an array of another library (e.g. a cupy array for a numpy hint) is
    rejected, and the shape must match the hint exactly -- without
    padding or broadcasting.

    !!! note
        The concrete validators (``IsNDArray``, ``IsDaskArray``,
        ``IsCupyArray``) are only defined and registered when their
        backing library (numpy, dask or cupy) is installed.
    """

    #: The scalar-type namespace (numpy, or cupy for cupy arrays) used to
    #: build the dtype table. dask reuses numpy's, since dask arrays hold
    #: numpy dtypes.
    SCALARS: tx.Any = None
    #: The concrete array type (``numpy.ndarray`` / ``cupy.ndarray`` /
    #: ``dask.array.Array``).
    ARRAY_TYPE: tx.Any = None
    #: The ``bagof.hints`` stub for the array type. On Python 3.8 (where the
    #: real type is not subscriptable) a parametrised hint carries the stub
    #: as its origin, so it is mapped back to ``ARRAY_TYPE``.
    HINT_TYPE: tx.Any = None

    @property
    def _array_origin(self) -> tx.Any:
        # Map the hint stub back to the real array type (see HINT_TYPE).
        origin = self.origin
        if origin is self.HINT_TYPE:
            return self.ARRAY_TYPE
        return origin

    @property
    def _target_scalar(self) -> tx.Any:
        # The scalar type named by ``ndarray[shape, dtype[X]]`` -> ``X``.
        args = self.args
        if len(args) < 2:
            return None
        dtype_args = get_args_uw(args[1])
        if not dtype_args:
            return None
        scalar = dtype_args[0]
        if scalar is tx.Any or not isinstance(scalar, type):
            # `Any` or a `TypeVar` (as in the bare `NDArray` alias).
            return None
        return scalar_maps(self.SCALARS).get(scalar, scalar)

    @property
    def _target_shape(self) -> tx.Optional[ShapeSpec]:
        # The shapes named by ``ndarray[shape, dtype]``, or None for any.
        args = self.args
        if not args:
            return None
        return shape_spec(args[0])

    def __call__(self, value: tx.Any) -> None:
        """Check the value's array type, dtype and shape."""
        origin = self._array_origin
        if not safe_isinstance(value, origin):
            raise self.type_error(
                value, f"Not an instance of {_qualname(origin)}."
            )
        scalar = self._target_scalar
        if scalar is not None and not safe_issubclass(
            value.dtype.type, scalar
        ):
            raise self.type_error(
                value,
                f"Invalid dtype {value.dtype}: "
                f"expected a subtype of {_qualname(scalar)}.",
            )
        shape = self._target_shape
        if shape is not None:
            message = shape.check(value.shape)
            if message is not None:
                raise self.value_error(value, message)


def _qualname(obj: tx.Any) -> str:
    """The dotted name of a class, for error messages."""
    module = getattr(obj, "__module__", None)
    name = getattr(obj, "__qualname__", None) or repr(obj)
    return f"{module}.{name}" if module else name
