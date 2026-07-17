__all__ = ["MatchesRegex"]

# stdlib
import re

# dependencies
import typing_extensions as tx

# bags
from bagof.core.magic import UNSET, safe_isinstance
from bagof.hints.typevars.co import STR

# locals
from .common import IsAnnotated, Validator


@IsAnnotated.register(re.Pattern)
class MatchesRegex(Validator[STR]):
    """Validator for strings that match a regex pattern."""

    DEFAULT = str

    def __init__(
        self,
        pattern: tx.Union[str, re.Pattern],
        hint: tx.Any = UNSET,
        compose: bool = False,
    ) -> None:
        """
        Parameters
        ----------
        pattern : str | re.Pattern
            The regex pattern to match against.
        hint : Any, optional
            The type hint to validate against.
        compose : bool
            Whether to compose this validator with others, when they are
            found in [`Annotated`][typing.Annotated] metadata.
        """
        super().__init__(hint, compose)
        if not safe_isinstance(pattern, re.Pattern):
            pattern = re.compile(pattern)
        self.pattern = pattern

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.pattern!r})"

    def __call__(self, value: STR) -> None:
        super().__call__(value)
        if not self.pattern.match(value):
            raise self.value_error(value, "Does not match pattern.")
