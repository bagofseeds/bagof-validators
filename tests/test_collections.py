# stdlib
import collections as std_collections
from collections import abc

# dependencies
import pytest
import typing_extensions as tx

# bags
from bagof.hints.typevars.co import INT, STR

# locals
from bagof.validators import collections
from bagof.validators.base import Validator


@pytest.mark.parametrize(
    "hint,value",
    [
        # Iterable
        (tx.Iterable, [1, 2, 3]),
        (tx.Iterable, (1, 2, 3)),
        (tx.Iterable, range(1, 4)),
        (tx.Iterable, (i for i in range(1, 4))),
        (tx.Iterable, {"a": 1, "b": 2, "c": 3}),
        (tx.Iterable, "abc"),
        (tx.Iterable, b"abc"),
        (tx.Iterable[int], [1, 2, 3]),
        (tx.Iterable[int], (1, 2, 3)),
        (tx.Iterable[int], range(1, 4)),
        (tx.Iterable[str], "abc"),
        (tx.Iterable[INT], [1, 2, 3]),
        (tx.Iterable[INT], (1, 2, 3)),
        (tx.Iterable[INT], range(1, 4)),
        (tx.Iterable[STR], "abc"),
        # Sequence
        (tx.Sequence, [1, 2, 3]),
        (tx.Sequence, (1, 2, 3)),
        (tx.Sequence, range(1, 4)),
        (tx.Sequence, "abc"),
        (tx.Sequence, b"abc"),
        (tx.Sequence[int], [1, 2, 3]),
        (tx.Sequence[int], (1, 2, 3)),
        (tx.Sequence[int], range(1, 4)),
        (tx.Sequence[str], "abc"),
        # List
        (tx.List, [1, 2, 3]),
        (tx.List[int], [1, 2, 3]),
    ]
)
def test_iterable_valid(hint: tx.Any, value: tx.Any) -> None:
    default_validator = collections.IsIterable()
    default_validator(value)
    validator = collections.IsIterable(hint)
    validator(value)


@pytest.mark.parametrize(
    "hint,value_factory",
    [
        (tx.Iterable[int], lambda: (i for i in range(1, 4))),
        (tx.Iterable[int], lambda: iter([1, 2, 3])),
        (tx.Iterable[int], lambda: map(int, "123")),
    ]
)
def test_iterable_impossible(
    hint: tx.Any, value_factory: tx.Callable[[], tx.Any]
) -> None:
    # A one-shot iterator yields itself from `__iter__`, so walking it to
    # check elements would consume the value being validated.
    validator = collections.IsIterable(hint)
    with pytest.raises(collections.ValidationError):
        validator(value_factory())


@pytest.mark.parametrize(
    "hint,value",
    [
        # Iterating a mapping yields its keys, so a dict with int keys is
        # a valid `Iterable[int]` -- and it is re-iterable, so the
        # elements can actually be checked.
        (tx.Iterable[int], {1: "a", 2: "b", 3: "c"}),
        (tx.Iterable[str], {"a": 1, "b": 2, "c": 3}),
        (tx.Iterable[int], {1, 2, 3}),
        (tx.Iterable[int], frozenset({1, 2, 3})),
        (tx.Iterable[int], range(3)),
    ]
)
def test_iterable_checks_any_reiterable_value(
    hint: tx.Any, value: tx.Any
) -> None:
    collections.IsIterable(hint)(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        (tx.Iterable[str], {1: "a"}),
        (tx.Iterable[int], {"a", "b"}),
    ]
)
def test_iterable_rejects_bad_elements_of_a_reiterable_value(
    hint: tx.Any, value: tx.Any
) -> None:
    with pytest.raises(collections.ValidationError):
        collections.IsIterable(hint)(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        # Iterable
        (tx.Iterable, 1),
        (tx.Iterable, None),
        (tx.Iterable[int], 1),
        (tx.Iterable[int], None),
        (tx.Iterable[int], ["a", "b", "c"]),
        (tx.Iterable[int], "abc"),
        (tx.Iterable[str], [1, 2, 3]),
        (tx.Iterable[INT], ["a", "b", "c"]),
        (tx.Iterable[STR], [1, 2, 3]),
        # Sequence
        (tx.Sequence, {"a": 1, "b": 2, "c": 3}),
        (tx.Sequence, (i for i in range(1, 4))),
        (tx.Sequence[int], ["a", "b", "c"]),
        (tx.Sequence[str], [1, 2, 3]),
        # List
        (tx.List, (1, 2, 3)),
        (tx.List[int], (1, 2, 3)),
    ]
)
def test_iterable_invalid(hint: tx.Any, value: tx.Any) -> None:
    validator = collections.IsIterable(hint)
    with pytest.raises(collections.ValidationError):
        validator(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        (tx.Mapping, {"a": 1, "b": 2}),
        (tx.Mapping[str, int], {"a": 1, "b": 2}),
        (tx.Mapping[STR, INT], {"a": 1, "b": 2}),
        (tx.Dict, {"a": 1, "b": 2}),
        (tx.Dict[str, int], {"a": 1, "b": 2}),
    ],
)
def test_mapping_valid(hint: tx.Any, value: tx.Any) -> None:
    default_validator = collections.IsMapping()
    default_validator(value)
    validator = collections.IsMapping(hint)
    validator(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        (tx.Mapping, 1),
        (tx.Mapping, None),
        (tx.Mapping[str, int], {"a": "1"}),
        (tx.Mapping[str, int], {1: 1}),
        (tx.Dict, [("a", 1)]),
        (tx.Dict[str, int], [("a", 1)]),
    ],
)
def test_mapping_invalid(hint: tx.Any, value: tx.Any) -> None:
    validator = collections.IsMapping(hint)
    with pytest.raises(collections.ValidationError):
        validator(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        (tx.Tuple, (1, 2, 3)),
        (tx.Tuple[int, str], (1, "a")),
        (tx.Tuple[int, ...], (1, 2, 3)),
    ],
)
def test_tuple_valid(hint: tx.Any, value: tx.Any) -> None:
    default_validator = collections.IsTuple()
    default_validator(value)
    validator = collections.IsTuple(hint)
    validator(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        (tx.Tuple, [1, 2, 3]),
        (tx.Tuple[int, str], [1, "a"]),
        (tx.Tuple[int, ...], [1, 2, 3]),
        (tx.Tuple[int, str], (1, 2)),
        (tx.Tuple[int, str], (1, "a", "x")),
        (tx.Tuple[int, ...], (1, "a", 3)),
    ],
)
def test_tuple_invalid(hint: tx.Any, value: tx.Any) -> None:
    validator = collections.IsTuple(hint)
    with pytest.raises(collections.ValidationError):
        validator(value)


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"a": 1, "b": 2},
    ],
)
def test_dict_valid(value: tx.Any) -> None:
    default_validator = collections.IsDict()
    default_validator(value)
    validator = collections.IsDict()
    validator(value)


@pytest.mark.parametrize(
    "value",
    [
        [],
        [("a", 1)],
        1,
        None,
    ],
)
def test_dict_invalid(value: tx.Any) -> None:
    validator = collections.IsDict()
    with pytest.raises(collections.ValidationError):
        validator(value)


class UserTD(tx.TypedDict):
    name: str
    age: int


class ClosedUserTD(tx.TypedDict, closed=True):
    name: str
    age: int


class ExtraUserTD(tx.TypedDict, extra_items=bool):
    name: str
    age: int


class PartialUserTD(tx.TypedDict, total=False):
    name: tx.Required[str]
    count: tx.NotRequired[int]


@pytest.mark.parametrize(
    "hint,value",
    [
        (UserTD, {"name": "Ada", "age": 37}),
        (UserTD, {"name": "Ada", "age": 37, "extra": True}),
        (ExtraUserTD, {"name": "Ada", "age": 37, "extra": True}),
        (PartialUserTD, {"name": "ok"}),
        (PartialUserTD, {"name": "ok", "count": 2}),
    ],
)
def test_typed_dict_valid(hint: tx.Any, value: tx.Any) -> None:
    validator = collections.IsTypedDict(hint)
    validator(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        (UserTD, []),  # wrong base type
        (UserTD, {"name": "Ada"}),  # missing required key
        (UserTD, {"name": "Ada", "age": "37"}),  # wrong value type
        (ClosedUserTD, {"name": "Ada", "age": 37, "extra": True}),  # extra key
        (ExtraUserTD, {"name": "Ada", "age": 37, "extra": 1}),  # wrong extra type  # noqa: E501
        (PartialUserTD, {}),  # name still required (tx.Required)
        (PartialUserTD, {"name": 1}),  # wrong required type
        (PartialUserTD, {"name": "ok", "count": "2"}),  # wrong optional type
    ],
)
def test_typed_dict_invalid(hint: tx.Any, value: tx.Any) -> None:
    validator = collections.IsTypedDict(hint)
    with pytest.raises(collections.ValidationError):
        validator(value)


@pytest.mark.parametrize(
    "length,hint,value",
    [
        (0, tx.List[int], []),
        (3, tx.List[int], [1, 2, 3]),
        (3, tx.Sequence[int], (1, 2, 3)),
    ],
)
def test_has_length_valid(length: int, hint: tx.Any, value: tx.Any) -> None:
    validator = collections.HasLength(length, hint)
    validator(value)


@pytest.mark.parametrize(
    "length,hint,value",
    [
        (3, tx.List[int], [1, 2]),
        (2, tx.List[int], [1, 2, 3]),
        (3, tx.List[int], [1, "2", 3]),
    ],
)
def test_has_length_invalid(length: int, hint: tx.Any, value: tx.Any) -> None:
    validator = collections.HasLength(length, hint)
    with pytest.raises(collections.ValidationError):
        validator(value)


# ----------------------------------------------------------------------
# Error messages
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "index,expected",
    [
        (0, "1st"), (1, "2nd"), (2, "3rd"), (3, "4th"),  # codespell:ignore nd
        (10, "11th"), (11, "12th"), (12, "13th"),
        (20, "21st"), (21, "22nd"), (22, "23rd"),  # codespell:ignore nd
        (100, "101st"),
    ],
)
def test_ordinal(index: int, expected: str) -> None:
    assert collections._ordinal(index) == expected


def test_element_index_matches_the_human_position() -> None:
    # The suffix table used to be applied to the zero-based `enumerate`
    # index, so the second element was reported as the "1st".
    with pytest.raises(collections.ValidationError, match="3rd element"):
        collections.IsIterable(tx.List[int])([1, 2, "x"])
    with pytest.raises(collections.ValidationError, match="1st element"):
        collections.IsTuple(tx.Tuple[int, int])(("x", 2))


def test_mapping_error_reports_the_mapping_not_its_items_view() -> None:
    with pytest.raises(collections.ValidationError) as info:
        collections.IsMapping(tx.Mapping[str, int])({"a": "x"})
    assert info.value.value == {"a": "x"}


# ----------------------------------------------------------------------
# Single-argument mappings
# ----------------------------------------------------------------------


def test_counter_validates_its_keys() -> None:
    # `Counter[K]` is a `Mapping[K, int]`, so it carries one type
    # argument. Destructuring it as a pair used to raise a bare
    # `ValueError: not enough values to unpack` from inside the validator.
    validator = Validator.get(tx.Counter[str])
    validator(std_collections.Counter())
    validator(std_collections.Counter({"a": 1}))
    with pytest.raises(collections.ValidationError, match="Key 1"):
        validator(std_collections.Counter({1: 1}))


def test_counter_values_are_checked_as_ints() -> None:
    validator = Validator.get(tx.Counter[str])
    with pytest.raises(collections.ValidationError):
        validator({"a": "not an int"})


def test_mapping_args_helper() -> None:
    assert collections._mapping_args((str, int), dict) == (str, int)
    assert collections._mapping_args((str,), std_collections.Counter) == (
        str, int
    )
    assert collections._mapping_args((str,), dict) == (str, tx.Any)


# ----------------------------------------------------------------------
# IsSet
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "hint,value",
    [
        (tx.Set[int], {1, 2}),
        (tx.Set[int], set()),
        (tx.FrozenSet[int], frozenset({1, 2})),
        (tx.AbstractSet[str], {"a"}),
        (set, {1, "a"}),
        (frozenset, frozenset()),
    ],
)
def test_set_valid(hint: tx.Any, value: tx.Any) -> None:
    # A parametrised set used to fall through to `IsIterable`, which
    # demanded an `abc.Sequence` -- so every one of these raised.
    Validator.get(hint)(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        (tx.Set[int], {"a"}),
        (tx.Set[int], {1, "a"}),
        (tx.FrozenSet[int], frozenset({"a"})),
        (tx.Set[int], [1, 2]),
    ],
)
def test_set_invalid(hint: tx.Any, value: tx.Any) -> None:
    with pytest.raises(collections.ValidationError):
        Validator.get(hint)(value)


@pytest.mark.parametrize(
    "hint,cls",
    [
        (abc.Set, collections.IsSet),
        (tx.Set[int], collections.IsMutableSet),
        (frozenset, collections.IsFrozenSet),
        (set, collections.IsMutableSet),
        (abc.MutableSet, collections.IsMutableSet),
    ],
)
def test_set_is_registered(hint: tx.Any, cls: tx.Any) -> None:
    assert isinstance(Validator.get(hint), cls)

