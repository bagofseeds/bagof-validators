"""Validators for numpy types (dtype, etc.)."""

__all__ = []

# dependencies
import typing_extensions as tx

# locals
from .base import Validator

if tx.TYPE_CHECKING:
    from bagof.hints.numpy.typevars.co import DTYPE
    from numpy import dtype, generic
else:
    try:
        from bagof.hints.numpy.typevars.co import DTYPE
        from numpy import dtype, generic
    except ImportError:  # pragma: no cover
        dtype = generic = None  # type: ignore[assignment]

if tx.TYPE_CHECKING or dtype is not None:

    class IsDType(Validator[DTYPE], register=(dtype, generic)):
        """Validator for [`numpy.dtype`][numpy.dtype]."""

        DEFAULT = dtype

    __all__ += ["IsDType"]
