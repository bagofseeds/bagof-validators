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
    ishintstance,
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
from .reports import (
    Fix,
    Problem,
    Severity,
    _annotation_meta,
    _attach,
    _collecting,
    _expected,
    _Frame,
    _hint_name,
    _problems_of,
    _short_repr,
    _wrong_type,
)


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
    """Validator for [`Union`][typing.Union]."""

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
        state = _collecting()
        if state is not None:
            return self._call_collecting(value, state)
        errors = []
        for arg in self.args:
            # Wrap each member so that a plain `TypeError`/`ValueError`
            # from inside it becomes a `ValidationError` here, rather than
            # escaping the loop and aborting the whole union -- a member
            # that cannot answer is a member that did not match, not a
            # reason to give up on the ones after it. Anything that is not
            # a validation failure still propagates.
            validator = self._wrap_validator(Validator.get(arg))
            try:
                return validator(value)
            except ValidationError as e:
                errors.append(e)
                continue

        raise self.type_error(
            value, "Not compatible with any of the union types.",
        ) from MultipleCauses(errors)

    def _call_collecting(self, value: T, state: tx.Any) -> None:
        # As above, inside `collect()`: the first member that does not
        # raise wins, with its warnings, if any. When none matches, the
        # problems of the member that matched best are kept.
        location, start = state.location, len(state.pending)
        errors, tried = [], []
        for arg in self.args:
            validator = Validator.get(arg)
            try:
                validator(value)
                return
            except ValidationError as e:
                error = e
                problems = _problems_of(e, value, location)
            except (TypeError, ValueError) as e:
                # A member that cannot answer did not match, as above.
                error = self.value_error(value)
                error.__cause__ = e
                problems = [Problem(
                    location, "value", f"{type(e).__name__}: {e}",
                    _expected(validator, "value"), _short_repr(value),
                    None,  # type: ignore[arg-type]  # resolved by `_settle`
                )]
            errors.append(error)
            tried.append(state.pending[start:] + problems)
            del state.pending[start:]
        # A member that failed on the value's own type says nothing that
        # `expected` does not. If one member got past that, the value
        # was most likely meant as that member: report it as if alone.
        shaped = [p for p in tried if not _wrong_type(p, location)]
        if len(shaped) == 1:
            problems = shaped[0]
        else:
            problems = [Problem(
                location, "type",
                "Not compatible with any of the union types.",
                _hint_name(self.hint), _short_repr(value),
                None,  # type: ignore[arg-type]  # resolved by `_settle`
                None, tuple(p for member in shaped for p in member),
            )]
        raise _attach(self.type_error(
            value, "Not compatible with any of the union types.",
        ), problems) from MultipleCauses(errors)


class IsLiteral(Validator[T], register=tx.Literal):
    """
    Validator for [`Literal`][typing.Literal].

    A value matches by **type as well as value**, as
    [PEP 586](https://peps.python.org/pep-0586/) specifies: `True` is not
    a valid `Literal[1]` even though `True == 1`, and neither is `1.0`.
    """

    DEFAULT = tx.Literal

    def __call__(self, value: T) -> None:
        # `ishintstance` already implements PEP 586 matching (including
        # keeping a NaN literal comparable with itself), so defer to it
        # rather than re-deriving membership here -- `value in self.args`
        # compares with `==`, which conflates `True` with `1`, and blows
        # up on a value whose `__eq__` is not boolean (e.g. an array).
        if not ishintstance(value, self.hint):
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

    _CACHED = Validator._CACHED + ("_report_meta",)

    @classmethod
    def register_metadata(
        cls, *hints: tx.Unpack[tx.Tuple[tx.Any, ...]]
    ) -> ClassDecorator:
        """
        Decorator to register a validator class for one or more
        `Annotated` metadata hints (e.g. [`re.Pattern`][]).

        Distinct from [`Validator.register`][], which registers a
        validator for a *type hint* in the global registry; this one
        registers it for a piece of `Annotated` **metadata**.

        Parameters
        ----------
        *hints
            One or more metadata hints to register the validator class
            for.

        Returns
        -------
        ClassDecorator
            A decorator that registers the validator class for the
            given metadata hints.
        """

        def decorator(validator_cls: tx.Type[Validator]) -> tx.Type[Validator]:
            for hint in hints:
                cls._REGISTRY[hint] = validator_cls
            return validator_cls

        return decorator

    # Deprecated alias. `register` means "register for a type hint"
    # everywhere else, and a bare `@IsAnnotated.register` used to
    # silently register the decorated class as a metadata *key*.
    register = register_metadata

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
            if safe_isinstance(arg, (Severity, Fix)):
                # How to report, not what to check: see `_severity_and_fix`.
                continue
            if safe_issubclass(arg, Validator):
                # Bind by keyword. Not every validator takes `hint` first
                # -- `HasLength(length, ...)`, `IsInRange(min, max, ...)`,
                # the comparators and `MatchesRegex(pattern, ...)` all take
                # their own configuration there -- and passing positionally
                # silently bound the annotated type as that argument. By
                # keyword, such a class raises a `TypeError` naming the
                # argument it is missing, which points at the real fix:
                # write an instance rather than the bare class.
                arg = arg(hint=wrapped_type)
            if not safe_isinstance(arg, Validator):
                # Look into annotation registry
                arg = self._get_validator(arg)
            if safe_isinstance(arg, Validator):
                if not arg.has_explicit_hint:
                    # A metadata validator written without a hint of its
                    # own validates the annotated type. Without this, a
                    # non-composable one - which replaces the base type
                    # check - was left checking its class `DEFAULT`, so
                    # `Annotated[int, IsPositive()]` accepted `1.5`.
                    arg = arg.rebind(wrapped_type)
                if getattr(arg, "compose", False):
                    validators.append(arg)
                else:
                    validators = [arg]

        if not validators or getattr(validators[0], "compose", False):
            validators.insert(0, Validator.get(wrapped_type))

        return tuple(validators)

    @property
    def _severity_and_fix(
        self,
    ) -> tx.Tuple[tx.Optional[Severity], tx.Optional[str]]:
        """
        The [`Severity`][bagof.validators.reports.Severity] and
        [`Fix`][bagof.validators.reports.Fix] found in the metadata, or
        `None` for either.
        """
        if getattr(self, "_report_meta", None) is None:
            self._report_meta = _annotation_meta(self.hint)
        return self._report_meta

    def __call__(self, value: T) -> None:
        severity, fix = self._severity_and_fix
        if _collecting() is not None:
            # Every validator in turn -- but a wrong type skips the
            # constraints after it, which would only repeat it, or worse.
            with _Frame(self, value) as frame:
                for validator in self.validators:
                    if not frame.check(validator, value) \
                            and frame.wrong_type():
                        break
                frame.relabel(severity, fix)
            return
        if severity is not None and not severity.fails:
            # A failure under a non-failing severity (e.g. a warning)
            # does not make the value invalid.
            try:
                for validator in self.validators:
                    validator(value)
            except ValidationError:
                pass
            return
        for validator in self.validators:
            validator(value)
