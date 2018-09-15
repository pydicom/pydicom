# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
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

import inspect  # for __dir__
import io
import os
import os.path
import sys
from bisect import bisect_left
from itertools import takewhile

import pydicom  # for dcmwrite
import pydicom.charset
import pydicom.config
from pydicom import compat
from pydicom._version import __version_info__
from pydicom.charset import default_encoding, convert_encodings
from pydicom.config import logger
from pydicom.datadict import dictionary_VR
from pydicom.datadict import (tag_for_keyword, keyword_for_tag,
                              repeater_has_keyword)
from pydicom.dataelem import DataElement, DataElement_from_raw, RawDataElement
from pydicom.pixel_data_handlers.util import (convert_color_space,
                                              reshape_pixel_array)
from pydicom.tag import Tag, BaseTag, tag_in_exception
from pydicom.uid import (ExplicitVRLittleEndian, ImplicitVRLittleEndian,
                         ExplicitVRBigEndian, PYDICOM_IMPLEMENTATION_UID)

if compat.in_py2:
    from pkgutil import find_loader as have_package
else:
    from importlib.util import find_spec as have_package

have_numpy = True
try:
    import numpy
except ImportError:
    have_numpy = False


class PropertyError(Exception):
    """For AttributeErrors caught in a property, so do not go to __getattr__"""
    #  http://docs.python.org/release/3.1.3/tutorial/errors.html#tut-userexceptions
    pass


class Dataset(dict):
    """A collection (dictionary) of DICOM DataElements.

    Examples
    --------
    Add DataElements to the Dataset (for elements in the DICOM dictionary):

    >>> ds = Dataset()
    >>> ds.PatientName = "CITIZEN^Joan"
    >>> ds.add_new(0x00100020, 'LO', '12345')
    >>> ds[0x0010, 0x0030] = DataElement(0x00100030, 'DA', '20010101')

    Add Sequence DataElement to the Dataset:

    >>> ds.BeamSequence = [Dataset(), Dataset(), Dataset()]
    >>> ds.BeamSequence[0].Manufacturer = "Linac, co."
    >>> ds.BeamSequence[1].Manufacturer = "Linac and Sons, co."
    >>> ds.BeamSequence[2].Manufacturer = "Linac and Daughters, co."

    Add private DataElements to the Dataset:

    >>> ds.add(DataElement(0x0043102b, 'SS', [4, 4, 0, 0]))
    >>> ds.add_new(0x0043102b, 'SS', [4, 4, 0, 0])
    >>> ds[0x0043, 0x102b] = DataElement(0x0043102b, 'SS', [4, 4, 0, 0])

    Updating and retrieving DataElement values:

    >>> ds.PatientName = "CITIZEN^Joan"
    >>> ds.PatientName
    'CITIZEN^Joan"
    >>> ds.PatientName = "CITIZEN^John"
    >>> ds.PatientName
    'CITIZEN^John'

    Retrieving a DataElement's value from a Sequence:

    >>> ds.BeamSequence[0].Manufacturer
    'Linac, co.'
    >>> ds.BeamSequence[1].Manufacturer
    'Linac and Sons, co.'

    Retrieving DataElements:

    >>> elem = ds[0x00100010]
    >>> elem = ds.data_element('PatientName')
    >>> elem
    (0010, 0010) Patient's Name                      PN: 'CITIZEN^Joan'

    Deleting a DataElement from the Dataset:

    >>> del ds.PatientID
    >>> del ds.BeamSequence[1].Manufacturer
    >>> del ds.BeamSequence[2]

    Deleting a private DataElement from the Dataset:

    >>> del ds[0x0043, 0x102b]

    Determining if a DataElement is present in the Dataset:

    >>> 'PatientName' in ds
    True
    >>> 'PatientID' in ds
    False
    >>> (0x0010, 0x0030) in ds
    True
    >>> 'Manufacturer' in ds.BeamSequence[0]
    True

    Iterating through the top level of a Dataset only (excluding Sequences):

    >>> for elem in ds:
    >>>    print(elem)

    Iterating through the entire Dataset (including Sequences):

    >>> for elem in ds.iterall():
    >>>     print(elem)

    Recursively iterate through a Dataset (including Sequences):

    >>> def recurse(ds):
    >>>     for elem in ds:
    >>>         if elem.VR == 'SQ':
    >>>             [recurse(item) for item in elem]
    >>>         else:
    >>>             # Do something useful with each DataElement

    Attributes
    ----------
    default_element_format : str
        The default formatting for string display.
    default_sequence_element_format : str
        The default formatting for string display of sequences.
    indent_chars : str
        For string display, the characters used to indent nested Sequences.
        Default is "   ".
    is_little_endian : bool
        Shall be set before writing with `write_like_original=False`.
        The written dataset (excluding the pixel data) will be written using
        the given endianess.
    is_implicit_VR : bool
        Shall be set before writing with `write_like_original=False`.
        The written dataset will be written using the transfer syntax with
        the given VR handling, e.g LittleEndianImplicit if True,
        and LittleEndianExplicit or BigEndianExplicit (depending on
        `is_little_endian`) if False.
    """
    indent_chars = "   "

    # Python 2: Classes defining __eq__ should flag themselves as unhashable
    __hash__ = None

    def __init__(self, *args, **kwargs):
        """Create a new Dataset instance."""
        self._parent_encoding = kwargs.get('parent_encoding', default_encoding)
        dict.__init__(self, *args)
        self.is_decompressed = False

        # the following read_XXX attributes are used internally to store
        # the properties of the dataset after read from a file

        # set depending on the endianess of the read dataset
        self.read_little_endian = None
        # set depending on the VR handling of the read dataset
        self.read_implicit_vr = None
        # set to the encoding the dataset had originally
        self.read_encoding = None

        self.is_little_endian = None
        self.is_implicit_VR = None

    def __enter__(self):
        """Method invoked on entry to a with statement."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Method invoked on exit from a with statement."""
        # Returning False will re-raise any exceptions that occur
        return False

    def add(self, data_element):
        """Add a DataElement to the Dataset.

        Equivalent to ds[data_element.tag] = data_element

        Parameters
        ----------
        data_element : pydicom.dataelem.DataElement
            The DataElement to add to the Dataset.
        """
        self[data_element.tag] = data_element

    def add_new(self, tag, VR, value):
        """Add a DataElement to the Dataset.

        Parameters
        ----------
        tag
            The DICOM (group, element) tag in any form accepted by
            pydicom.tag.Tag such as [0x0010, 0x0010], (0x10, 0x10), 0x00100010,
            etc.
        VR : str
            The 2 character DICOM value representation (see DICOM standard part
            5, Section 6.2).
        value
            The value of the data element. One of the following:
            * a single string or number
            * a list or tuple with all strings or all numbers
            * a multi-value string with backslash separator
            * for a sequence DataElement, an empty list or list of Dataset
        """
        data_element = DataElement(tag, VR, value)
        # use data_element.tag since DataElement verified it
        self[data_element.tag] = data_element

    def data_element(self, name):
        """Return the DataElement corresponding to the element keyword `name`.

        Parameters
        ----------
        name : str
            A DICOM element keyword.

        Returns
        -------
        pydicom.dataelem.DataElement or None
            For the given DICOM element `keyword`, return the corresponding
            Dataset DataElement if present, None otherwise.
        """
        tag = tag_for_keyword(name)
        # Test against None as (0000,0000) is a possible tag
        if tag is not None:
            return self[tag]
        return None

    def __contains__(self, name):
        """Extend dict.__contains__() to handle DICOM keywords.

        This is called for code like:
        >>> 'SliceLocation' in ds
        True

        Parameters
        ----------
        name : str or int or 2-tuple
            The Element keyword or tag to search for.

        Returns
        -------
        bool
            True if the DataElement is in the Dataset, False otherwise.
        """
        if isinstance(name, (str, compat.text_type)):
            tag = tag_for_keyword(name)
        else:
            try:
                tag = Tag(name)
            except Exception:
                return False
        # Test against None as (0000,0000) is a possible tag
        if tag is not None:
            return dict.__contains__(self, tag)
        else:
            return dict.__contains__(self,
                                     name)  # will no doubt raise an exception

    def decode(self):
        """Apply character set decoding to all DataElements in the Dataset.

        See DICOM PS3.5-2008 6.1.1.
        """
        # Find specific character set. 'ISO_IR 6' is default
        # May be multi-valued, but let pydicom.charset handle all logic on that
        dicom_character_set = self._character_set

        # Shortcut to the decode function in pydicom.charset
        decode_data_element = pydicom.charset.decode

        # Callback for walk(), to decode the chr strings if necessary
        # This simply calls the pydicom.charset.decode function
        def decode_callback(ds, data_element):
            """Callback to decode `data_element`."""
            if data_element.VR == 'SQ':
                for dset in data_element.value:
                    dset._parent_encoding = dicom_character_set
                    dset.decode()
            else:
                decode_data_element(data_element, dicom_character_set)

        self.walk(decode_callback, recursive=False)

    def __delattr__(self, name):
        """Intercept requests to delete an attribute by `name`.

        If `name` is a DICOM keyword:
            Delete the corresponding DataElement from the Dataset.
            >>> del ds.PatientName
        Else:
            Delete the class attribute as any other class would do.
            >>> del ds._is_some_attribute

        Parameters
        ----------
        name : str
            The keyword for the DICOM element or the class attribute to delete.
        """
        # First check if a valid DICOM keyword and if we have that data element
        tag = tag_for_keyword(name)
        if tag is not None and tag in self:
            dict.__delitem__(self,
                             tag)  # direct to dict as we know we have key
        # If not a DICOM name in this dataset, check for regular instance name
        #   can't do delete directly, that will call __delattr__ again
        elif name in self.__dict__:
            del self.__dict__[name]
        # Not found, raise an error in same style as python does
        else:
            raise AttributeError(name)

    def __delitem__(self, key):
        """Intercept requests to delete an attribute by key.

        Examples
        --------
        Indexing using DataElement tag
        >>> ds = Dataset()
        >>> ds.CommandGroupLength = 100
        >>> ds.PatientName = 'CITIZEN^Jan'
        >>> del ds[0x00000000]
        >>> ds
        (0010, 0010) Patient's Name                      PN: 'CITIZEN^Jan'

        Slicing using DataElement tag
        >>> ds = Dataset()
        >>> ds.CommandGroupLength = 100
        >>> ds.SOPInstanceUID = '1.2.3'
        >>> ds.PatientName = 'CITIZEN^Jan'
        >>> del ds[:0x00100000]
        >>> ds
        (0010, 0010) Patient's Name                      PN: 'CITIZEN^Jan'

        Parameters
        ----------
        key
            The key for the attribute to be deleted. If a slice is used then
            the tags matching the slice conditions will be deleted.
        """
        # If passed a slice, delete the corresponding DataElements
        if isinstance(key, slice):
            for tag in self._slice_dataset(key.start, key.stop, key.step):
                del self[tag]
        else:
            # Assume is a standard tag (for speed in common case)
            try:
                dict.__delitem__(self, key)
            # If not a standard tag, than convert to Tag and try again
            except KeyError:
                tag = Tag(key)
                dict.__delitem__(self, tag)

    def __dir__(self):
        """Give a list of attributes available in the Dataset.

        List of attributes is used, for example, in auto-completion in editors
        or command-line environments.
        """
        # Force zip object into a list in case of python3. Also backwards
        # compatible
        meths = set(list(zip(
            *inspect.getmembers(self.__class__, inspect.isroutine)))[0])
        props = set(list(zip(
            *inspect.getmembers(self.__class__, inspect.isdatadescriptor)))[0])
        dicom_names = set(self.dir())
        alldir = sorted(props | meths | dicom_names)
        return alldir

    def dir(self, *filters):
        """Return an alphabetical list of DataElement keywords in the Dataset.

        Intended mainly for use in interactive Python sessions. Only lists the
        DataElement keywords in the current level of the Dataset (i.e. the
        contents of any Sequence elements are ignored).

        Parameters
        ----------
        filters : str
            Zero or more string arguments to the function. Used for
            case-insensitive match to any part of the DICOM keyword.

        Returns
        -------
        list of str
            The matching DataElement keywords in the dataset. If no filters are
            used then all DataElement keywords are returned.
        """
        allnames = [keyword_for_tag(tag) for tag in self.keys()]
        # remove blanks - tags without valid names (e.g. private tags)
        allnames = [x for x in allnames if x]
        # Store found names in a dict, so duplicate names appear only once
        matches = {}
        for filter_ in filters:
            filter_ = filter_.lower()
            match = [x for x in allnames if x.lower().find(filter_) != -1]
            matches.update(dict([(x, 1) for x in match]))
        if filters:
            names = sorted(matches.keys())
            return names
        else:
            return sorted(allnames)

    def __eq__(self, other):
        """Compare `self` and `other` for equality.

        Returns
        -------
        bool
            The result if `self` and `other` are the same class
        NotImplemented
            If `other` is not the same class as `self` then returning
            NotImplemented delegates the result to superclass.__eq__(subclass)
        """
        # When comparing against self this will be faster
        if other is self:
            return True

        if isinstance(other, self.__class__):
            # Compare Elements using values()
            # Convert values() to a list for compatibility between
            #   python 2 and 3
            # Sort values() by element tag
            self_elem = sorted(list(self.values()), key=lambda x: x.tag)
            other_elem = sorted(list(other.values()), key=lambda x: x.tag)
            return self_elem == other_elem

        return NotImplemented

    def get(self, key, default=None):
        """Extend dict.get() to handle DICOM DataElement keywords.

        Parameters
        ----------
        key : str or pydicom.tag.Tag
            The element keyword or Tag or the class attribute name to get.
        default : obj or None
            If the DataElement or class attribute is not present, return
            `default` (default None).

        Returns
        -------
        value
            If `key` is the keyword for a DataElement in the Dataset then
            return the DataElement's value.
        pydicom.dataelem.DataElement
            If `key` is a tag for a DataElement in the Dataset then return the
            DataElement instance.
        value
            If `key` is a class attribute then return its value.
        """
        if isinstance(key, (str, compat.text_type)):
            try:
                return getattr(self, key)
            except AttributeError:
                return default
        else:
            # is not a string, try to make it into a tag and then hand it
            # off to the underlying dict
            if not isinstance(key, BaseTag):
                try:
                    key = Tag(key)
                except Exception:
                    raise TypeError("Dataset.get key must be a string or tag")
        try:
            return_val = self.__getitem__(key)
        except KeyError:
            return_val = default
        return return_val

    def __getattr__(self, name):
        """Intercept requests for Dataset attribute names.

        If `name` matches a DICOM keyword, return the value for the
        DataElement with the corresponding tag.

        Parameters
        ----------
        name
            A DataElement keyword or tag or a class attribute name.

        Returns
        -------
        value
              If `name` matches a DICOM keyword, returns the corresponding
              DataElement's value. Otherwise returns the class attribute's
              value (if present).
        """
        tag = tag_for_keyword(name)
        if tag is None:  # `name` isn't a DICOM element keyword
            # Try the base class attribute getter (fix for issue 332)
            return super(Dataset, self).__getattribute__(name)
        tag = Tag(tag)
        if tag not in self:  # DICOM DataElement not in the Dataset
            # Try the base class attribute getter (fix for issue 332)
            return super(Dataset, self).__getattribute__(name)
        else:
            return self[tag].value

    @property
    def _character_set(self):
        """The Dataset's SpecificCharacterSet value (if present)."""
        char_set = self.get(BaseTag(0x00080005), None)

        if not char_set:
            char_set = self._parent_encoding
        else:
            char_set = convert_encodings(char_set)

        return char_set

    def __getitem__(self, key):
        """Operator for Dataset[key] request.

        Any deferred data elements will be read in and an attempt will be made
        to correct any elements with ambiguous VRs.

        Examples
        --------
        Indexing using DataElement tag
        >>> ds = Dataset()
        >>> ds.SOPInstanceUID = '1.2.3'
        >>> ds.PatientName = 'CITIZEN^Jan'
        >>> ds.PatientID = '12345'
        >>> ds[0x00100010]
        'CITIZEN^Jan'

        Slicing using DataElement tag
        All group 0x0010 elements in the dataset
        >>> ds[0x00100000:0x0011000]
        (0010, 0010) Patient's Name                      PN: 'CITIZEN^Jan'
        (0010, 0020) Patient ID                          LO: '12345'

        All group 0x0002 elements in the dataset
        >>> ds[(0x0002, 0x0000):(0x0003, 0x0000)]

        Parameters
        ----------
        key
            The DICOM (group, element) tag in any form accepted by
            pydicom.tag.Tag such as [0x0010, 0x0010], (0x10, 0x10), 0x00100010,
            etc. May also be a slice made up of DICOM tags.

        Returns
        -------
        pydicom.dataelem.DataElement or pydicom.dataset.Dataset
            If a single DICOM element tag is used then returns the
            corresponding DataElement. If a slice is used then returns a
            Dataset object containing the corresponding DataElements.
        """
        # If passed a slice, return a Dataset containing the corresponding
        #   DataElements
        if isinstance(key, slice):
            return self._dataset_slice(key)

        if isinstance(key, BaseTag):
            tag = key
        else:
            tag = Tag(key)
        data_elem = dict.__getitem__(self, tag)

        if isinstance(data_elem, DataElement):
            return data_elem
        elif isinstance(data_elem, tuple):
            # If a deferred read, then go get the value now
            if data_elem.value is None:
                from pydicom.filereader import read_deferred_data_element
                data_elem = read_deferred_data_element(
                    self.fileobj_type, self.filename, self.timestamp,
                    data_elem)

            if tag != BaseTag(0x00080005):
                character_set = self.read_encoding or self._character_set
            else:
                character_set = default_encoding
            # Not converted from raw form read from file yet; do so now
            self[tag] = DataElement_from_raw(data_elem, character_set)

            # If the Element has an ambiguous VR, try to correct it
            if 'or' in self[tag].VR:
                from pydicom.filewriter import correct_ambiguous_vr_element
                self[tag] = correct_ambiguous_vr_element(
                    self[tag], self, data_elem[6])

        return dict.__getitem__(self, tag)

    def get_item(self, key):
        """Return the raw data element if possible.

        It will be raw if the user has never accessed the value, or set their
        own value. Note if the data element is a deferred-read element,
        then it is read and converted before being returned.

        Parameters
        ----------
        key
            The DICOM (group, element) tag in any form accepted by
            pydicom.tag.Tag such as [0x0010, 0x0010], (0x10, 0x10), 0x00100010,
            etc. May also be a slice made up of DICOM tags.

        Returns
        -------
        pydicom.dataelem.DataElement
        """
        if isinstance(key, slice):
            return self._dataset_slice(key)

        if isinstance(key, BaseTag):
            tag = key
        else:
            tag = Tag(key)
        data_elem = dict.__getitem__(self, tag)
        # If a deferred read, return using __getitem__ to read and convert it
        if isinstance(data_elem, tuple) and data_elem.value is None:
            return self[key]
        return data_elem

    def _dataset_slice(self, slice):
        """Return a slice that has the same properties as the original
        dataset. That includes properties related to endianess and VR handling,
        and the specific character set. No element conversion is done, e.g.
        elements of type RawDataElement are kept.
        """
        tags = self._slice_dataset(slice.start, slice.stop, slice.step)
        dataset = Dataset({tag: self.get_item(tag) for tag in tags})
        dataset.is_little_endian = self.is_little_endian
        dataset.is_implicit_VR = self.is_implicit_VR
        dataset.set_original_encoding(self.read_implicit_vr,
                                      self.read_little_endian,
                                      self.read_encoding)
        return dataset

    @property
    def is_original_encoding(self):
        """Return True if the properties to be used for writing are set and
        have the same value as the ones in the dataset after reading it.
        This includes properties related to endianess, VR handling and the
        specific character set.
        """
        return (self.is_implicit_VR is not None and
                self.is_little_endian is not None and
                self.read_implicit_vr == self.is_implicit_VR and
                self.read_little_endian == self.is_little_endian and
                self.read_encoding == self._character_set)

    def set_original_encoding(self, is_implicit_vr, is_little_endian,
                              character_encoding):
        """Set the values for the original transfer syntax and encoding.
        Can be used for a dataset with raw data elements to enable
        optimized writing (e.g. without decoding the data elements).
        """
        self.read_implicit_vr = is_implicit_vr
        self.read_little_endian = is_little_endian
        self.read_encoding = character_encoding

    def group_dataset(self, group):
        """Return a Dataset containing only DataElements of a certain group.

        Parameters
        ----------
        group : int
            The group part of a DICOM (group, element) tag.

        Returns
        -------
        pydicom.dataset.Dataset
            A dataset instance containing elements of the group specified.
        """
        return self[(group, 0x0000):(group + 1, 0x0000)]

    def __iter__(self):
        """Iterate through the top-level of the Dataset, yielding DataElements.

        >>> for elem in ds:
        >>>     print(elem)

        The DataElements are returned in increasing tag value order.
        Sequence items are returned as a single DataElement, so it is up to the
        calling code to recurse into the Sequence items if desired.

        Yields
        ------
        pydicom.dataelem.DataElement
            The Dataset's DataElements, sorted by increasing tag order.
        """
        # Note this is different than the underlying dict class,
        #        which returns the key of the key:value mapping.
        #   Here the value is returned (but data_element.tag has the key)
        taglist = sorted(self.keys())
        for tag in taglist:
            yield self[tag]

    def elements(self):
        """Iterate through the top-level of the Dataset, yielding DataElements
        or RawDataElements (no conversion done).

        >>> for elem in ds.elements():
        >>>     print(elem)

        The elements are returned in the same way as in __getitem__.

        Yields
        ------
        pydicom.dataelem.DataElement or pydicom.dataelem.RawDataElement
            The Dataset's DataElements, sorted by increasing tag order.
        """
        taglist = sorted(self.keys())
        for tag in taglist:
            yield self.get_item(tag)

    def __ne__(self, other):
        """Compare `self` and `other` for inequality."""
        return not self == other

    def convert_pixel_data(self):
        """Convert the Pixel Data to a numpy array internally.

        Returns
        -------
        None
            Converted pixel data is stored internally in the dataset.

        Notes
        -----
        If the pixel data is in a compressed image format, the data is
        decompressed and any related data elements are changed accordingly.
        """
        # Check if already have converted to a NumPy array
        # Also check if self.PixelData has changed. If so, get new NumPy array
        already_have = True
        if not hasattr(self, "_pixel_array"):
            already_have = False
        elif self._pixel_id != id(self.PixelData):
            already_have = False

        if already_have:
            return

        # Find all possible handlers that support the transfer syntax
        transfer_syntax = self.file_meta.TransferSyntaxUID
        possible_handlers = [hh for hh in pydicom.config.pixel_data_handlers
                             if hh.supports_transfer_syntax(transfer_syntax)]

        # No handlers support the transfer syntax
        if not possible_handlers:
            raise NotImplementedError(
                "Unable to decode pixel data with a transfer syntax UID of "
                "'{0}' ({1}) as there are no pixel data handlers "
                "available that support it. Please see the pydicom "
                "documentation for information on supported transfer syntaxes "
                .format(self.file_meta.TransferSyntaxUID,
                        self.file_meta.TransferSyntaxUID.name)
            )

        # Handlers that both support the transfer syntax and have their
        #   dependencies met
        available_handlers = [hh for hh in possible_handlers if
                              hh.is_available()]

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
                pkg_msg.append(
                    "{} (req. {})"
                    .format(hh.HANDLER_NAME, ', '.join(names))
                )

            raise RuntimeError(msg + ', '.join(pkg_msg))

        last_exception = None
        for handler in available_handlers:
            try:
                # Use the handler to get a 1D numpy array of the pixel data
                arr = handler.get_pixeldata(self)
                self._pixel_array = reshape_pixel_array(self, arr)

                # Some handler/transfer syntax combinations may need to
                #   convert the color space from YCbCr to RGB
                if handler.needs_to_convert_to_RGB(self):
                    self._pixel_array = convert_color_space(self._pixel_array,
                                                            'YBR_FULL',
                                                            'RGB')

                self._pixel_id = id(self.PixelData)

                return
            except Exception as exc:
                logger.debug(
                    "Exception raised by pixel data handler", exc_info=exc
                )
                last_exception = exc

        # The only way to get to this point is if we failed to get the pixel
        #   array because all suitable handlers raised exceptions
        self._pixel_array = None
        self._pixel_id = None

        logger.info(
            "Unable to decode the pixel data using the following handlers: {}."
            "Please see the list of supported Transfer Syntaxes in the "
            "pydicom documentation for alternative packages that might "
            "be able to decode the data"
            .format(", ".join([str(hh) for hh in available_handlers]))
        )

        raise last_exception

    def decompress(self):
        """Decompresses pixel data and modifies the Dataset in-place

        If not a compressed tranfer syntax, then pixel data is converted
        to a numpy array internally, but not returned.

        If compressed pixel data, then is decompressed using an image handler,
        and internal state is updated appropriately:
            - TransferSyntax is updated to non-compressed form
            - is_undefined_length for pixel data is set False

        Returns
        -------
        None

        Raises
        ------
        NotImplementedError
            If the pixel data was originally compressed but file is not
            ExplicitVR LittleEndian as required by Dicom standard
        """
        self.convert_pixel_data()
        self.is_decompressed = True
        # May have been undefined length pixel data, but won't be now
        if 'PixelData' in self:
            self[0x7fe00010].is_undefined_length = False

        # Make sure correct Transfer Syntax is set
        # According to the dicom standard PS3.5 section A.4,
        # all compressed files must have been explicit VR, little endian
        # First check if was a compressed file
        if (hasattr(self, 'file_meta') and
                self.file_meta.TransferSyntaxUID.is_compressed):
            # Check that current file as read does match expected
            if not self.is_little_endian or self.is_implicit_VR:
                msg = ("Current dataset does not match expected ExplicitVR "
                       "LittleEndian transfer syntax from a compressed "
                       "transfer syntax")
                raise NotImplementedError(msg)

            # All is as expected, updated the Transfer Syntax
            self.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    @property
    def pixel_array(self):
        """Return the Pixel Data as a NumPy array.

        Returns
        -------
        numpy.ndarray
            The Pixel Data (7FE0,0010) as a NumPy ndarray.
        """
        self.convert_pixel_data()
        return self._pixel_array

    # Format strings spec'd according to python string formatting options
    #    See http://docs.python.org/library/stdtypes.html#string-formatting-operations # noqa
    default_element_format = "%(tag)s %(name)-35.35s %(VR)s: %(repval)s"
    default_sequence_element_format = "%(tag)s %(name)-35.35s %(VR)s: %(repval)s"  # noqa

    def formatted_lines(
            self,
            element_format=default_element_format,
            sequence_element_format=default_sequence_element_format,
            indent_format=None):
        """Iterate through the Dataset yielding formatted str for each element.

        Parameters
        ----------
        element_format : str
            The string format to use for non-sequence elements. Formatting uses
            the attributes of DataElement. Default is
            "%(tag)s %(name)-35.35s %(VR)s: %(repval)s".
        sequence_element_format : str
            The string format to use for sequence elements. Formatting uses
            the attributes of DataElement. Default is
            "%(tag)s %(name)-35.35s %(VR)s: %(repval)s"
        indent_format : str or None
            Placeholder for future functionality.

        Yields
        ------
        str
            A string representation of a DataElement.
        """
        for data_element in self.iterall():
            # Get all the attributes possible for this data element (e.g.
            #   gets descriptive text name too)
            # This is the dictionary of names that can be used in the format
            #   string
            elem_dict = dict([(x, getattr(data_element, x)()
                               if callable(getattr(data_element, x)) else
                               getattr(data_element, x))
                              for x in dir(data_element)
                              if not x.startswith("_")])
            if data_element.VR == "SQ":
                yield sequence_element_format % elem_dict
            else:
                yield element_format % elem_dict

    def _pretty_str(self, indent=0, top_level_only=False):
        """Return a string of the DataElements in the Dataset, with indented
        levels.

        This private method is called by the __str__() method for handling
        print statements or str(dataset), and the __repr__() method.
        It is also used by top(), therefore the top_level_only flag.
        This function recurses, with increasing indentation levels.

        Parameters
        ----------
        index : int
            The indent level offset (default 0)
        top_level_only : bool
            When True, only create a string for the top level elements, i.e.
            exclude elements within any Sequences (default False).

        Returns
        -------
        str
            A string representation of the Dataset.
        """
        strings = []
        indent_str = self.indent_chars * indent
        nextindent_str = self.indent_chars * (indent + 1)
        for data_element in self:
            with tag_in_exception(data_element.tag):
                if data_element.VR == "SQ":  # a sequence
                    strings.append(indent_str + str(data_element.tag) +
                                   "  %s   %i item(s) ---- " %
                                   (data_element.description(),
                                    len(data_element.value)))
                    if not top_level_only:
                        for dataset in data_element.value:
                            strings.append(dataset._pretty_str(indent + 1))
                            strings.append(nextindent_str + "---------")
                else:
                    strings.append(indent_str + repr(data_element))
        return "\n".join(strings)

    def remove_private_tags(self):
        """Remove all private DataElements in the Dataset."""

        def RemoveCallback(dataset, data_element):
            """Internal method to use as callback to walk() method."""
            if data_element.tag.is_private:
                # can't del self[tag] - won't be right dataset on recursion
                del dataset[data_element.tag]

        self.walk(RemoveCallback)

    def save_as(self, filename, write_like_original=True):
        """Write the Dataset to `filename`.

        Saving a Dataset requires that the Dataset.is_implicit_VR and
        Dataset.is_little_endian attributes exist and are set appropriately. If
        Dataset.file_meta.TransferSyntaxUID is present then it should be set to
        a consistent value to ensure conformance.

        Conformance with DICOM File Format
        ----------------------------------
        If `write_like_original` is False, the Dataset will be stored in the
        DICOM File Format in accordance with DICOM Standard Part 10 Section 7.
        To do so requires that the `Dataset.file_meta` attribute exists and
        contains a Dataset with the required (Type 1) File Meta Information
        Group elements (see pydicom.filewriter.dcmwrite and
        pydicom.filewriter.write_file_meta_info for more information).

        If `write_like_original` is True then the Dataset will be written as is
        (after minimal validation checking) and may or may not contain all or
        parts of the File Meta Information (and hence may or may not be
        conformant with the DICOM File Format).

        Parameters
        ----------
        filename : str or file-like
            Name of file or the file-like to write the new DICOM file to.
        write_like_original : bool
            If True (default), preserves the following information from
            the Dataset (and may result in a non-conformant file):
            - preamble -- if the original file has no preamble then none will
                be written.
            - file_meta -- if the original file was missing any required File
                Meta Information Group elements then they will not be added or
                written.
                If (0002,0000) 'File Meta Information Group Length' is present
                then it may have its value updated.
            - seq.is_undefined_length -- if original had delimiters, write them
                now too, instead of the more sensible length characters
            - is_undefined_length_sequence_item -- for datasets that belong to
                a sequence, write the undefined length delimiters if that is
                what the original had.
            If False, produces a file conformant with the DICOM File Format,
            with explicit lengths for all elements.

        See Also
        --------
        pydicom.filewriter.write_dataset
            Write a DICOM Dataset to a file.
        pydicom.filewriter.write_file_meta_info
            Write the DICOM File Meta Information Group elements to a file.
        pydicom.filewriter.dcmwrite
            Write a DICOM file from a FileDataset instance.
        """
        # Ensure is_little_endian and is_implicit_VR are set
        if self.is_little_endian is None or self.is_implicit_VR is None:
            raise AttributeError(
                "'{0}.is_little_endian' and '{0}.is_implicit_VR' must be "
                "set appropriately before saving.".format(
                    self.__class__.__name__))

        pydicom.dcmwrite(filename, self, write_like_original)

    def ensure_file_meta(self):
        """Create an empty file meta dataset if none exists."""
        self.file_meta = getattr(self, 'file_meta', Dataset())

    def fix_meta_info(self, enforce_standard=True):
        """Ensure the file meta info exists and has the correct values
        for transfer syntax and media storage uids.

        .. warning::

            The transfer syntax for is_implicit_VR = False and
            is_little_endian = True is ambiguous and will therefore not be set.

        Parameters
        ----------
        enforce_standard : boolean
            If True, a check for incorrect and missing elements is performed.
            (see pydicom.filewriter.validate_file_meta)

        """
        self.ensure_file_meta()

        if self.is_little_endian and self.is_implicit_VR:
            self.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        elif not self.is_little_endian and not self.is_implicit_VR:
            self.file_meta.TransferSyntaxUID = ExplicitVRBigEndian
        elif not self.is_little_endian and self.is_implicit_VR:
            raise NotImplementedError("Implicit VR Big Endian is not a "
                                      "supported Transfer Syntax.")

        if 'SOPClassUID' in self:
            self.file_meta.MediaStorageSOPClassUID = self.SOPClassUID
        if 'SOPInstanceUID' in self:
            self.file_meta.MediaStorageSOPInstanceUID = self.SOPInstanceUID
        if enforce_standard:
            validate_file_meta(self.file_meta, enforce_standard=True)

    def __setattr__(self, name, value):
        """Intercept any attempts to set a value for an instance attribute.

        If name is a DICOM keyword, set the corresponding tag and DataElement.
        Else, set an instance (python) attribute as any other class would do.

        Parameters
        ----------
        name : str
            The element keyword for the DataElement you wish to add/change. If
            `name` is not a DICOM element keyword then this will be the
            name of the attribute to be added/changed.
        value
            The value for the attribute to be added/changed.
        """
        tag = tag_for_keyword(name)
        if tag is not None:  # successfully mapped name to a tag
            if tag not in self:
                # don't have this tag yet->create the data_element instance
                VR = dictionary_VR(tag)
                data_element = DataElement(tag, VR, value)
            else:
                # already have this data_element, just changing its value
                data_element = self[tag]
                data_element.value = value
            # Now have data_element - store it in this dict
            self[tag] = data_element
        elif repeater_has_keyword(name):
            # Check if `name` is repeaters element
            raise ValueError('{} is a DICOM repeating group '
                             'element and must be added using '
                             'the add() or add_new() methods.'
                             .format(name))
        else:
            # name not in dicom dictionary - setting a non-dicom instance
            # attribute
            # XXX note if user mis-spells a dicom data_element - no error!!!
            super(Dataset, self).__setattr__(name, value)

    def __setitem__(self, key, value):
        """Operator for Dataset[key] = value.

        Check consistency, and deal with private tags.

        Parameters
        ----------
        key : int
            The tag for the element to be added to the Dataset.
        value : pydicom.dataelem.DataElement or pydicom.dataelem.RawDataElement
            The element to add to the Dataset.

        Raises
        ------
        NotImplementedError
            If `key` is a slice.
        ValueError
            If the `key` value doesn't match DataElement.tag.
        """
        if isinstance(key, slice):
            raise NotImplementedError('Slicing is not supported for setting '
                                      'Dataset elements.')

        # OK if is subclass, e.g. DeferredDataElement
        if not isinstance(value, (DataElement, RawDataElement)):
            raise TypeError("Dataset contents must be DataElement instances.")
        if isinstance(value.tag, BaseTag):
            tag = value.tag
        else:
            tag = Tag(value.tag)
        if key != tag:
            raise ValueError("DataElement.tag must match the dictionary key")

        data_element = value
        if tag.is_private:
            # See PS 3.5-2008 section 7.8.1 (p. 44) for how blocks are reserved
            logger.debug("Setting private tag %r" % tag)
            private_block = tag.elem >> 8
            private_creator_tag = Tag(tag.group, private_block)
            if private_creator_tag in self and tag != private_creator_tag:
                if data_element.is_raw:
                    data_element = DataElement_from_raw(
                        data_element, self._character_set)
                data_element.private_creator = self[private_creator_tag].value
        dict.__setitem__(self, tag, data_element)

    def _slice_dataset(self, start, stop, step):
        """Return the element tags in the Dataset that match the slice.

        Parameters
        ----------
        start : int or 2-tuple of int or None
            The slice's starting element tag value, in any format accepted by
            pydicom.tag.Tag.
        stop : int or 2-tuple of int or None
            The slice's stopping element tag value, in any format accepted by
            pydicom.tag.Tag.
        step : int or None
            The slice's step size.

        Returns
        ------
        list of pydicom.tag.Tag
            The tags in the Dataset that meet the conditions of the slice.
        """
        # Check the starting/stopping Tags are valid when used
        if start is not None:
            start = Tag(start)
        if stop is not None:
            stop = Tag(stop)

        all_tags = sorted(self.keys())
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
        else:
            i_stop = bisect_left(all_tags, stop)
            return all_tags[i_start:i_stop:step]

    def __str__(self):
        """Handle str(dataset)."""
        return self._pretty_str()

    def top(self):
        """Return a str of the Dataset's top level DataElements only."""
        return self._pretty_str(top_level_only=True)

    def trait_names(self):
        """Return a list of valid names for auto-completion code.

        Used in IPython, so that data element names can be found and offered
        for autocompletion on the IPython command line.
        """
        return dir(self)  # only valid python >=2.6, else use self.__dir__()

    def update(self, dictionary):
        """Extend dict.update() to handle DICOM keywords."""
        for key, value in list(dictionary.items()):
            if isinstance(key, (str, compat.text_type)):
                setattr(self, key, value)
            else:
                self[Tag(key)] = value

    def iterall(self):
        """Iterate through the Dataset, yielding all DataElements.

        Unlike Dataset.__iter__, this *does* recurse into sequences,
        and so returns all data elements as if the file were "flattened".

        Yields
        ------
        pydicom.dataelem.DataElement
        """
        for data_element in self:
            yield data_element
            if data_element.VR == "SQ":
                sequence = data_element.value
                for dataset in sequence:
                    for elem in dataset.iterall():
                        yield elem

    def walk(self, callback, recursive=True):
        """Iterate through the DataElements and run `callback` on each.

        Visit all DataElements, possibly recursing into sequences and their
        datasets. The callback function is called for each DataElement
        (including SQ element). Can be used to perform an operation on certain
        types of DataElements. E.g., `remove_private_tags`() finds all private
        tags and deletes them. DataElement`s will come back in DICOM order (by
        increasing tag number within their dataset).

        Parameters
        ----------
        callback
            A callable that takes two arguments:
                * a Dataset
                * a DataElement belonging to that Dataset
        recursive : bool
            Flag to indicate whether to recurse into Sequences.
        """
        taglist = sorted(self.keys())
        for tag in taglist:

            with tag_in_exception(tag):
                data_element = self[tag]
                callback(self, data_element)  # self = this Dataset
                # 'tag in self' below needed in case callback deleted
                # data_element
                if recursive and tag in self and data_element.VR == "SQ":
                    sequence = data_element.value
                    for dataset in sequence:
                        dataset.walk(callback)

    __repr__ = __str__


class FileDataset(Dataset):
    """An extension of Dataset to make reading and writing to file-like easier.

    Attributes
    ----------
    preamble : str or bytes or None
        The optional DICOM preamble prepended to the dataset, if available.
    file_meta : pydicom.dataset.Dataset or None
        The Dataset's file meta information as a Dataset, if available (None if
        not present). Consists of group 0002 elements.
    filename : str or None
        The filename that the dataset was read from (if read from file) or None
        if the filename is not available (if read from a BytesIO or similar).
    fileobj_type
        The object type of the file-like the Dataset was read from.
    is_implicit_VR : bool
        True if the dataset encoding is implicit VR, False otherwise.
    is_little_endian : bool
        True if the dataset encoding is little endian byte ordering, False
        otherwise.
    timestamp : float or None
        The modification time of the file the dataset was read from, None if
        the modification time is not available.
    """

    def __init__(self,
                 filename_or_obj,
                 dataset,
                 preamble=None,
                 file_meta=None,
                 is_implicit_VR=True,
                 is_little_endian=True):
        """Initialize a Dataset read from a DICOM file.

        Parameters
        ----------
        filename_or_obj : str or BytesIO or None
            Full path and filename to the file, memory buffer object, or None
            if is a BytesIO.
        dataset : Dataset or dict
            Some form of dictionary, usually a Dataset from read_dataset().
        preamble : bytes or str, optional
            The 128-byte DICOM preamble.
        file_meta : Dataset, optional
            The file meta info dataset, as returned by _read_file_meta,
            or an empty dataset if no file meta information is in the file.
        is_implicit_VR : bool, optional
            True (default) if implicit VR transfer syntax used; False if
            explicit VR.
        is_little_endian : boolean
            True (default) if little-endian transfer syntax used; False if
            big-endian.
        """
        Dataset.__init__(self, dataset)
        self.preamble = preamble
        self.file_meta = file_meta
        self.is_implicit_VR = is_implicit_VR
        self.is_little_endian = is_little_endian
        if isinstance(filename_or_obj, compat.string_types):
            self.filename = filename_or_obj
            self.fileobj_type = open
        elif isinstance(filename_or_obj, io.BufferedReader):
            self.filename = filename_or_obj.name
            # This is the appropriate constructor for io.BufferedReader
            self.fileobj_type = open
        else:
            # use __class__ python <2.7?;
            # http://docs.python.org/reference/datamodel.html
            self.fileobj_type = filename_or_obj.__class__
            if getattr(filename_or_obj, "name", False):
                self.filename = filename_or_obj.name
            elif getattr(filename_or_obj, "filename",
                         False):  # gzip python <2.7?
                self.filename = filename_or_obj.filename
            else:
                # e.g. came from BytesIO or something file-like
                self.filename = None
        self.timestamp = None
        if self.filename and os.path.exists(self.filename):
            statinfo = os.stat(self.filename)
            self.timestamp = statinfo.st_mtime

    def __eq__(self, other):
        """Compare `self` and `other` for equality.

        Returns
        -------
        bool
            The result if `self` and `other` are the same class
        NotImplemented
            If `other` is not the same class as `self` then returning
            NotImplemented delegates the result to superclass.__eq__(subclass)
        """
        # When comparing against self this will be faster
        if other is self:
            return True

        if isinstance(other, self.__class__):
            # Compare Elements using values() and class members using __dict__
            # Convert values() to a list for compatibility between
            #   python 2 and 3
            # Sort values() by element tag
            self_elem = sorted(list(self.values()), key=lambda x: x.tag)
            other_elem = sorted(list(other.values()), key=lambda x: x.tag)
            return self_elem == other_elem and self.__dict__ == other.__dict__

        return NotImplemented


def validate_file_meta(file_meta, enforce_standard=True):
    """Validates the File Meta Information elements in `file_meta` and
    adds some tags if missing and `enforce_standard` is True.

    Parameters
    ----------
    file_meta : pydicom.dataset.Dataset
        The File Meta Information data elements.
    enforce_standard : bool
        If False, then only a check for invalid elements is performed.
        If True, the following elements will be added if not already present:
            * (0002,0001) FileMetaInformationVersion
            * (0002,0012) ImplementationClassUID
            * (0002,0013) ImplementationVersionName
        and the following elements will be checked:
            * (0002,0002) MediaStorageSOPClassUID
            * (0002,0003) MediaStorageSOPInstanceUID
            * (0002,0010) TransferSyntaxUID

    Raises
    ------
    ValueError
        If `enforce_standard` is True and any of the checked File Meta
        Information elements are missing from `file_meta`.
    ValueError
        If any non-Group 2 Elements are present in `file_meta`.
    """
    # Check that no non-Group 2 Elements are present
    for elem in file_meta.elements():
        if elem.tag.group != 0x0002:
            raise ValueError("Only File Meta Information Group (0002,eeee) "
                             "elements must be present in 'file_meta'.")

    if enforce_standard:
        if 'FileMetaInformationVersion' not in file_meta:
            file_meta.FileMetaInformationVersion = b'\x00\x01'

        if 'ImplementationClassUID' not in file_meta:
            file_meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID

        if 'ImplementationVersionName' not in file_meta:
            file_meta.ImplementationVersionName = (
                'PYDICOM ' + ".".join(str(x) for x in __version_info__))

        # Check that required File Meta Information elements are present
        missing = []
        for element in [0x0002, 0x0003, 0x0010]:
            if Tag(0x0002, element) not in file_meta:
                missing.append(Tag(0x0002, element))
        if missing:
            msg = ("Missing required File Meta Information elements from "
                   "'file_meta':\n")
            for tag in missing:
                msg += '\t{0} {1}\n'.format(tag, keyword_for_tag(tag))
            raise ValueError(msg[:-1])  # Remove final newline
