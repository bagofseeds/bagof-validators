# bagof-validators

Hint-based validators that operate at runtime.

## Example

```pycon
>>> from collections import abc
>>> from bagof.validators import get_validator
>>> valdiate = get_validator(abc.Sequence[int])
>>> validate([1, 2, 3])
>>> validate(1)
TypeValidationError: IsSequence(collections.abc.Sequence[int]): Not a valid instance.
|> value = 1
>>> validate(["a", "b", "c"])
ValueValidationError: IsSequence(collections.abc.Sequence[int]): Iterable's 0th element is not valid.
|> value = ['a', 'b', 'c']
```
