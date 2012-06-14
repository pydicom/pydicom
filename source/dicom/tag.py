# tag.py
"""Define Tag class to hold a dicom (group, element) tag"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

# Store the 4 bytes of a dicom tag as an arbitary length integer
#      (python "long" in python <3; "int" for python >=3).
# NOTE: This must be not be stored as a tuple internally, as some code logic
#       (e.g. in write_AT of filewriter) checks if a value is a multi-value element
# So, represent as a single number and separate to (group, element) when necessary.


def Tag(arg, arg2=None):
    """General function for creating a Tag in any of the standard forms:
    e.g.  Tag(0x00100010), Tag(0x10,0x10), Tag((0x10, 0x10))
    """
    if arg2 is not None:
        arg = (arg, arg2)  # act as if was passed a single tuple
    if isinstance(arg, (tuple, list)):
        if len(arg) != 2:
            raise ValueError("Tag must be an int or a 2-tuple")
        if isinstance(arg[0], (str, unicode)):  # py2to3: unicode not needed in py3
            if not isinstance(arg[1], (str, unicode)):  # py3: ditto
                raise ValueError("Both arguments must be hex strings if one is")
            arg = (int(arg[0], 16), int(arg[1], 16))
        if arg[0] > 0xFFFF or arg[1] > 0xFFFF:
            raise OverflowError("Groups and elements of tags must each be <=2 byte integers")
        long_value = (arg[0] << 16) | arg[1]
    elif isinstance(arg, (str, unicode)):  # py2to3: unicode not needed in pure py3
        raise ValueError("Tags cannot be instantiated from a single string")
    else:  # given a single number to use as a tag, as if (group, elem) already joined to a long
        long_value = arg
        if long_value > 0xFFFFFFFFL:
            raise OverflowError("Tags are limited to 32-bit length; tag {0!r}".format(arg))
    return BaseTag(long_value)

# py2to3: for some reason, the BaseTag class derived directly from long below
#     was not converted by 2to3, but conversion does work with this next line
BaseTag_base_class = long  # converted to "int" by 2to3


class BaseTag(BaseTag_base_class):
    """Class for storing the dicom (group, element) tag"""
    # Override comparisons so can convert "other" to Tag as necessary
    #   See Ordering Comparisons at http://docs.python.org/dev/3.0/whatsnew/3.0.html

    def __lt__(self, other):
        # Check if comparing with another Tag object; if not, create a temp one
        if not isinstance(other, BaseTag):
            try:
                other = Tag(other)
            except:
                raise TypeError("Cannot compare Tag with non-Tag item")
        return long(self) < long(other)

    def __eq__(self, other):
        # Check if comparing with another Tag object; if not, create a temp one
        if not isinstance(other, BaseTag):
            try:
                other = Tag(other)
            except:
                raise TypeError("Cannot compare Tag with non-Tag item")
        return long(self) == long(other)

    def __ne__(self, other):
        # Check if comparing with another Tag object; if not, create a temp one
        if not isinstance(other, BaseTag):
            try:
                other = Tag(other)
            except:
                raise TypeError("Cannot compare Tag with non-Tag item")
        return long(self) != long(other)

    # For python 3, any override of __cmp__ or __eq__ immutable requires
    #   explicit redirect of hash function to the parent class
    #   See http://docs.python.org/dev/3.0/reference/datamodel.html#object.__hash__
    __hash__ = long.__hash__

    def __str__(self):
        """String of tag value as (gggg, eeee)"""
        return "({0:04x}, {1:04x})".format(self.group, self.element)

    __repr__ = __str__

    @property
    def group(self):
        return self >> 16

    @property
    def element(self):
        """Return the element part of the (group,element) tag"""
        return self & 0xffff
    elem = element  # alternate syntax

    @property
    def is_private(self):
        """Return a boolean to indicate whether the tag is a private tag (odd group number)"""
        return self.group % 2 == 1


def TupleTag(group_elem):
    """Fast factory for BaseTag object with known safe (group, element) tuple"""
    long_value = group_elem[0] << 16 | group_elem[1]
    return BaseTag(long_value)

# Define some special tags:
# See PS 3.5-2008 section 7.5 (p.40)
ItemTag = TupleTag((0xFFFE, 0xE000))  # start of Sequence Item
ItemDelimiterTag = TupleTag((0xFFFE, 0xE00D))  # end of Sequence Item
SequenceDelimiterTag = TupleTag((0xFFFE, 0xE0DD))  # end of Sequence of undefined length
