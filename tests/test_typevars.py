"""
A typevar hint must validate exactly like the hint it is bound to.

Validators introspect `origin`/`args` to check a hint's structure. Since
`MagicHint.UNWRAP` includes `TypeVar`, a typevar is resolved to its bound
(or default, or constraints) first, so that building a validator directly
with a typevar, building it with the bound, and dispatching through the
registry all agree.
"""

# dependencies
import pytest
import typing_extensions as tx

# bags
from bagof.hints.typevars.co import INT

# locals
from bagof.validators import collections, common, numbers
from bagof.validators.base import Validator
from bagof.validators.exceptions import ValidationError


class UserTD(tx.TypedDict):
    name: str
    age: int


BOUND_TO_LIST = tx.TypeVar("BOUND_TO_LIST", bound=tx.List[int])
BOUND_TO_MAPPING = tx.TypeVar("BOUND_TO_MAPPING", bound=tx.Mapping[str, int])
BOUND_TO_TUPLE = tx.TypeVar("BOUND_TO_TUPLE", bound=tx.Tuple[int, str])
BOUND_TO_UNION = tx.TypeVar("BOUND_TO_UNION", bound=tx.Union[int, str])
BOUND_TO_LITERAL = tx.TypeVar("BOUND_TO_LITERAL", bound=tx.Literal["a", "b"])
BOUND_TO_TYPED_DICT = tx.TypeVar("BOUND_TO_TYPED_DICT", bound=UserTD)
BOUND_TO_FLOAT = tx.TypeVar("BOUND_TO_FLOAT", bound=float)

CONSTRAINED = tx.TypeVar("CONSTRAINED", int, str)
UNBOUND = tx.TypeVar("UNBOUND")

# (validator, bound hint, typevar bound to it, valid value, invalid value)
EQUIVALENCES = [
    (collections.IsIterable, tx.List[int], BOUND_TO_LIST, [1, 2], ["a"]),
    (collections.IsSequence, tx.List[int], BOUND_TO_LIST, [1, 2], ["a"]),
    (
        collections.IsMapping,
        tx.Mapping[str, int],
        BOUND_TO_MAPPING,
        {"a": 1},
        {"a": "b"},
    ),
    (
        collections.IsTuple,
        tx.Tuple[int, str],
        BOUND_TO_TUPLE,
        (1, "a"),
        (1, 2),
    ),
    (
        collections.IsTypedDict,
        UserTD,
        BOUND_TO_TYPED_DICT,
        {"name": "Ada", "age": 37},
        {"name": "Ada", "age": "37"},
    ),
    (common.IsUnion, tx.Union[int, str], BOUND_TO_UNION, 1, None),
    (
        common.IsLiteral,
        tx.Literal["a", "b"],
        BOUND_TO_LITERAL,
        "a",
        "c",
    ),
    # `float` widens to accept `int`; the typevar must widen too.
    (numbers.IsNumber, float, BOUND_TO_FLOAT, 1, 1j),
]

IDS = [str(case[0].__name__) for case in EQUIVALENCES]


@pytest.mark.parametrize("cls,hint,typevar,valid,invalid", EQUIVALENCES,
                         ids=IDS)
def test_typevar_accepts_like_its_bound(
    cls: tx.Any,
    hint: tx.Any,
    typevar: tx.Any,
    valid: tx.Any,
    invalid: tx.Any,
) -> None:
    cls(hint)(valid)
    cls(typevar)(valid)
    Validator.get(typevar)(valid)


@pytest.mark.parametrize("cls,hint,typevar,valid,invalid", EQUIVALENCES,
                         ids=IDS)
def test_typevar_rejects_like_its_bound(
    cls: tx.Any,
    hint: tx.Any,
    typevar: tx.Any,
    valid: tx.Any,
    invalid: tx.Any,
) -> None:
    # A typevar must never be laxer than its bound: before `UNWRAP` covered
    # typevars, `args` was empty and item checks were silently skipped.
    with pytest.raises(ValidationError):
        cls(hint)(invalid)
    with pytest.raises(ValidationError):
        cls(typevar)(invalid)
    with pytest.raises(ValidationError):
        Validator.get(typevar)(invalid)


@pytest.mark.parametrize("cls,hint,typevar,valid,invalid", EQUIVALENCES,
                         ids=IDS)
def test_typevar_introspection_matches_its_bound(
    cls: tx.Any,
    hint: tx.Any,
    typevar: tx.Any,
    valid: tx.Any,
    invalid: tx.Any,
) -> None:
    assert cls(typevar).origin == cls(hint).origin
    assert cls(typevar).args == cls(hint).args
    assert cls(typevar).unwrapped == cls(hint).unwrapped


# ----------------------------------------------------------------------
# Unwrapping rules
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "hint,expected",
    [
        # A bound resolves to the bound itself.
        (BOUND_TO_LIST, tx.List[int]),
        (INT, int),
        # Constraints resolve to their union.
        (CONSTRAINED, tx.Union[int, str]),
        # An unbound typevar resolves to `Any`.
        (UNBOUND, tx.Any),
        # Non-typevars are untouched.
        (tx.List[int], tx.List[int]),
        # `Annotated` is unwrapped as well, in any order.
        (tx.Annotated[BOUND_TO_LIST, "meta"], tx.List[int]),
    ],
)
def test_unwrapped(hint: tx.Any, expected: tx.Any) -> None:
    assert Validator(hint).unwrapped == expected


def test_constrained_typevar_validates_as_a_union() -> None:
    validator = common.IsUnion(CONSTRAINED)
    validator(1)
    validator("a")
    with pytest.raises(ValidationError):
        validator(None)


def test_unbound_typevar_accepts_anything() -> None:
    # An unbound typevar resolves to `Any`, which is maximally permissive.
    validator = Validator.get(UNBOUND)
    for value in (1, "a", None, [1], object()):
        validator(value)


def test_typevar_with_default() -> None:
    hint = tx.TypeVar("WITH_DEFAULT", default=tx.List[int])
    # A default takes precedence over the (absent) bound.
    assert Validator(hint).unwrapped == tx.List[int]
    collections.IsIterable(hint)([1, 2])
    with pytest.raises(ValidationError):
        collections.IsIterable(hint)(["a"])


def test_unwrap_is_overridable() -> None:
    # `UNWRAP` is inherited from `MagicHint`; a validator may opt out of
    # resolving typevars.
    class KeepsTypeVars(Validator[tx.Any]):
        UNWRAP = (tx.Annotated,)

    # Opting out leaves the typevar unresolved, so it has no args.
    assert KeepsTypeVars(BOUND_TO_LIST).args == ()
    assert KeepsTypeVars(BOUND_TO_LIST).unwrapped is BOUND_TO_LIST
    # ... whereas the default unwraps it.
    assert Validator(BOUND_TO_LIST).args == (int,)
    assert Validator.UNWRAP == (tx.Annotated, tx.TypeVar)
