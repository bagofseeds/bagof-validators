"""Validators for dask array types."""

__all__: list = []

# dependencies
import typing_extensions as tx

# bags
from bagof.core.magic import has_module, lazy_import

# locals
from ._arrays import ArrayValidator

if tx.TYPE_CHECKING:
    # Import the bare module so mkdocstrings resolves the `dask.array.*`
    # cross-references in the docstrings below. Type-checking only.
    import dask.array  # noqa: F401


# dask is only imported once a dask validator is actually used: the
# registry keys are forward references, resolved once `dask.array` (or the
# hint module) has been imported by the caller -- see `Validator.register`.
if tx.TYPE_CHECKING or has_module("dask"):

    class IsDaskArray(
        ArrayValidator,
        register=(
            tx.ForwardRef("dask.array.Array"),
            tx.ForwardRef("bagof.hints.dask.Array"),
        ),
    ):
        """
        Validator for [`dask.array.Array`][].

        A dimension whose size dask does not know yet (`nan`) is accepted.
        """

        DEFAULT = lazy_import("dask.array.Array")
        # dask arrays carry numpy dtypes, so the scalar table comes from
        # numpy.
        SCALARS = lazy_import("numpy")
        ARRAY_TYPE = lazy_import("dask.array.Array")
        HINT_TYPE = lazy_import("bagof.hints.dask.Array")

    __all__ += ["IsDaskArray"]
