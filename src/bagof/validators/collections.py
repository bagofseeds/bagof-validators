"""Validators for collection types (list, tuple, dict, etc.)."""

__all__ = [
    "IsIterable",
    "IsSequence",
    "IsMapping",
    "IsTupleIsh",
    "IsTuple",
    "IsDict",
    "IsTypedDict",
    "HasLength",
]

# stdlib
from collections import abc

# dependencies
import typing_extensions as tx

# bags
from bagof.core.magic import UNSET, safe_get_origin, safe_isinstance, unwrap
from bagof.hints.typevars.co import ITERABLE, MAPPING, SEQUENCE, TUPLE

# locals
from .base import Validator
from .exceptions import ValidationError


def _ordinal(index: int) -> str:
    """`0` -> `"1st"`, `1` -> `"2nd"`, `20` -> `"21st"`, ..."""
    n = index + 1
    if n % 100 in (11, 12, 13):
        return f"{n}th"
    return "{}{}".format(
        n, {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")  # codespell:ignore nd
    )


class IsIterable(Validator[ITERABLE], register=abc.Iterable):
    """
    Validator for [`abc.Iterable`][].

    !!! note
        When parameterized (e.g. `Iterable[int]`), each element is
        validated against the argument type. This requires the value
        to be an [`abc.Sequence`][] (e.g. a `list`), since a one-shot
        iterator or generator cannot be safely re-validated; a bare
        generator raises a `TypeValidationError` in that case.
    """

    DEFAULT = abc.Iterable

    def __call__(self, value: ITERABLE) -> None:
        super().__call__(value)  # check type
        if self.args:

            if not safe_isinstance(value, abc.Sequence):
                raise self.type_error(
                    value, "Cannot validate generator arguments",
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


class IsMapping(Validator[MAPPING], register=abc.Mapping):
    """Validator for [`abc.Mapping`][]."""

    DEFAULT = abc.Mapping
    FALLBACK = dict

    def __call__(self, value: MAPPING) -> None:
        super().__call__(value)  # check type
        if self.args:
            key_hint, val_hint = self.args
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
        total = getattr(origin, "__total__", True)
        extra_items = getattr(origin, "__extra_items__", tx.Any)
        closed = getattr(origin, "__closed__", False)
        annots = tx.get_type_hints(origin, include_extras=True)
        if extra_items is getattr(tx, "NoExtraItems", tx.Any):
            extra_items = tx.Any

        # Check explicitly defined keys
        for key, arg in annots.items():
            if key not in value:
                arg_origin = safe_get_origin(arg)
                if (
                    (total and arg_origin is not tx.NotRequired) or
                    (not total and arg_origin is tx.Required)
                ):
                    raise self.value_error(
                        value, f"Missing required key {key!r}"
                    )
            else:
                arg = unwrap(arg, (tx.Required, tx.NotRequired))
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
