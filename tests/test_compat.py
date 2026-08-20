# stdlib
import ast
import pathlib

# dependencies
import typing_extensions as tx

# locals
from bagof.validators import _compat

SRC = pathlib.Path(_compat.__file__)


def _bound_names(body: tx.List[ast.stmt]) -> tx.Set[str]:
    """Every name a block binds, by assignment or by import."""
    names = set()
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _typechecking_branches() -> tx.List[tx.Tuple[tx.Set[str], tx.Set[str]]]:
    """The (TYPE_CHECKING, runtime) name sets of each guarded block."""
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    out = []
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
            out.append((_bound_names(node.body), _bound_names(node.orelse)))
    return out


def test_type_checking_branches_bind_the_same_names() -> None:
    # A name defined only at runtime is undefined for a type checker (and
    # vice versa), which is invisible until a checker is pointed at the
    # package -- so assert the two branches agree, structurally.
    branches = _typechecking_branches()
    assert branches, "no `if tx.TYPE_CHECKING:` block found"
    for guarded, runtime in branches:
        only_guarded = sorted(guarded - runtime)
        only_runtime = sorted(runtime - guarded)
        assert guarded == runtime, (
            "TYPE_CHECKING and runtime branches bind different names: "
            f"only guarded={only_guarded}, only runtime={only_runtime}"
        )


def test_union_types_is_importable() -> None:
    assert tx.Union in _compat.UNION_TYPES
    assert _compat.UnionType in _compat.UNION_TYPES
