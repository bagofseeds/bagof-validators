"""Import smoke tests, and the lazy import of optional libraries."""

# stdlib
import importlib
import subprocess
import sys
import textwrap

# dependencies
import pytest


def _run(code: str) -> str:
    # In a fresh interpreter: this test session has imported numpy already.
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_template_submodule_is_importable() -> None:
    """The template package should be importable after installation."""
    module = importlib.import_module("bagof.validators")
    assert module is not None


def test_import_does_not_import_optional_libraries() -> None:
    out = _run("""
        import sys
        import bagof.validators
        libs = {"numpy", "cupy", "dask", "pandas"}
        print(sorted(libs & {m.partition(".")[0] for m in sys.modules}))
    """)
    assert out == "[]"


@pytest.mark.parametrize("numpy_first", [False, True])
def test_numpy_validators_resolve_whenever_numpy_is_imported(
    numpy_first: bool,
) -> None:
    pytest.importorskip("numpy")
    first, then = "import numpy as np", "from bagof.validators import *"
    if not numpy_first:
        first, then = then, first
    out = _run(f"""
        {first}
        {then}
        from bagof.hints.numpy import NDArray
        assert Validator.get_class(np.dtype) is IsDType
        assert Validator.get_class(np.float32) is IsDType
        assert Validator.get_class(np.ndarray) is IsNDArray
        assert Validator.get_class(NDArray[np.float64]) is IsNDArray
        assert IsDType.DEFAULT is np.dtype
        Validator.get(NDArray[np.float64])(np.zeros(3))
        try:
            Validator.get(np.dtype)(1)
        except Exception as e:
            print(type(e).__name__)
    """)
    assert out == "TypeValidationError"
