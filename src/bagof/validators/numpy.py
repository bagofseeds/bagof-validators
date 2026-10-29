"""Validators for numpy types (dtype, ndarray)."""

__all__: list = []

# dependencies
import typing_extensions as tx

# bags
from bagof.core.magic import has_module, lazy_import

# locals
from ._arrays import ArrayValidator
from .base import Validator

if tx.TYPE_CHECKING:
    # Import the bare module so mkdocstrings resolves the `numpy.*`
    # cross-references in the docstrings below. Type-checking only.
    import numpy  # noqa: F401
    from bagof.hints.numpy.typevars.co import DTYPE
else:
    # The numpy typevars import numpy; use a plain one at runtime.
    from bagof.hints.typevars.co import T as DTYPE


# numpy is only imported once a numpy validator is actually used: the
# registry keys are forward references, resolved once `numpy` (or the hint
# module) has been imported by the caller -- see `Validator.register`.
if tx.TYPE_CHECKING or has_module("numpy"):

    class IsDType(
        Validator[DTYPE],
        register=(
            tx.ForwardRef("numpy.dtype"),
            tx.ForwardRef("numpy.generic"),
        ),
    ):
        """Validator for [`numpy.dtype`][numpy.dtype]."""

        DEFAULT = lazy_import("numpy.dtype")

    class IsNDArray(
        ArrayValidator,
        register=(
            tx.ForwardRef("numpy.ndarray"),
            tx.ForwardRef("bagof.hints.numpy.ndarray"),
        ),
    ):
        """
        Validator for [`numpy.ndarray`][].

        Checks the array type, then the dtype and shape named in the hint
        (e.g. `ndarray[Tuple[Literal[3], int], dtype[float64]]`).
        """

        DEFAULT = lazy_import("numpy.ndarray")
        SCALARS = lazy_import("numpy")
        ARRAY_TYPE = lazy_import("numpy.ndarray")
        HINT_TYPE = lazy_import("bagof.hints.numpy.ndarray")

    __all__ += ["IsDType", "IsNDArray"]
