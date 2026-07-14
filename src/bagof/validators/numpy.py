__all__ = []

# dependencies
import typing_extensions as tx

# locals
from .base import Validator

if tx.TYPE_CHECKING:
    import numpy as np
    from bagof.hints.typevars.co import DTYPE
else:
    try:
        import numpy as np
        from bagof.hints.typevars.co import DTYPE
    except ImportError:
        np = None  # type: ignore[assignment]

if tx.TYPE_CHECKING or np:

    class IsDType(Validator[DTYPE], register=(np.dtype, np.generic)):
        """Validator for [`numpy.dtype`][numpy.dtype]."""

        DEFAULT = np.dtype

    __all__ += ["IsDType"]
