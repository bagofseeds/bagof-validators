"""
Automatic type-based validators.

Modules
-------
base
    Base class for magic validators.
collections
    Validators for collection types (list, tuple, dict, etc.).
common
    Common validators (any, union, etc.).
cupy
    Validators for cupy array types.
dask
    Validators for dask array types.
exceptions
    Exceptions raised by validators on validation error.
misc
    Miscellaneous validators (forbidden values, etc.).
numbers
    Validators for numeric types (int, float, etc.).
numpy
    Validators for numpy types (dtype, ndarray).
strings
    Validators for string types (regex patterns, etc.).
"""

__all__ = [
    "__version__",
    "base",
    "collections",
    "common",
    "cupy",
    "dask",
    "exceptions",
    "misc",
    "numbers",
    "numpy",
    "strings",
]

try:
    from ._version import __version__
except ImportError:  # pragma: no cover
    __version__ = "0+unknown"

from . import (
    base,
    collections,
    common,
    cupy,
    dask,
    exceptions,
    misc,
    numbers,
    numpy,
    strings,
)
from .base import *  # noqa: F401, F403
from .base import __all__ as __all_base
from .collections import *  # noqa: F401, F403
from .collections import __all__ as __all_collections
from .common import *  # noqa: F401, F403
from .common import __all__ as __all_common
from .cupy import *  # noqa: F401, F403
from .cupy import __all__ as __all_cupy
from .dask import *  # noqa: F401, F403
from .dask import __all__ as __all_dask
from .exceptions import *  # noqa: F401, F403
from .exceptions import __all__ as __all_exceptions
from .misc import *  # noqa: F401, F403
from .misc import __all__ as __all_misc
from .numbers import *  # noqa: F401, F403
from .numbers import __all__ as __all_numbers
from .numpy import *  # noqa: F401, F403
from .numpy import __all__ as __all_numpy
from .strings import *  # noqa: F401, F403
from .strings import __all__ as __all_strings

__all__ += __all_base
__all__ += __all_collections
__all__ += __all_common
__all__ += __all_cupy
__all__ += __all_dask
__all__ += __all_exceptions
__all__ += __all_misc
__all__ += __all_numbers
__all__ += __all_numpy
__all__ += __all_strings
