"""Validators for collection types (list, tuple, dict, etc.)."""

__all__ = [
    "IsIterable",
    "IsSequence",
    "IsIterator",
    "IsSet",
    "IsFrozenSet",
    "IsMutableSet",
    "IsMapping",
    "IsTupleIsh",
    "IsTuple",
    "IsDict",
    "IsTypedDict",
    "HasLength",
]

# stdlib
import collections
from collections import abc

# dependencies
import typing_extensions as tx

# bags
from bagof.core.magic import (
    UNSET,
    safe_get_args,
    safe_get_origin,
    safe_isinstance,
    typeddict_required_keys,
    unwrap,
)
from bagof.hints.typevars.co import ITERABLE, MAPPING, SEQUENCE, TUPLE

# locals
from .base import Validator
from .exceptions import ValidationError
from .reports import (
    _annotation_meta,
    _collecting,
    _expected,
    _Frame,
    _hint_name,
)

_REQUIREDNESS = (tx.Required, tx.NotRequired)


def _strip_requiredness(hint: tx.Any) -> tx.Any:
    """
    Remove a `Required` / `NotRequired` wrapper, inside or outside
    `Annotated`.

    Both nestings are legal (PEP 655), and typing keeps whichever was
    written: `NotRequired[Annotated[int, "m"]]` unwraps normally, but
    `Annotated[NotRequired[int], "m"]` has `Annotated` as its origin, so
    the wrapper has to be stripped from inside -- keeping the metadata,
    which may carry validators of its own.
    """
    inner = unwrap(hint, _REQUIREDNESS)
    if inner is not hint:
        return _strip_requiredness(inner)
    if safe_get_origin(hint) is tx.Annotated:
        args = safe_get_args(hint)
        if args:
            base, meta = args[0], args[1:]
            stripped = unwrap(base, _REQUIREDNESS)
            if stripped is not base:
                return tx.Annotated[(stripped,) + meta]
    return hint


def _ordinal(index: int) -> str:
    """`0` -> `"1st"`, `1` -> `"2nd"`, `20` -> `"21st"`, ..."""
    n = index + 1
    if n % 100 in (11, 12, 13):
        return f"{n}th"
    return "{}{}".format(
        n, {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")  # codespell:ignore nd
    )


def _mapping_args(
    args: tx.Tuple[tx.Any, ...], origin: tx.Any
) -> tx.Tuple[tx.Any, tx.Any]:
    """
    The (key, value) hints of a mapping, whatever arity it was written at.

    Most mappings carry both (`Dict[str, int]`), but some fix their value
    type and take only a key: `Counter[K]` is a `Mapping[K, int]`, and
    destructuring it as a pair used to raise a bare `ValueError` from
    inside the validator.
    """
    if len(args) >= 2:
        return args[0], args[1]
    implied = _IMPLIED_VALUE_HINT.get(origin, tx.Any)
    return args[0], implied


_IMPLIED_VALUE_HINT: tx.Dict[tx.Any, tx.Any] = {
    collections.Counter: int,
    abc.Set: tx.Any,
}


class IsIterable(Validator[ITERABLE], register=abc.Iterable):
    """
    Validator for [`abc.Iterable`][].

    !!! note
        When parameterized (e.g. `Iterable[int]`), each element is
        validated against the argument type. A one-shot iterator or
        generator cannot be checked this way -- walking it would consume
        the value being validated -- so it raises a
        `TypeValidationError` instead.
    """

    DEFAULT = abc.Iterable

    def __call__(self, value: ITERABLE) -> None:
        super().__call__(value)  # check type
        if self.args:

            if safe_isinstance(value, abc.Iterator):
                # A one-shot iterator yields itself from `__iter__`, so
                # walking it to check elements would consume the value
                # being validated. Anything else finite and re-iterable
                # (a set, a mapping's view, a range) is fair game.
                raise self.type_error(
                    value, "Cannot validate the elements of an iterator",
                )

            arg_validator = Validator.get(self.args[0])
            with _Frame(self, value) as frame:
                for i, item in enumerate(value):
                    frame.check(arg_validator, item, i, _element_message)


def _element_message(index: int, item: tx.Any) -> str:
    return f"Iterable's {_ordinal(index)} element is not valid."


class IsSequence(IsIterable[SEQUENCE], register=abc.Sequence):
    """Validator for [`abc.Sequence`][]."""

    DEFAULT = abc.Sequence
    FALLBACK = list


class IsIterator(IsIterable[ITERABLE], register=abc.Iterator):
    """
    Validator for [`Iterator`][collections.abc.Iterator].

    Only the container type is checked. An iterator yields itself from
    `__iter__`, so walking it to check elements would consume the very
    value being validated -- a parameterized hint like `Iterator[int]`
    therefore passes any iterator, and its elements are left unchecked.
    """

    DEFAULT = abc.Iterator

    def __call__(self, value: ITERABLE) -> None:
        # Deliberately skip `IsIterable.__call__`: its element loop is
        # what cannot be run here.
        Validator(self.hint)(value)


class IsSet(IsIterable[ITERABLE], register=abc.Set):
    """
    Validator for [`Set`][collections.abc.Set].

    A set is finite and re-iterable, so a parameterized hint
    (e.g. `Set[int]`) checks every member.
    """

    DEFAULT = abc.Set
    FALLBACK = frozenset


class IsFrozenSet(IsSet[ITERABLE], register=frozenset):
    """Validator for [`frozenset`][]."""

    DEFAULT = frozenset
    FALLBACK = frozenset


class IsMutableSet(IsSet[ITERABLE], register=(abc.MutableSet, set)):
    """Validator for [`MutableSet`][collections.abc.MutableSet]."""

    DEFAULT = abc.MutableSet
    FALLBACK = set


class IsMapping(Validator[MAPPING], register=abc.Mapping):
    """Validator for [`abc.Mapping`][]."""

    DEFAULT = abc.Mapping
    FALLBACK = dict

    def __call__(self, value: MAPPING) -> None:
        super().__call__(value)  # check type
        if self.args:
            key_hint, val_hint = _mapping_args(self.args, self.origin)
            key_validator = Validator.get(key_hint)
            val_validator = Validator.get(val_hint)
            # Iterate over a separate name: `value` is what the errors
            # below report, and it must stay the mapping the caller
            # passed rather than becoming its items view.
            items = value.items() if safe_isinstance(value, abc.Mapping) \
                else value

            with _Frame(self, value) as frame:
                for k, v in items:
                    frame.check(key_validator, k, k, _key_message, whole=True)
                    frame.check(val_validator, v, k, _value_message)


def _key_message(key: tx.Any, item: tx.Any) -> str:
    return f"Key {key!r} is not valid."


def _value_message(key: tx.Any, item: tx.Any) -> str:
    return f"At key {key!r}, value {item!r} is invalid."


class IsTupleIsh(Validator[TUPLE]):
    """
    Per-item validator for sequence (not necessarily tuple) containers.

    !!! note
        This validator is not registered by default, so it is only used
        when instantiated explicitly.
    """

    DEFAULT = tuple

    def __call__(self, value: TUPLE) -> None:
        if self.args:
            # If args are provided, we accept either lists or tuples.
            # This is because the tuple annotation is often used to specify
            # per-item types, but the value may be a list
            # (e.g., for JSON serialization).

            _type_check(self, IsSequence(), value)

            if len(self.args) == 2 and self.args[1] is Ellipsis:
                arg_validator = Validator.get(self.args[0])
                validators = [arg_validator] * len(value)

            else:
                if len(value) != len(self.args):
                    raise self.value_error(
                        value,
                        f"Invalid tuple length "
                        f"{len(value)!r} != {len(self.args)!r}",
                    )
                validators = map(Validator.get, self.args)

            with _Frame(self, value) as frame:
                for i, (validator, val) in enumerate(zip(validators, value)):
                    frame.check(validator, val, i, _tuple_message)

        else:
            # If no args are provided, we do make a "strong" type check.
            super().__call__(value)  # check type


def _tuple_message(index: int, item: tx.Any) -> str:
    return f"Tuple's {_ordinal(index)} element is not valid."


class IsTuple(IsTupleIsh[TUPLE], register=tuple):
    """Validator for [`tuple`][]."""

    DEFAULT = tuple

    def __call__(self, value: TUPLE) -> None:
        # Always check the type
        Validator(self.hint)(value)
        # Then check the items
        super().__call__(value)


class IsDict(IsMapping[MAPPING], register=dict):
    """Validator for [`dict`][]."""

    # Need to register a dict validator to avoid having the TypedDict
    # validator being used for dicts.
    DEFAULT = dict


class IsTypedDict(IsMapping[MAPPING], register=tx.TypedDict):
    """Validator for [`TypedDict`][typing.TypedDict]."""

    DEFAULT = tx.TypedDict

    def _options(
        self,
    ) -> tx.Tuple[tx.Dict[str, tx.Any], tx.Any, tx.Any, bool]:
        """The fields' hints, required keys, extra items and closedness."""
        origin = self.origin
        extra_items = getattr(origin, "__extra_items__", tx.Any)
        closed = getattr(origin, "__closed__", False)
        annots = tx.get_type_hints(origin, include_extras=True)
        if extra_items is getattr(tx, "NoExtraItems", tx.Any):
            extra_items = tx.Any
        # Shared with the sibling packages, so all three agree -- and it
        # falls back to `__total__` where the class has no
        # `__required_keys__`, which is `typing.TypedDict` before 3.9.
        required = typeddict_required_keys(origin)
        return annots, required, extra_items, closed

    def __call__(self, value: MAPPING) -> None:
        # Check type - do not use super() -> instances are not `TypedDict`
        _type_check(self, IsMapping(dict), value)

        # Get typeddict options
        annots, required, extra_items, closed = self._options()

        with _Frame(self, value) as frame:

            # Check explicitly defined keys
            for key, arg in annots.items():
                arg = _strip_requiredness(arg)
                if key not in value:
                    if key in required:
                        # A field whose `Severity` does not fail may be
                        # missing (and is reported at that severity).
                        severity, fix = _annotation_meta(arg)
                        frame.fail(
                            f"Missing required key {key!r}", key,
                            expected=_hint_name(arg), severity=severity,
                            fix=fix,
                        )
                else:
                    frame.check(
                        Validator.get(arg), value[key], key, _field_message
                    )

            # Check extra keys
            for key, item in value.items():
                if key not in annots:
                    if closed:
                        frame.fail(
                            f"Unexpected key {key!r}", key, found=item
                        )
                    else:
                        frame.check(
                            Validator.get(extra_items), item, key,
                            _extra_message,
                        )


def _field_message(key: tx.Any, item: tx.Any) -> str:
    return f"Value for key {key!r} is not valid."


def _extra_message(key: tx.Any, item: tx.Any) -> str:
    return f"Value for extra key {key!r} is not valid."


def _type_check(this: Validator, check: Validator, value: tx.Any) -> None:
    """
    Run a looser type check. Inside `collect()`, it fails in the name of
    `this`, so that a problem expects a `Sidecar` rather than a `dict`.
    """
    if _collecting() is None:
        check(value)
        return
    try:
        check(value)
    except ValidationError as e:
        raise this.type_error(value, e.message) from e


class HasLength(IsSequence[ITERABLE]):
    """
    Validator for [`abc.Sequence`][], that checks its length.

    !!! note
        This validator is not registered by default, so it is only used
        when instantiated explicitly, e.g. `HasLength(3)`.
    """

    def __init__(
        self,
        length: int,
        hint: tx.Any = UNSET,
        compose: bool = False,
    ) -> None:
        """
        Parameters
        ----------
        length : int
            The expected length of the sequence.
        hint : Any, optional
            The type hint to validate against.
        compose : bool
            Whether to compose this validator with others, when they are
            found in [`Annotated`][typing.Annotated] metadata.
        """
        super().__init__(hint, compose)
        self.length = length

    def __call__(self, value: ITERABLE) -> None:
        with _Frame(self, value) as frame:
            # Inside `collect()`, the length is checked even when an
            # element is not valid, but not when the type is wrong.
            if frame.check(super().__call__, value) or not frame.wrong_type():
                if len(value) != self.length:
                    frame.fail(
                        f"Does not match expected length "
                        f"{len(value)} != {self.length!r}.",
                        expected=_expected(self, "value"), found=value,
                    )
