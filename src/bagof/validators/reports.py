"""
Collect every validation problem into a report.

A validator stops at the first failure and raises it. Inside a
[`collect`][bagof.validators.reports.collect] block, a validator that
checks several items (the entries of a container, the fields of a
`TypedDict`, the constraints of an `Annotated` hint) checks all of
them instead, and every [`Problem`][bagof.validators.reports.Problem]
it finds is recorded, with its location, in a
[`Report`][bagof.validators.reports.Report]:

```pycon
>>> import typing_extensions as tx
>>> from bagof.validators import collect, get_validator
>>> class Sidecar(tx.TypedDict):
...     RepetitionTime: float
...     EchoTime: tx.List[float]
...     TaskName: str
>>> validate = get_validator(Sidecar)
>>> with collect() as report:
...     validate({"RepetitionTime": "2s", "EchoTime": [0.01, "x", None]})
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

By default, nothing is raised inside the block: the call above returned
normally, and its problems were recorded. Outside any `collect` block,
validators fail fast exactly as before.

## What happens to a problem

Every problem is recorded in the report. What else happens is the
problem's *action*, chosen per severity when the block is opened:

* `"ignore"`, the default: nothing else. The validator call returns
  normally, so an object being validated (for example a `bagof-magic`
  class with `validate=True`) is still built.
* `"warn"`: the call returns normally, and a
  [`ValidationWarning`][bagof.validators.reports.ValidationWarning] is
  emitted for the problem, naming its location.
* `"raise"`: once the validator has checked everything it was given,
  the call raises a
  [`ValidationError`][bagof.validators.exceptions.ValidationError]. The
  error propagates out of the `with` block as usual, and the report,
  which was filled before the error left the block, can be read in an
  `except` clause.

Keyword arguments name severities, and a single positional action
applies to every severity that is not named:

```python
with collect(error="raise", warning="warn") as report: ...
with collect("warn", recommended="ignore") as report: ...
```

```pycon
>>> import typing_extensions as tx
>>> from bagof.validators import ValidationError, collect, get_validator
>>> try:
...     with collect(error="raise") as report:
...         get_validator(tx.List[int])([1, "x", None])
... except ValidationError:
...     print(report)
2 problems (error: 2)
[1]: error: Not a valid instance.
    expected int, found 'x'
[2]: error: Not a valid instance.
    expected int, found None
```

The action is applied by the outermost validator call, the one made by
the code inside the block. A validator called by another validator
behaves as it does when failing fast: it raises on a failure, so that
a union, or a validator of your own that uses another one as a test,
sees the same outcome in and out of a `collect` block.

`collect` covers validation only. A conversion error (from
`bagof-converters`) is not a validation problem: it is not recorded,
and it propagates as usual. So does any other exception that is not a
`ValidationError`.

## What a problem records

* `location`: the path to the offending value, as a tuple of mapping
  keys, `TypedDict` fields and sequence indices. `()` is the value that
  was given to the validator. Unions and `Annotated` add nothing to it.
* `kind`: `"type"` (the value has the wrong type) or `"value"` (right
  type, wrong value), and a `message`.
* `expected`: the type that was expected, or the constraint that failed
  (for example `IsInRange(0, 1)`). `found`: a short, truncated repr of
  the offending value, or `None` when a required key is missing.
* `severity`: a [`Severity`][bagof.validators.reports.Severity],
  which is [`Severity.ERROR`][bagof.validators.reports.Severity.ERROR]
  unless the hint says otherwise.
* `fix`: how to fix the problem, when known, else `None`.
* `causes`: for a union, the problems that explain it (see below).

A `Problem` is a named tuple: `problem._asdict()` gives a plain dict
for JSON or a table.

## How the checks proceed

* **A wrong type stops descent into that value.** A list given where a
  mapping is expected is one problem, and its contents are not checked.
  The same goes for a tuple of the wrong length. Every other failure
  lets the validator carry on to the value's siblings.
* **`Annotated` constraints** are all checked, and each failing one is
  its own problem, unless the value has the wrong type, in which case
  the constraints after the type check are skipped.
* **A union** is satisfied by its first matching member, as when
  failing fast. When every member fails, the union keeps the problems
  of the member that matched best:

    * if exactly one member had the right shape (it failed on its
      contents or on a constraint, not on the value's own type), the
      report shows that member's problems, as if the union were not
      there. `Optional[Sidecar]` given a broken sidecar reports what is
      wrong inside the sidecar, not "not None and not a Sidecar";
    * otherwise the union is one problem, whose `causes` hold the
      problems of every member that had the right shape (none, when no
      member did: `expected` then names them all).

* **A validator you wrote yourself** takes part without any change.
  Each validator that it calls checks every item it is given, and the
  problems found below it keep their locations, also when it re-raises
  their error with `raise ... from error`. A failure of its own is one
  problem at its location; give it a fix hint with
  `raise self.error(value, "...", type="value", fix="...")`. An error
  that it catches and does not re-raise is not recorded.

## Nested blocks

A `collect` block opened inside another one has its own report and its
own actions; it does not inherit those of the outer block. A problem
reaches the outer report only when its error propagates out of the
inner block, which happens when its action in the inner block is
`"raise"`. In that respect an inner block behaves like an `except`
clause: what it handles stays in it.

The state of a block is held in a [`ContextVar`][contextvars.ContextVar],
so each thread and each `asyncio` task sees only the blocks it opened
itself (and those of the context it was started from).

## Severity and fix hints

Both are set with `Annotated` metadata, without writing a validator:

```python
class Sidecar(tx.TypedDict, total=False):
    RepetitionTime: tx.Required[tx.Annotated[
        float, Severity("recommended"), Fix("Give it in seconds."),
    ]]
    SliceTiming: tx.Annotated[tx.List[float], Severity.WARNING]
```

```python
with collect(recommended="warn") as report:
    get_validator(Sidecar)(data)
```

A severity says how serious a failure of that hint is, independently of
what a `collect` block does with it. A severity that `fails` (such as
`Severity.ERROR`) makes the value invalid, and only such a problem
makes [`Report.ok`][bagof.validators.reports.Report.ok] false. Outside
a `collect` block, a validator raises exactly for those problems, so a
failure under `Severity.WARNING`, or under a custom severity that does
not fail, does not raise. On a required `TypedDict` field, the severity
also covers the key being missing. The nearest annotation decides: an
error inside `Annotated[..., Severity.WARNING]` becomes a warning,
while a problem that already has a severity keeps it.

A [`Fix`][bagof.validators.reports.Fix] is attached to every problem
found under it that has no fix of its own.
"""

__all__ = [
    "collect",
    "Report",
    "Problem",
    "Severity",
    "Fix",
    "ValidationWarning",
]

# Design notes (issue #50) -- the mechanics behind the rules above.
#
# * One entry point: `collect()`, a context manager, so that code which
#   calls validators indirectly (a `bagof-magic` class, a user's own
#   validator) is covered without passing anything through it. Prior
#   art: pydantic's `ValidationError.errors()` (a flat list of dicts
#   with `loc`/`type`/`msg`/`input`) -- the report is flat for the same
#   reason, tools sort, filter and count it -- and the `warnings`
#   module's `catch_warnings`, for the shape of the API.
#
# * The state lives in a `ContextVar` (`_STATE`): stdlib since 3.7,
#   per thread and per asyncio task. Nothing changes when it is unset,
#   so outside `collect()` every validator runs its fail-fast code.
#
# * The outermost validator call applies the actions. Every `__call__`
#   defined on a `Validator` subclass is wrapped once, by the metaclass
#   (`_entry`). Outside `collect()`, or below the outermost call, the
#   wrapper only reads the ContextVar and calls through. The outermost
#   call settles the problems found below it: it raises if any action
#   is "raise", else warns as asked, records, and returns normally.
#   Below it, validators raise as when failing fast -- except that the
#   multi-item ones check every item first -- so a union, or a
#   validator used as a predicate (`try: v(x) except ...`), sees the
#   same outcome as when failing fast. Were the actions applied at every
#   level, `error="ignore"` would make a failing union member "match".
#
# * Problems travel with the errors. A multi-item validator checks its
#   items in a `_Frame`, which records each item's problems in
#   `_State.pending`, at the location the frames have built. If any of
#   them fails, the frame moves them onto the error it raises (its
#   `problems` attribute), so an error that is caught and handled takes
#   its problems with it, and nothing stale is left behind. The parent
#   frame adopts them; a plain error becomes one problem. An error that
#   wraps another one `from` it keeps the problems of its cause.
#
# * Severity is resolved bottom-up. A problem is recorded with
#   `severity=None` ("not said"); the nearest `Annotated` with a
#   `Severity` labels the unlabelled problems under it; `_settle` turns
#   what is left into `Severity.ERROR`. A frame fails when a problem
#   under it fails, `None` counting as an error.
#
# * `Severity.fails` is kept beside the actions rather than replaced by
#   them: the actions are the caller's policy for one block (and default
#   to "ignore"), while `fails` is what the hint's author says about
#   validity. `Report.ok`, the fail-fast mode and the union's notion of
#   a match need an answer that does not depend on the block.
#
# * Union relevance follows pydantic's "smart" mode and jsonschema's
#   `best_match` in spirit, with one deterministic rule: a member that
#   failed with a type problem at the union's own location is
#   uninformative (`expected` already names it).

# stdlib
import contextlib
import contextvars
import functools
import re
import reprlib
import warnings

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

Action: tx.TypeAlias = tx.Literal["raise", "warn", "ignore"]
"""What a [`collect`][bagof.validators.reports.collect] block does with
a problem, besides recording it."""

_ACTIONS = ("raise", "warn", "ignore")


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
    serious a failure of that hint is. The label is also the keyword
    that chooses, in a [`collect`][bagof.validators.reports.collect]
    block, what is done with such a problem:

    ```pycon
    >>> import typing_extensions as tx
    >>> from bagof.validators import Severity, collect, get_validator
    >>> validate = get_validator(tx.Annotated[int, Severity.WARNING])
    >>> validate("x")          # a warning does not fail validation
    >>> with collect(warning="ignore") as report:
    ...     validate("x")
    >>> print(report)
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
    >>> from bagof.validators import Fix, collect, get_validator
    >>> hint = tx.Annotated[float, Fix("Give it in seconds.")]
    >>> with collect() as report:
    ...     get_validator(hint)("2s")
    >>> report[0].fix
    'Give it in seconds.'
    ```
    """


class ValidationWarning(UserWarning):
    """
    The warning emitted for a problem whose action is `"warn"` in a
    [`collect`][bagof.validators.reports.collect] block.

    Its message names the problem's location, severity and message, as
    a line of the printed report does. Filter it like any warning, for
    example `warnings.simplefilter("error", ValidationWarning)`.
    """


class Problem(tx.NamedTuple):
    """
    One problem found by a validator inside a
    [`collect`][bagof.validators.reports.collect] block.
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
    Every [`Problem`][bagof.validators.reports.Problem] recorded in a
    [`collect`][bagof.validators.reports.collect] block, in the order
    they were found.

    A report is a sequence of problems for tools, and prints for people.
    The report that a block yields is filled while the block runs, and
    stays readable once it has been left, including when the block was
    left by an error. A report can also be built from problems, for
    example to merge several:

    ```python
    merged = Report([*first_report, *second_report])
    ```

    !!! note
        Like any sequence, an empty report is falsy, but a report of
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
        self._problems: tx.List[Problem] = list(problems)

    @property
    def problems(self) -> tx.Tuple[Problem, ...]:
        """The problems, in order."""
        return tuple(self._problems)

    @property
    def ok(self) -> bool:
        """
        Whether no problem makes the value invalid.

        This depends on the problems' severities only, not on what the
        block did with them: a report of errors that were ignored is not
        ok.
        """
        return not any(problem.fails for problem in self._problems)

    def __getitem__(self, index: tx.Any) -> tx.Any:
        return self._problems[index]

    def __len__(self) -> int:
        return len(self._problems)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Report):
            return NotImplemented
        return self._problems == other._problems

    __hash__ = None  # type: ignore[assignment]

    def summary(self) -> str:
        """One line: how many problems, by severity."""
        if not self._problems:
            return "No problems."
        counts: tx.Dict[str, int] = {}
        for problem in self._problems:
            label = _label(problem.severity)
            counts[label] = counts.get(label, 0) + 1
        n = len(self._problems)
        detail = ", ".join(f"{k}: {v}" for k, v in counts.items())
        return f"{n} problem{'s' if n != 1 else ''} ({detail})"

    def __str__(self) -> str:
        lines = [self.summary()]
        for problem in self._problems:
            lines.extend(_render(problem, ""))
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"<Report: {self.summary()}>"


@contextlib.contextmanager
def collect(
    default: tx.Optional[Action] = None, /, **actions: Action
) -> tx.Iterator[Report]:
    """
    Record every validation problem found inside the block.

    Inside the block, a validator that checks several items checks all
    of them rather than stopping at the first failure, and every problem
    found is recorded in the report that the block yields. See
    [`reports`][bagof.validators.reports] for how the checks proceed.

    !!! example
        ```pycon
        >>> import typing_extensions as tx
        >>> from bagof.validators import collect, get_validator
        >>> validate = get_validator(tx.Dict[str, tx.List[int]])
        >>> with collect() as report:
        ...     validate({"a": [1, "x"], "b": 2})
        >>> report.ok
        False
        >>> print(report)
        2 problems (error: 2)
        ['a'][1]: error: Not a valid instance.
            expected int, found 'x'
        ['b']: error: Not a valid instance.
            expected list[int], found 2
        ```

    Parameters
    ----------
    default : {"ignore", "warn", "raise"}, optional
        The action for every severity that is not named by a keyword.
        `"ignore"` when not given.
    **actions : {"ignore", "warn", "raise"}
        The action for the severity of that name, for example
        `error="raise"`, `warning="warn"` or `recommended="warn"`.
        Every problem is recorded, whatever its action. With
        `"ignore"`, nothing else is done. With `"warn"`, a
        [`ValidationWarning`][bagof.validators.reports.ValidationWarning]
        is emitted. With `"raise"`, the validator call raises once it
        has checked everything it was given, and the error propagates
        out of the block.

    Yields
    ------
    Report
        The problems found in the block, filled as it runs. It can
        still be read once the block has been left, also from an
        `except` clause.

    Raises
    ------
    ValueError
        If an action is not one of `"ignore"`, `"warn"` and `"raise"`.
    """
    for action in (default, *actions.values()):
        if action is not None and action not in _ACTIONS:
            raise ValueError(
                f"Unknown action {action!r}: expected one of "
                f"{', '.join(map(repr, _ACTIONS))}."
            )
    state = _State(default or "ignore", actions)
    token = _STATE.set(state)
    try:
        yield state.report
    except ValidationError as error:
        # Raised by the outermost validator call (its problems are on
        # it), or by the block's own code. Recorded, never swallowed.
        state.report._problems.extend(
            _settle(_problems_of(error, UNSET, ()))
        )
        raise
    finally:
        _STATE.reset(token)


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
        f"{_label(problem.severity)}: {problem.message}"
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
# Collection (private: used by the validators)
# ----------------------------------------------------------------------


def _label(severity: tx.Any) -> str:
    """A severity's label; `None` (not said yet) is an error."""
    return "error" if severity is None else str(severity)


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


class _State:
    """What a `collect()` block holds while it runs."""

    __slots__ = ("report", "default", "actions", "busy", "pending",
                 "location")

    def __init__(self, default: str, actions: tx.Dict[str, str]) -> None:
        self.report = Report()
        self.default = default
        self.actions = actions
        # Whether a validator call is running (only the outermost one
        # settles), the problems found below it so far, and where the
        # value being checked is.
        self.busy = False
        self.pending: tx.List[Problem] = []
        self.location: Location = ()

    def action(self, severity: tx.Any) -> str:
        return self.actions.get(_label(severity), self.default)

    def run(self, call: tx.Callable, this: tx.Any, value: tx.Any) -> tx.Any:
        """Make the outermost validator call, and settle its problems."""
        self.busy = True
        try:
            try:
                result = call(this, value)
            except ValidationError as error:
                problems = _settle(
                    self.pending + _problems_of(error, value, ())
                )
                if self._raises(problems):
                    _attach(error, problems)
                    raise
                self._keep(problems)
                return None
            problems = _settle(self.pending)
            if self._raises(problems):
                # Only a problem that does not fail (e.g. a warning) can
                # get here: the validator itself did not raise.
                raise _attach(this.value_error(
                    value, _summarize(problems)
                ), problems)
            self._keep(problems)
            return result
        finally:
            self.busy = False
            self.pending = []
            self.location = ()

    def _raises(self, problems: tx.List[Problem]) -> bool:
        actions = [self.action(problem.severity) for problem in problems]
        # Warn now: the problems with "warn" travel on the error, and
        # the block records them, but it does not warn again.
        for problem, action in zip(problems, actions):
            if action == "warn":
                warnings.warn(
                    ValidationWarning(_one_line(problem)), stacklevel=4
                )
        return "raise" in actions

    def _keep(self, problems: tx.List[Problem]) -> None:
        self.report._problems.extend(problems)


_STATE: "contextvars.ContextVar[tx.Optional[_State]]" = (
    contextvars.ContextVar("bagof.validators.collect", default=None)
)


def _collecting() -> tx.Optional[_State]:
    """The running `collect()` block, while a validator call runs in it."""
    state = _STATE.get()
    if state is None or not state.busy:
        return None
    return state


def _entry(call: tx.Callable) -> tx.Callable:
    """Wrap a validator's `__call__` so that, inside `collect()`, the
    outermost call settles the problems found below it."""

    @functools.wraps(call)
    def __call__(self: tx.Any, value: tx.Any) -> tx.Any:
        state = _STATE.get()
        if state is None or state.busy:
            return call(self, value)
        return state.run(call, self, value)

    return __call__


def _attach(
    error: ValidationError, problems: tx.Iterable[Problem]
) -> ValidationError:
    error.problems = tuple(problems)
    return error


def _problems_of(
    error: BaseException, value: tx.Any, location: Location
) -> tx.List[Problem]:
    """The problems an error carries, from itself or from its cause; or
    one problem made from the error."""
    seen = set()
    cause: tx.Optional[BaseException] = error
    while cause is not None and id(cause) not in seen:
        problems = getattr(cause, "problems", None)
        if problems:
            return list(problems)
        seen.add(id(cause))
        cause = cause.__cause__
    return [_problem(error, value, location)]


def _problem(
    error: BaseException,
    value: tx.Any,
    location: Location,
    message: tx.Optional[str] = None,
) -> Problem:
    """One problem, made from a plain validation error."""
    kind = "type" if isinstance(error, TypeError) else "value"
    found = getattr(error, "value", UNSET)
    if found is UNSET:
        found = value
    return Problem(
        location,
        kind,
        message or getattr(error, "message", "") or "Invalid value.",
        _expected(getattr(error, "this", None), kind),
        None if found is UNSET else _short_repr(found),
        None,  # type: ignore[arg-type]  # resolved by `_settle`
        getattr(error, "fix", None),
    )


def _wrong_type(problems: tx.Iterable[Problem], location: Location) -> bool:
    """Whether a failing type problem was recorded at `location`."""
    return any(
        p.kind == "type" and p.location == location and p.fails
        for p in problems
    )


def _summarize(problems: tx.Sequence[Problem]) -> str:
    return str(Report(problems))


def _one_line(problem: Problem) -> str:
    first, *rest = _render(problem, "")
    detail = "; ".join(line.strip() for line in rest)
    return f"{first} ({detail})" if detail else first


class _Frame:
    """
    Where a validator checks several items.

    Outside `collect()`, `check` and `fail` raise as a fail-fast
    validator does. Inside it, they record problems at the item's
    location and carry on; when the frame closes, it raises one error
    carrying all of its problems if any of them fails.
    """

    __slots__ = ("this", "value", "state", "start", "location", "last",
                 "caught")

    def __init__(self, this: tx.Any, value: tx.Any) -> None:
        self.this = this
        self.value = value
        self.state = _collecting()

    def __enter__(self) -> "_Frame":
        state = self.state
        if state is not None:
            self.start = self.last = len(state.pending)
            self.location = state.location
            self.caught: tx.List[ValidationError] = []
        return self

    def check(
        self,
        validator: tx.Callable[[tx.Any], tx.Any],
        item: tx.Any,
        key: tx.Any = UNSET,
        message: tx.Optional[tx.Callable[[tx.Any, tx.Any], str]] = None,
        whole: bool = False,
    ) -> bool:
        """
        Validate `item`, found at `key` (or at the frame's own location).
        Returns whether nothing failed.

        Failing fast, a failure is raised again as the frame's own error
        with `message(key, item)`, or as it is without a `message`.
        Collecting, it is recorded; with `whole`, as one problem with
        that message, whatever was found below it.
        """
        state = self.state
        if state is None:
            if message is None:
                validator(item)
                return True
            try:
                validator(item)
            except ValidationError as e:
                raise self.this.value_error(
                    self.value, message(key, item)
                ) from e
            return True
        location = self.location
        if key is not UNSET:
            location = location + (key,)
        state.location = location
        self.last = len(state.pending)
        try:
            validator(item)
        except ValidationError as e:
            self.caught.append(e)
            if whole and message is not None:
                state.pending.append(
                    _problem(e, item, location, message(key, item))
                )
            else:
                state.pending.extend(_problems_of(e, item, location))
        finally:
            state.location = self.location
        return not any(p.fails for p in state.pending[self.last:])

    def wrong_type(self) -> bool:
        """Whether the last check failed on the value's own type."""
        return _wrong_type(self.state.pending[self.last:], self.location)

    def fail(
        self,
        message: str,
        key: tx.Any = UNSET,
        expected: tx.Optional[str] = None,
        found: tx.Any = UNSET,
        severity: tx.Optional[Severity] = None,
        fix: tx.Optional[str] = None,
    ) -> None:
        """A failure of the frame's own (a missing or unexpected key)."""
        state = self.state
        if state is None:
            if _fails(severity):
                raise self.this.value_error(self.value, message)
            return
        location = self.location
        if key is not UNSET:
            location = location + (key,)
        state.pending.append(Problem(
            location, "value", message, expected,
            None if found is UNSET else _short_repr(found),
            severity,  # type: ignore[arg-type]  # resolved by `_settle`
            fix,
        ))

    def relabel(
        self, severity: tx.Optional[Severity], fix: tx.Optional[str]
    ) -> None:
        """Give the frame's unlabelled problems a severity and a fix."""
        if self.state is None or (severity is None and fix is None):
            return
        pending = self.state.pending
        for i in range(self.start, len(pending)):
            problem = pending[i]
            if severity is not None and problem.severity is None:
                problem = problem._replace(severity=severity)
            if fix is not None and problem.fix is None:
                problem = problem._replace(fix=fix)
            pending[i] = problem

    def __exit__(
        self, etype: tx.Any, error: tx.Any, traceback: tx.Any
    ) -> bool:
        state = self.state
        if state is None:
            return False
        if error is not None:
            if not isinstance(error, ValidationError):
                return False
            # A failure in the frame's own code, after some items.
            self.caught.append(error)
            state.pending.extend(
                _problems_of(error, self.value, self.location)
            )
        problems = state.pending[self.start:]
        if not any(p.fails for p in problems):
            return True
        del state.pending[self.start:]
        if len(self.caught) == 1 and all(
            p.location == self.location for p in problems
        ):
            # One failure of the value itself (e.g. its type, under
            # `Annotated`): the same error as when failing fast.
            raise _attach(self.caught[0], problems)
        raise _attach(self.this.value_error(
            self.value, _summarize(problems)
        ), problems)


def _resolve(problem: Problem) -> Problem:
    severity = problem.severity
    if severity is None:
        severity = Severity.ERROR
    return problem._replace(
        severity=severity, causes=tuple(map(_resolve, problem.causes)),
    )


def _settle(problems: tx.Iterable[Problem]) -> tx.List[Problem]:
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
