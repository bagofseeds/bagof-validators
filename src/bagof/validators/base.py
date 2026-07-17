"""Base class for all validators."""

__all__ = [
    "Validator",
    "register_validator",
    "get_validator",
    "get_validator_class"
]

# dependencies
import typing_extensions as tx  # noqa: I001

# bags
from bagof.core.magic import (
    UNSET,
    MagicHint,
    get_from_registry,
    ishintstance,
    safe_isinstance,
    safe_issubclass,
)
from bagof.hints.typevars.co import TYPE, T

# locals
from .exceptions import (
    TypeValidationError,
    ValidationError,
    ValueValidationError,
)

# typing

ClassDecorator: tx.TypeAlias = tx.Callable[[TYPE], TYPE]
"""A class decorator (that takes a class and returns a class)."""

ValidatorRegistry = tx.Dict[tx.Hashable, tx.Type["Validator"]]
"""A registry of validators, mapping type hints to validator classes."""

# constants
VALIDATORS: ValidatorRegistry = {}
"""The global registry of validators."""


class ValidatorMetaclass(type(MagicHint)):
    """Metaclass for all validators."""

    def __new__(
        metacls,
        name: str,
        bases: tx.Tuple[type, ...],
        namespace: tx.Mapping[str, tx.Any],
        **kwargs
    ) -> tx.Self:
        register = kwargs.pop("register", UNSET)
        cls = super().__new__(metacls, name, bases, namespace, **kwargs)
        if register is not UNSET:
            if register is True:
                register = (cls.DEFAULT,)
            if not isinstance(register, tuple):
                register = (register,)
            Validator.register(cls, *register)
        return cls


class Validator(MagicHint[T], metaclass=ValidatorMetaclass):
    """
    Base class for magic validators.

    The default validator falls back to a rather crude heuristic to check
    whether the type of the validated object is compatible with the type hint.
    This does not work well for generic types, so it is recommended to
    implement a custom validator for generic types.
    """

    DEFAULT = tx.Any

    def __init__(self, hint: tx.Any = UNSET, compose: bool = False) -> None:
        """
        Parameters
        ----------
        hint
            The type hint to use for this magic object.
            If not provided, the default hint for the class is used.
        compose : bool
            Whether to compose this validator with others, when they are
            found in [`Annotated`][typing.Annotated] metadata.
        """
        super().__init__(hint)
        self.compose = compose

    def __call__(self, value: T) -> None:
        """
        Validate the given value.

        Parameters
        ----------
        value : T
            The value to validate.

        Raises
        ------
        ValidationError
            If the value is not valid for this validator.
        """
        if not ishintstance(value, self.hint):
            raise self.type_error(value, "Not a valid instance.")

    def error(
        self, value: tx.Any, message: tx.Optional[str] = None, **kwargs
    ) -> ValidationError:
        """Return a [`ValidationError`][] with the given value and message."""
        type = kwargs.pop("type", ValidationError)
        type = {
            "value": ValueValidationError,
            "type": TypeValidationError
        }.get(type, type)
        kwargs.setdefault("this", self)
        kwargs.setdefault("value", value)
        if message is None:
            message = "Invalid value."
        return type(message, **kwargs)

    def type_error(
        self, value: tx.Any, message: tx.Optional[str] = None
    ) -> TypeValidationError:
        """Return a [`TypeValidationError`][] with the given value."""
        if message is None:
            message = f"Invalid value type: {type(value)}"
        return self.error(value, message, type=TypeValidationError)

    def value_error(
        self, value: tx.Any, message: tx.Optional[str] = None
    ) -> ValueValidationError:
        """Return a [`ValueValidationError`][] with the given value."""
        if message is None:
            message = "Invalid value."
        return self.error(value, message, type=ValueValidationError)

    def _wrap_validator(self, validator: tx.Callable) -> tx.Callable:
        """
        A wrapper that wraps a validator to catch errors and raise a
        [`ValidationError`][] instead. Defined here so that subclasses
        to not need to each implement this.
        """
        return _trywrap_validator(validator, self.value_error)

    @tx.overload
    @staticmethod
    def register(
        validator: tx.Type["Validator"],
        *hints: tx.Unpack[tx.Tuple[tx.Any]],
        registry: ValidatorRegistry = ...
    ) -> tx.Type["Validator"]:
        ...

    @tx.overload
    @staticmethod
    def register(
        *hints: tx.Unpack[tx.Tuple[tx.Any]],
        registry: ValidatorRegistry = ...
    ) -> ClassDecorator:
        ...

    @staticmethod
    def register(*hints, registry=VALIDATORS):
        """
        Decorator to register a validator class for one or more type hints.

        !!! example
            ```python
            @Validator.register
            class IntValidator(Validator[int]):

                DEFAULT = int

                def __call__(self, value: int) -> None:
                    try:
                        int(value)
                    except (TypeError, ValueError) as e:
                        raise self.type_error(value) from e
            ```

        Parameters
        ----------
        *hints
            One or more type hints to register the validator class for.
        registry : ValidatorRegistry
            The registry to register the validator class in.
            Defaults to the global registry.

        Returns
        -------
        ClassDecorator
            A decorator that registers the validator class for the given
            type hints.

        """
        if hints and safe_issubclass(hints[0], Validator):
            validator, *hints = hints
            return Validator.register(*hints, registry=registry)(validator)

        def decorator(cls: tx.Type[Validator]) -> tx.Type[Validator]:
            hints_ = hints or (cls.DEFAULT,)
            for hint in hints_:
                registry[hint] = cls
            return cls

        return decorator

    @staticmethod
    def get(
        hint: tx.Any,
        registry: ValidatorRegistry = VALIDATORS,
        fallback: tx.Optional[tx.Type["Validator"]] = UNSET
    ) -> tx.Optional["Validator"]:
        """
        Get the best-matching conversion function for a given type hint.

        Parameters
        ----------
        hint
            The type hint for which to get a validator.
        registry : ValidatorRegistry
            The registry to look up the validator in.
            Defaults to the global registry.
        fallback : tx.Optional[Type[Validator]]
            The fallback validator class to use if no matching validator
            is found. Defaults to [`Validator`][].
            Pass `None` explicitly to get `None` instead of a fallback.

        Returns
        -------
        tx.Optional[Validator]
            The best-matching validator for the given type hint, or `None`
            if no matching validator is found and no fallback is provided.
        """
        cls = Validator.get_class(hint, registry, fallback)
        if cls is None:
            return None
        return cls(hint)

    @staticmethod
    def get_class(
        hint: tx.Any,
        registry: ValidatorRegistry = VALIDATORS,
        fallback: tx.Optional[tx.Type["Validator"]] = UNSET
    ) -> tx.Optional[tx.Type["Validator"]]:
        """
        Get the best-matching conversion class for a given type hint.

        Parameters
        ----------
        hint
            The type hint for which to get a validator.
        registry : ValidatorRegistry
            The registry to look up the validator in.
            Defaults to the global registry.
        fallback : tx.Optional[Type[Validator]]
            The fallback validator class to use if no matching validator
            is found. Defaults to [`Validator`][].
            Pass `None` explicitly to get `None` instead of a fallback.

        Returns
        -------
        tx.Optional[Type[Validator]]
            The best-matching validator class for the given type hint,
            or `None` if no matching validator is found and no fallback
            is provided.
        """
        if fallback is UNSET:
            fallback = Validator
        return get_from_registry(hint, registry) or fallback


register_validator = Validator.register
"""Backward-compatible alias for [`Validator.register`][]"""

get_validator = Validator.get
"""Backward-compatible alias for [`Validator.get`][]"""

get_validator_class = Validator.get_class
"""Backward-compatible alias for [`Validator.get_class`][]"""


def _trywrap_validator(
    validator: tx.Callable[[T], None],
    error: tx.Union[Exception, tx.Type[Exception], tx.Callable[[T], Exception]]
) -> tx.Callable[[T], None]:
    """
    Wrap a validator to catch errors and raise a [`ValidationError`][] instead.
    """
    def wrapped(value: T) -> None:
        try:
            return validator(value)
        except (TypeError, ValueError) as e:
            _error = error
            if not safe_isinstance(_error, BaseException):
                # Either an exception class or a factory (e.g. `value_error`).
                _error = _error(value)
            raise _error from e
    return wrapped
