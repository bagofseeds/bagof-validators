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

A validator stops at the first failure. Its `report` method keeps going,
and returns every problem it found, with where it is:

```pycon
>>> from typing import Dict, List
>>> validate = get_validator(Dict[str, List[int]])
>>> report = validate.report({"a": [1, "x"], "b": 2})
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

`Severity` and `Fix` in `Annotated` metadata set how serious a failure is,
and how to fix it. See the `reports` module for the details.
