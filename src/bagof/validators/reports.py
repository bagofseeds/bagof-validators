"""
Reports that collect every validation failure.

A validator stops at the first failure and raises it. Its
[`report`][bagof.validators.base.Validator.report] method keeps going
instead, and returns a [`Report`][bagof.validators.reports.Report] of
every [`Problem`][bagof.validators.reports.Problem] it found:

```pycon
>>> import typing_extensions as tx
>>> from bagof.validators import Validator
>>> class Sidecar(tx.TypedDict):
...     RepetitionTime: float
...     EchoTime: tx.List[float]
...     TaskName: str
>>> report = Validator.get(Sidecar).report(
...     {"RepetitionTime": "2s", "EchoTime": [0.01, "x", None]}
... )
>>> report.ok
False
>>> print(report)
4 problems (error: 4)
['RepetitionTime']: error: Not a valid instance.
    expected float, found '2s'
['EchoTime'][1]: error: Not a valid instance.
    expected float, found 'x'
['EchoTime'][2]: error: Not a valid instance.
    expected float, found None
['TaskName']: error: Missing required key 'TaskName'
    expected str
>>> [problem.location for problem in report]
[('RepetitionTime',), ('EchoTime', 1), ('EchoTime', 2), ('TaskName',)]
```

The validator itself is unchanged: calling it still raises on the first
failure.

## What a problem records

* `location`: the path to the offending value, as a tuple of mapping
  keys, `TypedDict` fields and sequence indices. `()` is the value
  itself. Unions and `Annotated` add nothing to it.
* `kind`: `"type"` (the value has the wrong type) or `"value"` (right
  type, wrong value), and a `message`.
* `expected`: the type that was expected, or the constraint that failed
  (e.g. `IsInRange(0, 1)`). `found`: a short, truncated repr of the
  offending value; `None` when a required key is missing.
* `severity`: a [`Severity`][bagof.validators.reports.Severity],
  [`Severity.ERROR`][bagof.validators.reports.Severity.ERROR] unless the
  hint says otherwise.
* `fix`: how to fix it, when known, else `None`.
* `causes`: for a union, the problems that explain it (see below).

A `Problem` is a named tuple: `problem._asdict()` gives a plain dict for
JSON or a table.

## How the walk proceeds

* **A wrong type stops descent into that value.** A list given where a
  mapping is expected is one problem; its contents are not checked.
  The same goes for a tuple of the wrong length. Every other failure
  lets the walk carry on to the value's siblings.
* **`Annotated` constraints** are all checked, and each failing one is
  its own problem -- unless the value has the wrong type, in which case
  the constraints are skipped.
* **A union** is satisfied by its first matching member, as when
  failing fast. When every member fails:

    * if exactly one member had the right shape (it failed on its
      contents or on a constraint, not on the value's own type), the
      report shows that member's problems, as if the union were not
      there. `Optional[Sidecar]` given a broken sidecar reports what is
      wrong inside the sidecar, not "not None and not a Sidecar";
    * otherwise the union is one problem, whose `causes` hold the
      problems of every member that had the right shape (none, when no
      member did: `expected` then names them all).

* **A validator you wrote yourself** is checked as one unit: its first
  failure is one problem at its location. Give it a fix hint with
  `raise self.error(value, "...", type="value", fix="...")`.

## Severity and fix hints

Both are set with `Annotated` metadata, without writing a validator:

```python
class Sidecar(tx.TypedDict, total=False):
    RepetitionTime: tx.Required[tx.Annotated[
        float, Severity("recommended"), Fix("Give it in seconds."),
    ]]
    SliceTiming: tx.Annotated[tx.List[float], Severity.WARNING]
```

A severity says how serious a failure of that hint is. Only a severity
that `fails` (such as `Severity.ERROR`) makes the value invalid, and the
validator agrees with its report: it raises exactly when
`report.ok` is false. So a failure under `Severity.WARNING` is reported
as a warning and no longer raises. On a required `TypedDict` field, the
severity also covers the key being missing. An annotation relabels only
the failing problems under it: an error inside
`Annotated[..., Severity.WARNING]` becomes a warning, while a warning
inside `Annotated[..., Severity("proscribed", fails=True)]` stays a
warning.

A [`Fix`][bagof.validators.reports.Fix] is attached to every problem
found under it that has no fix of its own.
"""

__all__ = ["Report", "Problem", "Severity", "Fix"]

# Design notes (issue #50) -- the mechanics behind the rules above.
#
# * Entry point. `Validator.report(value, location=())`: one method on
#   every validator, nothing to configure on `get_validator`. Prior art:
#   jsonschema's `iter_errors` (a second entry point beside `validate`)
#   and pydantic's `ValidationError.errors()` (a flat list of dicts with
#   `loc`/`type`/`msg`/`input`). The report is flat for the same reason:
#   tools sort, filter and count it. It is a plain `Sequence`, not an
#   exception: there is no `ExceptionGroup` before 3.11, and a report of
#   warnings only is not a failure. cattrs' `ClassValidationError` (an
#   exception tree with notes) is closer to the fail-fast
#   `MultipleCauses` chain, which is left as it is.
#
# * No context through `__call__`. A collect-aware validator defines a
#   private `_collect(value, report)`; `_Collector.check` calls it in
#   place of `__call__`, and every other validator is called exactly as
#   when failing fast, as one unit. So the fail-fast path is not
#   rewritten, and a validator that calls another one as a predicate
#   (`try: v(x) except ValidationError: ...`) still gets a raise.
#   `_collect` is used only when the class that defines the nearest
#   `__call__` also defines `_collect` (`_collector_for`): a subclass
#   that overrides `__call__` (`IsIterator`, or a user's) silently
#   falls back to the one-unit check rather than skipping its own code.
#
# * Severity is resolved bottom-up. A problem is recorded with
#   `severity=None` ("not said"); the nearest `Annotated` with a
#   `Severity` relabels the failing problems under it; `_finish` turns
#   what is left into `Severity.ERROR`. A union member "matched" when it
#   added no failing problem, so a member with warnings only wins, as it
#   would when failing fast.
#
# * Union relevance follows pydantic's "smart" mode and jsonschema's
#   `best_match` in spirit, with one deterministic rule: a member that
#   failed with a type problem at the union's own location is
#   uninformative (`expected` already names it).

# stdlib
import functools
import re
import reprlib

# dependencies
import typing_extensions as tx

# bags
from bagof.core.magic import (
    UNSET,
    MagicHint,
    safe_get_args,
    safe_get_origin,
    unwrap,
)

# locals
from ._compat import UNION_TYPES, NoneType
from .exceptions import ValidationError

Location: tx.TypeAlias = tx.Tuple[tx.Hashable, ...]
"""The path to a value: mapping keys, field names and indices."""


class Severity(str):
    """
    How serious a [`Problem`][bagof.validators.reports.Problem] is.

    A severity is a string, its label, so it compares and serialises as
    one: `problem.severity == "warning"`. Two are built in,
    [`Severity.ERROR`][bagof.validators.reports.Severity.ERROR] and
    [`Severity.WARNING`][bagof.validators.reports.Severity.WARNING]; make
    your own for other levels:

    ```pycon
    >>> from bagof.validators import Severity
    >>> recommended = Severity("recommended")
    >>> proscribed = Severity("proscribed", fails=True)
    >>> recommended == "recommended", recommended.fails, proscribed.fails
    (True, False, True)
    ```

    Put one in [`Annotated`][typing.Annotated] metadata to set how
    serious a failure of that hint is:

    ```pycon
    >>> import typing_extensions as tx
    >>> from bagof.validators import Severity, Validator
    >>> validate = Validator.get(tx.Annotated[int, Severity.WARNING])
    >>> validate("x")          # a warning does not fail validation
    >>> print(validate.report("x"))
    1 problem (warning: 1)
    <root>: warning: Not a valid instance.
        expected int, found 'x'
    ```
    """

    ERROR: tx.ClassVar["Severity"]
    """A failure: the value is invalid."""

    WARNING: tx.ClassVar["Severity"]
    """A problem worth showing that does not make the value invalid."""

    fails: bool
    """Whether a problem of this severity makes the value invalid."""

    def __new__(cls, label: str, fails: bool = False) -> "Severity":
        """
        Parameters
        ----------
        label : str
            The name of the level, e.g. `"recommended"`.
        fails : bool
            Whether a problem of this severity makes the value invalid.
        """
        self = super().__new__(cls, label)
        self.fails = bool(fails)
        return self

    def __reduce__(self) -> tx.Tuple[tx.Any, ...]:
        return (type(self), (str(self), self.fails))


Severity.ERROR = Severity("error", fails=True)
Severity.WARNING = Severity("warning")


class Fix(str):
    """
    A hint on how to fix a failure, as [`Annotated`][typing.Annotated]
    metadata.

    ```pycon
    >>> import typing_extensions as tx
    >>> from bagof.validators import Fix, Validator
    >>> hint = tx.Annotated[float, Fix("Give it in seconds.")]
    >>> Validator.get(hint).report("2s")[0].fix
    'Give it in seconds.'
    ```
    """


class Problem(tx.NamedTuple):
    """
    One failure, as found by
    [`Validator.report`][bagof.validators.base.Validator.report].
    """

    location: Location
    """The path to the offending value; `()` is the value itself."""

    kind: str
    """`"type"` (wrong type) or `"value"` (right type, wrong value)."""

    message: str
    """What is wrong."""

    expected: tx.Optional[str] = None
    """The expected type, or the constraint that failed."""

    found: tx.Optional[str] = None
    """A short repr of the offending value; `None` if it is missing."""

    severity: Severity = Severity.ERROR
    """How serious the problem is."""

    fix: tx.Optional[str] = None
    """How to fix it, when known."""

    causes: tx.Tuple["Problem", ...] = ()
    """For a union that no member matched: the members' problems."""

    @property
    def fails(self) -> bool:
        """Whether this problem makes the value invalid."""
        return _fails(self.severity)

    def __str__(self) -> str:
        return "\n".join(_render(self, ""))


class Report(tx.Sequence[Problem]):
    """
    Every [`Problem`][bagof.validators.reports.Problem] found in a value,
    in the order they were met.

    A report is a sequence of problems for tools, and prints for people.
    Build one with
    [`Validator.report`][bagof.validators.base.Validator.report]; build
    one yourself to merge several, e.g. one per file:

    ```python
    validate = Validator.get(Sidecar)
    report = Report(
        problem
        for name, data in sidecars.items()
        for problem in validate.report(data, location=(name,))
    )
    ```

    !!! note
        Like any sequence, an empty report is falsy -- but a report of
        warnings only is not, and still describes a valid value. Test
        [`ok`][bagof.validators.reports.Report.ok] for validity.
    """

    def __init__(self, problems: tx.Iterable[Problem] = ()) -> None:
        """
        Parameters
        ----------
        problems : Iterable[Problem]
            The problems, in order.
        """
        self.problems: tx.Tuple[Problem, ...] = tuple(problems)

    @property
    def ok(self) -> bool:
        """Whether no problem makes the value invalid."""
        return not any(problem.fails for problem in self.problems)

    def __getitem__(self, index: tx.Any) -> tx.Any:
        return self.problems[index]

    def __len__(self) -> int:
        return len(self.problems)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Report):
            return NotImplemented
        return self.problems == other.problems

    __hash__ = None  # type: ignore[assignment]

    def summary(self) -> str:
        """One line: how many problems, by severity."""
        if not self.problems:
            return "No problems."
        counts: tx.Dict[str, int] = {}
        for problem in self.problems:
            label = str(problem.severity)
            counts[label] = counts.get(label, 0) + 1
        n = len(self.problems)
        detail = ", ".join(f"{k}: {v}" for k, v in counts.items())
        return f"{n} problem{'s' if n != 1 else ''} ({detail})"

    def __str__(self) -> str:
        lines = [self.summary()]
        for problem in self.problems:
            lines.extend(_render(problem, ""))
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"<Report: {self.summary()}>"


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------

_REPR = reprlib.Repr()
_REPR.maxstring = 60
_REPR.maxother = 60
_REPR.maxlevel = 3
_REPR.maxlist = _REPR.maxtuple = _REPR.maxset = _REPR.maxfrozenset = 6
_REPR.maxdict = 4

_HINT_PREFIX = re.compile(
    r"\b(?:typing_extensions|typing|collections\.abc|builtins)\."
)
_HINT_CLASS = re.compile(r"<class '(?:[\w.]+\.)?(\w+)'>")
_MAX_HINT = 120


def _short_repr(value: tx.Any) -> str:
    """A repr of `value`, cut down to a line."""
    return _REPR.repr(value)


def _hint_name(hint: tx.Any) -> str:
    """A readable name for a type hint: `list[int] | None`, the same on
    every Python version."""
    try:
        text = _hint_text(hint)
    except Exception:  # a hint is a hint; never fail to name it
        text = repr(hint)
    if len(text) > _MAX_HINT:
        text = text[:_MAX_HINT - 3] + "..."
    return text


def _hint_text(hint: tx.Any) -> str:
    if hint is None or hint is NoneType:
        return "None"
    if hint is Ellipsis:
        return "..."
    origin = safe_get_origin(hint)
    if origin is tx.Annotated:
        return _hint_text(unwrap(hint, tx.Annotated))
    args = safe_get_args(hint)
    if origin in UNION_TYPES:
        return " | ".join(map(_hint_text, args))
    if isinstance(origin, type):
        if not args or origin is hint:
            return origin.__name__
        return f"{origin.__name__}[{', '.join(map(_hint_text, args))}]"
    # `Literal`, `Any`, a typevar, ...: their own repr, minus the module.
    return _HINT_PREFIX.sub("", _HINT_CLASS.sub(r"\1", repr(hint)))


def _expected(validator: tx.Any, kind: str) -> tx.Optional[str]:
    """What a failing validator expected: its type, or its constraint."""
    if not isinstance(validator, MagicHint):
        return None
    if kind == "type":
        return _hint_name(validator.hint)
    if type(validator).__repr__ is MagicHint.__repr__:
        return f"{type(validator).__name__}({_hint_name(validator.hint)})"
    return repr(validator)


def _location_str(location: Location) -> str:
    if not location:
        return "<root>"
    return "".join(f"[{key!r}]" for key in location)


def _render(problem: Problem, indent: str) -> tx.List[str]:
    lines = [
        f"{indent}{_location_str(problem.location)}: "
        f"{problem.severity}: {problem.message}"
    ]
    detail = []
    if problem.expected is not None:
        detail.append(f"expected {problem.expected}")
    if problem.found is not None:
        detail.append(f"found {problem.found}")
    if detail:
        lines.append(f"{indent}    " + ", ".join(detail))
    if problem.fix:
        lines.append(f"{indent}    fix: {problem.fix}")
    for cause in problem.causes:
        lines.extend(_render(cause, indent + "    "))
    return lines


# ----------------------------------------------------------------------
# Collection (private: used by the collect-aware validators)
# ----------------------------------------------------------------------


def _fails(severity: tx.Any) -> bool:
    if severity is None:  # not said yet: an error unless relabelled
        return True
    return bool(getattr(severity, "fails", severity == "error"))


def _annotation_meta(
    hint: tx.Any,
) -> tx.Tuple[tx.Optional[Severity], tx.Optional[str]]:
    """The `Severity` and `Fix` in a hint's `Annotated` metadata."""
    severity = fix = None
    if safe_get_origin(hint) is tx.Annotated:
        for arg in safe_get_args(hint)[1:]:
            if isinstance(arg, Severity):
                severity = arg
            elif isinstance(arg, Fix):
                fix = str(arg)
    return severity, fix


@functools.lru_cache(maxsize=1024)
def _collector_for(cls: type) -> tx.Optional[tx.Callable]:
    """
    The `_collect` method that stands for `cls.__call__`, if any.

    Only when the class that defines the nearest `__call__` also
    defines `_collect`: a subclass that overrides `__call__` alone is
    checked as one unit, so its own checks are never skipped.
    """
    for klass in cls.__mro__:
        if "__call__" in vars(klass):
            return vars(klass).get("_collect")
    return None


class _Collector:
    """Where a report is gathered: the current location and problems."""

    __slots__ = ("location", "problems")

    def __init__(self, location: Location = ()) -> None:
        self.location: Location = location
        self.problems: tx.List[Problem] = []

    def branch(self) -> "_Collector":
        """An empty collector at the same location (to try a union)."""
        return _Collector(self.location)

    def check(
        self,
        validator: tx.Callable,
        value: tx.Any,
        key: tx.Any = UNSET,
        catch_plain: bool = False,
    ) -> bool:
        """
        Validate `value` (at `key` below the current location) and record
        what fails. Returns whether nothing failing was recorded.

        With `catch_plain`, a plain `TypeError`/`ValueError` is recorded
        as a problem, as a union does when failing fast.
        """
        outer = self.location
        if key is not UNSET:
            self.location = outer + (key,)
        start = len(self.problems)
        try:
            collect = _collector_for(type(validator))
            if collect is None:
                validator(value)
            else:
                collect(validator, value, self)
        except ValidationError as e:
            self.record_error(e, value)
        except (TypeError, ValueError) as e:
            if not catch_plain:
                raise
            self.record(
                "value", f"{type(e).__name__}: {e}",
                expected=_expected(validator, "value"),
                found=_short_repr(value),
            )
        finally:
            self.location = outer
        return not any(p.fails for p in self.problems[start:])

    def wrong_type(self, start: int = 0) -> bool:
        """Whether a failing type problem was recorded right here."""
        return any(
            p.kind == "type" and p.location == self.location and p.fails
            for p in self.problems[start:]
        )

    def record(
        self,
        kind: str,
        message: str,
        key: tx.Any = UNSET,
        expected: tx.Optional[str] = None,
        found: tx.Optional[str] = None,
        severity: tx.Optional[Severity] = None,
        fix: tx.Optional[str] = None,
        causes: tx.Tuple[Problem, ...] = (),
    ) -> None:
        location = self.location
        if key is not UNSET:
            location = location + (key,)
        self.problems.append(Problem(
            location, kind, message, expected, found,
            severity,  # type: ignore[arg-type]  # resolved by `_finish`
            fix, causes,
        ))

    def record_error(self, error: ValidationError, value: tx.Any) -> None:
        kind = "type" if isinstance(error, TypeError) else "value"
        found = getattr(error, "value", UNSET)
        if found is UNSET:
            found = value
        self.record(
            kind,
            getattr(error, "message", "") or "Invalid value.",
            expected=_expected(getattr(error, "this", None), kind),
            found=_short_repr(found),
            fix=getattr(error, "fix", None),
        )


def _resolve(problem: Problem) -> Problem:
    severity = problem.severity
    if severity is None:
        severity = Severity.ERROR
    return problem._replace(
        severity=severity, causes=tuple(map(_resolve, problem.causes)),
    )


def _finish(problems: tx.Iterable[Problem]) -> tx.List[Problem]:
    """Settle severities, and drop repeats (a check run twice)."""
    seen: tx.Set[Problem] = set()
    out = []
    for problem in map(_resolve, problems):
        try:
            if problem in seen:
                continue
            seen.add(problem)
        except TypeError:  # an unhashable key in the location
            pass
        out.append(problem)
    return out


def _collect_report(
    validator: tx.Callable, value: tx.Any, location: tx.Iterable[tx.Any]
) -> Report:
    collector = _Collector(tuple(location))
    collector.check(validator, value)
    return Report(_finish(collector.problems))
