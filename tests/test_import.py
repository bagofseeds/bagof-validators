"""Import smoke tests, and the lazy numpy import guard."""

# stdlib
import importlib
import subprocess
import sys
import textwrap

# dependencies
import pytest


def _run(code: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_template_submodule_is_importable() -> None:
    """The template package should be importable after installation."""
    module = importlib.import_module("bagof.validators")
    assert module is not None


def test_import_does_not_import_numpy() -> None:
    """
    `import bagof.validators` must not import numpy by itself.

    Its dependencies (`bagof.core.magic`) may still import numpy eagerly,
    so a plain `"numpy" in sys.modules` check would not be meaningful.
    Instead, numpy imports are blocked, and the module that asked for
    each one is recorded: none may come from `bagof.validators`.
    """
    out = _run("""
        import sys

        requests = []

        class Block:
            def find_spec(self, name, path=None, target=None):
                if name.partition(".")[0] != "numpy":
                    return None
                frame = sys._getframe(1)
                while frame is not None:
                    mod = frame.f_globals.get("__name__", "")
                    if not mod.startswith(("importlib", "_frozen")):
                        requests.append(mod)
                        break
                    frame = frame.f_back
                raise ImportError(f"blocked: {name}")

        sys.meta_path.insert(0, Block())
        import bagof.validators
        own = {m for m in requests if m.startswith("bagof.validators")}
        print(sorted(own))
        print("numpy" in sys.modules)
    """)
    own, loaded = out.split()
    assert own == "[]"
    assert loaded == "False"


def test_import_does_not_add_numpy_when_dependencies_do_not() -> None:
    """If no dependency imports numpy, neither does `bagof.validators`."""
    out = _run("""
        import sys
        import bagof.core.magic, bagof.hints.typevars.co
        before = "numpy" in sys.modules
        import bagof.validators
        print(before, "numpy" in sys.modules)
    """)
    before, after = out.split()
    if before == "True":
        pytest.skip("a dependency imports numpy eagerly")
    assert after == "False"


def test_numpy_validators_resolve_after_late_import() -> None:
    pytest.importorskip("numpy")
    out = _run("""
        import sys
        from bagof.validators import IsDType, Validator
        import numpy as np
        assert Validator.get_class(np.dtype) is IsDType
        assert Validator.get_class(np.generic) is IsDType
        assert Validator.get_class(np.float32) is IsDType
        assert IsDType.DEFAULT is np.dtype
        Validator.get(np.dtype)(np.dtype("float32"))
        try:
            Validator.get(np.dtype)(1)
        except Exception as e:
            print(type(e).__name__)
    """)
    assert out.strip() == "TypeValidationError"
