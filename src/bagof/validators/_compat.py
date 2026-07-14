import typing_extensions as tx

# optional
if tx.TYPE_CHECKING:
    from types import NoneType, UnionType

else:
    try:
        from types import NoneType
    except ImportError:  # pragma: no cover
        NoneType = type(None)  # type: ignore[assignment]

    try:
        from types import UnionType
        UNION_TYPES = (tx.Union, UnionType)
    except ImportError:  # pragma: no cover
        UnionType = tx.Union  # type: ignore[assignment]
        UNION_TYPES = (tx.Union,)

if tx.TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

else:
    try:
        import numpy as np
    except ImportError:  # pragma: no cover
        np = None  # type: ignore[assignment]

    try:
        import numpy.typing as npt
    except ImportError:  # pragma: no cover
        npt = None  # type: ignore[assignment]
