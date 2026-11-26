"""Collecting every failure into a report (`Validator.report`, #50)."""

# stdlib
import pickle

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
    Validator,
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
    report = Validator.get(Sidecar).report(value)
    assert list(report) == []
    assert report.ok
    assert not report
    assert str(report) == "No problems."


def test_nested_failures_at_every_depth() -> None:
    value = {
        "RepetitionTime": "2s",
        "EchoTime": [0.01, "x", None],
        "Coils": {
            "head": {"Name": 3, "Channels": [1, "two", 3, "four"]},
            "neck": {"Channels": []},
            "body": "not a coil",
        },
    }
    report = Validator.get(Sidecar).report(value)
    assert locations(report) == [
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
    report = Validator.get(tx.Dict[str, tx.List[int]]).report(
        {"a": "abc", "b": [1, "x"]}
    )
    # "abc" is iterable, but not a list: one problem, its characters are
    # not checked.
    assert locations(report) == [("a",), ("b", 1)]
    assert report[0].kind == "type"
    assert report[0].expected == "list[int]"


def test_top_level_wrong_type_is_one_problem() -> None:
    report = Validator.get(Sidecar).report([1, 2])
    assert locations(report) == [()]
    assert report[0].kind == "type"


def test_tuple_items_and_wrong_length() -> None:
    assert locations(
        Validator.get(tx.Tuple[int, str, int]).report((1, 2, "x"))
    ) == [(1,), (2,)]
    report = Validator.get(tx.Tuple[int, str]).report((1, 2, 3))
    assert locations(report) == [()]
    assert report[0].kind == "value"
    assert locations(
        Validator.get(tx.Tuple[int, ...]).report((1, "a", 2.5))
    ) == [(1,), (2,)]


def test_set_elements_and_mapping_keys() -> None:
    report = Validator.get(tx.Set[int]).report({"a"})
    assert locations(report) == [(0,)]
    report = Validator.get(tx.Dict[str, int]).report({1: 1, "b": "x"})
    assert locations(report) == [(1,), ("b",)]
    assert report[0].message == "Key 1 is not valid."
    assert report[0].expected == "str"
    assert report[0].found == "1"


def test_closed_and_extra_items_typeddict() -> None:
    report = Validator.get(Closed).report({"a": "x", "b": 1, "c": 2})
    assert locations(report) == [("a",), ("b",), ("c",)]
    assert report[1].message == "Unexpected key 'b'"


def test_typevar_is_transparent() -> None:
    T = tx.TypeVar("T", bound=tx.List[int])
    assert locations(Validator.get(T).report([1, "x", "y"])) == [(1,), (2,)]


def test_iterator_elements_cannot_be_checked() -> None:
    report = Validator.get(tx.Iterable[int]).report(iter([1]))
    assert locations(report) == [()]
    assert report[0].kind == "type"


def test_location_prefix_and_merging() -> None:
    validate = Validator.get(tx.Dict[str, int])
    files = {"a.json": {"x": "1"}, "b.json": {}, "c.json": {"y": None}}
    report = Report(
        problem
        for name, data in files.items()
        for problem in validate.report(data, location=(name,))
    )
    assert locations(report) == [("a.json", "x"), ("c.json", "y")]


# ----------------------------------------------------------------------
# Unions
# ----------------------------------------------------------------------


def test_union_that_matches_adds_nothing() -> None:
    validate = Validator.get(tx.Union[int, tx.List[int]])
    assert list(validate.report(1)) == []
    assert list(validate.report([1, 2])) == []


def test_union_reports_the_one_member_with_the_right_shape() -> None:
    # `None` fails on type; the TypedDict got past its type check, so the
    # report shows what is wrong inside it, as if the union were absent.
    report = Validator.get(tx.Optional[Small]).report({"a": "x"})
    assert locations(report) == [("a",)]
    assert report[0].expected == "int"
    # Same through a list member, deeper.
    report = Validator.get(
        tx.Dict[str, tx.Union[float, tx.List[float]]]
    ).report({"k": [1.0, "x", 2.0, "y"]})
    assert locations(report) == [("k", 1), ("k", 3)]


def test_union_reports_a_failing_constraint_of_the_matching_type() -> None:
    hint = tx.Union[int, tx.Annotated[str, MatchesRegex("^a")]]
    report = Validator.get(hint).report("zz")
    assert locations(report) == [()]
    assert report[0].kind == "value"
    assert report[0].message == "Does not match pattern."


def test_union_with_no_member_of_the_right_type() -> None:
    report = Validator.get(tx.Optional[tx.List[int]]).report("x")
    assert len(report) == 1
    problem = report[0]
    assert problem.location == ()
    assert problem.kind == "type"
    assert problem.message == "Not compatible with any of the union types."
    assert problem.expected == "list[int] | None"
    assert problem.found == "'x'"
    assert problem.causes == ()


def test_ambiguous_union_keeps_every_candidate_as_causes() -> None:
    report = Validator.get(tx.Dict[str, tx.Union[Small, Other]]).report(
        {"k": {"a": "x"}}
    )
    assert locations(report) == [("k",)]
    problem = report[0]
    assert problem.expected == "Small | Other"
    assert [c.location for c in problem.causes] == [("k", "a"), ("k", "b")]
    assert [c.message for c in problem.causes] == [
        "Not a valid instance.", "Missing required key 'b'",
    ]


def test_union_member_raising_a_plain_error_is_a_problem() -> None:
    class Raises(Validator[int]):
        def __call__(self, value: int) -> None:
            raise ValueError("boom")

    hint = tx.Union[tx.Annotated[int, Raises()], str]
    report = Validator.get(hint).report(1)
    assert len(report) == 1
    assert report[0].message == "ValueError: boom"


def test_union_member_with_warnings_only_matches() -> None:
    hint = tx.Union[tx.Annotated[int, IsPositive(), Severity.WARNING], str]
    report = Validator.get(hint).report(-1)
    assert report.ok
    assert [p.severity for p in report] == ["warning"]


# ----------------------------------------------------------------------
# Annotated constraints
# ----------------------------------------------------------------------


def test_every_failing_constraint_is_reported() -> None:
    hint = tx.Annotated[
        str, MatchesRegex("^a", compose=True), HasLength(3, compose=True),
    ]
    report = Validator.get(hint).report("bb")
    assert [p.message for p in report] == [
        "Does not match pattern.",
        "Does not match expected length 2 != 3.",
    ]
    assert report[0].expected == "MatchesRegex(re.compile('^a'))"
    assert all(p.kind == "value" for p in report)


def test_a_wrong_type_skips_the_constraints() -> None:
    hint = tx.Annotated[str, MatchesRegex("^a", compose=True)]
    report = Validator.get(hint).report(1)
    assert len(report) == 1
    assert report[0].kind == "type"


def test_constraint_inside_a_container() -> None:
    hint = tx.List[tx.Annotated[float, IsInRange(0, 1)]]
    report = Validator.get(hint).report([0.5, 2, "x", -1])
    assert locations(report) == [(1,), (2,), (3,)]
    assert [p.kind for p in report] == ["value", "type", "value"]
    assert report[0].expected == "IsInRange(0, 1)"


def test_a_check_run_twice_is_reported_once() -> None:
    # The composed `HasLength` re-checks the list's elements.
    hint = tx.Annotated[tx.List[int], HasLength(3, compose=True)]
    report = Validator.get(hint).report([1, "a"])
    assert locations(report) == [(1,), ()]


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


def test_warning_is_reported_and_does_not_fail() -> None:
    validate = Validator.get(tx.Annotated[int, Severity.WARNING])
    report = validate.report("x")
    assert report.ok
    assert len(report) == 1
    assert report[0].severity == "warning"
    assert not report[0].fails
    validate("x")  # agrees with the report: does not raise


def test_default_severity_is_error() -> None:
    report = Validator.get(int).report("x")
    assert report[0].severity is Severity.ERROR
    assert not report.ok


def test_custom_failing_severity_relabels_errors() -> None:
    proscribed = Severity("proscribed", fails=True)
    hint = tx.Dict[str, tx.Annotated[tx.List[int], proscribed]]
    report = Validator.get(hint).report({"k": [1, "x"]})
    assert locations(report) == [("k", 1)]
    assert report[0].severity == "proscribed"
    assert not report.ok
    with pytest.raises(ValidationError):
        Validator.get(hint)({"k": [1, "x"]})


def test_outer_warning_relabels_inner_errors() -> None:
    hint = tx.Annotated[Small, Severity.WARNING]
    report = Validator.get(hint).report({"a": "x"})
    assert [p.severity for p in report] == ["warning"]
    assert report.ok
    Validator.get(hint)({"a": "x"})


def test_inner_warning_stays_a_warning() -> None:
    inner = tx.Annotated[int, Severity.WARNING]
    hint = tx.Annotated[tx.List[inner], Severity("proscribed", fails=True)]
    report = Validator.get(hint).report([1, "x"])
    assert [p.severity for p in report] == ["warning"]
    assert report.ok
    Validator.get(hint)([1, "x"])


def test_severity_covers_a_missing_required_field() -> None:
    validate = Validator.get(Recommended)
    report = validate.report({"Name": "n"})
    assert locations(report) == [("RepetitionTime",)]
    problem = report[0]
    assert problem.severity == "recommended"
    assert problem.fix == "Give it in seconds."
    assert problem.expected == "float"
    assert report.ok
    validate({"Name": "n"})  # a recommended field may be missing
    # A missing field without a severity still fails, both ways.
    assert not validate.report({"RepetitionTime": 1.0}).ok
    with pytest.raises(ValueValidationError):
        validate({"RepetitionTime": 1.0})
    # And a present but wrong value is still checked, at that severity.
    report = validate.report({"Name": "n", "RepetitionTime": "x", "Old": ""})
    assert [(p.location, p.severity) for p in report] == [
        (("RepetitionTime",), "recommended"), (("Old",), "warning"),
    ]


# ----------------------------------------------------------------------
# Fix hints
# ----------------------------------------------------------------------


def test_fix_metadata() -> None:
    hint = tx.List[tx.Annotated[float, Fix("Give it in seconds.")]]
    report = Validator.get(hint).report([1.0, "2s"])
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
    assert Validator.get(hint).report(3)[0].fix == "Add one."
    assert Validator.get(hint).report("x")[0].fix == "Use an even number."
    with pytest.raises(ValueValidationError) as info:
        Even()(3)
    assert info.value.fix == "Add one."
    again = pickle.loads(pickle.dumps(info.value))
    assert again.fix == "Add one."
    assert str(again) == str(info.value)


def test_errors_without_a_fix() -> None:
    error = ValueValidationError("message")
    assert error.fix is None


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
    report = Validator.get(tx.Dict[str, tx.Annotated[
        Small, Fix("See the spec."),
    ]]).report({"x": {"a": "1"}})
    assert str(report) == "\n".join([
        "1 problem (error: 1)",
        "['x']['a']: error: Not a valid instance.",
        "    expected int, found '1'",
        "    fix: See the spec.",
    ])
    report = Validator.get(hint).report(value)
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
    report = Validator.get(hint).report(("a", "b", "c"))
    assert report.summary() == "3 problems (warning: 1, error: 2)"
    assert str(report).splitlines()[1] == (
        "[0]: warning: Not a valid instance."
    )
    assert str(Validator.get(int).report("x")).splitlines()[1] == (
        "<root>: error: Not a valid instance."
    )


def test_problems_are_named_tuples() -> None:
    problem = Validator.get(tx.List[int]).report([1, "x"])[0]
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
    assert not Report([built]).ok
    assert Report([built._replace(severity="note")]).ok


# ----------------------------------------------------------------------
# Fail-fast mode is unchanged
# ----------------------------------------------------------------------

FAIL_FAST_CASES = [
    (int, "x", TypeValidationError, "Not a valid instance."),
    (tx.List[int], [1, "x"], ValueValidationError,
     "Iterable's 2nd element is not valid."),
    (tx.Dict[str, int], {"a": "x"}, ValueValidationError,
     "At key 'a', value 'x' is invalid."),
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
]


@pytest.mark.parametrize("hint,value,error,message", FAIL_FAST_CASES)
def test_fail_fast_is_unchanged(
    hint: tx.Any, value: tx.Any, error: type, message: str
) -> None:
    validate = get_validator(hint)
    with pytest.raises(error) as before:
        validate(value)
    assert type(before.value) is error
    assert before.value.message == message
    validate.report(value)
    with pytest.raises(error) as after:
        validate(value)
    assert str(after.value) == str(before.value)


def test_a_subclass_overriding_call_is_checked_as_one_unit() -> None:
    class NoX(IsMapping):
        def __call__(self, value: tx.Any) -> None:
            super().__call__(value)
            if "x" in value:
                raise self.value_error(value, "No x.")

    validate = NoX(tx.Dict[str, int])
    report = validate.report({"x": 1, "y": "z"})
    # Its own check is not skipped, and it is not broken down.
    assert locations(report) == [()]
    assert report[0].message == "At key 'y', value 'z' is invalid."
    assert validate.report({"x": 1})[0].message == "No x."


def test_a_validator_used_as_a_predicate_still_sees_a_raise() -> None:
    class ListOrText(Validator[tx.Any]):
        def __call__(self, value: tx.Any) -> None:
            try:
                Validator.get(tx.List[int])(value)
            except ValidationError:
                Validator.get(str)(value)

    validate = ListOrText()
    assert list(validate.report("abc")) == []
    assert locations(validate.report([1, "x"])) == [()]


def test_unexpected_errors_propagate() -> None:
    class Broken(Validator[tx.Any]):
        def __call__(self, value: tx.Any) -> None:
            raise RuntimeError("bug")

    with pytest.raises(RuntimeError):
        Validator.get(tx.List[tx.Annotated[int, Broken()]]).report([1])
