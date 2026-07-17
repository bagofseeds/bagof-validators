"""Common validators (any, union, etc.)"""

__all__ = [
    "IsAny",
    "IsNone",
    "IsUnion",
    "IsLiteral",
    "IsTypeVar",
    "IsAnnotated",
]

# dependencies
import typing_extensions as tx

# bags
from bagof.core.magic import (
    MultipleCauses,
    safe_get_args,
    safe_isinstance,
    safe_issubclass,
    unwrap,
)
from bagof.hints.typevars.co import NONE, NoneType, T

# locals
from ._compat import UNION_TYPES, UnionType
from .base import ClassDecorator, Validator, ValidatorRegistry
from .exceptions import ValidationError


class IsAny(Validator[T], register=tx.Any):
    """Validator for [`Any`][typing.Any]."""

    def __call__(self, value: T) -> None:
        return


class IsNone(Validator[NONE], register=NoneType):
    """Validator for [`None`][]."""

    DEFAULT = NoneType

    def __call__(self, value: NONE) -> None:
        if value is not None:
            raise self.type_error(value, "Not None.")


class IsUnion(Validator[T], register=(tx.Union, UnionType)):
    """Validator for [`Union`][typing.Any]."""

    DEFAULT = tx.Union

    def __init__(self, *a, **k) -> None:
        super().__init__(*a, **k)
        # `self.origin` unwraps typevars as well, so a typevar bound to a
        # union is accepted, and validates like the union itself.
        if self.origin not in UNION_TYPES:
            raise TypeError(f"{self!r}: Hint is not a Union type")
        if len(self.args) == 0:
            raise TypeError(f"{self!r}: No arguments provided")

    def __call__(self, value: T) -> None:
        errors = []
        for arg in self.args:
            try:
                validator = Validator.get(arg)
                return validator(value)
            except ValidationError as e:
                errors.append(e)
                continue

        raise self.type_error(
            value, "Not compatible with any of the union types.",
        ) from MultipleCauses(errors)


class IsLiteral(Validator[T], register=tx.Literal):
    """Validator for [`Literal`][typing.Literal]."""

    DEFAULT = tx.Literal

    def __call__(self, value: T) -> None:
        if value not in self.args:
            raise self.type_error(
                value, "Not compatible with any of the literals",
            )


class IsTypeVar(Validator[T], register=tx.TypeVar):
    """Validator for [`TypeVar`][typing.TypeVar]."""

    DEFAULT = tx.TypeVar("T")

    def __call__(self, value: T) -> None:
        # `unwrapped` resolves the typevar (see `Validator.UNWRAP`), so this
        # re-dispatches to the validator registered for the bound itself.
        return Validator.get(self.unwrapped)(value)


class IsAnnotated(Validator[T], register=tx.Annotated):
    """
    Validator for [`Annotated`][typing.Annotated].

    !!! note
        Annotated validators look for validators in the metadata of an
        annotated type hint and apply them in order (if they are composable).
    """

    _REGISTRY: ValidatorRegistry = {}

    @classmethod
    def register(cls, *hints: tx.Unpack[tx.Tuple[tx.Any]]) -> ClassDecorator:

        def decorator(validator_cls: tx.Type[Validator]) -> tx.Type[Validator]:
            for hint in hints:
                cls._REGISTRY[hint] = validator_cls
            return validator_cls

        return decorator

    @classmethod
    def _get_validator(cls, hint: tx.Any) -> tx.Optional[Validator]:
        # Metadata are usually instances (e.g. `re.compile(...)`), whereas
        # the registry is keyed by their type (e.g. `re.Pattern`), so fall
        # back to a lookup by type. The metadata itself is then passed to
        # the validator's constructor.
        validator_cls = Validator.get_class(
            hint, registry=cls._REGISTRY, fallback=None
        ) or Validator.get_class(
            type(hint), registry=cls._REGISTRY, fallback=None
        )
        if validator_cls is None:
            return None
        return validator_cls(hint)

    @property
    def validators(self) -> tx.Tuple[Validator, ...]:
        if getattr(self, "_validators", None) is None:
            self._validators = self._get_validators()
        return self._validators

    def _get_validators(self) -> tx.Tuple[Validator, ...]:
        wrapped_type = unwrap(self.hint, tx.Annotated)
        validators = []
        for arg in safe_get_args(self.hint):
            if safe_issubclass(arg, Validator):
                arg = arg(wrapped_type)
            if not safe_isinstance(arg, Validator):
                # Look into annotation registry
                arg = self._get_validator(arg)
            if safe_isinstance(arg, Validator):
                if getattr(arg, "compose", False):
                    validators.append(arg)
                else:
                    validators = [arg]

        if not validators or getattr(validators[0], "compose", False):
            validators.insert(0, Validator.get(wrapped_type))

        return tuple(validators)

    def __call__(self, value: T) -> None:
        for validator in self.validators:
            validator(value)
