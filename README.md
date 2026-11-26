# bagof-validators

Hint-based validators that operate at runtime.

## Example

```pycon
>>> from collections import abc
>>> from bagof.validators import get_validator
>>> validate = get_validator(abc.Sequence[int])
>>> validate([1, 2, 3])
>>> validate(1)
TypeValidationError: IsSequence(collections.abc.Sequence[int]): Not a valid instance.
|> value = 1
>>> validate(["a", "b", "c"])
ValueValidationError: IsSequence(collections.abc.Sequence[int]): Iterable's 0th element is not valid.
|> value = ['a', 'b', 'c']
```

## Every problem at once

A validator stops at the first failure. Inside a `collect` block, a
validator that checks several items checks all of them, and every problem
it finds is recorded in a report, with its location:

```pycon
>>> from typing import Dict, List
>>> from bagof.validators import collect, get_validator
>>> validate = get_validator(Dict[str, List[int]])
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
>>> [(problem.location, problem.kind) for problem in report]
[(('a', 1), 'type'), (('b',), 'type')]
```

By default, the block only records: nothing is raised and nothing is
printed, so code that validates as it builds an object (such as a
`bagof-magic` class with `validate=True`) still builds it. Each severity
can instead be given the action `"warn"`, which emits a warning per
problem, or `"raise"`, which raises once the validator has checked
everything. The error then propagates out of the block, and the report can
still be read:

```python
try:
    with collect(error="raise", warning="warn") as report:
        config = MySidecar(**data)
except ValidationError:
    print(report)
```

Outside a `collect` block, validators fail fast as before. `Severity` and
`Fix` in `Annotated` metadata set how serious a failure is, and how to fix
it. See the `reports` module for the details.
