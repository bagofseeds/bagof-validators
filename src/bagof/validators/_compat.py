import typing_extensions as tx

# optional
if tx.TYPE_CHECKING:
    from types import NoneType, UnionType

    UNION_TYPES = (tx.Union, UnionType)

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
