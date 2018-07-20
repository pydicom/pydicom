# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Define Tag class to hold a DICOM (group, element) tag and related functions.

The 4 bytes of the DICOM tag are stored as an arbitrary length 'long' for
Python 2 and as an 'int' for Python 3. Tags are stored as a single number and
separated to (group, element) as required.
"""
# NOTE: Tags must be not be stored as a tuple internally, as some code logic
#       (e.g. in filewriter.write_AT) checks if a value is a multi-value
#       element
import traceback
from contextlib import contextmanager

from pydicom import compat


@contextmanager
def tag_in_exception(tag):
    """Use `tag` within a context.

    Used to include the tag details in the traceback message when an exception
    is raised within the context.

    Parameters
    ----------
    tag : pydicom.tag.Tag
        The tag to use in the context.
    """
    try:
        yield
    except Exception as ex:
        stack_trace = traceback.format_exc()
        msg = 'With tag {0} got exception: {1}\n{2}'.format(
            tag,
            str(ex),
            stack_trace)
        raise type(ex)(msg)


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
    if isinstance(arg, BaseTag):
        return arg

    if arg2 is not None:
        arg = (arg, arg2)  # act as if was passed a single tuple

    if isinstance(arg, (tuple, list)):
        if len(arg) != 2:
            raise ValueError("Tag must be an int or a 2-tuple")

        valid = False
        if isinstance(arg[0], compat.string_types):
            valid = isinstance(arg[1], (str, compat.string_types))
            if valid:
                arg = (int(arg[0], 16), int(arg[1], 16))
        elif isinstance(arg[0], compat.number_types):
            valid = isinstance(arg[1], compat.number_types)
        if not valid:
            raise ValueError("Both arguments for Tag must be the same type, "
                             "either string or int.")

        if arg[0] > 0xFFFF or arg[1] > 0xFFFF:
            raise OverflowError("Groups and elements of tags must each "
                                "be <=2 byte integers")

        long_value = (arg[0] << 16) | arg[1]

    # Single str parameter
    elif isinstance(arg, (str, compat.text_type)):
        long_value = int(arg, 16)
        if long_value > 0xFFFFFFFF:
            raise OverflowError("Tags are limited to 32-bit length; tag {0!r}"
                                .format(long_value))

    # Single int parameter
    else:
        long_value = arg
        if long_value > 0xFFFFFFFF:
            raise OverflowError("Tags are limited to 32-bit length; tag {0!r}"
                                .format(long_value))

    if long_value < 0:
        raise ValueError("Tags must be positive.")

    return BaseTag(long_value)


if compat.in_py2:
    # May get an overflow error with int if sys.maxsize < 0xFFFFFFFF
    BaseTag_base_class = long
else:
    BaseTag_base_class = int


class BaseTag(BaseTag_base_class):
    """Represents a DICOM element (group, element) tag.

    If using python 2.7 then tags are represented as a long, while for python
    3 they are represented as an int.

    Attributes
    ----------
    element : int
        The element number of the tag.
    group : int
        The group number of the tag.
    is_private : bool
        Returns True if the corresponding element is private, False otherwise.
    """
    # Override comparisons so can convert "other" to Tag as necessary
    #   See Ordering Comparisons at:
    #   http://docs.python.org/dev/3.0/whatsnew/3.0.html
    def __le__(self, other):
        """Return True if `self`  is less than or equal to `other`."""
        return self == other or self < other

    def __lt__(self, other):
        """Return True if `self` is less than `other`."""
        # Check if comparing with another Tag object; if not, create a temp one
        if not isinstance(other, BaseTag):
            try:
                other = Tag(other)
            except Exception:
                raise TypeError("Cannot compare Tag with non-Tag item")

        return BaseTag_base_class(self) < BaseTag_base_class(other)

    def __ge__(self, other):
        """Return True if `self` is greater than or equal to `other`."""
        return self == other or self > other

    def __gt__(self, other):
        """Return True if `self` is greater than `other`."""
        return not (self == other or self < other)

    def __eq__(self, other):
        """Return True if `self` equals `other`."""
        # Check if comparing with another Tag object; if not, create a temp one
        if not isinstance(other, BaseTag_base_class):
            try:
                other = Tag(other)
            except Exception:
                raise TypeError("Cannot compare Tag with non-Tag item")

        return BaseTag_base_class(self) == BaseTag_base_class(other)

    def __ne__(self, other):
        """Return True if `self` does not equal `other`."""
        return not self == other

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

    @property
    def is_private_creator(self):
        """Return True if the tag is a private creator."""
        return self.is_private and 0x0010 <= self.element < 0x0100


def TupleTag(group_elem):
    """Fast factory for BaseTag object with known safe (group, elem) tuple"""
    long_value = group_elem[0] << 16 | group_elem[1]
    return BaseTag(long_value)


# Define some special tags:
# See DICOM Standard Part 5, Section 7.5

# start of Sequence Item
ItemTag = TupleTag((0xFFFE, 0xE000))

# end of Sequence Item
ItemDelimiterTag = TupleTag((0xFFFE, 0xE00D))

# end of Sequence of undefined length
SequenceDelimiterTag = TupleTag((0xFFFE, 0xE0DD))
