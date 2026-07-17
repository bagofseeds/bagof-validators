# stdlib
import re

# dependencies
import pytest
import typing_extensions as tx

# bags
from bagof.hints.typevars.co import STR

# locals
from bagof.validators import strings
from bagof.validators.common import IsAnnotated
from bagof.validators.exceptions import (
    TypeValidationError,
    ValueValidationError,
)


@pytest.mark.parametrize(
    "pattern,value",
    [
        (r"^a", "abc"),
        (r"^a", "a"),
        (re.compile(r"^a"), "abc"),
        (r"\d+", "123"),
        # `match` only anchors at the start, not at the end.
        (r"^a", "axyz"),
        (r"", "anything"),
    ],
)
def test_matches_regex_valid(pattern: tx.Any, value: tx.Any) -> None:
    validator = strings.MatchesRegex(pattern)
    validator(value)


@pytest.mark.parametrize(
    "pattern,value",
    [
        (r"^a", "xyz"),
        (r"^a", ""),
        (re.compile(r"^a"), "xyz"),
        (r"\d+", "abc"),
    ],
)
def test_matches_regex_invalid(pattern: tx.Any, value: tx.Any) -> None:
    validator = strings.MatchesRegex(pattern)
    with pytest.raises(ValueValidationError):
        validator(value)


@pytest.mark.parametrize("value", [1, None, ["a"], b"abc"])
def test_matches_regex_wrong_type(value: tx.Any) -> None:
    # The type is checked before the pattern.
    validator = strings.MatchesRegex(r"^a")
    with pytest.raises(TypeValidationError):
        validator(value)


@pytest.mark.parametrize("hint", [str, STR])
def test_matches_regex_hint(hint: tx.Any) -> None:
    validator = strings.MatchesRegex(r"^a", hint)
    validator("abc")
    with pytest.raises(ValueValidationError):
        validator("xyz")


def test_matches_regex_compiles_str_pattern() -> None:
    validator = strings.MatchesRegex(r"^a")
    assert validator.pattern == re.compile(r"^a")
    # An already-compiled pattern is kept as-is.
    pattern = re.compile(r"^a")
    assert strings.MatchesRegex(pattern).pattern is pattern


def test_matches_regex_repr() -> None:
    validator = strings.MatchesRegex(r"^a")
    assert repr(validator) == "MatchesRegex(re.compile('^a'))"


@pytest.mark.parametrize(
    "hint,value",
    [
        (tx.Annotated[str, re.compile(r"^a")], "abc"),
        (tx.Annotated[str, strings.MatchesRegex(r"^a")], "abc"),
    ],
)
def test_matches_regex_annotated_valid(hint: tx.Any, value: tx.Any) -> None:
    IsAnnotated(hint)(value)


@pytest.mark.parametrize(
    "hint,value",
    [
        # A bare `re.Pattern` in the metadata is looked up in the
        # `IsAnnotated` registry and resolves to `MatchesRegex`.
        (tx.Annotated[str, re.compile(r"^a")], "xyz"),
        (tx.Annotated[str, strings.MatchesRegex(r"^a")], "xyz"),
    ],
)
def test_matches_regex_annotated_invalid(hint: tx.Any, value: tx.Any) -> None:
    with pytest.raises(ValueValidationError):
        IsAnnotated(hint)(value)


def test_matches_regex_registered_for_annotated() -> None:
    validators = IsAnnotated(tx.Annotated[str, re.compile(r"^a")]).validators
    assert len(validators) == 1
    assert isinstance(validators[0], strings.MatchesRegex)
    assert validators[0].pattern == re.compile(r"^a")
