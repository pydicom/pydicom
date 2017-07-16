"""Define Tag class to hold a DICOM (group, element) tag."""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file LICENSE included with this distribution, also
#    available at https://github.com/pydicom/pydicom

# Store the 4 bytes of a dicom tag as an arbitary length integer
#      (python "long" in python <3; "int" for python >=3).
# NOTE: This must be not be stored as a tuple internally, as some code logic
#       (e.g. in write_AT of filewriter) checks if a value is a multi-value
#       element
# So, represent as a single number and separate to (group, element) when
#       necessary.

from pydicom import compat


def Tag(arg, arg2=None):
    """Create a Tag.

    General function for creating a Tag in any of the standard forms:

    * Tag(0x00100015)
    * Tag('0x00100015')
    * Tag((0x10, 0x50))
    * Tag(('0x10', '0x50'))
    * Tag(0x0010, 0x0015)
    * Tag(0x10, 0x15)
    * Tag(2341, 0x10)
    * Tag('0xFE', '0x0010')

    Parameters
    ----------
    arg : int or str or 2-tuple/list
        If int or str, then either the group or the combined
        group/element number of the DICOM tag. If 2-tuple/list
        then the (group, element) numbers as int or str.
    arg2 : int or str, optional
        The element number of the DICOM tag, required when
        `arg` only contains the group number of the tag.

    Returns
    -------
    pydicom.tag.BaseTag
    """
    if arg2 is not None:
        arg = (arg, arg2)  # act as if was passed a single tuple

    if isinstance(arg, (tuple, list)):
        if len(arg) != 2:
            raise ValueError("Tag must be an int or a 2-tuple")

        # Check argument types aren't mixed (i.e. str and int)
        arg_types = set([type(arg[0]), type(arg[1])])
        if len(arg_types) != 1:
            raise ValueError("Both arguments for Tag must be the same type.")

        # Double str parameters
        if isinstance(arg[0], (str, compat.text_type)):
            arg = (int(arg[0], 16), int(arg[1], 16))

        if arg[0] > 0xFFFF or arg[1] > 0xFFFF:
            raise OverflowError("Groups and elements of tags must each "
                                "be <=2 byte integers")

        long_value = (arg[0] << 16) | arg[1]

    # Single str parameter
    elif isinstance(arg, (str, compat.text_type)):
        arg = int(arg, 16)
        long_value = arg
        if long_value > 0xFFFFFFFF:
            raise OverflowError("Tags are limited to 32-bit length; tag {0!r}"
                                .format(arg))

    # Single int parameter
    else:
        long_value = arg
        if long_value > 0xFFFFFFFF:
            raise OverflowError("Tags are limited to 32-bit length; tag {0!r}"
                                .format(arg))

    if long_value < 0:
        raise ValueError("Tags must be positive.")

    return BaseTag(long_value)


if compat.in_py2:
    # In python 2.6, int is shorter and 0xFFFF << 16 gets converted to long,
    #   causing Overflow error in TupleTag
    BaseTag_base_class = long
else:
    BaseTag_base_class = int


class BaseTag(BaseTag_base_class):
    """Represents a DICOM element (group, element) tag.

    Attributes
    ----------
    element : int
        The element number of the tag
    group : int
        The group number of the tag
    is_private : bool
        Returns True if the corresponding element is private,
        False otherwise.
    """
    # Override comparisons so can convert "other" to Tag as necessary
    #   See Ordering Comparisons at:
    #   http://docs.python.org/dev/3.0/whatsnew/3.0.html
    def __le__(self, other):
        """Return True if `self`  is less than or equal to `other`."""
        return (self == other or self < other)

    def __lt__(self, other):
        """Return True if `self` is less than `other`."""
        # Check if comparing with another Tag object;
        # if not, create a temp one
        if not isinstance(other, BaseTag):
            try:
                other = Tag(other)
            except Exception:
                raise TypeError("Cannot compare Tag with non-Tag item")

        return BaseTag_base_class(self) < BaseTag_base_class(other)

    def __ge__(self, other):
        """Return True if `self` is greater than or equal to `other`."""
        return (self == other or self > other)

    def __gt__(self, other):
        """Return True if `self` is greater than `other`."""
        return not (self == other or self < other)

    def __eq__(self, other):
        """Return True if `self` equals `other`."""
        # Check if comparing with another Tag object; if not, create a temp one
        if not isinstance(other, BaseTag):
            try:
                other = Tag(other)
            except Exception:
                raise TypeError("Cannot compare Tag with non-Tag item")
        return BaseTag_base_class(self) == BaseTag_base_class(other)

    def __ne__(self, other):
        """Return True if `self` does not equal `other`."""
        return not (self == other)

    # For python 3, any override of __cmp__ or __eq__
    # immutable requires explicit redirect of hash function
    # to the parent class
    #   See http://docs.python.org/dev/3.0/reference/
    #              datamodel.html#object.__hash__
    __hash__ = BaseTag_base_class.__hash__

    def __str__(self):
        """Return the tag value as a hex string '(gggg, eeee)'."""
        return "({0:04x}, {1:04x})".format(self.group, self.element)

    __repr__ = __str__

    @property
    def group(self):
        """Return the tag's group number."""
        return self >> 16

    @property
    def element(self):
        """Return the tag's element number."""
        return self & 0xffff

    elem = element  # alternate syntax

    @property
    def is_private(self):
        """Return True if the tag is private (has an odd group number)."""
        return self.group % 2 == 1


def TupleTag(group_elem):
    """Fast factory for BaseTag object with known safe
       (group, element) tuple"""
    long_value = group_elem[0] << 16 | group_elem[1]
    return BaseTag(long_value)


# Define some special tags:
# See PS 3.5-2008 section 7.5 (p.40)


# start of Sequence Item
ItemTag = TupleTag((0xFFFE, 0xE000))


# end of Sequence Item
ItemDelimiterTag = TupleTag((0xFFFE, 0xE00D))


# end of Sequence of undefined length
SequenceDelimiterTag = TupleTag((0xFFFE, 0xE0DD))
