"""Validators for numpy types (dtype, etc.)."""

__all__ = []

# dependencies
import typing_extensions as tx

# bags
from bagof.core.magic import has_module, lazy_import

# locals
from .base import Validator

if tx.TYPE_CHECKING:
    from bagof.hints.numpy.typevars.co import DTYPE
else:
    # The numpy typevars import numpy; use a plain one at runtime.
    from bagof.hints.typevars.co import T as DTYPE

# numpy is only imported once a numpy validator is actually used: the
# registry keys are forward references, resolved once numpy has been
# imported by the caller -- see `Validator.register`.
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

    __all__ += ["IsDType"]
