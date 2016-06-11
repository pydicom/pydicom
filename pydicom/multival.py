# multival.py
"""Code for multi-value data elements values, or any list of items that
must all be the same type.
"""
# Copyright (c) 2009-2012 Darcy Mason
# This file is part of pydicom, relased under an MIT-style license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom
#


class MultiValue(list):
    """Class to hold any multi-valued DICOM value, or any list of items
    that are all of the same type.

    This class enforces that any items added to the list are of the correct type,
    by calling the constructor on any items that are added. Therefore, the
    constructor must behave nicely if passed an object that is already its type.
    The constructor should raise TypeError if the item cannot be converted.

    Note, however, that DS and IS types can be a blank string '' rather
    than an instance of their classes.
    """

    def __init__(self, type_constructor, iterable):
        """Initialize the list of values

        :param type_constructor: a constructor for the required type for all list
                           items. Could be the class, or a factory function.
                           For DICOM mult-value data elements, this will be the
                           class or type corresponding to the VR.
        :param iterable: an iterable (e.g. list, tuple) of items to initialize
                        the MultiValue list
        """
        from pydicom.valuerep import DSfloat, DSdecimal, IS
        self.type_constructor = type_constructor
        if isinstance(type_constructor, (DSfloat, IS, DSdecimal)):
            converted_list = [type_constructor(x) if x != ''
                              else x for x in iterable]
        else:
            converted_list = [type_constructor(x) for x in iterable]
        super(MultiValue, self).__init__(converted_list)

    def append(self, val):
        super(MultiValue, self).append(self.type_constructor(val))

    def __deepcopy__(self, memo):
        return MultiValue(self.type_constructor, self)

    def extend(self, list_of_vals):
        super(MultiValue, self).extend((self.type_constructor(x) for x in list_of_vals))

    def insert(self, position, val):
        super(MultiValue, self).insert(position, self.type_constructor(val))

    def __setitem__(self, i, val):
        """Set an item of the list, making sure it is of the right VR type"""
        if isinstance(i, slice):
            val = [self.type_constructor(x) for x in val]
        else:
            val = self.type_constructor(val)
        super(MultiValue, self).__setitem__(i, val)

    def __str__(self):
        lines = [str(x) for x in self]
        return "['" + "', '".join(lines) + "']"
    __repr__ = __str__
