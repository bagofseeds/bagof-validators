"""Validators for numpy types (dtype, ndarray)."""

__all__ = []

# dependencies
import typing_extensions as tx

# locals
from ._arrays import ArrayValidator
from .base import Validator

if tx.TYPE_CHECKING:
    # Import the bare module so mkdocstrings resolves the `numpy.*`
    # cross-references in the docstrings below. Type-checking only.
    import numpy  # noqa: F401
    import numpy as np
    from bagof.hints.numpy import ndarray as _hint_ndarray
    from bagof.hints.numpy.typevars.co import DTYPE
    from numpy import dtype, generic
else:
    try:
        import numpy as np
        from bagof.hints.numpy import ndarray as _hint_ndarray
        from bagof.hints.numpy.typevars.co import DTYPE
        from numpy import dtype, generic
    except ImportError:  # pragma: no cover
        np = _hint_ndarray = dtype = generic = None  # type: ignore

if tx.TYPE_CHECKING or dtype is not None:

    class IsDType(Validator[DTYPE], register=(dtype, generic)):
        """Validator for [`numpy.dtype`][numpy.dtype]."""

        DEFAULT = dtype

    class IsNDArray(ArrayValidator, register=(np.ndarray, _hint_ndarray)):
        """
        Validator for [`numpy.ndarray`][].

        Checks the array type, then the dtype and shape named in the hint
        (e.g. `ndarray[Tuple[Literal[3], int], dtype[float64]]`).
        """

        DEFAULT = np.ndarray
        SCALARS = np
        ARRAY_TYPE = np.ndarray
        HINT_TYPE = _hint_ndarray

    __all__ += ["IsDType", "IsNDArray"]
