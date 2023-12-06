# Copyright 2008-2021 pydicom authors. See LICENSE file for details.
"""Define the Dataset and FileDataset classes.

The Dataset class represents the DICOM Dataset while the FileDataset class
adds extra functionality to Dataset when data is read from or written to file.

Overview of DICOM object model
------------------------------
Dataset (dict subclass)
  Contains DataElement instances, each of which has a tag, VR, VM and value.
    The DataElement value can be:
        * A single value, such as a number, string, etc. (i.e. VM = 1)
        * A list of numbers, strings, etc. (i.e. VM > 1)
        * A Sequence (list subclass), where each item is a Dataset which
            contains its own DataElements, and so on in a recursive manner.
"""
import copy
import io
import json
import os
import os.path
import re
import warnings
from bisect import bisect_left
from collections.abc import (
    ValuesView,
    Iterator,
    Callable,
    MutableSequence,
    MutableMapping,
    Set,
)
from contextlib import nullcontext
from importlib.util import find_spec as have_package
from itertools import takewhile
from types import TracebackType
from typing import (
    Optional,
    TypeAlias,
    Any,
    AnyStr,
    cast,
    BinaryIO,
    TypeVar,
    overload,
)

from pydicom.filebase import DicomFileLike

try:
    import numpy
except ImportError:
    pass

import pydicom  # for dcmwrite
from pydicom import jsonrep, config
from pydicom._version import __version_info__
from pydicom.charset import default_encoding, convert_encodings
from pydicom.config import logger
from pydicom.datadict import (
    dictionary_description,
    dictionary_VR,
    tag_for_keyword,
    keyword_for_tag,
    repeater_has_keyword,
    get_private_entry,
)
from pydicom.dataelem import DataElement, DataElement_from_raw, RawDataElement
from pydicom.encaps import encapsulate, encapsulate_extended
from pydicom.fileutil import path_from_pathlike, PathType
from pydicom.pixel_data_handlers.util import (
    convert_color_space,
    reshape_pixel_array,
    get_image_pixel_ids,
    get_nr_frames,
)
from pydicom.tag import Tag, BaseTag, tag_in_exception, TagType, TAG_PIXREP
from pydicom.uid import (
    ExplicitVRLittleEndian,
    RLELossless,
    PYDICOM_IMPLEMENTATION_UID,
    UID,
)
from pydicom.valuerep import VR as VR_, AMBIGUOUS_VR
from pydicom.waveforms import numpy_handler as wave_handler


class PrivateBlock:
    """Helper class for a private block in the :class:`Dataset`.

    .. versionadded:: 1.3

    See the DICOM Standard, Part 5,
    :dcm:`Section 7.8.1<part05/sect_7.8.html#sect_7.8.1>` - Private Data
    Element Tags

    Attributes
    ----------
    group : int
        The private group where the private block is located as a 32-bit
        :class:`int`.
    private_creator : str
        The private creator string related to the block.
    dataset : Dataset
        The parent dataset.
    block_start : int
        The start element of the private block as a 32-bit :class:`int`. Note
        that the 2 low order hex digits of the element are always 0.
    """

    def __init__(
        self, key: tuple[int, str], dataset: "Dataset", private_creator_element: int
    ) -> None:
        """Initializes an object corresponding to a private tag block.

        Parameters
        ----------
        key : tuple
            The private (tag group, creator) as ``(int, str)``. The group
            must be an odd number.
        dataset : Dataset
            The parent :class:`Dataset`.
        private_creator_element : int
            The element of the private creator tag as a 32-bit :class:`int`.
        """
        self.group = key[0]
        self.private_creator = key[1]
        self.dataset = dataset
        self.block_start = private_creator_element << 8

    def get_tag(self, element_offset: int) -> BaseTag:
        """Return the private tag ID for the given `element_offset`.

        Parameters
        ----------
        element_offset : int
            The lower 16 bits (e.g. 2 hex numbers) of the element tag.

        Returns
        -------
            The tag ID defined by the private block location and the
            given element offset.

        Raises
        ------
        ValueError
            If `element_offset` is too large.
        """
        if element_offset > 0xFF:
            raise ValueError("Element offset must be less than 256")
        return Tag(self.group, self.block_start + element_offset)

    def __contains__(self, element_offset: int) -> bool:
        """Return ``True`` if the tag with given `element_offset` is in
        the parent :class:`Dataset`.
        """
        return self.get_tag(element_offset) in self.dataset

    def __getitem__(self, element_offset: int) -> DataElement:
        """Return the data element in the parent dataset for the given element
        offset.

        Parameters
        ----------
        element_offset : int
            The lower 16 bits (e.g. 2 hex numbers) of the element tag.

        Returns
        -------
            The data element of the tag in the parent dataset defined by the
            private block location and the given element offset.

        Raises
        ------
        ValueError
            If `element_offset` is too large.
        KeyError
            If no data element exists at that offset.
        """
        return self.dataset.__getitem__(self.get_tag(element_offset))

    def __delitem__(self, element_offset: int) -> None:
        """Delete the tag with the given `element_offset` from the dataset.

        Parameters
        ----------
        element_offset : int
            The lower 16 bits (e.g. 2 hex numbers) of the element tag
            to be deleted.

        Raises
        ------
        ValueError
            If `element_offset` is too large.
        KeyError
            If no data element exists at that offset.
        """
        del self.dataset[self.get_tag(element_offset)]

    def add_new(self, element_offset: int, VR: str, value: object) -> None:
        """Add a private element to the parent :class:`Dataset`.

        Adds the private tag with the given `VR` and `value` to the parent
        :class:`Dataset` at the tag ID defined by the private block and the
        given `element_offset`.

        Parameters
        ----------
        element_offset : int
            The lower 16 bits (e.g. 2 hex numbers) of the element tag
            to be added.
        VR : str
            The 2 character DICOM value representation.
        value
            The value of the data element. See :meth:`Dataset.add_new()`
            for a description.
        """
        tag = self.get_tag(element_offset)
        self.dataset.add_new(tag, VR, value)
        self.dataset[tag].private_creator = self.private_creator


def _dict_equal(a: "Dataset", b: Any, exclude: list[str] | None = None) -> bool:
    """Common method for Dataset.__eq__ and FileDataset.__eq__

    Uses .keys() as needed because Dataset iter return items not keys
    `exclude` is used in FileDataset__eq__ ds.__dict__ compare, which
    would also compare the wrapped _dict member (entire dataset) again.
    """
    return (
        len(a) == len(b)
        and all(key in b for key in a.keys())
        and all(
            a[key] == b[key]
            for key in a.keys()
            if exclude is None or key not in exclude
        )
    )


_DatasetValue = DataElement | RawDataElement
_DatasetType: TypeAlias = "Dataset | MutableMapping[BaseTag, _DatasetValue]"


class Dataset:
    """A DICOM dataset as a mutable mapping of DICOM Data Elements.

    Examples
    --------
    Add an element to the :class:`Dataset` (for elements in the DICOM
    dictionary):

    >>> ds = Dataset()
    >>> ds.PatientName = "CITIZEN^Joan"
    >>> ds.add_new(0x00100020, 'LO', '12345')
    >>> ds[0x0010, 0x0030] = DataElement(0x00100030, 'DA', '20010101')

    Add a sequence element to the :class:`Dataset`

    >>> ds.BeamSequence = [Dataset(), Dataset(), Dataset()]
    >>> ds.BeamSequence[0].Manufacturer = "Linac, co."
    >>> ds.BeamSequence[1].Manufacturer = "Linac and Sons, co."
    >>> ds.BeamSequence[2].Manufacturer = "Linac and Daughters, co."

    Add private elements to the :class:`Dataset`

    >>> block = ds.private_block(0x0041, 'My Creator', create=True)
    >>> block.add_new(0x01, 'LO', '12345')

    Updating and retrieving element values:

    >>> ds.PatientName = "CITIZEN^Joan"
    >>> ds.PatientName
    'CITIZEN^Joan'
    >>> ds.PatientName = "CITIZEN^John"
    >>> ds.PatientName
    'CITIZEN^John'

    Retrieving an element's value from a Sequence:

    >>> ds.BeamSequence[0].Manufacturer
    'Linac, co.'
    >>> ds.BeamSequence[1].Manufacturer
    'Linac and Sons, co.'

    Accessing the :class:`~pydicom.dataelem.DataElement` items:

    >>> elem = ds['PatientName']
    >>> elem
    (0010,0010) Patient's Name                      PN: 'CITIZEN^John'
    >>> elem = ds[0x00100010]
    >>> elem
    (0010,0010) Patient's Name                      PN: 'CITIZEN^John'
    >>> elem = ds.data_element('PatientName')
    >>> elem
    (0010,0010) Patient's Name                      PN: 'CITIZEN^John'

    Accessing a private :class:`~pydicom.dataelem.DataElement`
    item:

    >>> block = ds.private_block(0x0041, 'My Creator')
    >>> elem = block[0x01]
    >>> elem
    (0041,1001) Private tag data                    LO: '12345'
    >>> elem.value
    '12345'

    Alternatively:

    >>> ds.get_private_item(0x0041, 0x01, 'My Creator').value
    '12345'

    Deleting an element from the :class:`Dataset`

    >>> del ds.PatientID
    >>> del ds.BeamSequence[1].Manufacturer
    >>> del ds.BeamSequence[2]

    Deleting a private element from the :class:`Dataset`

    >>> block = ds.private_block(0x0041, 'My Creator')
    >>> if 0x01 in block:
    ...     del block[0x01]

    Determining if an element is present in the :class:`Dataset`

    >>> 'PatientName' in ds
    True
    >>> 'PatientID' in ds
    False
    >>> (0x0010, 0x0030) in ds
    True
    >>> 'Manufacturer' in ds.BeamSequence[0]
    True

    Iterating through the top level of a :class:`Dataset` only (excluding
    Sequences):

    >>> for elem in ds:
    ...    print(elem)
    (0010,0010) Patient's Name                      PN: 'CITIZEN^John'

    Iterating through the entire :class:`Dataset` (including Sequences):

    >>> for elem in ds.iterall():
    ...     print(elem)
    (0010,0010) Patient's Name                      PN: 'CITIZEN^John'

    Recursively iterate through a :class:`Dataset` (including Sequences):

    >>> def recurse(ds):
    ...     for elem in ds:
    ...         if elem.VR == 'SQ':
    ...             [recurse(item) for item in elem.value]
    ...         else:
    ...             # Do something useful with each DataElement

    Converting the :class:`Dataset` to and from JSON:

    >>> ds = Dataset()
    >>> ds.PatientName = "Some^Name"
    >>> jsonmodel = ds.to_json()
    >>> ds2 = Dataset()
    >>> ds2.from_json(jsonmodel)
    (0010,0010) Patient's Name                      PN: 'Some^Name'

    Attributes
    ----------
    default_element_format : str
        The default formatting for string display.
    default_sequence_element_format : str
        The default formatting for string display of sequences.
    indent_chars : str
        For string display, the characters used to indent nested Sequences.
        Default is ``"   "``.
    """

    indent_chars = "   "

    def __init__(self, *args: _DatasetType, **kwargs: Any) -> None:
        """Create a new :class:`Dataset` instance."""
        self._parent_encoding: str | list[str] = kwargs.get(
            "parent_encoding", default_encoding
        )

        self._dict: MutableMapping[BaseTag, _DatasetValue]
        if not args:
            self._dict = {}
        elif isinstance(args[0], Dataset):
            self._dict = args[0]._dict
        else:
            self._dict = args[0]

        self.is_decompressed = False

        # the following read_XXX attributes are used internally to store
        # the properties of the dataset after read from a file
        # set depending on the endianness of the read dataset
        self._read_little: bool | None = None
        # set depending on the VR handling of the read dataset
        self._read_implicit: bool | None = None
        # The dataset's original character set encoding
        self._read_charset: str | MutableSequence[str] = ""

        # TODO: v4.0
        #   Remove is_little_endian and is_implicit_VR
        if not config._use_future:
            self._is_little_endian: bool | None = None
            self._is_implicit_VR: bool | None = None

        # True if the dataset is a sequence item with undefined length
        self.is_undefined_length_sequence_item = False

        # known private creator blocks
        self._private_blocks: dict[tuple[int, str], PrivateBlock] = {}

        self._pixel_array: numpy.ndarray | None = None
        self._pixel_id: dict[str, int] = {}

        self.file_meta: FileMetaDataset

        # Used after reading an implicit dataset to help determine the VR of
        #   ambiguous US or SS elements that depend on the value of (0028,0103)
        #   *Pixel Representation*
        # It gets set by __getitem__() and __setitem()__ and is used by the
        #   ambiguous VR correction function
        self._pixel_rep: int

    def __enter__(self) -> "Dataset":
        """Method invoked on entry to a with statement."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """Method invoked on exit from a with statement."""
        # Returning anything other than True will re-raise any exceptions
        return None

    def add(self, data_element: DataElement) -> None:
        """Add an element to the :class:`Dataset`.

        Equivalent to ``ds[data_element.tag] = data_element``

        Parameters
        ----------
        data_element : dataelem.DataElement
            The :class:`~pydicom.dataelem.DataElement` to add.
        """
        self[data_element.tag] = data_element

    def add_new(self, tag: TagType, VR: str, value: Any) -> None:
        """Create a new element and add it to the :class:`Dataset`.

        Parameters
        ----------
        tag
            The DICOM (group, element) tag in any form accepted by
            :func:`~pydicom.tag.Tag` such as ``[0x0010, 0x0010]``,
            ``(0x10, 0x10)``, ``0x00100010``, etc.
        VR : str
            The 2 character DICOM value representation (see DICOM Standard,
            Part 5, :dcm:`Section 6.2<part05/sect_6.2.html>`).
        value
            The value of the data element. One of the following:

            * a single string or number
            * a :class:`list` or :class:`tuple` with all strings or all numbers
            * a multi-value string with backslash separator
            * for a sequence element, an empty :class:`list` or ``list`` of
              :class:`Dataset`
        """
        self.add(DataElement(tag, VR, value))

    def add_new_private(
        self,
        private_creator: str,
        group: int,
        element_offset: int,
        value: Any,
        vr: str | None = None,
    ) -> None:
        """Create a new private element and add it to the :class:`Dataset`.

        Parameters
        ----------
        private_creator : str
            The private creator string related to the new tag.
        group : int
            The group ID (0x0009 - 0xFFFF) for the private tag.
            Must be an odd number.
        element_offset : int
            The tag offset, e.g. the lower byte of the tag element of the
            private tag (0x00 - 0xFF). The higher byte is defined by the location
            of the private creator tag.
        value : Any
            The value of the data element. One of the following:

            * a single string or number
            * a :class:`list` or :class:`tuple` with all strings or all numbers
            * a multi-value string with backslash separator
            * for a sequence element, an empty :class:`list` or ``list`` of
              :class:`Dataset`
        vr : str | None
            The two-letter DICOM value representation, or ``None``.
            If set to ``None``, it is taken from the private tag dictionary.

        Raises
        ------
        ValueError
            If `group` doesn't belong to a private tag or `private_creator` is empty.
        KeyError
            If `vr` is ``None`` and the tag is not found in the private tag dictionary.
        """
        block = self.private_block(group, private_creator, create=True)
        if vr is None:
            vr = get_private_entry((group, element_offset), private_creator)[0]
        block.add_new(element_offset, vr, value)

    def __array__(self) -> "numpy.ndarray":
        """Support accessing the dataset from a numpy array."""
        return numpy.asarray(self._dict)

    def data_element(self, name: str) -> DataElement | None:
        """Return the element corresponding to the element keyword `name`.

        Parameters
        ----------
        name : str
            A DICOM element keyword.

        Returns
        -------
        dataelem.DataElement or None
            For the given DICOM element `keyword`, return the corresponding
            :class:`~pydicom.dataelem.DataElement` if present, ``None``
            otherwise.
        """
        tag = tag_for_keyword(name)
        # Test against None as (0000,0000) is a possible tag
        if tag is not None:
            return self[tag]
        return None

    def __contains__(self, name: TagType) -> bool:
        """Simulate dict.__contains__() to handle DICOM keywords.

        Examples
        --------

        >>> ds = Dataset()
        >>> ds.SliceLocation = '2'
        >>> 'SliceLocation' in ds
        True

        Parameters
        ----------
        name : str or int or 2-tuple
            The element keyword or tag to search for.

        Returns
        -------
        bool
            ``True`` if the corresponding element is in the :class:`Dataset`,
            ``False`` otherwise.
        """
        try:
            return Tag(name) in self._dict
        except Exception as exc:
            msg = (
                f"Invalid value '{name}' used with the 'in' operator: must be "
                "an element tag as a 2-tuple or int, or an element keyword"
            )
            if isinstance(exc, OverflowError):
                msg = (
                    "Invalid element tag value used with the 'in' operator: "
                    "tags have a maximum value of (0xFFFF, 0xFFFF)"
                )

            if config.INVALID_KEY_BEHAVIOR == "WARN":
                warnings.warn(msg)
            elif config.INVALID_KEY_BEHAVIOR == "RAISE":
                raise ValueError(msg) from exc

        return False

    def decode(self) -> None:
        """Apply character set decoding to the elements in the
        :class:`Dataset`.

        See DICOM Standard, Part 5,
        :dcm:`Section 6.1.1<part05/chapter_6.html#sect_6.1.1>`.
        """
        # Find specific character set. 'ISO_IR 6' is default
        # May be multi-valued, but let pydicom.charset handle all logic on that
        dicom_character_set = self._character_set

        # Shortcut to the decode function in pydicom.charset
        decode_data_element = pydicom.charset.decode_element

        # Callback for walk(), to decode the chr strings if necessary
        # This simply calls the pydicom.charset.decode_element function
        def decode_callback(ds: "Dataset", data_element: DataElement) -> None:
            """Callback to decode `data_element`."""
            if data_element.VR == VR_.SQ:
                for dset in data_element.value:
                    dset._parent_encoding = dicom_character_set
                    dset.decode()
            else:
                decode_data_element(data_element, dicom_character_set)

        self.walk(decode_callback, recursive=False)

    def copy(self) -> "Dataset":
        """Return a shallow copy of the dataset."""
        return copy.copy(self)

    def __delattr__(self, name: str) -> None:
        """Intercept requests to delete an attribute by `name`.

        Examples
        --------

        >>> ds = Dataset()
        >>> ds.PatientName = 'foo'
        >>> ds.some_attribute = True

        If `name` is a DICOM keyword - delete the corresponding
        :class:`~pydicom.dataelem.DataElement`

        >>> del ds.PatientName
        >>> 'PatientName' in ds
        False

        If `name` is another attribute - delete it

        >>> del ds.some_attribute
        >>> hasattr(ds, 'some_attribute')
        False

        Parameters
        ----------
        name : str
            The keyword for the DICOM element or the class attribute to delete.
        """
        # First check if a valid DICOM keyword and if we have that data element
        tag = cast(BaseTag, tag_for_keyword(name))
        if tag is not None and tag in self._dict:
            del self._dict[tag]
        # If not a DICOM name in this dataset, check for regular instance name
        #   can't do delete directly, that will call __delattr__ again
        elif name in self.__dict__:
            del self.__dict__[name]
        # Not found, raise an error in same style as python does
        else:
            raise AttributeError(name)

    def __delitem__(self, key: "slice | BaseTag | TagType") -> None:
        """Intercept requests to delete an attribute by key.

        Examples
        --------
        Indexing using :class:`~pydicom.dataelem.DataElement` tag

        >>> ds = Dataset()
        >>> ds.CommandGroupLength = 100
        >>> ds.PatientName = 'CITIZEN^Jan'
        >>> del ds[0x00000000]
        >>> ds
        (0010,0010) Patient's Name                      PN: 'CITIZEN^Jan'

        Slicing using :class:`~pydicom.dataelem.DataElement` tag

        >>> ds = Dataset()
        >>> ds.CommandGroupLength = 100
        >>> ds.SOPInstanceUID = '1.2.3'
        >>> ds.PatientName = 'CITIZEN^Jan'
        >>> del ds[:0x00100000]
        >>> ds
        (0010,0010) Patient's Name                      PN: 'CITIZEN^Jan'

        Parameters
        ----------
        key
            The key for the attribute to be deleted. If a ``slice`` is used
            then the tags matching the slice conditions will be deleted.
        """
        # If passed a slice, delete the corresponding DataElements
        if isinstance(key, slice):
            for tag in self._slice_dataset(key.start, key.stop, key.step):
                del self._dict[tag]
                # invalidate private blocks in case a private creator is
                # deleted - will be re-created on next access
                if self._private_blocks and BaseTag(tag).is_private_creator:
                    self._private_blocks = {}
        elif isinstance(key, BaseTag):
            del self._dict[key]
            if self._private_blocks and key.is_private_creator:
                self._private_blocks = {}
        else:
            # If not a standard tag, than convert to Tag and try again
            tag = Tag(key)
            del self._dict[tag]
            if self._private_blocks and tag.is_private_creator:
                self._private_blocks = {}

    def __dir__(self) -> list[str]:
        """Return a list of methods, properties, attributes and element
        keywords available in the :class:`Dataset`.

        List of attributes is used, for example, in auto-completion in editors
        or command-line environments.
        """
        names = set(super().__dir__())
        keywords = set(self.dir())

        return sorted(names | keywords)

    def dir(self, *filters: str) -> list[str]:
        """Return an alphabetical list of element keywords in the
        :class:`Dataset`.

        Intended mainly for use in interactive Python sessions. Only lists the
        element keywords in the current level of the :class:`Dataset` (i.e.
        the contents of any sequence elements are ignored).

        Parameters
        ----------
        filters : str
            Zero or more string arguments to the function. Used for
            case-insensitive match to any part of the DICOM keyword.

        Returns
        -------
        list of str
            The matching element keywords in the dataset. If no
            filters are used then all element keywords are returned.
        """
        allnames = [keyword_for_tag(tag) for tag in self._dict.keys()]
        # remove blanks - tags without valid names (e.g. private tags)
        allnames = [x for x in allnames if x]
        # Store found names in a dict, so duplicate names appear only once
        matches = {}
        for filter_ in filters:
            filter_ = filter_.lower()
            match = [x for x in allnames if x.lower().find(filter_) != -1]
            matches.update({x: 1 for x in match})

        if filters:
            return sorted(matches.keys())

        return sorted(allnames)

    def __eq__(self, other: Any) -> bool:
        """Compare `self` and `other` for equality.

        Returns
        -------
        bool
            The result if `self` and `other` are the same class
        NotImplemented
            If `other` is not the same class as `self` then returning
            :class:`NotImplemented` delegates the result to
            ``superclass.__eq__(subclass)``.
        """
        # When comparing against self this will be faster
        if other is self:
            return True

        if isinstance(other, self.__class__):
            return _dict_equal(self, other)

        return NotImplemented

    @overload
    def get(self, key: str, default: Any | None = None) -> Any:
        pass  # pragma: no cover

    @overload
    def get(
        self, key: int | tuple[int, int] | BaseTag, default: Any | None = None
    ) -> DataElement:
        pass  # pragma: no cover

    def get(
        self, key: str | int | tuple[int, int] | BaseTag, default: Any | None = None
    ) -> Any | DataElement:
        """Simulate ``dict.get()`` to handle element tags and keywords.

        Parameters
        ----------
        key : str or int or Tuple[int, int] or BaseTag
            The element keyword or tag or the class attribute name to get.
        default : obj or None, optional
            If the element or class attribute is not present, return
            `default` (default ``None``).

        Returns
        -------
        value
            If `key` is the keyword for an element in the :class:`Dataset`
            then return the element's value.
        dataelem.DataElement
            If `key` is a tag for a element in the :class:`Dataset` then
            return the :class:`~pydicom.dataelem.DataElement`
            instance.
        value
            If `key` is a class attribute then return its value.
        """
        if isinstance(key, str):
            try:
                return getattr(self, key)
            except AttributeError:
                return default

        # is not a string, try to make it into a tag and then hand it
        # off to the underlying dict
        try:
            key = Tag(key)
        except Exception as exc:
            raise TypeError("Dataset.get key must be a string or tag") from exc

        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def items(self) -> Set[tuple[BaseTag, _DatasetValue]]:
        """Return the :class:`Dataset` items to simulate :meth:`dict.items`.

        Returns
        -------
        dict_items
            The top-level (:class:`~pydicom.tag.BaseTag`,
            :class:`~pydicom.dataelem.DataElement`) items for the
            :class:`Dataset`.
        """
        return self._dict.items()

    def keys(self) -> Set[BaseTag]:
        """Return the :class:`Dataset` keys to simulate :meth:`dict.keys`.

        Returns
        -------
        dict_keys
            The :class:`~pydicom.tag.BaseTag` of all the elements in
            the :class:`Dataset`.
        """
        return self._dict.keys()

    def values(self) -> ValuesView[_DatasetValue]:
        """Return the :class:`Dataset` values to simulate :meth:`dict.values`.

        Returns
        -------
        dict_keys
            The :class:`DataElements<pydicom.dataelem.DataElement>` that make
            up the values of the :class:`Dataset`.
        """
        return self._dict.values()

    def __getattr__(self, name: str) -> Any:
        """Intercept requests for :class:`Dataset` attribute names.

        If `name` matches a DICOM keyword, return the value for the
        element with the corresponding tag.

        Parameters
        ----------
        name : str
            An element keyword or a class attribute name.

        Returns
        -------
        value
              If `name` matches a DICOM keyword, returns the corresponding
              element's value. Otherwise returns the class attribute's
              value (if present).
        """
        tag = tag_for_keyword(name)
        if tag is not None:  # None means `name` isn't a DICOM element keyword
            tag = Tag(tag)
            if tag in self._dict:
                return self[tag].value

        # no tag or tag not contained in the dataset
        if name == "_dict":
            # special handling for contained dict, needed for pickle
            return {}
        # Try the base class attribute getter (fix for issue 332)
        return object.__getattribute__(self, name)

    @property
    def _character_set(self) -> str | list[str]:
        """The character set used to encode text values."""
        char_set = self.get(BaseTag(0x00080005), None)
        if not char_set:
            return self._parent_encoding

        return convert_encodings(char_set.value)

    @property
    def original_character_set(self) -> str | MutableSequence[str]:
        """Return the original character set encoding for a dataset decoded
        from a file or buffer.

        Returns
        -------
        str | MutableSequence[str]
            The original character set encoding of the dataset as given by
            the (0008,0005) *Specific Character Set*, or `iso8859
            <https://docs.python.org/3/library/codecs.html#standard-encodings>`_
            if the dataset has been created from scratch.
        """
        return self._read_charset

    @property
    def read_encoding(self) -> str | MutableSequence[str]:
        """Return the original character set encoding for a decoded dataset.

        .. deprecated:: 3.0

            ``read_encoding`` will be removed in v4.0, use
            :attr:`~pydicom.dataset.Dataset.original_character_set` instead.

        """
        name = type(self).__name__
        if config._use_future:
            raise AttributeError(f"'{name}' object has no attribute 'read_encoding'")

        warnings.warn(
            (
                f"'{name}.read_encoding' will be removed in v4.0, use "
                f"'{name}.original_character_set' instead"
            ),
            DeprecationWarning,
        )

        return self.original_character_set

    @read_encoding.setter
    def read_encoding(self, value: str | MutableSequence[str]) -> None:
        name = type(self).__name__
        if config._use_future:
            raise AttributeError(f"'{name}' object has no attribute 'read_encoding'")

        warnings.warn(
            (
                f"'{name}.read_encoding' will be removed in v4.0, use "
                f"'{name}.original_character_set' instead"
            ),
            DeprecationWarning,
        )

        self._read_charset = value

    @overload
    def __getitem__(self, key: slice) -> "Dataset":
        pass  # pragma: no cover

    @overload
    def __getitem__(self, key: TagType) -> DataElement:
        pass  # pragma: no cover

    def __getitem__(self, key: "slice | TagType") -> "Dataset | DataElement":
        """Operator for ``Dataset[key]`` request.

        Any deferred data elements will be read in and an attempt will be made
        to correct any elements with ambiguous VRs.

        Examples
        --------
        Indexing using :class:`~pydicom.dataelem.DataElement` tag

        >>> ds = Dataset()
        >>> ds.SOPInstanceUID = '1.2.3'
        >>> ds.PatientName = 'CITIZEN^Jan'
        >>> ds.PatientID = '12345'
        >>> ds[0x00100010].value
        'CITIZEN^Jan'

        Slicing using element tags; all group ``0x0010`` elements in
        the  dataset

        >>> ds[0x00100000:0x00110000]
        (0010,0010) Patient's Name                      PN: 'CITIZEN^Jan'
        (0010,0020) Patient ID                          LO: '12345'

        All group ``0x0002`` elements in the dataset

        >>> ds[(0x0002, 0x0000):(0x0003, 0x0000)]
        <BLANKLINE>

        Parameters
        ----------
        key
            The DICOM (group, element) tag in any form accepted by
            :func:`~pydicom.tag.Tag` such as ``[0x0010, 0x0010]``,
            ``(0x10, 0x10)``, ``0x00100010``, etc. May also be a :class:`slice`
            made up of DICOM tags.

        Returns
        -------
        dataelem.DataElement or Dataset
            If a single DICOM element tag is used then returns the
            corresponding :class:`~pydicom.dataelem.DataElement`.
            If a :class:`slice` is used then returns a :class:`Dataset` object
            containing the corresponding
            :class:`DataElements<pydicom.dataelem.DataElement>`.
        """
        # If passed a slice, return a Dataset containing the corresponding
        #   DataElements
        if isinstance(key, slice):
            return self._dataset_slice(key)

        if isinstance(key, BaseTag):
            tag = key
        else:
            try:
                tag = Tag(key)
            except Exception as exc:
                raise KeyError(f"'{key}'") from exc

        elem = self._dict[tag]

        if isinstance(elem, RawDataElement):
            # If a deferred read, then go get the value now
            if elem.value is None and elem.length != 0:
                from pydicom.filereader import read_deferred_data_element

                elem = read_deferred_data_element(
                    self.fileobj_type, self.filename, self.timestamp, elem
                )

            if tag != BaseTag(0x00080005):
                character_set = self.original_character_set or self._character_set
            else:
                character_set = default_encoding
            # Not converted from raw form read from file yet; do so now
            self[tag] = DataElement_from_raw(elem, character_set, self)

            # On initial read of the dataset, propagate the pixel representation
            #   (if any) to child datasets in any sequences.
            # This is used as part of the ambiguous VR correction for US or SS
            if self[tag].VR == VR_.SQ:
                self._set_pixel_representation(self[tag])

            # If the Element has an ambiguous VR, try to correct it
            if self[tag].VR in AMBIGUOUS_VR:
                from pydicom.filewriter import correct_ambiguous_vr_element

                self[tag] = correct_ambiguous_vr_element(self[tag], self, elem[6])

        return cast(DataElement, self._dict.get(tag))

    def private_block(
        self, group: int, private_creator: str, create: bool = False
    ) -> PrivateBlock:
        """Return the block for the given tag `group` and `private_creator`.

        .. versionadded:: 1.3

        If `create` is ``True`` and the `private_creator` does not exist,
        the private creator tag is added.

        Notes
        -----
        We ignore the unrealistic case that no free block is available.

        Parameters
        ----------
        group : int
            The group of the private tag to be found as a 32-bit :class:`int`.
            Must be an odd number (e.g. a private group).
        private_creator : str
            The private creator string associated with the tag.
        create : bool, optional
            If ``True`` and `private_creator` does not exist, a new private
            creator tag is added at the next free block. If ``False``
            (the default) and `private_creator` does not exist,
            :class:`KeyError` is raised instead.

        Returns
        -------
        PrivateBlock
            The existing or newly created private block.

        Raises
        ------
        ValueError
            If `group` doesn't belong to a private tag or `private_creator`
            is empty.
        KeyError
            If the private creator tag is not found in the given group and
            the `create` parameter is ``False``.
        """

        def new_block(element: int) -> PrivateBlock:
            block = PrivateBlock(key, self, element)
            self._private_blocks[key] = block
            return block

        key = (group, private_creator)
        if key in self._private_blocks:
            return self._private_blocks[key]

        if not private_creator:
            raise ValueError("Private creator must have a value")

        if group % 2 == 0:
            raise ValueError("Tag must be private if private creator is given")

        # find block with matching private creator
        block = self[(group, 0x10):(group, 0x100)]  # type: ignore[misc]
        data_el = next((elem for elem in block if elem.value == private_creator), None)
        if data_el is not None:
            return new_block(data_el.tag.element)

        if not create:
            # not found and shall not be created - raise
            raise KeyError(f"Private creator '{private_creator}' not found")

        # private creator not existing - find first unused private block
        # and add the private creator
        first_free_el = next(
            el for el in range(0x10, 0x100) if Tag(group, el) not in self._dict
        )
        self.add_new(Tag(group, first_free_el), "LO", private_creator)
        return new_block(first_free_el)

    def private_creators(self, group: int) -> list[str]:
        """Return a list of private creator names in the given group.

        .. versionadded:: 1.3

        Examples
        --------
        This can be used to check if a given private creator exists in
        the group of the dataset:

        >>> ds = Dataset()
        >>> if 'My Creator' in ds.private_creators(0x0041):
        ...     block = ds.private_block(0x0041, 'My Creator')

        Parameters
        ----------
        group : int
            The private group as a 32-bit :class:`int`. Must be an odd number.

        Returns
        -------
        list of str
            All private creator names for private blocks in the group.

        Raises
        ------
        ValueError
            If `group` is not a private group.
        """
        if group % 2 == 0:
            raise ValueError("Group must be an odd number")

        block = self[(group, 0x10):(group, 0x100)]  # type: ignore[misc]
        return [x.value for x in block]

    def get_private_item(
        self, group: int, element_offset: int, private_creator: str
    ) -> DataElement:
        """Return the data element for the given private tag `group`.

        .. versionadded:: 1.3

        This is analogous to ``Dataset.__getitem__()``, but only for private
        tags. This allows to find the private tag for the correct private
        creator without the need to add the tag to the private dictionary
        first.

        Parameters
        ----------
        group : int
            The private tag group where the item is located as a 32-bit int.
        element_offset : int
            The lower 16 bits (e.g. 2 hex numbers) of the element tag.
        private_creator : str
            The private creator for the tag. Must match the private creator
            for the tag to be returned.

        Returns
        -------
        dataelem.DataElement
            The corresponding element.

        Raises
        ------
        ValueError
            If `group` is not part of a private tag or `private_creator` is
            empty.
        KeyError
            If the private creator tag is not found in the given group.
            If the private tag is not found.
        """
        block = self.private_block(group, private_creator)
        return self.__getitem__(block.get_tag(element_offset))

    @overload
    def get_item(self, key: slice) -> "Dataset":
        pass  # pragma: no cover

    @overload
    def get_item(self, key: TagType) -> DataElement:
        pass  # pragma: no cover

    def get_item(
        self, key: "slice | TagType"
    ) -> "Dataset | DataElement | RawDataElement | None":
        """Return the raw data element if possible.

        It will be raw if the user has never accessed the value, or set their
        own value. Note if the data element is a deferred-read element,
        then it is read and converted before being returned.

        Parameters
        ----------
        key
            The DICOM (group, element) tag in any form accepted by
            :func:`~pydicom.tag.Tag` such as ``[0x0010, 0x0010]``,
            ``(0x10, 0x10)``, ``0x00100010``, etc. May also be a :class:`slice`
            made up of DICOM tags.

        Returns
        -------
        dataelem.DataElement
            The corresponding element.
        """
        if isinstance(key, slice):
            return self._dataset_slice(key)

        elem = self._dict.get(Tag(key))
        # If a deferred read, return using __getitem__ to read and convert it
        if isinstance(elem, RawDataElement) and elem.value is None:
            return self[key]

        return elem

    def _dataset_slice(self, slce: slice) -> "Dataset":
        """Return a slice that has the same properties as the original dataset.

        That includes properties related to endianness and VR handling,
        and the specific character set. No element conversion is done, e.g.
        elements of type ``RawDataElement`` are kept.
        """
        tags = self._slice_dataset(slce.start, slce.stop, slce.step)
        ds = Dataset({tag: self.get_item(tag) for tag in tags})
        is_implicit, is_little = self.original_encoding
        ds.set_original_encoding(is_implicit, is_little, self.original_character_set)
        if not config._use_future:
            ds._is_little_endian = self.is_little_endian
            ds._is_implicit_VR = self.is_implicit_VR

        return ds

    @property
    def is_implicit_VR(self) -> bool | None:
        """Get/set the VR method used when encoding the dataset.

        .. deprecated:: 3.0

            ``is_implicit_VR`` will be removed in v4.0, set the *Transfer
            Syntax UID* or use the `implicit_vr` argument with
            :meth:`~pydicom.dataset.Dataset.save_as` or
            :func:`~pydicom.filewriter.dcmwrite` instead.

        Returns
        -------
        bool | None
            If the dataset has been created from scratch then returns ``None``,
            otherwise returns the VR encoding method used by the decoded
            dataset.
        """
        if config._use_future:
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute 'is_implicit_VR'"
            )

        return self._is_implicit_VR

    @is_implicit_VR.setter
    def is_implicit_VR(self, value: bool | None) -> None:
        name = type(self).__name__
        if config._use_future:
            raise AttributeError(f"'{name}' object has no attribute 'is_implicit_VR'")

        warnings.warn(
            (
                f"'{name}.is_implicit_VR' will be removed in v4.0, set the "
                "Transfer Syntax UID or use the 'implicit_vr' argument with "
                f"{name}.save_as() or dcmwrite() instead"
            ),
            DeprecationWarning,
        )
        self._is_implicit_VR = value

    @property
    def is_little_endian(self) -> bool | None:
        """Get/set the endianness used when encoding the dataset.

        .. deprecated:: 3.0

            ``is_little_endian`` will be removed in v4.0, set the *Transfer
            Syntax UID* or use the `little_endian` argument with
            :meth:`~pydicom.dataset.Dataset.save_as` or
            :func:`~pydicom.filewriter.dcmwrite` instead.

        Returns
        -------
        bool | None
            If the dataset has been created from scratch then returns ``None``,
            otherwise returns the endianness of the encoding used by the
            decoded dataset.
        """
        if config._use_future:
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute 'is_little_endian'"
            )

        return self._is_little_endian

    @is_little_endian.setter
    def is_little_endian(self, value: bool | None) -> None:
        name = type(self).__name__
        if config._use_future:
            raise AttributeError(f"'{name}' object has no attribute 'is_little_endian'")

        warnings.warn(
            (
                f"'{name}.is_little_endian' will be removed in v4.0, set the "
                "Transfer Syntax UID or use the 'little_endian' argument with "
                f"{name}.save_as() or dcmwrite() instead"
            ),
            DeprecationWarning,
        )
        self._is_little_endian = value

    @property
    def is_original_encoding(self) -> bool:
        """Return ``True`` if the encoding to be used for writing is set and
        is the same as that used to originally encode the  :class:`Dataset`.

        .. versionadded:: 1.1

        This includes properties related to endianness, VR handling and the
        (0008,0005) *Specific Character Set*.
        """
        if config._use_future:
            return self.original_character_set == self._character_set

        current_encoding = (self.is_implicit_VR, self.is_little_endian)
        return (
            None not in current_encoding
            and self.original_encoding == current_encoding
            and self.original_character_set == self._character_set
        )

    @property
    def original_encoding(self) -> tuple[bool, bool] | tuple[None, None]:
        """Return the original encoding used for a dataset decoded from a file
        or buffer.

        Returns
        -------
        tuple[bool, bool] | tuple[None, None]
            For a dataset decoded from a file or buffer this is whether
            the encoding used implicit/explicit VR and little/big endian
            as ``(encoded as implicit VR, encoded as little endian)``. Returns
            ``(None, None)`` for a dataset created from scratch.
        """
        return cast(
            tuple[bool, bool] | tuple[None, None],
            (self._read_implicit, self._read_little),
        )

    def set_original_encoding(
        self,
        is_implicit_vr: bool | None,
        is_little_endian: bool | None,
        character_encoding: str | MutableSequence[str] | None = None,
    ) -> None:
        """Set the values for the original dataset encoding.

        .. versionadded:: 1.2

        Can be used for a :class:`Dataset` with raw data elements to enable
        optimized writing (e.g. without decoding the data elements).

        .. versionchanged:: 3.0

            `character_encoding` is now optional

        Parameters
        ----------
        is_implicit_vr : bool | None
            The the original VR encoding of the dataset, ``True`` for implicit
            VR, ``False`` for explicit VR or ``None`` to reset.
        is_little_endian : bool | None
            Set the original endianness of the dataset, ``True`` for little
            endian, ``False`` for big or ``None`` to reset.
        character_encoding : str | MutableSequence[str], optional
            Set the original character set encoding of the dataset. If ``None``
            then no changes will be made to the original character set
            encoding.
        """
        self._read_implicit = is_implicit_vr
        self._read_little = is_little_endian
        if character_encoding is not None:
            self._read_charset = character_encoding

    def group_dataset(self, group: int) -> "Dataset":
        """Return a :class:`Dataset` containing only elements of a certain
        group.

        Parameters
        ----------
        group : int
            The group part of a DICOM (group, element) tag.

        Returns
        -------
        Dataset
            A :class:`Dataset` containing elements of the group specified.
        """
        return self[(group, 0x0000) : (group + 1, 0x0000)]  # type: ignore[misc]

    def __iter__(self) -> Iterator[DataElement]:
        """Iterate through the top-level of the Dataset, yielding DataElements.

        Examples
        --------

        >>> ds = Dataset()
        >>> for elem in ds:
        ...     print(elem)

        The :class:`DataElements<pydicom.dataelem.DataElement>` are returned in
        increasing tag value order. Sequence items are returned as a single
        :class:`~pydicom.dataelem.DataElement`, so it is up
        to the calling code to recurse into the Sequence items if desired.

        Yields
        ------
        dataelem.DataElement
            The :class:`Dataset`'s
            :class:`DataElements<pydicom.dataelem.DataElement>`, sorted by
            increasing tag order.
        """
        # Note this is different than the underlying dict class,
        #        which returns the key of the key:value mapping.
        #   Here the value is returned (but data_element.tag has the key)
        taglist = sorted(self._dict.keys())
        for tag in taglist:
            yield self[tag]

    def elements(self) -> Iterator[DataElement]:
        """Yield the top-level elements of the :class:`Dataset`.

        .. versionadded:: 1.1

        Examples
        --------

        >>> ds = Dataset()
        >>> for elem in ds.elements():
        ...     print(elem)

        The elements are returned in the same way as in
        ``Dataset.__getitem__()``.

        Yields
        ------
        dataelem.DataElement or dataelem.RawDataElement
            The unconverted elements sorted by increasing tag order.
        """
        taglist = sorted(self._dict.keys())
        for tag in taglist:
            yield self.get_item(tag)

    def __len__(self) -> int:
        """Return the number of elements in the top level of the dataset."""
        return len(self._dict)

    def __ne__(self, other: Any) -> bool:
        """Compare `self` and `other` for inequality."""
        return not self == other

    def clear(self) -> None:
        """Delete all the elements from the :class:`Dataset`."""
        self._dict.clear()

    def pop(self, key: "BaseTag | TagType", *args: Any) -> _DatasetValue:
        """Emulate :meth:`dict.pop` with support for tags and keywords.

        Removes the element for `key` if it exists and returns it,
        otherwise returns a default value if given or raises :class:`KeyError`.

        Parameters
        ----------
        key : int or str or 2-tuple

            * If :class:`tuple` - the group and element number of the DICOM tag
            * If :class:`int` - the combined group/element number
            * If :class:`str` - the DICOM keyword of the tag

        *args : zero or one argument
            Defines the behavior if no tag exists for `key`: if given,
            it defines the return value, if not given, :class:`KeyError` is
            raised

        Returns
        -------
        RawDataElement or DataElement
            The element for `key` if it exists, or the default value if given.

        Raises
        ------
        KeyError
            If the `key` is not a valid tag or keyword.
            If the tag does not exist and no default is given.
        """
        try:
            key = Tag(key)
        except Exception:
            pass

        return self._dict.pop(cast(BaseTag, key), *args)

    def popitem(self) -> tuple[BaseTag, _DatasetValue]:
        """Emulate :meth:`dict.popitem`.

        Returns
        -------
        tuple of (BaseTag, DataElement)
        """
        return self._dict.popitem()

    def setdefault(self, key: TagType, default: Any | None = None) -> DataElement:
        """Emulate :meth:`dict.setdefault` with support for tags and keywords.

        Examples
        --------

        >>> ds = Dataset()
        >>> elem = ds.setdefault((0x0010, 0x0010), "Test")
        >>> elem
        (0010,0010) Patient's Name                      PN: 'Test'
        >>> elem.value
        'Test'
        >>> elem = ds.setdefault('PatientSex',
        ...     DataElement(0x00100040, 'CS', 'F'))
        >>> elem.value
        'F'

        Parameters
        ----------
        key : int, str or 2-tuple of int

            * If :class:`tuple` - the group and element number of the DICOM tag
            * If :class:`int` - the combined group/element number
            * If :class:`str` - the DICOM keyword of the tag
        default : pydicom.dataelem.DataElement or object, optional
            The :class:`~pydicom.dataelem.DataElement` to use with `key`, or
            the value of the :class:`~pydicom.dataelem.DataElement` to use with
            `key` (default ``None``).

        Returns
        -------
        pydicom.dataelem.DataElement or object
            The :class:`~pydicom.dataelem.DataElement` for `key`.

        Raises
        ------
        ValueError
            If `key` is not convertible to a valid tag or a known element
            keyword.
        KeyError
            If :attr:`~pydicom.config.settings.reading_validation_mode` is
             ``RAISE`` and `key` is an unknown non-private tag.
        """
        tag = Tag(key)
        if tag in self:
            return self[tag]

        vr: str | VR_
        if not isinstance(default, DataElement):
            if tag.is_private:
                vr = VR_.UN
            else:
                try:
                    vr = dictionary_VR(tag)
                except KeyError:
                    if config.settings.writing_validation_mode == config.RAISE:
                        raise KeyError(f"Unknown DICOM tag {tag}")

                    vr = VR_.UN
                    warnings.warn(f"Unknown DICOM tag {tag} - setting VR to 'UN'")

            default = DataElement(tag, vr, default)

        self[key] = default

        return default

    def convert_pixel_data(self, handler_name: str = "") -> None:
        """Convert pixel data to a :class:`numpy.ndarray` internally.

        Parameters
        ----------
        handler_name : str, optional
            The name of the pixel handler that shall be used to
            decode the data. Supported names are: ``'gdcm'``,
            ``'pillow'``, ``'jpeg_ls'``, ``'rle'``, ``'numpy'`` and
            ``'pylibjpeg'``. If not used (the default), a matching handler is
            used from the handlers configured in
            :attr:`~pydicom.config.pixel_data_handlers`.

        Returns
        -------
        None
            Converted pixel data is stored internally in the dataset.

        Raises
        ------
        ValueError
            If `handler_name` is not a valid handler name.
        NotImplementedError
            If the given handler or any handler, if none given, is unable to
            decompress pixel data with the current transfer syntax
        RuntimeError
            If the given handler, or the handler that has been selected if
            none given, is not available.

        Notes
        -----
        If the pixel data is in a compressed image format, the data is
        decompressed and any related data elements are changed accordingly.
        """
        # Check if already have converted to a NumPy array
        # Also check if pixel data has changed. If so, get new NumPy array
        already_have = True
        if not hasattr(self, "_pixel_array"):
            already_have = False
        elif self._pixel_id != get_image_pixel_ids(self):
            already_have = False

        if already_have:
            return

        if handler_name:
            self._convert_pixel_data_using_handler(handler_name)
        else:
            self._convert_pixel_data_without_handler()

    def _convert_pixel_data_using_handler(self, name: str) -> None:
        """Convert the pixel data using handler with the given name.
        See :meth:`~Dataset.convert_pixel_data` for more information.
        """
        # handle some variations in name
        handler_name = name.lower()
        if not handler_name.endswith("_handler"):
            handler_name += "_handler"
        if handler_name == "numpy_handler":
            handler_name = "np_handler"
        if handler_name == "jpeg_ls_handler":
            # the name in config differs from the actual handler name
            # we allow both
            handler_name = "jpegls_handler"
        if not hasattr(pydicom.config, handler_name):
            raise ValueError(f"'{name}' is not a known handler name")

        handler = getattr(pydicom.config, handler_name)

        tsyntax = self.file_meta.TransferSyntaxUID
        if not handler.supports_transfer_syntax(tsyntax):
            raise NotImplementedError(
                "Unable to decode pixel data with a transfer syntax UID"
                f" of '{tsyntax}' ({tsyntax.name}) using the pixel data "
                f"handler '{name}'. Please see the pydicom documentation for "
                "information on supported transfer syntaxes."
            )
        if not handler.is_available():
            raise RuntimeError(
                f"The pixel data handler '{name}' is not available on your "
                "system. Please refer to the pydicom documentation for "
                "information on installing needed packages."
            )
        # if the conversion fails, the exception is propagated up
        self._do_pixel_data_conversion(handler)

    def _convert_pixel_data_without_handler(self) -> None:
        """Convert the pixel data using the first matching handler.
        See :meth:`~Dataset.convert_pixel_data` for more information.
        """
        # Find all possible handlers that support the transfer syntax
        ts = self.file_meta.TransferSyntaxUID
        possible_handlers = [
            hh
            for hh in pydicom.config.pixel_data_handlers
            if hh is not None and hh.supports_transfer_syntax(ts)
        ]

        # No handlers support the transfer syntax
        if not possible_handlers:
            raise NotImplementedError(
                "Unable to decode pixel data with a transfer syntax UID of "
                f"'{ts}' ({ts.name}) as there are no pixel data "
                "handlers available that support it. Please see the pydicom "
                "documentation for information on supported transfer syntaxes "
            )

        # Handlers that both support the transfer syntax and have their
        #   dependencies met
        available_handlers = [hh for hh in possible_handlers if hh.is_available()]

        # There are handlers that support the transfer syntax but none of them
        #   can be used as missing dependencies
        if not available_handlers:
            # For each of the possible handlers we want to find which
            #   dependencies are missing
            msg = (
                "The following handlers are available to decode the pixel "
                "data however they are missing required dependencies: "
            )
            pkg_msg = []
            for hh in possible_handlers:
                hh_deps = hh.DEPENDENCIES
                # Missing packages
                missing = [dd for dd in hh_deps if have_package(dd) is None]
                # Package names
                names = [hh_deps[name][1] for name in missing]
                pkg_msg.append(f"{hh.HANDLER_NAME} (req. {', '.join(names)})")

            raise RuntimeError(msg + ", ".join(pkg_msg))

        last_exception = None
        for handler in available_handlers:
            try:
                self._do_pixel_data_conversion(handler)
                return
            except Exception as exc:
                logger.debug("Exception raised by pixel data handler", exc_info=exc)
                last_exception = exc

        # The only way to get to this point is if we failed to get the pixel
        #   array because all suitable handlers raised exceptions
        self._pixel_array = None
        self._pixel_id = {}

        logger.info(
            "Unable to decode the pixel data using the following handlers: {}."
            "Please see the list of supported Transfer Syntaxes in the "
            "pydicom documentation for alternative packages that might "
            "be able to decode the data".format(
                ", ".join([str(hh) for hh in available_handlers])
            )
        )
        raise last_exception  # type: ignore[misc]

    def _do_pixel_data_conversion(self, handler: Any) -> None:
        """Do the actual data conversion using the given handler."""

        # Use the handler to get a 1D numpy array of the pixel data
        # Will raise an exception if no pixel data element
        arr = handler.get_pixeldata(self)
        self._pixel_array = reshape_pixel_array(self, arr)

        # Some handler/transfer syntax combinations may need to
        #   convert the color space from YCbCr to RGB
        if handler.needs_to_convert_to_RGB(self):
            self._pixel_array = convert_color_space(
                self._pixel_array, "YBR_FULL", "RGB"
            )

        self._pixel_id = get_image_pixel_ids(self)

    def compress(
        self,
        transfer_syntax_uid: str,
        arr: Optional["numpy.ndarray"] = None,
        encoding_plugin: str = "",
        decoding_plugin: str = "",
        encapsulate_ext: bool = False,
        **kwargs: Any,
    ) -> None:
        """Compress and update an uncompressed dataset in-place with the
        resulting :dcm:`encapsulated<part05/sect_A.4.html>` pixel data.

        .. versionadded:: 2.2

        The dataset must already have the following
        :dcm:`Image Pixel<part03/sect_C.7.6.3.html>` module elements present
        with correct values that correspond to the resulting compressed
        pixel data:

        * (0028,0002) *Samples per Pixel*
        * (0028,0004) *Photometric Interpretation*
        * (0028,0008) *Number of Frames* (if more than 1 frame will be present)
        * (0028,0010) *Rows*
        * (0028,0011) *Columns*
        * (0028,0100) *Bits Allocated*
        * (0028,0101) *Bits Stored*
        * (0028,0103) *Pixel Representation*

        This method will add the file meta dataset if none is present and add
        or modify the following elements:

        * (0002,0010) *Transfer Syntax UID*
        * (7FE0,0010) *Pixel Data*

        If *Samples per Pixel* is greater than 1 then the following element
        will also be added:

        * (0028,0006) *Planar Configuration*

        If the compressed pixel data is too large for encapsulation using a
        basic offset table then an :dcm:`extended offset table
        <part03/sect_C.7.6.3.html>` will also be used, in which case the
        following elements will also be added:

        * (7FE0,0001) *Extended Offset Table*
        * (7FE0,0002) *Extended Offset Table Lengths*

        **Supported Transfer Syntax UIDs**

        +----------------------+----------+----------------------------------+
        | UID                  | Plugins  | Encoding Guide                   |
        +======================+==========+==================================+
        | *RLE Lossless* -     |pydicom,  | :doc:`RLE Lossless               |
        | 1.2.840.10008.1.2.5  |pylibjpeg,| </guides/encoding/rle_lossless>` |
        |                      |gdcm      |                                  |
        +----------------------+----------+----------------------------------+

        Examples
        --------

        Compress the existing uncompressed *Pixel Data* in place:

        >>> from pydicom import examples
        >>> from pydicom.uid import RLELossless
        >>> ds = examples.ct
        >>> ds.compress(RLELossless)
        >>> ds.save_as("ct_rle_lossless.dcm")

        Parameters
        ----------
        transfer_syntax_uid : pydicom.uid.UID
            The UID of the :dcm:`transfer syntax<part05/chapter_10.html>` to
            use when compressing the pixel data.
        arr : numpy.ndarray, optional
            Compress the uncompressed pixel data in `arr` and use it
            to set the *Pixel Data*. If `arr` is not used then the
            existing *Pixel Data* in the dataset will be compressed instead.
            The :attr:`~numpy.ndarray.shape`, :class:`~numpy.dtype` and
            contents of the array should match the dataset.
        encoding_plugin : str, optional
            Use the `encoding_plugin` to compress the pixel data. See the
            :doc:`user guide </old/image_data_compression>` for a list of
            plugins available for each UID and their dependencies. If not
            specified then all available plugins will be tried (default).
        decoding_plugin : str, optional
            Placeholder for future functionality.
        encapsulate_ext : bool, optional
            If ``True`` then force the addition of an extended offset table.
            If ``False`` (default) then an extended offset table
            will be added if needed for large amounts of compressed *Pixel
            Data*, otherwise just the basic offset table will be used.
        **kwargs
            Optional keyword parameters for the encoding plugin may also be
            present. See the :doc:`encoding plugins options
            </guides/encoding/encoder_plugin_options>` for more information.
        """
        from pydicom.encoders import get_encoder

        uid = UID(transfer_syntax_uid)

        # Raises NotImplementedError if `uid` is not supported
        encoder = get_encoder(uid)
        if not encoder.is_available:
            missing = "\n".join([f"    {s}" for s in encoder.missing_dependencies])
            raise RuntimeError(
                f"The '{uid.name}' encoder is unavailable because its "
                f"encoding plugins are missing dependencies:\n"
                f"{missing}"
            )

        if arr is None:
            # Encode the current *Pixel Data*
            frame_iterator = encoder.iter_encode(
                self,
                encoding_plugin=encoding_plugin,
                decoding_plugin=decoding_plugin,
                **kwargs,
            )
        else:
            # Encode from an uncompressed pixel data array
            kwargs.update(encoder.kwargs_from_ds(self))
            frame_iterator = encoder.iter_encode(
                arr, encoding_plugin=encoding_plugin, **kwargs
            )

        # Encode!
        encoded = [f for f in frame_iterator]

        # Encapsulate the encoded *Pixel Data*
        nr_frames = get_nr_frames(self)
        total = (nr_frames - 1) * 8 + sum([len(f) for f in encoded[:-1]])
        if encapsulate_ext or total > 2**32 - 1:
            (
                self.PixelData,
                self.ExtendedOffsetTable,
                self.ExtendedOffsetTableLengths,
            ) = encapsulate_extended(encoded)
        else:
            self.PixelData = encapsulate(encoded)

        # PS3.5 Annex A.4 - encapsulated pixel data uses undefined length
        self["PixelData"].is_undefined_length = True

        # Set the correct *Transfer Syntax UID*
        if not hasattr(self, "file_meta"):
            self.file_meta = FileMetaDataset()

        self.file_meta.TransferSyntaxUID = uid

        # Add or update any other required elements
        if self.SamplesPerPixel > 1:
            self.PlanarConfiguration: int = 1 if uid == RLELossless else 0

    def decompress(self, handler_name: str = "") -> None:
        """Decompresses *Pixel Data* and modifies the :class:`Dataset`
        in-place.

        .. versionadded:: 1.4

            The `handler_name` keyword argument was added

        If not a compressed transfer syntax, then pixel data is converted
        to a :class:`numpy.ndarray` internally, but not returned.

        If compressed pixel data, then is decompressed using an image handler,
        and internal state is updated appropriately:

        - ``Dataset.file_meta.TransferSyntaxUID`` is updated to non-compressed
          form
        - :attr:`~pydicom.dataelem.DataElement.is_undefined_length`
          is ``False`` for the (7FE0,0010) *Pixel Data* element.

        .. versionchanged:: 1.4

            The `handler_name` keyword argument was added

        Parameters
        ----------
        handler_name : str, optional
            The name of the pixel handler that shall be used to
            decode the data. Supported names are: ``'gdcm'``,
            ``'pillow'``, ``'jpeg_ls'``, ``'rle'``, ``'numpy'`` and
            ``'pylibjpeg'``.
            If not used (the default), a matching handler is used from the
            handlers configured in :attr:`~pydicom.config.pixel_data_handlers`.

        Returns
        -------
        None

        Raises
        ------
        NotImplementedError
            If the pixel data was originally compressed but file is not
            *Explicit VR Little Endian* as required by the DICOM Standard.
        """
        self.convert_pixel_data(handler_name)
        self.is_decompressed = True
        # May have been undefined length pixel data, but won't be now
        if "PixelData" in self:
            self[0x7FE00010].is_undefined_length = False

        # Make sure correct Transfer Syntax is set
        # According to the dicom standard PS3.5 section A.4,
        # all compressed files must have been explicit VR, little endian
        # First check if was a compressed file
        if (
            hasattr(self, "file_meta")
            and self.file_meta.TransferSyntaxUID.is_compressed
        ):
            # Check that current file as read does match expected
            if not self.is_little_endian or self.is_implicit_VR:
                msg = (
                    "Current dataset does not match expected ExplicitVR "
                    "LittleEndian transfer syntax from a compressed "
                    "transfer syntax"
                )
                raise NotImplementedError(msg)

            # All is as expected, updated the Transfer Syntax
            self.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    def overlay_array(self, group: int) -> "numpy.ndarray":
        """Return the *Overlay Data* in `group` as a :class:`numpy.ndarray`.

        .. versionadded:: 1.4

        Parameters
        ----------
        group : int
            The group number of the overlay data.

        Returns
        -------
        numpy.ndarray
            The (`group`,3000) *Overlay Data* converted to a
            :class:`numpy.ndarray`.
        """
        if group < 0x6000 or group > 0x60FF:
            raise ValueError(
                "The group part of the 'Overlay Data' element tag must be "
                "between 0x6000 and 0x60FF (inclusive)"
            )

        from pydicom.config import overlay_data_handlers

        available_handlers = [hh for hh in overlay_data_handlers if hh.is_available()]
        if not available_handlers:
            # For each of the handlers we want to find which
            #   dependencies are missing
            msg = (
                "The following handlers are available to decode the overlay "
                "data however they are missing required dependencies: "
            )
            pkg_msg = []
            for hh in overlay_data_handlers:
                hh_deps = hh.DEPENDENCIES
                # Missing packages
                missing = [dd for dd in hh_deps if have_package(dd) is None]
                # Package names
                names = [hh_deps[name][1] for name in missing]
                pkg_msg.append(f"{hh.HANDLER_NAME} (req. {', '.join(names)})")

            raise RuntimeError(msg + ", ".join(pkg_msg))

        last_exception = None
        for handler in available_handlers:
            try:
                # Use the handler to get an ndarray of the pixel data
                func = handler.get_overlay_array
                return cast("numpy.ndarray", func(self, group))
            except Exception as exc:
                logger.debug("Exception raised by overlay data handler", exc_info=exc)
                last_exception = exc

        logger.info(
            "Unable to decode the overlay data using the following handlers: "
            "{}. Please see the list of supported Transfer Syntaxes in the "
            "pydicom documentation for alternative packages that might "
            "be able to decode the data".format(
                ", ".join([str(hh) for hh in available_handlers])
            )
        )

        raise last_exception  # type: ignore[misc]

    @property
    def pixel_array(self) -> "numpy.ndarray":
        """Return the pixel data as a :class:`numpy.ndarray`.

        .. versionchanged:: 1.4

            Added support for *Float Pixel Data* and *Double Float Pixel Data*

        Returns
        -------
        numpy.ndarray
            The (7FE0,0008) *Float Pixel Data*, (7FE0,0009) *Double Float
            Pixel Data* or (7FE0,0010) *Pixel Data* converted to a
            :class:`numpy.ndarray`.
        """
        self.convert_pixel_data()
        return cast("numpy.ndarray", self._pixel_array)

    def waveform_array(self, index: int) -> "numpy.ndarray":
        """Return an :class:`~numpy.ndarray` for the multiplex group at
        `index` in the (5400,0100) *Waveform Sequence*.

        .. versionadded:: 2.1

        Parameters
        ----------
        index : int
            The index of the multiplex group to return the array for.

        Returns
        ------
        numpy.ndarray
            The *Waveform Data* for the multiplex group as an
            :class:`~numpy.ndarray` with shape (samples, channels). If
            (003A,0210) *Channel Sensitivity* is present
            then the values will be in the units specified by the (003A,0211)
            *Channel Sensitivity Units Sequence*.

        See Also
        --------
        :func:`~pydicom.waveforms.numpy_handler.generate_multiplex`
        :func:`~pydicom.waveforms.numpy_handler.multiplex_array`
        """
        if not wave_handler.is_available():
            raise RuntimeError("The waveform data handler requires numpy")

        return wave_handler.multiplex_array(self, index, as_raw=False)

    # Format strings spec'd according to python string formatting options
    #    See https://docs.python.org/3/library/stdtypes.html#printf-style-string-formatting # noqa
    default_element_format = "%(tag)s %(name)-35.35s %(VR)s: %(repval)s"
    default_sequence_element_format = (
        "%(tag)s %(name)-35.35s %(VR)s: %(repval)s"  # noqa
    )

    def formatted_lines(
        self,
        element_format: str = default_element_format,
        sequence_element_format: str = default_sequence_element_format,
        indent_format: str | None = None,
    ) -> Iterator[str]:
        """Iterate through the :class:`Dataset` yielding formatted :class:`str`
        for each element.

        Parameters
        ----------
        element_format : str
            The string format to use for non-sequence elements. Formatting uses
            the attributes of
            :class:`~pydicom.dataelem.DataElement`. Default is
            ``"%(tag)s %(name)-35.35s %(VR)s: %(repval)s"``.
        sequence_element_format : str
            The string format to use for sequence elements. Formatting uses
            the attributes of
            :class:`~pydicom.dataelem.DataElement`. Default is
            ``"%(tag)s %(name)-35.35s %(VR)s: %(repval)s"``
        indent_format : str or None
            Placeholder for future functionality.

        Yields
        ------
        str
            A string representation of an element.
        """
        exclusion = (
            "from_json",
            "to_json",
            "to_json_dict",
            "clear",
            "description",
            "validate",
        )
        for elem in self.iterall():
            # Get all the attributes possible for this data element (e.g.
            #   gets descriptive text name too)
            # This is the dictionary of names that can be used in the format
            #   string
            elem_dict = {
                attr: (
                    getattr(elem, attr)()
                    if callable(getattr(elem, attr))
                    else getattr(elem, attr)
                )
                for attr in dir(elem)
                if not attr.startswith("_") and attr not in exclusion
            }
            if elem.VR == VR_.SQ:
                yield sequence_element_format % elem_dict
            else:
                yield element_format % elem_dict

    def _pretty_str(self, indent: int = 0, top_level_only: bool = False) -> str:
        """Return a string of the DataElements in the Dataset, with indented
        levels.

        This private method is called by the ``__str__()`` method for handling
        print statements or ``str(dataset)``, and the ``__repr__()`` method.
        It is also used by ``top()``, therefore the `top_level_only` flag.
        This function recurses, with increasing indentation levels.

        ..versionchanged:: 2.0

            The file meta information is returned in its own section,
            if :data:`~pydicom.config.show_file_meta` is ``True`` (default)

        Parameters
        ----------
        indent : int, optional
            The indent level offset (default ``0``).
        top_level_only : bool, optional
            When True, only create a string for the top level elements, i.e.
            exclude elements within any Sequences (default ``False``).

        Returns
        -------
        str
            A string representation of the Dataset.
        """
        strings = []
        indent_str = self.indent_chars * indent
        nextindent_str = self.indent_chars * (indent + 1)

        # Display file meta, if configured to do so, and have a non-empty one
        if (
            hasattr(self, "file_meta")
            and self.file_meta
            and pydicom.config.show_file_meta
        ):
            strings.append(f"{'Dataset.file_meta ':-<49}")
            for elem in self.file_meta:
                with tag_in_exception(elem.tag):
                    strings.append(indent_str + repr(elem))
            strings.append(f"{'':-<49}")

        for elem in self:
            with tag_in_exception(elem.tag):
                if elem.VR == VR_.SQ:  # a sequence
                    strings.append(
                        f"{indent_str}{str(elem.tag)}  {elem.name}  "
                        f"{len(elem.value)} item(s) ---- "
                    )
                    if not top_level_only:
                        for dataset in elem.value:
                            strings.append(dataset._pretty_str(indent + 1))
                            strings.append(nextindent_str + "---------")
                else:
                    strings.append(indent_str + repr(elem))
        return "\n".join(strings)

    @property
    def read_implicit_vr(self) -> bool | None:
        """Get the VR method used by the original encoding of the dataset.

        .. deprecated:: 3.0

            ``read_implicit_vr`` will be removed in v4.0, , use
            :attr:`~pydicom.dataset.Dataset.original_encoding` instead.

        Returns
        -------
        bool | None
            Returns ``None`` if the dataset has been created from scratch,
            otherwise returns ``True`` if the dataset was decoded from file
            or buffer and used implicit VR, ``False`` if it used explicit VR.
        """
        name = type(self).__name__
        if config._use_future:
            raise AttributeError(f"'{name}' object has no attribute 'read_implicit_vr'")

        warnings.warn(
            (
                f"'{name}.read_implicit_vr' will be removed in v4.0, use "
                f"'{name}.original_encoding[0]' instead"
            ),
            DeprecationWarning,
        )
        return self._read_implicit

    @property
    def read_little_endian(self) -> bool | None:
        """Get the endianness used by the original encoding of the dataset.

        .. deprecated:: 3.0

            ``read_little_endian`` will be removed in v4.0, use
            :attr:`~pydicom.dataset.Dataset.original_encoding` instead.

        Returns
        -------
        bool | None
            Returns ``None`` if the dataset has been created from scratch,
            otherwise returns ``True`` if the dataset was decoded from file
            or buffer and used little endian encoding, ``False`` for big
            endian.
        """
        name = type(self).__name__
        if config._use_future:
            raise AttributeError(
                f"'{name}' object has no attribute 'read_little_endian'"
            )

        warnings.warn(
            (
                f"'{name}.read_little_endian' will be removed in v4.0, use "
                f"'{name}.original_encoding[1]' instead"
            ),
            DeprecationWarning,
        )
        return self._read_little

    def remove_private_tags(self) -> None:
        """Remove all private elements from the :class:`Dataset`."""

        def remove_callback(dataset: "Dataset", elem: DataElement) -> None:
            """Internal method to use as callback to walk() method."""
            if elem.tag.is_private:
                # can't del self[tag] - won't be right dataset on recursion
                del dataset[elem.tag]

        self.walk(remove_callback)

    def save_as(
        self,
        filename: "str | os.PathLike[AnyStr] | BinaryIO",
        /,
        *,
        write_like_original: bool | None = True,
        implicit_vr: bool | None = None,
        little_endian: bool | None = None,
        enforce_file_format: bool = False,
    ) -> None:
        """Encode the current :class:`Dataset` and write it to `filename`.

        See the documentation for :func:`~pydicom.filewriter.dcmwrite` for
        more detailed information.

        .. warning::

            Encoding a dataset with ``little_endian=False`` (i.e. as big
            endian) is not recommended. Big endian encoding was retired from
            the DICOM Standard in 2006.

        .. warning::

            This function cannot be used to convert a decoded dataset to an
            encoding that uses a different endianness, such as from big to
            little endian. :func:`~pydicom.filewriter.dcmwrite()` must be used
            instead, however the process is not automatic. See the
            documentation of :func:`~pydicom.filewriter.dcmwrite()` for
            details.

        .. versionchanged:: 3.0

            Added `implicit_vr`, `little_endian` and `enforce_file_format`

        .. deprecated:: 3.0

            `write_like_original` will be removed in v4.0, please use
            `enforce_file_format` instead

        Parameters
        ----------
        filename : str | PathLike | BinaryIO
            The path, file-like or buffer to write the encoded dataset to.
        write_like_original : bool, optional
            If ``True`` (default) then write the dataset as-is, otherwise
            ensure that the dataset is written in the DICOM File Format or
            raise an exception is that isn't possible. This parameter is
            deprecated, please use `enforce_file_format` instead.
        implicit_vr : bool, optional
            Required if the dataset has no valid public *Transfer Syntax UID*
            set in the file meta and
            :attr:`~pydicom.dataset.Dataset.is_implicit_VR` or
            :attr:`~pydicom.dataset.Dataset.original_encoding` are ``None``. If
            ``True`` then encode using implicit VR, otherwise use explicit VR.
        little_endian : bool, optional
            Required if the dataset has no valid public *Transfer Syntax UID*
            set in the file meta and
            :attr:`~pydicom.dataset.Dataset.is_little_endian` or
            :attr:`~pydicom.dataset.Dataset.original_encoding` are ``None``. If
            ``True`` (default) then use little endian byte order when encoding,
            otherwise use big endian (not recommended).
        enforce_file_format : bool, optional
            If ``True`` then ensure the dataset is written in the DICOM File
            Format or raise an exception if that isn't possible. If ``False``
            (default) then write the dataset as-is, preserving the following -
            which may result in a non-conformant file:

            - ``Dataset.preamble``: if the dataset has no preamble then none
              will be written
            - ``Dataset.file_meta``: if the dataset is missing any required
              *File Meta Information Group* elements then they will not be
              added or written

        See Also
        --------
        pydicom.filewriter.dcmwrite
            Encode a :class:`Dataset` and write it to a file or buffer.
        """
        class_name = type(self).__name__

        # TODO: Remove in v4.0
        if write_like_original is False:
            if config._use_future:
                raise TypeError(
                    f"Invalid keyword argument for {class_name}.save_as(): "
                    "'write_like_original'"
                )

            warnings.warn(
                (
                    "'write_like_original' is deprecated and will be removed in "
                    "v4.0, please use 'enforce_file_format=True' instead"
                ),
                DeprecationWarning,
            )
            enforce_file_format = not write_like_original

        # The default for little_endian is `None` so we can prevent conversion
        #   between little and big endian, but we actually default it to `True`
        #   when `implicit_vr` is used
        if implicit_vr is not None and little_endian is None:
            little_endian = True

        # Disallow conversion between little and big endian encoding
        if self.original_encoding[1] is not None:
            file_meta = getattr(self, "file_meta", {})
            syntax = file_meta.get("TransferSyntaxUID", None)

            use_little: bool | None = None
            try:
                use_little = syntax.is_little_endian
            except (AttributeError, ValueError):
                if little_endian is not None:
                    use_little = little_endian
                elif not config._use_future:
                    use_little = self.is_little_endian

            if use_little is not None and self.original_encoding[1] != use_little:
                raise ValueError(
                    f"'{class_name}.save_as()' cannot be used to convert "
                    "between little and big endian encoding. Please read the "
                    "documentation for filewriter.dcmwrite() if this is what "
                    "you really want to do"
                )

        pydicom.dcmwrite(
            filename,
            self,
            implicit_vr=implicit_vr,
            little_endian=little_endian,
            enforce_file_format=enforce_file_format,
        )

    def ensure_file_meta(self) -> None:
        """Create an empty ``Dataset.file_meta`` if none exists.

        .. versionadded:: 1.2
        """
        # Changed in v2.0 so does not re-assign self.file_meta with getattr()
        if not hasattr(self, "file_meta"):
            self.file_meta = FileMetaDataset()

    def __setattr__(self, name: str, value: Any) -> None:
        """Intercept any attempts to set a value for an instance attribute.

        If name is a DICOM keyword, set the corresponding tag and DataElement.
        Else, set an instance (python) attribute as any other class would do.

        Parameters
        ----------
        name : str
            The keyword for the element you wish to add/change. If
            `name` is not a DICOM element keyword then this will be the
            name of the attribute to be added/changed.
        value
            The value for the attribute to be added/changed.
        """
        # Save time for common Dataset attributes that are not DICOM keywords
        # This check is fast if `name` is a DICOM keyword (first chr is upper)
        # The startswith is needed for `is_implicit_VR`
        if name.startswith("is_") or name.islower():
            if name == "file_meta":
                self._set_file_meta(value)
            else:
                object.__setattr__(self, name, value)
            return

        tag = tag_for_keyword(name)
        if tag is not None:  # successfully mapped name to a tag
            if tag not in self:
                # don't have this tag yet->create the data_element instance
                vr = dictionary_VR(tag)
                elem = DataElement(tag, vr, value)
            else:
                # already have this data_element, just changing its value
                elem = self[tag]
                elem.value = value
            # Now have data_element - store it in this dict
            self[tag] = elem
        elif repeater_has_keyword(name):
            # Check if `name` is repeaters element
            raise ValueError(
                f"'{name}' is a DICOM repeating group element and must be "
                "added using the add() or add_new() methods."
            )
        else:
            # Warn if `name` is camel case but not a keyword
            if _RE_CAMEL_CASE.match(name):
                msg = (
                    f"Camel case attribute '{name}' used which is not in the "
                    "element keyword data dictionary"
                )
                if config.INVALID_KEYWORD_BEHAVIOR == "WARN":
                    warnings.warn(msg)
                elif config.INVALID_KEYWORD_BEHAVIOR == "RAISE":
                    raise ValueError(msg)

            # name not in dicom dictionary - setting a non-dicom instance
            # attribute
            # XXX note if user misspells a dicom data_element - no error!!!
            object.__setattr__(self, name, value)

    def _set_file_meta(self, value: Optional["Dataset"]) -> None:
        """Set the Dataset's File Meta Information attribute."""
        if value is None:
            self.__dict__["file_meta"] = value
            return

        if not isinstance(value, Dataset):
            cls_name = self.__class__.__name__
            raise TypeError(
                f"'{cls_name}.file_meta' must be a 'FileMetaDataset' instance"
            )

        if not isinstance(value, FileMetaDataset):
            # Also validates for only group 2 elements
            value = FileMetaDataset(value)

        self.__dict__["file_meta"] = value

    def __setitem__(self, key: "slice | TagType", elem: _DatasetValue) -> None:
        """Operator for ``Dataset[key] = elem``.

        Parameters
        ----------
        key : int or Tuple[int, int] or str
            The tag for the element to be added to the :class:`Dataset`.
        elem : dataelem.DataElement or dataelem.RawDataElement
            The element to add to the :class:`Dataset`.

        Raises
        ------
        NotImplementedError
            If `key` is a :class:`slice`.
        ValueError
            If the `key` value doesn't match the corresponding
            :attr:`DataElement.tag<pydicom.dataelem.tag>`.
        """
        if isinstance(key, slice):
            raise NotImplementedError(
                "Slicing is not supported when setting Dataset items"
            )

        try:
            key = Tag(key)
        except Exception as exc:
            raise ValueError(
                f"Unable to convert the key '{key}' to an element tag"
            ) from exc

        if not isinstance(elem, DataElement | RawDataElement):
            raise TypeError("Dataset items must be 'DataElement' instances")

        if isinstance(elem.tag, BaseTag):
            elem_tag = elem.tag
        else:
            elem_tag = Tag(elem.tag)

        if key != elem_tag:
            raise ValueError(
                f"The key '{key}' doesn't match the 'DataElement' tag '{elem_tag}'"
            )

        if elem_tag.is_private:
            # See PS 3.5-2008 section 7.8.1 (p. 44) for how blocks are reserved
            logger.debug(f"Setting private tag {elem_tag}")
            private_block = elem_tag.element >> 8
            private_creator_tag = Tag(elem_tag.group, private_block)
            if private_creator_tag in self and elem_tag != private_creator_tag:
                if isinstance(elem, RawDataElement):
                    elem = DataElement_from_raw(elem, self._character_set, self)
                elem.private_creator = self[private_creator_tag].value

        self._dict[elem_tag] = elem

        if elem.VR == VR_.SQ and isinstance(elem, DataElement):
            if not isinstance(elem.value, pydicom.Sequence):
                elem.value = pydicom.Sequence(elem.value)  # type: ignore

            # Update the `_pixel_rep` attribute when nested sequences
            #   containing RawDataElements are being added to a different
            #   dataset
            self._set_pixel_representation(cast(DataElement, elem))

    def _set_pixel_representation(self, elem: DataElement) -> None:
        """Set the `_pixel_rep` attribute for the current dataset and child
        datasets of the sequence element `elem`."""
        # `TAG_PIXREP` is (0028,0103) *Pixel Representation*
        # May be DataElement or RawDataElement, also value may be None
        pr: int | bytes | None = None
        if TAG_PIXREP in self._dict:
            pr = self[TAG_PIXREP].value
        elif hasattr(self, "_pixel_rep"):  # Must be second conditional
            pr = self._pixel_rep

        if pr is not None:
            self._pixel_rep = int(b"\x01" in pr) if isinstance(pr, bytes) else pr

        if elem.VR != VR_.SQ:
            return

        # Note that the value of `_pixel_rep` gets updated as we move
        #   down the tree - the value used to correct ambiguous
        #   elements will be from the closest dataset to that element
        for item in elem.value:
            if TAG_PIXREP in item._dict:
                pr = item._dict[TAG_PIXREP].value
                if pr is not None:
                    item._pixel_rep = (
                        int(b"\x01" in pr) if isinstance(pr, bytes) else pr
                    )
                elif hasattr(self, "_pixel_rep"):
                    item._pixel_rep = self._pixel_rep
            elif hasattr(self, "_pixel_rep"):
                item._pixel_rep = self._pixel_rep

    def _slice_dataset(
        self, start: "TagType | None", stop: "TagType | None", step: int | None
    ) -> list[BaseTag]:
        """Return the element tags in the Dataset that match the slice.

        Parameters
        ----------
        start : int or 2-tuple of int or None
            The slice's starting element tag value, in any format accepted by
            :func:`~pydicom.tag.Tag`.
        stop : int or 2-tuple of int or None
            The slice's stopping element tag value, in any format accepted by
            :func:`~pydicom.tag.Tag`.
        step : int or None
            The slice's step size.

        Returns
        ------
        list of BaseTag
            The tags in the :class:`Dataset` that meet the conditions of the
            slice.
        """
        # Check the starting/stopping Tags are valid when used
        if start is not None:
            start = Tag(start)
        if stop is not None:
            stop = Tag(stop)

        all_tags = sorted(self._dict.keys())
        # If the Dataset is empty, return an empty list
        if not all_tags:
            return []

        # Special case the common situations:
        #   - start and/or stop are None
        #   - step is 1

        if start is None:
            if stop is None:
                # For step=1 avoid copying the list
                return all_tags if step == 1 else all_tags[::step]
            else:  # Have a stop value, get values until that point
                step1_list = list(takewhile(lambda x: x < stop, all_tags))
                return step1_list if step == 1 else step1_list[::step]

        # Have a non-None start value.  Find its index
        i_start = bisect_left(all_tags, start)
        if stop is None:
            return all_tags[i_start::step]

        i_stop = bisect_left(all_tags, stop)
        return all_tags[i_start:i_stop:step]

    def __str__(self) -> str:
        """Handle str(dataset).

        ..versionchanged:: 2.0

            The file meta information was added in its own section,
            if :data:`pydicom.config.show_file_meta` is ``True``

        """
        return self._pretty_str()

    def top(self) -> str:
        """Return a :class:`str` representation of the top level elements."""
        return self._pretty_str(top_level_only=True)

    def trait_names(self) -> list[str]:
        """Return a :class:`list` of valid names for auto-completion code.

        Used in IPython, so that data element names can be found and offered
        for autocompletion on the IPython command line.
        """
        return dir(self)

    def update(self, d: _DatasetType) -> None:
        """Extend :meth:`dict.update` to handle DICOM tags and keywords.

        Parameters
        ----------
        d : dict or Dataset
            The :class:`dict` or :class:`Dataset` to use when updating the
            current object.
        """
        for key, value in list(d.items()):
            if isinstance(key, str):
                setattr(self, key, value)
            else:
                self[Tag(cast(int, key))] = value

    def iterall(self) -> Iterator[DataElement]:
        """Iterate through the :class:`Dataset`, yielding all the elements.

        Unlike ``iter(Dataset)``, this *does* recurse into sequences,
        and so yields all elements as if dataset were "flattened".

        Yields
        ------
        dataelem.DataElement
        """
        for elem in self:
            yield elem
            if elem.VR == VR_.SQ:
                for ds in elem.value:
                    yield from ds.iterall()

    def walk(
        self, callback: Callable[["Dataset", DataElement], None], recursive: bool = True
    ) -> None:
        """Iterate through the :class:`Dataset's<Dataset>` elements and run
        `callback` on each.

        Visit all elements in the :class:`Dataset`, possibly recursing into
        sequences and their items. The `callback` function is called for each
        :class:`~pydicom.dataelem.DataElement` (including elements
        with a VR of 'SQ'). Can be used to perform an operation on certain
        types of elements.

        For example,
        :meth:`~Dataset.remove_private_tags` finds all elements with private
        tags and deletes them.

        The elements will be returned in order of increasing tag number within
        their current :class:`Dataset`.

        Parameters
        ----------
        callback
            A callable function that takes two arguments:

            * a :class:`Dataset`
            * a :class:`~pydicom.dataelem.DataElement` belonging
              to that :class:`Dataset`

        recursive : bool, optional
            Flag to indicate whether to recurse into sequences (default
            ``True``).
        """
        taglist = sorted(self._dict.keys())
        for tag in taglist:
            with tag_in_exception(tag):
                data_element = self[tag]
                callback(self, data_element)  # self = this Dataset
                # 'tag in self' below needed in case callback deleted
                # data_element
                if recursive and tag in self and data_element.VR == VR_.SQ:
                    sequence = data_element.value
                    for dataset in sequence:
                        dataset.walk(callback)

    @classmethod
    def from_json(
        cls: type["Dataset"],
        json_dataset: dict[str, Any] | str | bytes | bytearray,
        bulk_data_uri_handler: Callable[
            [str, str, str], None | str | int | float | bytes
        ]
        | Callable[[str], None | str | int | float | bytes]
        | None = None,
    ) -> "Dataset":
        """Return a :class:`Dataset` from a DICOM JSON Model object.

        .. versionadded:: 1.3

        See the DICOM Standard, Part 18, :dcm:`Annex F<part18/chapter_F.html>`.

        Parameters
        ----------
        json_dataset : dict, str, bytes or bytearray
            :class:`dict`, :class:`str`, :class:`bytes` or :class:`bytearray`
            representing a DICOM Data Set formatted based on the :dcm:`DICOM
            JSON Model<part18/chapter_F.html>`.
        bulk_data_uri_handler : callable, optional
            Callable function that accepts either the tag, vr and
            "BulkDataURI" value or just the "BulkDataURI" value of the JSON
            representation of a data element and returns the actual value of
            that data element (retrieved via DICOMweb WADO-RS). If no
            `bulk_data_uri_handler` is specified (default) then the
            corresponding element will have an "empty" value such as
            ``""``, ``b""`` or ``None`` depending on the `vr` (i.e. the
            Value Multiplicity will be 0).

        Returns
        -------
        Dataset
        """
        if isinstance(json_dataset, str | bytes | bytearray):
            json_dataset = cast(dict[str, Any], json.loads(json_dataset))

        dataset = cls()
        for tag, mapping in json_dataset.items():
            # `tag` is an element tag in uppercase hex format as a str
            # `mapping` is Dict[str, Any] and should have keys 'vr' and at most
            #   one of ('Value', 'BulkDataURI', 'InlineBinary') but may have
            #   none of those if the element's VM is 0
            vr = mapping["vr"]
            unique_value_keys = tuple(
                set(mapping.keys()) & set(jsonrep.JSON_VALUE_KEYS)
            )
            if len(unique_value_keys) == 0:
                value_key = None
                value = [""]
            else:
                value_key = unique_value_keys[0]
                value = mapping[value_key]
            data_element = DataElement.from_json(
                cls, tag, vr, value, value_key, bulk_data_uri_handler
            )
            dataset.add(data_element)
        return dataset

    def to_json_dict(
        self,
        bulk_data_threshold: int = 1024,
        bulk_data_element_handler: Callable[[DataElement], str] | None = None,  # noqa
        suppress_invalid_tags: bool = False,
    ) -> dict[str, Any]:
        """Return a dictionary representation of the :class:`Dataset`
        conforming to the DICOM JSON Model as described in the DICOM
        Standard, Part 18, :dcm:`Annex F<part18/chapter_F.html>`.

        .. versionadded:: 1.4

        Parameters
        ----------
        bulk_data_threshold : int, optional
            Threshold for the length of a base64-encoded binary data element
            above which the element should be considered bulk data and the
            value provided as a URI rather than included inline (default:
            ``1024``). Ignored if no bulk data handler is given.
        bulk_data_element_handler : callable, optional
            Callable function that accepts a bulk data element and returns a
            JSON representation of the data element (dictionary including the
            "vr" key and either the "InlineBinary" or the "BulkDataURI" key).
        suppress_invalid_tags : bool, optional
            Flag to specify if errors while serializing tags should be logged
            and the tag dropped or if the error should be bubbled up.

        Returns
        -------
        dict
            :class:`Dataset` representation based on the DICOM JSON Model.
        """
        json_dataset = {}
        context = config.strict_reading() if suppress_invalid_tags else nullcontext()
        with context:
            for key in self.keys():
                json_key = f"{key:08X}"
                try:
                    data_element = self[key]
                    json_dataset[json_key] = data_element.to_json_dict(
                        bulk_data_element_handler=bulk_data_element_handler,
                        bulk_data_threshold=bulk_data_threshold,
                    )
                except Exception as exc:
                    logger.error(f"Error while processing tag {json_key}")
                    if not suppress_invalid_tags:
                        raise exc

        return json_dataset

    def to_json(
        self,
        bulk_data_threshold: int = 1024,
        bulk_data_element_handler: Callable[[DataElement], str] | None = None,  # noqa
        dump_handler: Callable[[dict[str, Any]], str] | None = None,
        suppress_invalid_tags: bool = False,
    ) -> str:
        """Return a JSON representation of the :class:`Dataset`.

        .. versionadded:: 1.3

        See the DICOM Standard, Part 18, :dcm:`Annex F<part18/chapter_F.html>`.

        Parameters
        ----------
        bulk_data_threshold : int, optional
            Threshold for the length of a base64-encoded binary data element
            above which the element should be considered bulk data and the
            value provided as a URI rather than included inline (default:
            ``1024``). Ignored if no bulk data handler is given.
        bulk_data_element_handler : callable, optional
            Callable function that accepts a bulk data element and returns a
            JSON representation of the data element (dictionary including the
            "vr" key and either the "InlineBinary" or the "BulkDataURI" key).
        dump_handler : callable, optional
            Callable function that accepts a :class:`dict` and returns the
            serialized (dumped) JSON string (by default uses
            :func:`json.dumps`).

            .. note:

                Make sure to use a dump handler that sorts the keys (see
                example below) to create DICOM-conformant JSON.
        suppress_invalid_tags : bool, optional
            Flag to specify if errors while serializing tags should be logged
            and the tag dropped or if the error should be bubbled up.

        Returns
        -------
        str
            :class:`Dataset` serialized into a string based on the DICOM JSON
            Model.

        Examples
        --------
        >>> def my_json_dumps(data):
        ...     return json.dumps(data, indent=4, sort_keys=True)
        >>> ds.to_json(dump_handler=my_json_dumps)
        """
        if dump_handler is None:

            def json_dump(d: Any) -> str:
                return json.dumps(d, sort_keys=True)

            dump_handler = json_dump

        return dump_handler(
            self.to_json_dict(
                bulk_data_threshold,
                bulk_data_element_handler,
                suppress_invalid_tags=suppress_invalid_tags,
            )
        )

    __repr__ = __str__


_FileDataset = TypeVar("_FileDataset", bound="FileDataset")


class FileDataset(Dataset):
    """An extension of :class:`Dataset` to make reading and writing to
    file-like easier.

    Attributes
    ----------
    preamble : str or bytes or None
        The optional DICOM preamble prepended to the :class:`FileDataset`, if
        available.
    file_meta : FileMetaDataset or None
        The Dataset's file meta information as a :class:`FileMetaDataset`,
        if available (``None`` if not present).
        Consists of group ``0x0002`` elements.
    filename : str or None
        The filename that the :class:`FileDataset` was read from (if read from
        file) or ``None`` if the filename is not available (if read from a
        :class:`io.BytesIO` or  similar).
    fileobj_type
        The object type of the file-like the :class:`FileDataset` was read
        from.
    is_implicit_VR : bool
        ``True`` if the dataset encoding is implicit VR, ``False`` otherwise.
    is_little_endian : bool
        ``True`` if the dataset encoding is little endian byte ordering,
        ``False`` otherwise.
    timestamp : float or None
        The modification time of the file the :class:`FileDataset` was read
        from, ``None`` if the modification time is not available.
    """

    def __init__(
        self,
        filename_or_obj: PathType | BinaryIO | DicomFileLike,
        dataset: _DatasetType,
        preamble: bytes | None = None,
        file_meta: Optional["FileMetaDataset"] = None,
        is_implicit_VR: bool = True,
        is_little_endian: bool = True,
    ) -> None:
        """Initialize a :class:`FileDataset` read from a DICOM file.

        Parameters
        ----------
        filename_or_obj : str or PathLike or BytesIO or None
            Full path and filename to the file, memory buffer object, or
            ``None`` if is a :class:`io.BytesIO`.
        dataset : Dataset or dict
            Some form of dictionary, usually a :class:`Dataset` returned from
            :func:`~pydicom.filereader.dcmread`.
        preamble : bytes or str, optional
            The 128-byte DICOM preamble.
        file_meta : FileMetaDataset, optional
            The file meta :class:`FileMetaDataset`, such as the one returned by
            :func:`~pydicom.filereader.read_file_meta_info`, or an empty
            :class:`FileMetaDataset` if no file meta information is in the
            file.
        is_implicit_VR : bool, optional
            ``True`` (default) if implicit VR transfer syntax used; ``False``
            if explicit VR.
        is_little_endian : bool
            ``True`` (default) if little-endian transfer syntax used; ``False``
            if big-endian.
        """
        Dataset.__init__(self, dataset)
        self.preamble = preamble
        self.file_meta: FileMetaDataset = (
            file_meta if file_meta is not None else FileMetaDataset()
        )
        # TODO: Remove in v4.0
        if not config._use_future:
            self._is_implicit_VR: bool = is_implicit_VR
            self._is_little_endian: bool = is_little_endian

        self._read_implicit: bool = is_implicit_VR
        self._read_little: bool = is_little_endian

        filename: str | None = None
        filename_or_obj = path_from_pathlike(filename_or_obj)
        self.fileobj_type: Any = None
        self.filename: PathType | BinaryIO = ""

        if isinstance(filename_or_obj, str):
            filename = filename_or_obj
            self.fileobj_type = open
        elif isinstance(filename_or_obj, io.BufferedReader):
            filename = filename_or_obj.name
            # This is the appropriate constructor for io.BufferedReader
            self.fileobj_type = open
        else:
            # use __class__ python <2.7?;
            # https://docs.python.org/3/reference/datamodel.html
            self.fileobj_type = filename_or_obj.__class__
            if hasattr(filename_or_obj, "name"):
                filename = filename_or_obj.name
            elif hasattr(filename_or_obj, "filename"):
                filename = filename_or_obj.filename
            else:
                # e.g. came from BytesIO or something file-like
                self.filename = filename_or_obj

        self.timestamp = None
        if filename:
            self.filename = filename
            if os.path.exists(filename):
                statinfo = os.stat(filename)
                self.timestamp = statinfo.st_mtime

    def _copy_implementation(self, copy_function: Callable) -> "FileDataset":
        """Implementation of ``__copy__`` and ``__deepcopy__``.
        Sets the filename to ``None`` if it isn't a string,
        and copies all other attributes using `copy_function`.
        """
        copied = self.__class__(
            self.filename,
            self,
            self.preamble,
            self.file_meta,
            self.is_implicit_VR,  # type: ignore[arg-type]
            self.is_little_endian,  # type: ignore[arg-type]
        )
        filename = self.filename
        if filename is not None and not isinstance(filename, str):
            warnings.warn(
                "The 'filename' attribute of the dataset is a "
                "file-like object and will be set to None "
                "in the copied object"
            )
            self.filename = None  # type: ignore[assignment]
        for k, v in self.__dict__.items():
            copied.__dict__[k] = copy_function(v)

        self.filename = filename

        return copied

    def __copy__(self) -> "FileDataset":
        """Return a shallow copy of the file dataset.
        Make sure that the filename is not copied in case it is a file-like
        object.

        Returns
        -------
        FileDataset
            A shallow copy of the file data set.
        """
        return self._copy_implementation(copy.copy)

    def __deepcopy__(self, _: dict[int, Any] | None) -> "FileDataset":
        """Return a deep copy of the file dataset.
        Make sure that the filename is not copied in case it is a file-like
        object.

        Returns
        -------
        FileDataset
            A deep copy of the file data set.
        """
        return self._copy_implementation(copy.deepcopy)


def validate_file_meta(
    file_meta: "FileMetaDataset", enforce_standard: bool = True
) -> None:
    """Validate the *File Meta Information* elements in `file_meta`.

    .. versionchanged:: 1.2

        Moved from :mod:`pydicom.filewriter`.

    Parameters
    ----------
    file_meta : Dataset
        The *File Meta Information* data elements.
    enforce_standard : bool, optional
        If ``False``, then only a check for invalid elements is performed.
        If ``True`` (default), the following elements will be added if not
        already present and the Type 1 elements given a value if empty:

        * (0002,0001) *File Meta Information Version*, Type 1
        * (0002,0012) *Implementation Class UID*, Type 1
        * (0002,0013) *Implementation Version Name*, Type 3

        and the following elements will be checked to ensure they're present
        and have a non-empty value:

        * (0002,0002) *Media Storage SOP Class UID*, Type 1
        * (0002,0003) *Media Storage SOP Instance UID*, Type 1
        * (0002,0010) *Transfer Syntax UID*, Type 1

    Raises
    ------
    ValueError
        If `enforce_standard` is ``True`` and any of the Type 1 *File Meta
        Information* elements are missing from `file_meta` or have no value.
    ValueError
        If any non-Group 2 Elements are present in `file_meta`.
    """
    # Check that no non-Group 2 Elements are present
    for elem in file_meta.elements():
        if elem.tag.group != 0x0002:
            raise ValueError(
                "Only File Meta Information group (0002,eeee) elements may be "
                "present in 'file_meta'."
            )

    if enforce_standard:
        if (
            "FileMetaInformationVersion" not in file_meta
            or file_meta["FileMetaInformationVersion"].is_empty
        ):
            file_meta.FileMetaInformationVersion = b"\x00\x01"

        if (
            "ImplementationClassUID" not in file_meta
            or file_meta["ImplementationClassUID"].is_empty
        ):
            file_meta.ImplementationClassUID = UID(PYDICOM_IMPLEMENTATION_UID)

        if "ImplementationVersionName" not in file_meta:
            file_meta.ImplementationVersionName = (
                f"PYDICOM {'.'.join(__version_info__)}"
            )

        invalid = []
        for tag in [0x00020002, 0x00020003, 0x00020010]:
            if tag not in file_meta or file_meta[tag].is_empty:
                invalid.append(f"{Tag(tag)} {dictionary_description(tag)}")

        if invalid:
            raise AttributeError(
                "Required File Meta Information elements are either missing "
                f"or have an empty value: {', '.join(invalid)}"
            )


class FileMetaDataset(Dataset):
    """Contains a collection (dictionary) of group 2 DICOM Data Elements.

    .. versionadded:: 2.0

    Derived from :class:`~pydicom.dataset.Dataset`, but only allows
    Group 2 (File Meta Information) data elements
    """

    def __init__(self, *args: _DatasetType, **kwargs: Any) -> None:
        """Initialize a FileMetaDataset

        Parameters are as per :class:`Dataset`; this overrides the super class
        only to check that all are group 2 data elements

        Raises
        ------
        ValueError
            If any data elements are not group 2.
        TypeError
            If the passed argument is not a :class:`dict` or :class:`Dataset`
        """
        super().__init__(*args, **kwargs)
        FileMetaDataset.validate(self._dict)

        # Set type hints for the possible contents - VR, Type (1|1C|3)
        self.FileMetaInformationGroupLength: int  # UL, 1
        self.FileMetaInformationVersion: bytes  # OB, 1
        self.MediaStorageSOPClassUID: UID  # UI, 1
        self.MediaStorageSOPInstanceUID: UID  # UI, 1
        self.TransferSyntaxUID: UID  # UI, 1
        self.ImplementationClassUID: UID  # UI, 1
        self.ImplementationVersionName: str | None  # SH, 3
        self.SourceApplicationEntityTitle: str | None  # AE, 3
        self.SendingApplicationEntityTitle: str | None  # AE, 3
        self.ReceivingApplicationEntityTitle: str | None  # AE, 3
        self.SourcePresentationAddress: str | None  # UR, 3
        self.ReceivingPresentationAddress: str | None  # UR, 3
        self.PrivateInformationCreatorUID: UID | None  # UI, 3
        self.PrivateInformation: bytes  # OB, 1C

    @staticmethod
    def validate(init_value: _DatasetType) -> None:
        """Raise errors if initialization value is not acceptable for file_meta

        Parameters
        ----------
        init_value: dict or Dataset
            The tag:data element pairs to initialize a file meta dataset

        Raises
        ------
        TypeError
            If the passed argument is not a :class:`dict` or :class:`Dataset`
        ValueError
            If any data elements passed are not group 2.
        """
        if init_value is None:
            return

        if not isinstance(init_value, Dataset | dict):
            raise TypeError(
                f"Argument must be a dict or Dataset, not {type(init_value)}"
            )

        non_group2 = [str(Tag(tag)) for tag in init_value.keys() if Tag(tag).group != 2]
        if non_group2:
            raise ValueError(
                "File meta datasets may only contain group 2 elements but the "
                f"following elements are present: {', '.join(non_group2)}"
            )

    def __setitem__(self, key: "slice | TagType", value: _DatasetValue) -> None:
        """Override parent class to only allow setting of group 2 elements.

        Parameters
        ----------
        key : int or Tuple[int, int] or str
            The tag for the element to be added to the Dataset.
        value : dataelem.DataElement or dataelem.RawDataElement
            The element to add to the :class:`FileMetaDataset`.

        Raises
        ------
        ValueError
            If `key` is not a DICOM Group 2 tag.
        """

        if isinstance(value.tag, BaseTag):
            tag = value.tag
        else:
            tag = Tag(value.tag)

        if tag.group != 2:
            raise ValueError(
                "Only group 2 data elements are allowed in a FileMetaDataset"
            )

        super().__setitem__(key, value)

    @property
    def _tsyntax_encoding(self) -> tuple[bool, bool] | tuple[None, None]:
        """Return the transfer syntax encoding method (if any)

        Returns
        -------
        tuple[bool, bool] | tuple[None, None]
            If the file meta has a valid public Transfer Syntax UID then
            returns (is implicit, is little), otherwise returns (None, None).
        """
        tsyntax = self.get("TransferSyntaxUID", None)
        if not tsyntax or tsyntax.is_private or not tsyntax.is_transfer_syntax:
            return (None, None)

        return (tsyntax.is_implicit_VR, tsyntax.is_little_endian)


_RE_CAMEL_CASE = re.compile(
    # Ensure mix of upper and lowercase and digits, no underscores
    # If first character is lowercase ensure at least one uppercase char
    "(?P<start>(^[A-Za-z])((?=.+?[A-Z])[A-Za-z0-9]+)|(^[A-Z])([A-Za-z0-9]+))"
    "(?P<last>[A-Za-z0-9][^_]$)"  # Last character is alphanumeric
)
