# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Define Tag class to hold a DICOM (group, element) tag and related functions.

The 4 bytes of the DICOM tag are stored as an 'int'. Tags are
stored as a single number and separated to (group, element) as required.
"""
# NOTE: Tags must be not be stored as a tuple internally, as some code logic
#       (e.g. in filewriter.write_AT) checks if a value is a multi-value
#       element
import traceback
from typing import Tuple, Any, Union, TypeVar, Optional, ContextManager
from contextlib import contextmanager


@contextmanager
def tag_in_exception(tag: BaseTag) -> ContextManager:
    """Use `tag` within a context.

    Used to include the tag details in the traceback message when an exception
    is raised within the context.

    Parameters
    ----------
    tag : BaseTag
        The tag to use in the context.
    """
    try:
        yield
    except Exception as ex:
        stack_trace = traceback.format_exc()
        msg = f"With tag {tag} got exception: {str(ex)}\n{stack_trace}"
        raise type(ex)(msg)


T = TypeVar("T", int, str)


def Tag(arg: Union[T, Tuple[T, T]], arg2: Optional[T] = None) -> BaseTag:
    """Create a :class:`BaseTag`.

    General function for creating a :class:`BaseTag` in any of the standard
    forms:

    * ``Tag(0x00100015)``
    * ``Tag('0x00100015')``
    * ``Tag((0x10, 0x50))``
    * ``Tag(('0x10', '0x50'))``
    * ``Tag(0x0010, 0x0015)``
    * ``Tag(0x10, 0x15)``
    * ``Tag(2341, 0x10)``
    * ``Tag('0xFE', '0x0010')``
    * ``Tag("PatientName")``

    .. versionchanged:: 1.3

        Added support for creating a ``BaseTag`` using an element keyword

    Parameters
    ----------
    arg : int or str or 2-tuple
        If :class:`int` or :class:`str`, then either the group or the combined
        group/element number of the DICOM tag. If :class:`tuple` then the
        (group, element) numbers as :class:`!int` or :class:`!str`.
    arg2 : int or str, optional
        The element number of the DICOM tag, required when `arg` only contains
        the group number of the tag.

    Returns
    -------
    BaseTag
    """
    if isinstance(arg, BaseTag):
        return arg

    if arg2 is not None:
        # act as if was passed a single tuple
        arg = (arg, arg2)  # type: ignore

    if isinstance(arg, (tuple, list)):
        if len(arg) != 2:
            raise ValueError("Tag must be created using an int or 2-tuple")

        valid = False
        if isinstance(arg[0], str):
            valid = isinstance(arg[1], str)
            if valid:
                arg = (int(arg[0], 16), int(arg[1], 16))  # type: ignore
        elif isinstance(arg[0], int):
            valid = isinstance(arg[1], int)
        if not valid:
            raise ValueError(
                "Both arguments for Tag must be the same type, either "
                "string or int."
            )

        if arg[0] > 0xFFFF or arg[1] > 0xFFFF:  # type: ignore
            raise OverflowError(
                "Groups and elements of tags must each be <=2 byte integers"
            )

        long_value = (arg[0] << 16) | arg[1]  # type: ignore

    # Single str parameter
    elif isinstance(arg, str):
        try:
            long_value = int(arg, 16)
            if long_value > 0xFFFFFFFF:
                raise OverflowError(
                    f"Tags are limited to 32-bit length; tag {long_value!r}"
                )
        except ValueError:
            # Try a DICOM keyword
            from pydicom.datadict import tag_for_keyword
            long_value = tag_for_keyword(arg)
            if long_value is None:
                raise ValueError(
                    f"'{arg}' is not a valid int or DICOM keyword"
                )
    # Single int parameter
    else:
        long_value = arg
        if long_value > 0xFFFFFFFF:
            raise OverflowError(
                f"Tags are limited to 32-bit length; tag {long_value!r}"
            )

    if long_value < 0:
        raise ValueError("Tags must be positive.")

    return BaseTag(long_value)


class BaseTag(int):
    """Represents a DICOM element (group, element) tag.

    Tags are represented as an :class:`int`.

    Attributes
    ----------
    element : int
        The element number of the tag.
    group : int
        The group number of the tag.
    is_private : bool
        Returns ``True`` if the corresponding element is private, ``False``
        otherwise.
    """
    # Override comparisons so can convert "other" to Tag as necessary
    #   See Ordering Comparisons at:
    #   http://docs.python.org/dev/3.0/whatsnew/3.0.html
    def __le__(self, other: Any) -> bool:
        """Return ``True`` if `self`  is less than or equal to `other`."""
        return self == other or self < other

    def __lt__(self, other: Any) -> bool:
        """Return ``True`` if `self` is less than `other`."""
        # Check if comparing with another Tag object; if not, create a temp one
        if not isinstance(other, BaseTag):
            try:
                other = Tag(other)
            except Exception:
                raise TypeError("Cannot compare Tag with non-Tag item")

        return int(self) < int(other)

    def __ge__(self, other: Any) -> bool:
        """Return ``True`` if `self` is greater than or equal to `other`."""
        return self == other or self > other

    def __gt__(self, other: Any) -> bool:
        """Return ``True`` if `self` is greater than `other`."""
        return not (self == other or self < other)

    def __eq__(self, other: Any) -> bool:
        """Return ``True`` if `self` equals `other`."""
        # Check if comparing with another Tag object; if not, create a temp one
        if not isinstance(other, int):
            try:
                other = Tag(other)
            except Exception:
                raise TypeError("Cannot compare Tag with non-Tag item")

        return int(self) == int(other)

    def __ne__(self, other: Any) -> bool:
        """Return ``True`` if `self` does not equal `other`."""
        return not self == other

    # For python 3, any override of __cmp__ or __eq__
    # immutable requires explicit redirect of hash function
    # to the parent class
    #   See http://docs.python.org/dev/3.0/reference/
    #              datamodel.html#object.__hash__
    __hash__ = int.__hash__

    def __str__(self) -> str:
        """Return the tag value as a hex string '(gggg, eeee)'."""
        return "({0:04x}, {1:04x})".format(self.group, self.element)

    __repr__ = __str__

    @property
    def group(self) -> int:
        """Return the tag's group number as :class:`int`."""
        return self >> 16

    @property
    def element(self) -> int:
        """Return the tag's element number as :class:`int`."""
        return self & 0xffff

    elem = element  # alternate syntax

    @property
    def is_private(self) -> bool:
        """Return ``True`` if the tag is private (has an odd group number)."""
        return self.group % 2 == 1

    @property
    def is_private_creator(self) -> bool:
        """Return ``True`` if the tag is a private creator.

        .. versionadded:: 1.1
        """
        return self.is_private and 0x0010 <= self.element < 0x0100


def TupleTag(group_elem: Tuple[int, int]) -> BaseTag:
    """Fast factory for :class:`BaseTag` object with known safe (group, elem)
    :class:`tuple`
    """
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
