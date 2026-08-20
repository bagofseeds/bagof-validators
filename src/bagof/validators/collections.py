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
    unwrap,
)
from bagof.hints.typevars.co import ITERABLE, MAPPING, SEQUENCE, TUPLE

# locals
from .base import Validator
from .exceptions import ValidationError

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
            for i, item in enumerate(value):
                try:
                    arg_validator(item)
                except ValidationError as e:
                    raise self.value_error(
                        value,
                        f"Iterable's {_ordinal(i)} element is not valid.",
                    ) from e


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

            for k, v in items:

                try:
                    key_validator(k)
                except ValidationError as e:
                    raise self.value_error(
                        value, f"Key {k!r} is not valid.",
                    ) from e

                try:
                    val_validator(v)
                except ValidationError as e:
                    raise self.value_error(
                        value, f"At key {k!r}, value {v!r} is invalid.",
                    ) from e


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

            IsSequence()(value)  # check type

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

            for i, (validator, val) in enumerate(zip(validators, value)):
                try:
                    validator(val)
                except ValidationError as e:
                    raise self.value_error(
                        value,
                        f"Tuple's {_ordinal(i)} element is not valid.",
                    ) from e

        else:
            # If no args are provided, we do make a "strong" type check.
            super().__call__(value)  # check type


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

    def __call__(self, value: MAPPING) -> None:
        # Check type - do not use super() -> instances are not `TypedDict`
        IsMapping(dict)(value)

        # Get typeddict options
        origin = self.origin
        extra_items = getattr(origin, "__extra_items__", tx.Any)
        closed = getattr(origin, "__closed__", False)
        annots = tx.get_type_hints(origin, include_extras=True)
        if extra_items is getattr(tx, "NoExtraItems", tx.Any):
            extra_items = tx.Any
        # `__required_keys__` is the canonical answer, and the only one
        # that survives both an `Annotated` wrapper (where the origin is
        # `Annotated`, not `Required`/`NotRequired`) and inheritance from
        # bases declared with a different `total=`.
        required = getattr(origin, "__required_keys__", None)
        if required is None:  # pragma: no cover - every TypedDict has it
            required = frozenset(annots)

        # Check explicitly defined keys
        for key, arg in annots.items():
            if key not in value:
                if key in required:
                    raise self.value_error(
                        value, f"Missing required key {key!r}"
                    )
            else:
                arg = _strip_requiredness(arg)
                validator = Validator.get(arg)
                try:
                    validator(value[key])
                except ValidationError as e:
                    raise self.value_error(
                        value, f"Value for key {key!r} is not valid."
                    ) from e

        # Check extra keys
        for key, arg in value.items():
            if key not in annots:
                if closed:
                    raise self.value_error(value, f"Unexpected key {key!r}")
                validator = Validator.get(extra_items)
                try:
                    validator(arg)
                except ValidationError as e:
                    raise self.value_error(
                        value, f"Value for extra key {key!r} is not valid."
                    ) from e


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
        super().__call__(value)
        if len(value) != self.length:
            raise self.value_error(
                value, f"Does not match expected length "
                f"{len(value)} != {self.length!r}."
            )
