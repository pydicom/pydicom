# tag.py
"""Define Tag class to hold a dicom (group, element) tag"""
#
# Copyright 2004, Darcy Mason
# This file is part of pydicom.
#
# pydicom is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# pydicom is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License (license.txt) for more details

class Tag(long):
    """Class for storing the dicom (group, element) tag"""
    # Store the 4 bytes of a dicom tag as a python long (arbitrary length, not like C-language long).
    # Using python int's may be different on different hardware platforms.
    # Simpler to deal with one number and separate to (group, element) when necessary.
    # Also can deal with python differences in handling ints starting in python 2.4,
    #   by forcing all inputs to a proper long where the differences go away
    def __new__(cls, arg, arg2=None):
        if arg2:
            arg = (arg, arg2) # act as if was passed a single tuple
        if isinstance(arg, tuple):
            if len(arg) != 2:
                raise ValueError, "Tag must be an int or a 2-tuple"
            if arg[0] > 0xFFFF or arg[1] > 0xFFFF:
                raise OverflowError, "Groups and elements of tags must each be <=2 byte integers"
            long_value = long(arg[0])<<16 | arg[1]  # long needed for python <2.4 where shift could make int negative
        elif isinstance(arg, basestring):
            raise ValueError, "Tags cannot be instantiated from a string"
        else: # given a single number to use as a tag, as if (group, elem) already joined to a long
            long_value = long(hex(arg), 16) # needed in python <2.4 to avoid negative ints
            if long_value > 0xFFFFFFFFL:
                raise OverflowError, "Tags are limited to 32-bit length; tag %r, long value %r" % (arg, long_value)
        # Now have the correct long value, set it using the python long class
        return super(Tag, cls).__new__(cls, long_value)

    def __cmp__(self, other):
        # We allow comparisons to other longs or (group,elem) tuples directly.
        # So first check if comparing with another Tag object; if not, create a temp one
        othertag=other
        if not isinstance(other, Tag):
            try:
                othertag = Tag(other)
            except:
                raise TypeError, "Cannot compare dicom Tag with non-Tag item"
        return super(Tag, self).__cmp__(othertag)

    def __str__(self):
        """String of tag value as (gggg, eeee)"""
        return "(%04x, %04x)" % (self.group, self.elem)

    __repr__ = __str__
    
    # Property group
    def getGroup(self):
        return self >>16
    group = property(getGroup)

    # Property elem
    def getElem(self):
        return self & 0xffff
    elem  = property(getElem)
    element = elem
   
    # Property isPrivate
    def getIsPrivate(self):
        """Private tags have an odd group number"""
        return self.group % 2 == 1
    isPrivate = property(getIsPrivate)

# Define some special tags:
# See PS 3.5-2008 section 7.5 (p.40)
ItemTag = Tag(0xFFFE, 0xE000) # start of Sequence Item
ItemDelimiterTag = Tag((0xFFFE, 0xE00D)) # end of Sequence Item
SequenceDelimiterTag = Tag(0xFFFE,0xE0DD) # end of Sequence of undefined length
