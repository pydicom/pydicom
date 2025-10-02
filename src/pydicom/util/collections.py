from collections import UserDict
from typing import Any
from collections.abc import Mapping, Iterable


class CaseInsensitiveDict(UserDict):
    def __init__(self, data: Mapping[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__()
        if data:
            self.update(data)
        if kwargs:
            self.update(kwargs)

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key.lower(), value)

    def __getitem__(self, key: str) -> Any:
        return super().__getitem__(key.lower())

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key.lower())

    def __contains__(self, key: object) -> bool:
        if isinstance(key, str):
            return super().__contains__(key.lower())
        return super().__contains__(key)

    def get(self, key: str, default: Any | None = None) -> Any:
        return super().get(key.lower(), default)

    def update(self, *args: Any, **kwargs: Any) -> None:
        """
        Update the dictionary with the key/value pairs from other, overwriting existing keys.
        Accepts mappings, iterables of key-value pairs, and keyword arguments.
        """
        if args:
            other = args[0]
            if isinstance(other, Mapping):
                for k, v in other.items():
                    self[k] = v
            elif isinstance(other, Iterable):
                for k, v in other:
                    self[k] = v
        for k, v in kwargs.items():
            self[k] = v
