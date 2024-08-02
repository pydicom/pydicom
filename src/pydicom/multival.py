# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Code for multi-value data elements values,
or any list of items that must all be the same type.
"""

from typing import overload, Any, cast, TypeVar
from collections.abc import Iterable, Callable, MutableSequence, Iterator


T = TypeVar("T")
Self = TypeVar("Self", bound="ConstrainedList")


class ConstrainedList(MutableSequence[T]):
    """A list of items that must all be of the same type."""

    def __init__(self, iterable: Iterable[T] | None = None) -> None:
        """Create a new ConstrainedList.

        Parameters
        ----------
        iterable : Iterable[T]
            An iterable such as a :class:`list` or :class:`tuple` containing
            the items to be used to create the ``ConstrainedList``.
        """
        self._list: list[T] = []
        if iterable is not None:
            self._list = [self._validate(item) for item in iterable]

    def append(self, item: T) -> None:
        """Append an item."""
        self._list.append(self._validate(item))

    def __delitem__(self, index: slice | int) -> None:
        """Remove the item(s) at `index`."""
        del self._list[index]

    def extend(self, val: Iterable[T]) -> None:
        """Extend using an iterable containing the same types of item."""
        if not hasattr(val, "__iter__"):
            raise TypeError("An iterable is required")

        self._list.extend([self._validate(item) for item in val])

    def __eq__(self, other: Any) -> Any:
        """Return ``True`` if `other` is equal to self."""
        return self._list == other

    @overload
    def __getitem__(self, index: int) -> T:
        pass  # pragma: no cover

    @overload
    def __getitem__(self, index: slice) -> MutableSequence[T]:
        pass  # pragma: no cover

    def __getitem__(self, index: slice | int) -> MutableSequence[T] | T:
        """Return item(s) from self."""
        return self._list[index]

    def __iadd__(self: Self, other: Iterable[T]) -> Self:
        """Implement += [T, ...]."""
        if not hasattr(other, "__iter__"):
            raise TypeError("An iterable is required")

        self._list += [self._validate(item) for item in other]
        return self

    def insert(self, position: int, item: T) -> None:
        """Insert an `item` at `position`."""
        self._list.insert(position, self._validate(item))

    def __iter__(self) -> Iterator[T]:
        """Yield items."""
        yield from self._list

    def __len__(self) -> int:
        """Return the number of contained items."""
        return len(self._list)

    def __ne__(self, other: Any) -> Any:
        """Return ``True`` if `other` is not equal to self."""
        return self._list != other

    @overload
    def __setitem__(self, idx: int, val: T) -> None:
        pass  # pragma: no cover

    @overload
    def __setitem__(self, idx: slice, val: Iterable[T]) -> None:
        pass  # pragma: no cover

    def __setitem__(self, index: slice | int, val: Iterable[T] | T) -> None:
        """Add item(s) at `index`."""
        if isinstance(index, slice):
            val = cast(Iterable[T], val)
            self._list.__setitem__(index, [self._validate(item) for item in val])
        else:
            val = cast(T, val)
            self._list.__setitem__(index, self._validate(val))

    def _validate(self, item: Any) -> T:
        """Return items that have been validated as being of the expected type"""
        raise NotImplementedError(
            f"'{type(self).__name__}._validate()' must be implemented"
        )


class MultiValue(ConstrainedList[T]):
    """Class to hold any multi-valued DICOM value, or any list of items that
    are all of the same type.

    This class enforces that any items added to the list are of the correct
    type, by calling the constructor on any items that are added. Therefore,
    the constructor must behave nicely if passed an object that is already its
    type. The constructor should raise :class:`TypeError` if the item cannot be
    converted.

    Note, however, that DS and IS types can be a blank string ``''`` rather
    than an instance of their classes.
    """

    def __init__(
        self,
        type_constructor: Callable[[Any], T],
        iterable: Iterable[Any],
    ) -> None:
        """Create a new :class:`MultiValue` from an iterable and ensure each
        item in the :class:`MultiValue` has the same type.

        Parameters
        ----------
        type_constructor : callable
            A constructor for the required type for all items. Could be
            the class, or a factory function. Takes a single parameter and
            returns the input as the desired type (or raises an appropriate
            exception).
        iterable : iterable
            An iterable (e.g. :class:`list`, :class:`tuple`) of items to
            initialize the :class:`MultiValue` list. Each item in the iterable
            is passed to `type_constructor` and the returned value added to
            the :class:`MultiValue`.
        """
        self._constructor = type_constructor

        super().__init__(iterable)

    def _validate(self, item: Any | T) -> T:
        return self._constructor(item)

    def sort(self, *args: Any, **kwargs: Any) -> None:
        self._list.sort(*args, **kwargs)

    def __str__(self) -> str:
        if not self:
            return ""
        lines = (f"{x!r}" if isinstance(x, str | bytes) else str(x) for x in self)
        return f"[{', '.join(lines)}]"

    __repr__ = __str__
