# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Code for multi-value data elements values,
or any list of items that must all be the same type.
"""

try:
    from collections.abc import MutableSequence
except ImportError:
    from collections import MutableSequence


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

    def __init__(self, type_constructor, iterable):
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

        def number_string_type_constructor(x):
            return self.type_constructor(x) if x != '' else x

        self._list = list()
        self.type_constructor = type_constructor
        if type_constructor in (DSfloat, IS, DSdecimal):
            type_constructor = number_string_type_constructor
        for x in iterable:
            self._list.append(type_constructor(x))

    def insert(self, position, val):
        self._list.insert(position, self.type_constructor(val))

    def append(self, val):
        self._list.append(self.type_constructor(val))

    def __setitem__(self, i, val):
        """Set an item of the list, making sure it is of the right VR type"""
        if isinstance(i, slice):
            val = [self.type_constructor(v) for v in val]
            self._list.__setitem__(i, val)
        else:
            self._list.__setitem__(i, self.type_constructor(val))

    def __str__(self):
        if not self:
            return ''
        lines = ["'{}'".format(x) if isinstance(x, (str, bytes))
                 else str(x) for x in self]
        return "[" + ", ".join(lines) + "]"

    __repr__ = __str__

    def __len__(self):
        return len(self._list)

    def __getitem__(self, index):
        return self._list[index]

    def __delitem__(self, index):
        del self._list[index]

    def __iter__(self):
        return iter(self._list)

    def __eq__(self, other):
        return self._list == other

    def __ne__(self, other):
        return self._list != other

    def sort(self, key=None, reverse=False):
        self._list.sort(key=key, reverse=reverse)
