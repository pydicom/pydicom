# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Code for multi-value data elements values,
or any list of items that must all be the same type.
"""

try:
    from collections.abc import MutableSequence
except ImportError:
    from collections import MutableSequence

from typing import (
    Iterable, Union, List, overload, Iterator, Optional, Callable, Any,
    Sequence, cast
)


class MultiValue(MutableSequence):
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
        type_constructor: Callable[[object], object],
        iterable: Iterable[object]
    ) -> None:
        """Initialize the list of values

        Parameters
        ----------
        type_constructor : type
            A constructor for the required type for all list items. Could be
            the class, or a factory function. For DICOM multi-value data
            elements, this will be the class or type corresponding to the VR.
        iterable : iterable
            An iterable (e.g. :class:`list`, :class:`tuple`) of items to
            initialize the :class:`MultiValue` list.
        """
        from pydicom.valuerep import DSfloat, DSdecimal, IS

        def nr_str_constructor(x: object) -> object:
            return self.type_constructor(x) if x != '' else x

        self._list = list()
        self.type_constructor = type_constructor
        if type_constructor in (DSfloat, IS, DSdecimal):
            type_constructor = nr_str_constructor

        for x in iterable:
            self._list.append(type_constructor(x))

    def insert(self, position: int, val: object) -> None:
        self._list.insert(position, self.type_constructor(val))

    def append(self, val: object) -> None:
        self._list.append(self.type_constructor(val))

    @overload
    def __setitem__(self, i: int, val: object) -> None: pass

    @overload
    def __setitem__(self, i: slice, val: Sequence[object]) -> None: pass

    def __setitem__(
        self, i: Union[slice, int], val: Union[Sequence[object], object]
    ) -> None:
        """Set an item of the list, making sure it is of the right VR type"""
        if isinstance(i, slice):
            val = cast(Sequence[object], val)
            val = [self.type_constructor(v) for v in val]
            self._list.__setitem__(i, val)
        else:
            self._list.__setitem__(i, self.type_constructor(val))

    def __str__(self) -> str:
        if not self:
            return ''
        lines = [
            f"'{x}'" if isinstance(x, (str, bytes)) else str(x) for x in self
        ]
        return f"[{', '.join(lines)}]"

    __repr__ = __str__

    def __len__(self) -> int:
        return len(self._list)

    @overload
    def __getitem__(self, index: int) -> object: pass

    @overload
    def __getitem__(self, index: slice) -> Sequence[object]: pass

    def __getitem__(
        self, index: Union[slice, int]
    ) -> Union[Sequence[object], object]:
        return self._list[index]

    def __delitem__(self, index: Union[slice, int]) -> None:
        del self._list[index]

    def __iter__(self) -> Iterator[object]:
        return iter(self._list)

    def __eq__(self, other: object) -> bool:
        return self._list == other

    def __ne__(self, other: object) -> bool:
        return self._list != other

    def sort(
        self,
        key: Optional[Callable[[object], object]] = None,
        reverse: bool = False
    ) -> None:
        self._list.sort(key=key, reverse=reverse)
