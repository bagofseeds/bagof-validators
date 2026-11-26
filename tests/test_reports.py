"""Collecting every validation problem with `collect()` (#50)."""

# stdlib
import asyncio
import pickle
import threading
import warnings

# dependencies
import pytest
import typing_extensions as tx

# locals
from bagof.validators import (
    Fix,
    HasLength,
    IsInRange,
    IsMapping,
    IsPositive,
    MatchesRegex,
    Problem,
    Report,
    Severity,
    ValidationWarning,
    Validator,
    collect,
    get_validator,
)
from bagof.validators.exceptions import (
    TypeValidationError,
    ValidationError,
    ValueValidationError,
)

# ----------------------------------------------------------------------
# Hints used throughout
# ----------------------------------------------------------------------


class Coil(tx.TypedDict):
    Name: str
    Channels: tx.List[int]


class Sidecar(tx.TypedDict):
    RepetitionTime: float
    EchoTime: tx.List[float]
    Coils: tx.Dict[str, Coil]
    TaskName: str


class Small(tx.TypedDict):
    a: int


class Other(tx.TypedDict):
    b: int


class Closed(tx.TypedDict, closed=True):
    a: int


class Recommended(tx.TypedDict, total=False):
    Name: tx.Required[str]
    RepetitionTime: tx.Required[tx.Annotated[
        float, Severity("recommended"), Fix("Give it in seconds."),
    ]]
    Old: tx.NotRequired[tx.Annotated[int, Severity.WARNING]]


BROKEN_SIDECAR = {
    "RepetitionTime": "2s",
    "EchoTime": [0.01, "x", None],
    "Coils": {
        "head": {"Name": 3, "Channels": [1, "two", 3, "four"]},
        "neck": {"Channels": []},
        "body": "not a coil",
    },
}

BROKEN_SIDECAR_LOCATIONS = [
    ("RepetitionTime",),
    ("EchoTime", 1),
    ("EchoTime", 2),
    ("Coils", "head", "Name"),
    ("Coils", "head", "Channels", 1),
    ("Coils", "head", "Channels", 3),
    ("Coils", "neck", "Name"),
    ("Coils", "body"),
    ("TaskName",),
]


def collected(hint: tx.Any, value: tx.Any, *default, **actions) -> Report:
    """The report of validating `value` against `hint` in a block."""
    validate = hint if isinstance(hint, Validator) else get_validator(hint)
    with collect(*default, **actions) as report:
        assert validate(value) is None
    return report


def locations(report: Report) -> tx.List[tx.Tuple[tx.Hashable, ...]]:
    return [problem.location for problem in report]


# ----------------------------------------------------------------------
# Locations through nested containers
# ----------------------------------------------------------------------


def test_valid_value_gives_an_empty_report() -> None:
    value = {
        "RepetitionTime": 2.0,
        "EchoTime": [0.01, 0.02],
        "Coils": {"head": {"Name": "h", "Channels": [1, 2]}},
        "TaskName": "rest",
    }
    report = collected(Sidecar, value)
    assert list(report) == []
    assert report.ok
    assert not report
    assert str(report) == "No problems."


def test_nested_failures_at_every_depth() -> None:
    report = collected(Sidecar, BROKEN_SIDECAR)
    assert locations(report) == BROKEN_SIDECAR_LOCATIONS
    assert not report.ok
    assert all(problem.fails for problem in report)
    assert [p.kind for p in report] == [
        "type", "type", "type", "type", "type", "type",
        "value", "type", "value",
    ]
    missing = report[6]
    assert missing.message == "Missing required key 'Name'"
    assert missing.expected == "str"
    assert missing.found is None
    body = report[7]
    assert body.expected == "Coil"
    assert body.found == "'not a coil'"


def test_a_wrong_container_type_stops_descent() -> None:
    report = collected(tx.Dict[str, tx.List[int]], {"a": "abc", "b": [1, "x"]})
    # "abc" is iterable, but not a list: one problem, its characters are
    # not checked.
    assert locations(report) == [("a",), ("b", 1)]
    assert report[0].kind == "type"
    assert report[0].expected == "list[int]"


def test_top_level_wrong_type_is_one_problem() -> None:
    report = collected(Sidecar, [1, 2])
    assert locations(report) == [()]
    assert report[0].kind == "type"


def test_tuple_items_and_wrong_length() -> None:
    assert locations(
        collected(tx.Tuple[int, str, int], (1, 2, "x"))
    ) == [(1,), (2,)]
    report = collected(tx.Tuple[int, str], (1, 2, 3))
    assert locations(report) == [()]
    assert report[0].kind == "value"
    assert locations(
        collected(tx.Tuple[int, ...], (1, "a", 2.5))
    ) == [(1,), (2,)]
    report = collected(tx.Tuple[int, str], {1, 2})
    assert report[0].expected == "tuple[int, str]"


def test_set_elements_and_mapping_keys() -> None:
    assert locations(collected(tx.Set[int], {"a"})) == [(0,)]
    report = collected(tx.Dict[str, int], {1: 1, "b": "x"})
    assert locations(report) == [(1,), ("b",)]
    assert report[0].message == "Key 1 is not valid."
    assert report[0].expected == "str"
    assert report[0].found == "1"


def test_closed_and_extra_items_typeddict() -> None:
    report = collected(Closed, {"a": "x", "b": 1, "c": 2})
    assert locations(report) == [("a",), ("b",), ("c",)]
    assert report[1].message == "Unexpected key 'b'"
    assert report[1].found == "1"


def test_typevar_is_transparent() -> None:
    T = tx.TypeVar("T", bound=tx.List[int])
    assert locations(collected(T, [1, "x", "y"])) == [(1,), (2,)]


def test_iterator_elements_cannot_be_checked() -> None:
    report = collected(tx.Iterable[int], iter([1]))
    assert locations(report) == [()]
    assert report[0].kind == "type"


def test_several_calls_in_one_block() -> None:
    validate = get_validator(tx.Dict[str, int])
    with collect() as report:
        validate({"x": "1"})
        validate({})
        validate({"y": None})
    assert locations(report) == [("x",), ("y",)]
    merged = Report([*report, *collected(int, "z")])
    assert locations(merged) == [("x",), ("y",), ()]


# ----------------------------------------------------------------------
# Actions
# ----------------------------------------------------------------------


def test_the_default_action_is_to_ignore() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        report = collected(Sidecar, BROKEN_SIDECAR)
        # A single value too: the call returns normally.
        assert len(collected(int, "x")) == 1
    assert locations(report) == BROKEN_SIDECAR_LOCATIONS
    assert not report.ok


def test_warn_emits_one_warning_per_problem() -> None:
    with pytest.warns(ValidationWarning) as caught:
        report = collected(tx.List[int], [1, "x", None], error="warn")
    assert [str(w.message) for w in caught] == [
        "[1]: error: Not a valid instance. (expected int, found 'x')",
        "[2]: error: Not a valid instance. (expected int, found None)",
    ]
    assert locations(report) == [(1,), (2,)]
    # The warning points at the code that called the validator.
    assert {w.filename for w in caught} == {__file__}
    assert issubclass(ValidationWarning, UserWarning)


def test_raise_propagates_after_every_sibling_was_checked() -> None:
    validate = get_validator(Sidecar)
    with pytest.raises(ValueValidationError) as info:
        with collect(error="raise") as report:
            validate(BROKEN_SIDECAR)
            pytest.fail("not reached")  # pragma: no cover
    # The report was filled before the error left the block, and can
    # still be read.
    assert locations(report) == BROKEN_SIDECAR_LOCATIONS
    assert list(info.value.problems) == list(report)
    assert str(report) in info.value.message
    # The same report can be read from an `except` clause.
    try:
        with collect(error="raise") as report:
            validate(BROKEN_SIDECAR)
    except ValidationError:
        assert len(report) == len(BROKEN_SIDECAR_LOCATIONS)
    else:  # pragma: no cover
        pytest.fail("not raised")


def test_raise_keeps_the_error_of_a_single_value() -> None:
    with pytest.raises(TypeValidationError) as info:
        with collect("raise") as report:
            get_validator(int)("x")
    assert info.value.message == "Not a valid instance."
    assert locations(report) == [()]
    # Through `Annotated` too: the same error as when failing fast.
    hint = tx.Annotated[int, IsPositive()]
    with pytest.raises(TypeValidationError):
        with collect("raise"):
            get_validator(hint)("x")


def test_actions_are_chosen_per_severity() -> None:
    hint = tx.List[tx.Annotated[int, Severity.WARNING]]
    # A warning does not raise, under `error="raise"`.
    report = collected(hint, ["a"], error="raise")
    assert [p.severity for p in report] == ["warning"]
    assert report.ok
    # But it does under `warning="raise"`, although it does not fail.
    with pytest.raises(ValueValidationError) as info:
        with collect(warning="raise") as report:
            get_validator(hint)(["a", 1, "b"])
    assert locations(report) == [(0,), (2,)]
    assert [p.severity for p in info.value.problems] == ["warning"] * 2
    # Errors and warnings mixed: each gets its own action.
    mixed = tx.Tuple[tx.Annotated[int, Severity.WARNING], int]
    with pytest.warns(ValidationWarning) as caught:
        with pytest.raises(ValueValidationError):
            with collect(error="raise", warning="warn") as report:
                get_validator(mixed)(("a", "b"))
    assert [str(w.message)[:13] for w in caught] == ["[0]: warning:"]
    assert [p.severity for p in report] == ["warning", "error"]


def test_custom_severities_are_named_by_keyword() -> None:
    with pytest.warns(ValidationWarning, match="recommended"):
        report = collected(
            Recommended, {"Name": "n", "RepetitionTime": "x"},
            recommended="warn",
        )
    assert [p.severity for p in report] == ["recommended"]
    with pytest.raises(ValueValidationError):
        collected(Recommended, {"Name": "n"}, recommended="raise")
    # Not named: the default action.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        collected(Recommended, {"Name": "n"}, error="raise")


def test_a_positional_action_sets_every_severity() -> None:
    hint = tx.Tuple[
        tx.Annotated[int, Severity.WARNING],
        tx.Annotated[int, Severity("recommended")],
        int,
    ]
    with pytest.warns(ValidationWarning) as caught:
        report = collected(hint, ("a", "b", "c"), "warn")
    assert len(caught) == 3
    assert [p.severity for p in report] == ["warning", "recommended", "error"]
    # A keyword still names its own severity.
    with pytest.warns(ValidationWarning) as caught:
        collected(hint, ("a", "b", "c"), "warn", recommended="ignore")
    assert len(caught) == 2
    with pytest.raises(ValueValidationError):
        collected(hint, ("a", 1, 2), "raise")


def test_unknown_actions_are_refused() -> None:
    with pytest.raises(ValueError, match="Unknown action 'fail'"):
        with collect("fail"):
            pass  # pragma: no cover
    with pytest.raises(ValueError, match="Unknown action 'stop'"):
        with collect(error="stop"):
            pass  # pragma: no cover


# ----------------------------------------------------------------------
# What the block records, and what it lets through
# ----------------------------------------------------------------------


def test_a_validation_error_raised_by_the_block_is_recorded() -> None:
    error = ValueValidationError("Bad input.", value=3)
    with pytest.raises(ValueValidationError) as info:
        with collect() as report:
            raise error
    assert info.value is error
    assert [(p.location, p.message, p.found) for p in report] == [
        ((), "Bad input.", "3"),
    ]
    with pytest.raises(ValidationError):
        with collect() as report:
            raise ValidationError("No value.")
    assert report[0].found is None


def test_an_error_caught_inside_the_block_is_not_recorded() -> None:
    with collect() as report:
        try:
            with collect("raise"):
                get_validator(tx.List[int])([1, "x"])
        except ValidationError:
            pass
    assert list(report) == []


def test_non_validation_errors_propagate() -> None:
    class Broken(Validator[tx.Any]):
        def __call__(self, value: tx.Any) -> None:
            raise RuntimeError("bug")

    validate = get_validator(tx.List[tx.Annotated[int, Broken()]])
    with pytest.raises(RuntimeError):
        with collect() as report:
            validate([1])
    assert list(report) == []
    # The block is left in a usable state after one.
    with collect() as report:
        with pytest.raises(RuntimeError):
            validate(["x"])
        get_validator(tx.List[int])(["x"])
    assert locations(report) == [(0,)]


# ----------------------------------------------------------------------
# Nested blocks
# ----------------------------------------------------------------------


def test_an_inner_block_has_its_own_report_and_actions() -> None:
    validate = get_validator(tx.List[int])
    with collect(error="raise") as outer:
        with collect() as inner:  # does not inherit `error="raise"`
            validate(["a"])
        assert locations(inner) == [(0,)]
    assert list(outer) == []


def test_a_raised_problem_reaches_the_outer_report() -> None:
    validate = get_validator(tx.List[int])
    with pytest.raises(ValueValidationError):
        with collect() as outer:
            validate(["a"])
            with collect("raise") as inner:
                validate([1, "b"])
    assert locations(inner) == [(1,)]
    assert locations(outer) == [(0,), (1,)]


# ----------------------------------------------------------------------
# Threads and tasks
# ----------------------------------------------------------------------


def test_a_block_is_not_seen_by_other_threads() -> None:
    errors = []

    def other() -> None:
        try:
            get_validator(tx.List[int])(["t"])
        except ValidationError as e:
            errors.append(e)

    with collect() as report:
        get_validator(tx.List[int])(["main"])
        thread = threading.Thread(target=other)
        thread.start()
        thread.join()
    # The other thread failed fast, and its problem is not here.
    assert len(errors) == 1 and errors[0].problems == ()
    assert [p.found for p in report] == ["'main'"]


def test_threads_have_their_own_blocks() -> None:
    barrier = threading.Barrier(2)
    reports = {}

    def work(name: str) -> None:
        with collect() as report:
            for i in range(20):
                get_validator(tx.List[int])([name, i])
                if i == 0:
                    barrier.wait()
        reports[name] = report

    threads = [threading.Thread(target=work, args=(n,)) for n in "ab"]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    for name in "ab":
        assert {p.found for p in reports[name]} == {repr(name)}
        assert len(reports[name]) == 20


def test_tasks_have_their_own_blocks() -> None:
    async def work(name: str) -> Report:
        with collect() as report:
            for _ in range(5):
                get_validator(tx.List[int])([name])
                await asyncio.sleep(0)
        return report

    async def outside() -> tx.Optional[ValidationError]:
        await asyncio.sleep(0)
        try:
            get_validator(int)("free")
        except ValidationError as e:
            return e
        return None  # pragma: no cover

    async def main() -> tx.List[tx.Any]:
        return list(await asyncio.gather(work("a"), work("b"), outside()))

    a, b, error = asyncio.run(main())
    assert {p.found for p in a} == {"'a'"} and len(a) == 5
    assert {p.found for p in b} == {"'b'"} and len(b) == 5
    assert isinstance(error, TypeValidationError)


# ----------------------------------------------------------------------
# Unions
# ----------------------------------------------------------------------


def test_union_that_matches_adds_nothing() -> None:
    hint = tx.Union[int, tx.List[int]]
    assert list(collected(hint, 1)) == []
    assert list(collected(hint, [1, 2])) == []


def test_union_reports_the_one_member_with_the_right_shape() -> None:
    # `None` fails on type; the TypedDict got past its type check, so the
    # report shows what is wrong inside it, as if the union were absent.
    report = collected(tx.Optional[Small], {"a": "x"})
    assert locations(report) == [("a",)]
    assert report[0].expected == "int"
    # Same through a list member, deeper.
    report = collected(
        tx.Dict[str, tx.Union[float, tx.List[float]]],
        {"k": [1.0, "x", 2.0, "y"]},
    )
    assert locations(report) == [("k", 1), ("k", 3)]


def test_union_reports_a_failing_constraint_of_the_matching_type() -> None:
    hint = tx.Union[int, tx.Annotated[str, MatchesRegex("^a")]]
    report = collected(hint, "zz")
    assert locations(report) == [()]
    assert report[0].kind == "value"
    assert report[0].message == "Does not match pattern."


def test_union_with_no_member_of_the_right_type() -> None:
    report = collected(tx.Optional[tx.List[int]], "x")
    assert len(report) == 1
    problem = report[0]
    assert problem.location == ()
    assert problem.kind == "type"
    assert problem.message == "Not compatible with any of the union types."
    assert problem.expected == "list[int] | None"
    assert problem.found == "'x'"
    assert problem.causes == ()


def test_ambiguous_union_keeps_every_candidate_as_causes() -> None:
    report = collected(
        tx.Dict[str, tx.Union[Small, Other]], {"k": {"a": "x"}}
    )
    assert locations(report) == [("k",)]
    problem = report[0]
    assert problem.expected == "Small | Other"
    assert [c.location for c in problem.causes] == [("k", "a"), ("k", "b")]
    assert [c.message for c in problem.causes] == [
        "Not a valid instance.", "Missing required key 'b'",
    ]
    assert [c.severity for c in problem.causes] == ["error", "error"]


def test_union_member_raising_a_plain_error_is_a_problem() -> None:
    class Raises(Validator[int]):
        def __call__(self, value: int) -> None:
            raise ValueError("boom")

    hint = tx.Union[tx.Annotated[int, Raises()], str]
    report = collected(hint, 1)
    assert len(report) == 1
    assert report[0].message == "ValueError: boom"


def test_union_member_with_warnings_only_matches() -> None:
    hint = tx.Union[tx.Annotated[int, IsPositive(), Severity.WARNING], str]
    report = collected(hint, -1)
    assert report.ok
    assert [p.severity for p in report] == ["warning"]


def test_union_members_are_tried_whatever_the_actions() -> None:
    # Ignoring errors does not make a failing member "match".
    hint = tx.Union[tx.List[int], tx.List[str]]
    assert list(collected(hint, ["a", "b"])) == []
    assert list(collected(hint, ["a", "b"], "raise")) == []


# ----------------------------------------------------------------------
# Annotated constraints
# ----------------------------------------------------------------------


def test_every_failing_constraint_is_reported() -> None:
    hint = tx.Annotated[
        str, MatchesRegex("^a", compose=True), HasLength(3, compose=True),
    ]
    report = collected(hint, "bb")
    assert [p.message for p in report] == [
        "Does not match pattern.",
        "Does not match expected length 2 != 3.",
    ]
    assert report[0].expected == "MatchesRegex(re.compile('^a'))"
    assert all(p.kind == "value" for p in report)


def test_a_wrong_type_skips_the_constraints() -> None:
    hint = tx.Annotated[str, MatchesRegex("^a", compose=True)]
    report = collected(hint, 1)
    assert len(report) == 1
    assert report[0].kind == "type"
    # And the length of a value of the wrong type is not checked.
    report = collected(HasLength(2, hint=tx.List[int]), 3)
    assert len(report) == 1


def test_constraint_inside_a_container() -> None:
    hint = tx.List[tx.Annotated[float, IsInRange(0, 1)]]
    report = collected(hint, [0.5, 2, "x", -1])
    assert locations(report) == [(1,), (2,), (3,)]
    assert [p.kind for p in report] == ["value", "type", "value"]
    assert report[0].expected == "IsInRange(0, 1)"


def test_a_check_run_twice_is_reported_once() -> None:
    # The composed `HasLength` re-checks the list's elements.
    hint = tx.Annotated[tx.List[int], HasLength(3, compose=True)]
    report = collected(hint, [1, "a"])
    assert locations(report) == [(1,), ()]
    assert report[1].message == "Does not match expected length 2 != 3."


# ----------------------------------------------------------------------
# Severities
# ----------------------------------------------------------------------


def test_severity_is_a_string() -> None:
    assert Severity.ERROR == "error" and Severity.ERROR.fails
    assert Severity.WARNING == "warning" and not Severity.WARNING.fails
    custom = Severity("proscribed", fails=True)
    assert custom == "proscribed" and custom.fails
    again = pickle.loads(pickle.dumps(custom))
    assert again == "proscribed" and again.fails
    assert isinstance(again, Severity)


def test_warning_is_recorded_and_does_not_fail() -> None:
    hint = tx.Annotated[int, Severity.WARNING]
    report = collected(hint, "x")
    assert report.ok
    assert len(report) == 1
    assert report[0].severity == "warning"
    assert not report[0].fails
    get_validator(hint)("x")  # agrees with the report: does not raise


def test_default_severity_is_error() -> None:
    report = collected(int, "x")
    assert report[0].severity is Severity.ERROR
    assert not report.ok


def test_ignored_errors_still_make_the_report_not_ok() -> None:
    assert not collected(tx.List[int], ["x"], error="ignore").ok
    with pytest.warns(ValidationWarning):
        assert not collected(tx.List[int], ["x"], error="warn").ok


def test_custom_failing_severity_relabels_errors() -> None:
    proscribed = Severity("proscribed", fails=True)
    hint = tx.Dict[str, tx.Annotated[tx.List[int], proscribed]]
    report = collected(hint, {"k": [1, "x"]})
    assert locations(report) == [("k", 1)]
    assert report[0].severity == "proscribed"
    assert not report.ok
    with pytest.raises(ValidationError):
        get_validator(hint)({"k": [1, "x"]})


def test_outer_warning_relabels_inner_errors() -> None:
    hint = tx.Annotated[Small, Severity.WARNING]
    report = collected(hint, {"a": "x"})
    assert [p.severity for p in report] == ["warning"]
    assert report.ok
    get_validator(hint)({"a": "x"})


def test_inner_warning_stays_a_warning() -> None:
    inner = tx.Annotated[int, Severity.WARNING]
    hint = tx.Annotated[tx.List[inner], Severity("proscribed", fails=True)]
    report = collected(hint, [1, "x"])
    assert [p.severity for p in report] == ["warning"]
    assert report.ok
    get_validator(hint)([1, "x"])


def test_severity_covers_a_missing_required_field() -> None:
    validate = get_validator(Recommended)
    report = collected(Recommended, {"Name": "n"})
    assert locations(report) == [("RepetitionTime",)]
    problem = report[0]
    assert problem.severity == "recommended"
    assert problem.fix == "Give it in seconds."
    assert problem.expected == "float"
    assert report.ok
    validate({"Name": "n"})  # a recommended field may be missing
    # A missing field without a severity still fails, both ways.
    assert not collected(Recommended, {"RepetitionTime": 1.0}).ok
    with pytest.raises(ValueValidationError):
        validate({"RepetitionTime": 1.0})
    # And a present but wrong value is still checked, at that severity.
    report = collected(
        Recommended, {"Name": "n", "RepetitionTime": "x", "Old": ""}
    )
    assert [(p.location, p.severity) for p in report] == [
        (("RepetitionTime",), "recommended"), (("Old",), "warning"),
    ]


# ----------------------------------------------------------------------
# Fix hints
# ----------------------------------------------------------------------


def test_fix_metadata() -> None:
    hint = tx.List[tx.Annotated[float, Fix("Give it in seconds.")]]
    report = collected(hint, [1.0, "2s"])
    assert report[0].fix == "Give it in seconds."
    assert type(report[0].fix) is str


class Even(Validator[int]):
    DEFAULT = int

    def __call__(self, value: int) -> None:
        super().__call__(value)
        if value % 2:
            raise self.error(value, "Odd.", type="value", fix="Add one.")


def test_fix_from_a_validator_wins_over_metadata() -> None:
    hint = tx.Annotated[int, Even(), Fix("Use an even number.")]
    assert collected(hint, 3)[0].fix == "Add one."
    assert collected(hint, "x")[0].fix == "Use an even number."
    with pytest.raises(ValueValidationError) as info:
        Even()(3)
    assert info.value.fix == "Add one."
    again = pickle.loads(pickle.dumps(info.value))
    assert again.fix == "Add one."
    assert str(again) == str(info.value)


def test_errors_without_a_fix_or_problems() -> None:
    error = ValueValidationError("message")
    assert error.fix is None
    assert error.problems == ()


# ----------------------------------------------------------------------
# Validators written by hand
# ----------------------------------------------------------------------


class Pair(Validator[tx.Any]):
    """Two lists of ints, checked by calling another validator."""

    def __call__(self, value: tx.Any) -> None:
        check = get_validator(tx.List[int])
        check(value[0])
        check(value[1])


def test_a_custom_validator_takes_part() -> None:
    report = collected(
        tx.Dict[str, tx.Annotated[tx.Any, Pair()]], {"p": ([1, "a"], [])}
    )
    # The first list's problems, at their location below the custom
    # validator; it raised there, as when failing fast.
    assert locations(report) == [("p", 1)]


def test_a_custom_validator_inside_a_container() -> None:
    report = collected(tx.List[tx.Annotated[int, Even()]], [2, 3, "x", 5])
    assert locations(report) == [(1,), (2,), (3,)]
    assert [p.message for p in report] == [
        "Odd.", "Not a valid instance.", "Odd.",
    ]


def test_a_custom_validator_that_re_raises_keeps_the_problems() -> None:
    class Wraps(Validator[tx.Any]):
        def __call__(self, value: tx.Any) -> None:
            try:
                get_validator(tx.Dict[str, int])(value)
            except ValidationError as e:
                raise self.value_error(value, "Bad mapping.") from e

    report = collected(
        tx.List[tx.Annotated[tx.Any, Wraps()]], [{"a": "x", "b": None}, {}]
    )
    assert locations(report) == [(0, "a"), (0, "b")]
    # A plain failure, re-raised: the wrapper's own message.
    report = collected(tx.Annotated[tx.Any, Wraps()], 3)
    assert [p.message for p in report] == ["Bad mapping."]


def test_a_subclass_overriding_call_takes_part() -> None:
    class NoX(IsMapping):
        def __call__(self, value: tx.Any) -> None:
            super().__call__(value)
            if "x" in value:
                raise self.value_error(value, "No x.")

    report = collected(NoX(tx.Dict[str, int]), {"y": "z", "w": None})
    assert locations(report) == [("y",), ("w",)]
    report = collected(NoX(tx.Dict[str, int]), {"x": 1})
    assert [p.message for p in report] == ["No x."]


def test_a_failure_in_a_validators_own_loop_keeps_the_items() -> None:
    from bagof.validators.reports import _Frame

    class Fussy(Validator[tx.Any]):
        def __call__(self, value: tx.Any) -> None:
            with _Frame(self, value) as frame:
                frame.check(get_validator(int), value[0], 0)
                raise self.value_error(value, "Too fussy.")

    report = collected(Fussy(), ["x"])
    assert [(p.location, p.message) for p in report] == [
        ((0,), "Not a valid instance."), ((), "Too fussy."),
    ]
    with pytest.raises(ValueValidationError, match="Too fussy."):
        Fussy()([1])


def test_a_validator_used_as_a_predicate_still_sees_a_raise() -> None:
    class ListOrText(Validator[tx.Any]):
        def __call__(self, value: tx.Any) -> None:
            try:
                Validator.get(tx.List[int])(value)
            except ValidationError:
                Validator.get(str)(value)

    assert list(collected(ListOrText(), "abc")) == []
    assert locations(collected(ListOrText(), [1, "x"])) == [()]


# ----------------------------------------------------------------------
# Rendering and structure
# ----------------------------------------------------------------------


def test_str_rendering() -> None:
    hint = tx.Dict[str, tx.Union[Small, Other]]
    value = {
        "a.json": {"a": "x"},
        "b.json": {"a": [1] * 100},
        "c.json": "x" * 200,
    }
    report = collected(
        tx.Dict[str, tx.Annotated[Small, Fix("See the spec.")]],
        {"x": {"a": "1"}},
    )
    assert str(report) == "\n".join([
        "1 problem (error: 1)",
        "['x']['a']: error: Not a valid instance.",
        "    expected int, found '1'",
        "    fix: See the spec.",
    ])
    report = collected(hint, value)
    assert str(report) == "\n".join([
        "3 problems (error: 3)",
        "['a.json']: error: Not compatible with any of the union types.",
        "    expected Small | Other, found {'a': 'x'}",
        "    ['a.json']['a']: error: Not a valid instance.",
        "        expected int, found 'x'",
        "    ['a.json']['b']: error: Missing required key 'b'",
        "        expected int",
        "['b.json']: error: Not compatible with any of the union types.",
        "    expected Small | Other, found {'a': [1, 1, 1, 1, 1, 1, ...]}",
        "    ['b.json']['a']: error: Not a valid instance.",
        "        expected int, found [1, 1, 1, 1, 1, 1, ...]",
        "    ['b.json']['b']: error: Missing required key 'b'",
        "        expected int",
        "['c.json']: error: Not compatible with any of the union types.",
        # A long string is cut down to a line, keeping both ends.
        "    expected Small | Other, found '" + "x" * 27 + "..." + "x" * 28
        + "'",
    ])
    assert repr(report) == "<Report: 3 problems (error: 3)>"


def test_summary_counts_by_severity_in_order() -> None:
    hint = tx.Tuple[tx.Annotated[int, Severity.WARNING], int, int]
    report = collected(hint, ("a", "b", "c"))
    assert report.summary() == "3 problems (warning: 1, error: 2)"
    assert str(report).splitlines()[1] == (
        "[0]: warning: Not a valid instance."
    )
    assert str(collected(int, "x")).splitlines()[1] == (
        "<root>: error: Not a valid instance."
    )


def test_problems_are_named_tuples() -> None:
    problem = collected(tx.List[int], [1, "x"])[0]
    assert problem._asdict() == {
        "location": (1,),
        "kind": "type",
        "message": "Not a valid instance.",
        "expected": "int",
        "found": "'x'",
        "severity": "error",
        "fix": None,
        "causes": (),
    }
    assert str(problem) == (
        "[1]: error: Not a valid instance.\n    expected int, found 'x'"
    )
    built = Problem(("a",), "value", "Bad.")
    assert built.severity is Severity.ERROR and built.fails
    assert Report([built]) == Report([built])
    assert Report([built]) != [built]
    assert Report([built]).problems == (built,)
    assert not Report([built]).ok
    assert Report([built._replace(severity="note")]).ok


# ----------------------------------------------------------------------
# Fail-fast mode is unchanged outside a block
# ----------------------------------------------------------------------

FAIL_FAST_CASES = [
    (int, "x", TypeValidationError, "Not a valid instance."),
    (tx.List[int], [1, "x"], ValueValidationError,
     "Iterable's 2nd element is not valid."),
    (tx.Dict[str, int], {"a": "x"}, ValueValidationError,
     "At key 'a', value 'x' is invalid."),
    (tx.Dict[str, int], {1: 1}, ValueValidationError,
     "Key 1 is not valid."),
    (tx.Tuple[int, str], (1, 2), ValueValidationError,
     "Tuple's 2nd element is not valid."),
    (Small, {}, ValueValidationError, "Missing required key 'a'"),
    (Small, {"a": "x"}, ValueValidationError,
     "Value for key 'a' is not valid."),
    (Closed, {"a": 1, "b": 2}, ValueValidationError, "Unexpected key 'b'"),
    (tx.Optional[tx.List[int]], [1, "x"], TypeValidationError,
     "Not compatible with any of the union types."),
    (tx.Annotated[int, IsPositive()], -1, ValueValidationError,
     "Not a positive value."),
    (HasLength(3, hint=tx.List[int]), [1, "x"], ValueValidationError,
     "Iterable's 2nd element is not valid."),
    (HasLength(3, hint=tx.List[int]), [1], ValueValidationError,
     "Does not match expected length 1 != 3."),
]


@pytest.mark.parametrize("hint,value,error,message", FAIL_FAST_CASES)
def test_fail_fast_is_unchanged(
    hint: tx.Any, value: tx.Any, error: type, message: str
) -> None:
    validate = hint if isinstance(hint, Validator) else get_validator(hint)
    with pytest.raises(error) as before:
        validate(value)
    assert type(before.value) is error
    assert before.value.message == message
    assert before.value.problems == ()
    with collect():
        validate(value)
    with pytest.raises(error) as after:
        validate(value)
    assert str(after.value) == str(before.value)
    assert after.value.problems == ()


# ----------------------------------------------------------------------
# bagof-magic classes
# ----------------------------------------------------------------------


def test_a_magic_class_inside_a_block() -> None:
    magic = pytest.importorskip("bagof.magic")

    class Scan(magic.Magic, validate=True):
        RepetitionTime: float
        EchoTime: tx.List[float]

    data = {"RepetitionTime": "2s", "EchoTime": [0.01, "x"]}
    # Recorded, and the instance is built.
    with collect() as report:
        scan = Scan(**data)
    assert scan.EchoTime == [0.01, "x"]
    assert not report.ok
    # Each field is validated on its own: a location starts at the field.
    assert locations(report) == [(), (1,)]
    with pytest.warns(ValidationWarning):
        with collect("warn") as report:
            Scan(**data)
    assert len(report) == 2
    # Raised: no instance. The fields after the failing one are not
    # checked.
    with pytest.raises(ValidationError):
        with collect("raise") as report:
            Scan(**data)
    assert locations(report) == [()]
