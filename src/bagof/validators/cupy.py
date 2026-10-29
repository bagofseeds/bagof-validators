"""Validators for cupy array types."""

__all__: list = []

# dependencies
import typing_extensions as tx

# bags
from bagof.core.magic import has_module, lazy_import

# locals
from ._arrays import ArrayValidator

if tx.TYPE_CHECKING:
    # Import the bare module so mkdocstrings resolves the `cupy.*`
    # cross-references in the docstrings below. Type-checking only.
    import cupy  # noqa: F401


# cupy is only imported once a cupy validator is actually used: the
# registry keys are forward references, resolved once `cupy` (or the hint
# module) has been imported by the caller -- see `Validator.register`.
if tx.TYPE_CHECKING or has_module("cupy"):  # pragma: no cover
    # cupy needs a CUDA toolchain and cannot be installed on a CPU runner,
    # so this validator is only ever type-checked, never exercised in CI.

    class IsCupyArray(
        ArrayValidator,
        register=(
            tx.ForwardRef("cupy.ndarray"),
            tx.ForwardRef("bagof.hints.cupy.ndarray"),
        ),
    ):
        """Validator for [`cupy.ndarray`][]."""

        DEFAULT = lazy_import("cupy.ndarray")
        SCALARS = lazy_import("cupy")
        ARRAY_TYPE = lazy_import("cupy.ndarray")
        HINT_TYPE = lazy_import("bagof.hints.cupy.ndarray")

    __all__ += ["IsCupyArray"]
