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
#
# Copyright (c) 2008-2013 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom
#

import inspect  # for __dir__
import io
import os.path
import sys

from pydicom import compat
from pydicom.charset import default_encoding, convert_encodings
from pydicom.datadict import dictionaryVR
from pydicom.datadict import tag_for_name, all_names_for_tag
from pydicom.tag import Tag, BaseTag
from pydicom.dataelem import DataElement, DataElement_from_raw, RawDataElement
from pydicom.uid import NotCompressedPixelTransferSyntaxes, UncompressedPixelTransferSyntaxes
from pydicom.tagtools import tag_in_exception
import pydicom  # for write_file
import pydicom.charset
from pydicom.config import logger
import pydicom.encaps

sys_is_little_endian = (sys.byteorder == 'little')

have_numpy = True
try:
    import numpy
except ImportError:
    have_numpy = False

have_gdcm = True
try:
    import gdcm
except ImportError:
    have_gdcm = False

stat_available = True
try:
    from os import stat
except ImportError:
    stat_available = False
have_jpeg_ls = True

try:
    import jpeg_ls
except ImportError:
    have_jpeg_ls = False

have_pillow = True
try:
    from PIL import Image as PILImg
except ImportError:
    have_pillow = False
    # If that failed, try the alternate import syntax for PIL.
    try:
        import Image as PILImg
    except ImportError:
        # Neither worked, so it's likely not installed.
        have_pillow = False


class PropertyError(Exception):
    """For AttributeErrors caught in a property, so do not go to __getattr__"""
    #  http://docs.python.org/release/3.1.3/tutorial/errors.html#tut-userexceptions
    pass


class Dataset(dict):
    """A collection (dictionary) of DICOM DataElements.

    Examples
    --------
    Add DataElements to the Dataset (for elements in the DICOM dictionary).
    >>> ds = Dataset()
    >>> ds.PatientName = "CITIZEN^Joan"
    >>> ds.add_new(0x00100020, 'LO', '12345')
    >>> ds[0x0010, 0x0030] = DataElement(0x00100030, 'DA', '20010101')

    Add Sequence DataElement to the Dataset
    >>> ds.BeamSequence = [Dataset(), Dataset(), Dataset()]
    >>> ds.BeamSequence[0].Manufacturer = "Linac, co."
    >>> ds.BeamSequence[1].Manufacturer = "Linac and Sons, co."
    >>> ds.BeamSequence[2].Manufacturer = "Linac and Daughters, co."

    Add private DataElements to the Dataset
    >>> ds.add(DataElement(0x0043102b, 'SS', [4, 4, 0, 0]))
    >>> ds.add_new(0x0043102b, 'SS', [4, 4, 0, 0])
    >>> ds[0x0043, 0x102b] = DataElement(0x0043102b, 'SS', [4, 4, 0, 0])

    Updating and retrieving DataElement values
    >>> ds.PatientName = "CITIZEN^Joan"
    >>> ds.PatientName
    'CITIZEN^Joan"
    >>> ds.PatientName = "CITIZEN^John"
    >>> ds.PatientName
    'CITIZEN^John'

    Retrieving a DataElement's value from a Sequence
    >>> ds.BeamSequence[0].Manufacturer
    'Linac, co.'
    >>> ds.BeamSequence[1].Manufacturer
    'Linac and Sons, co.'

    Retrieving DataElements
    >>> elem = ds[0x00100010]
    >>> elem = ds.data_element('PatientName')
    >>> elem
    (0010, 0010) Patient's Name                      PN: 'CITIZEN^Joan'

    Deleting a DataElement from the Dataset
    >>> del ds.PatientID
    >>> del ds.BeamSequence[1].Manufacturer
    >>> del ds.BeamSequence[2]

    Deleting a private DataElement from the Dataset
    >>> del ds[0x0043, 0x102b]

    Determining if a DataElement is present in the Dataset
    >>> 'PatientName' in ds
    True
    >>> 'PatientID' in ds
    False
    >>> 0x00100030 in ds
    True
    >>> 'Manufacturer' in ds.BeamSequence[0]
    True

    Iterating through the top level of a Dataset only (excluding Sequences)
    >>> for elem in ds:
    >>>    print(elem)

    Iterating through the entire Dataset (including Sequences)
    >>> for elem in ds.iterall():
    >>>     print(elem)

    Recursively iterate through a Dataset (including Sequences)
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
    """
    indent_chars = "   "

    # Python 2: Classes which define __eq__ should flag themselves as unhashable
    __hash__ = None

    def __init__(self, *args, **kwargs):
        """Create a new Dataset instance."""
        self._parent_encoding = kwargs.get('parent_encoding', default_encoding)
        dict.__init__(self, *args)

    def __enter__(self):
        """Method invoked on entry to a with statement."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Method invoked on exit from a with statement."""
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
        tag = tag_for_name(name)
        if tag:
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
            tag = tag_for_name(name)
        else:
            try:
                tag = Tag(name)
            except:
                return False
        if tag:
            return dict.__contains__(self, tag)
        else:
            return dict.__contains__(self, name)  # will no doubt raise an exception

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
        tag = tag_for_name(name)
        if tag is not None and tag in self:
            dict.__delitem__(self, tag)  # direct to dict as we know we have key
        # If not a DICOM name in this dataset, check for regular instance name
        #   can't do delete directly, that will call __delattr__ again
        elif name in self.__dict__:
            del self.__dict__[name]
        # Not found, raise an error in same style as python does
        else:
            raise AttributeError(name)

    def __delitem__(self, key):
        """Intercept requests to delete an attribute by key.

        >>> del ds[0x00100010]

        Parameters
        ----------
        key
            The key for the attribute to be deleted.
        """
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
                    *inspect.getmembers(Dataset, inspect.isroutine)))[0])
        props = set(list(zip(
                    *inspect.getmembers(Dataset, inspect.isdatadescriptor)))[0])
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
        allnames = []
        for tag, data_element in self.items():
            allnames.extend(all_names_for_tag(tag))
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
            # Compare Elements using values() and class variables using __dict__
            # Convert values() to a list for compatibility between
            #   python 2 and 3
            return (list(self.values()) == list(other.values()) and
                    self.__dict__ == other.__dict__)

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
            If `key` is the keyword for a DataElement in the Dataset then return
            the DataElement's value.
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
                except:
                    raise TypeError("Dataset.get key must be a string or tag")
        try:
            return_val = self.__getitem__(key)
        except KeyError:
            return_val = default
        return return_val

    def __getattr__(self, name):
        """Intercept requests for unknown Dataset attribute names.

        If the name matches a DICOM keyword, return the value for the
        DataElement with the corresponding tag.

        Parameters
        ----------
        name
            A DataElement keyword or tag or a class attribute name.

        Returns
        -------
        value
            The corresponding DataElement's value.
        """
        # __getattr__ only called if instance cannot find name in self.__dict__
        # So, if name is not a dicom string, then is an error
        tag = tag_for_name(name)
        if tag is None:
            raise AttributeError("Dataset does not have attribute "
                                 "'{0:s}'.".format(name))
        tag = Tag(tag)
        if tag not in self:
            raise AttributeError("Dataset does not have attribute "
                                 "'{0:s}'.".format(name))
        else:  # do have that dicom data_element
            return self[tag].value

    @property
    def _character_set(self):
        """The Dataset's SpecificCharacterSet value (if present)."""
        char_set = self.get('SpecificCharacterSet', None)

        if not char_set:
            char_set = self._parent_encoding
        else:
            char_set = convert_encodings(char_set)

        return char_set

    def __getitem__(self, key):
        """Operator for Dataset[key] request.

        Any deferred data elements will be read in and an attempt will be made
        to correct any elements with ambiguous VRs.

        Parameters
        ----------
        key
            The DICOM (group, element) tag in any form accepted by
            pydicom.tag.Tag such as [0x0010, 0x0010], (0x10, 0x10), 0x00100010,
            etc.

        Returns
        -------
        pydicom.dataelem.DataElement
        """
        tag = Tag(key)
        data_elem = dict.__getitem__(self, tag)

        if isinstance(data_elem, DataElement):
            return data_elem
        elif isinstance(data_elem, tuple):
            # If a deferred read, then go get the value now
            if data_elem.value is None:
                from pydicom.filereader import read_deferred_data_element
                data_elem = read_deferred_data_element(self.fileobj_type,
                                                       self.filename,
                                                       self.timestamp,
                                                       data_elem)

            if tag != (0x08, 0x05):
                character_set = self._character_set
            else:
                character_set = default_encoding
            # Not converted from raw form read from file yet; do so now
            self[tag] = DataElement_from_raw(data_elem, character_set)

            # If the Element has an ambiguous VR, try to correct it
            if 'or' in self[tag].VR:
                from pydicom.filewriter import correct_ambiguous_vr_element
                self[tag] = correct_ambiguous_vr_element(self[tag], self,
                                                         data_elem[6])

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
            etc.

        Returns
        -------
        pydicom.dataelem.DataElement
        """
        tag = Tag(key)
        data_elem = dict.__getitem__(self, tag)
        # If a deferred read, return using __getitem__ to read and convert it
        if isinstance(data_elem, tuple) and data_elem.value is None:
            return self[key]
        return data_elem

    def group_dataset(self, group):
        """Return a Dataset containing only DataElements of a certain group.

        Parameters
        ----------
        group : int
            The group part of a dicom (group, element) tag.

        Returns
        -------
        pydicom.dataset.Dataset
            A dataset instance containing elements of the group specified.
        """
        ds = Dataset()
        ds.update(dict([(tag, data_element) for tag, data_element in self.items()
                        if tag.group == group]))
        return ds

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

    def _is_uncompressed_transfer_syntax(self):
        """Return True if the TransferSyntaxUID is a compressed syntax."""
        # FIXME uses file_meta here, should really only be thus for FileDataset
        return self.file_meta.TransferSyntaxUID in NotCompressedPixelTransferSyntaxes

    def __ne__(self, other):
        """Compare `self` and `other` for inequality."""
        return not (self == other)

    def _pixel_data_numpy(self):
        """If NumPy is available, return an ndarray of the Pixel Data.

        Falls back to GDCM in case of unsupported transfer syntaxes.

        Raises
        ------
        TypeError
            If there is no Pixel Data or not a supported data type.
        ImportError
            If NumPy isn't found, or in the case of fallback, if GDCM isn't
            found.

        Returns
        -------
        numpy.ndarray
            The contents of the Pixel Data element (7FE0,0010) as an ndarray.
        """
        if not self._is_uncompressed_transfer_syntax():
            if not have_gdcm:
                raise NotImplementedError("Pixel Data is compressed in a "
                                          "format pydicom does not yet handle. "
                                          "Cannot return array. Pydicom might "
                                          "be able to convert the pixel data "
                                          "using GDCM if it is installed.")
            elif not self.filename:
                raise NotImplementedError("GDCM is only supported when the "
                                          "dataset has been created with a "
                                          "filename.")
        if not have_numpy:
            msg = "The Numpy package is required to use pixel_array, and " \
                  "numpy could not be imported."
            raise ImportError(msg)
        if 'PixelData' not in self:
            raise TypeError("No pixel data found in this dataset.")

        # There are two cases:
        # 1) uncompressed PixelData -> use numpy
        # 2) compressed PixelData, filename is available and GDCM is
        #    available -> use GDCM
        if self._is_uncompressed_transfer_syntax():
            # Make NumPy format code, e.g. "uint16", "int32" etc
            # from two pieces of info:
            #    self.PixelRepresentation -- 0 for unsigned, 1 for signed;
            #    self.BitsAllocated -- 8, 16, or 32
            format_str = '%sint%d' % (('u', '')[self.PixelRepresentation],
                                      self.BitsAllocated)
            try:
                numpy_dtype = numpy.dtype(format_str)
            except TypeError:
                msg = ("Data type not understood by NumPy: "
                       "format='%s', PixelRepresentation=%d, BitsAllocated=%d")
                raise TypeError(msg % (format_str, self.PixelRepresentation,
                                       self.BitsAllocated))

            if self.is_little_endian != sys_is_little_endian:
                numpy_dtype = numpy_dtype.newbyteorder('S')

            pixel_bytearray = self.PixelData
        elif have_gdcm and self.filename:
            # read the file using GDCM
            # FIXME this should just use self.PixelData instead of self.filename
            #       but it is unclear how this should be achieved using GDCM
            gdcm_image_reader = gdcm.ImageReader()
            gdcm_image_reader.SetFileName(self.filename)
            if not gdcm_image_reader.Read():
                raise TypeError("GDCM could not read DICOM image")
            gdcm_image = gdcm_image_reader.GetImage()

            # determine the correct numpy datatype
            gdcm_numpy_typemap = {
                gdcm.PixelFormat.INT8:     numpy.int8,
                gdcm.PixelFormat.UINT8:    numpy.uint8,
                gdcm.PixelFormat.UINT16:   numpy.uint16,
                gdcm.PixelFormat.INT16:    numpy.int16,
                gdcm.PixelFormat.UINT32:   numpy.uint32,
                gdcm.PixelFormat.INT32:    numpy.int32,
                gdcm.PixelFormat.FLOAT32:  numpy.float32,
                gdcm.PixelFormat.FLOAT64:  numpy.float64
            }
            gdcm_pixel_format = gdcm_image.GetPixelFormat().GetScalarType()
            if gdcm_pixel_format in gdcm_numpy_typemap:
                numpy_dtype = gdcm_numpy_typemap[gdcm_pixel_format]
            else:
                raise TypeError('{0} is not a GDCM supported '
                                'pixel format'.format(gdcm_pixel_format))

            # GDCM returns char* as type str. Under Python 2 `str` are
            # byte arrays by default. Python 3 decodes this to
            # unicode strings by default.
            # The SWIG docs mention that they always decode byte streams
            # as utf-8 strings for Python 3, with the `surrogateescape`
            # error handler configured.
            # Therefore, we can encode them back to their original bytearray
            # representation on Python 3 by using the same parameters.
            pixel_bytearray = gdcm_image.GetBuffer()
            if sys.version_info >= (3, 0):
                pixel_bytearray = pixel_bytearray.encode("utf-8",
                                                         "surrogateescape")

            # if GDCM indicates that a byte swap is in order, make
            #   sure to inform numpy as well
            if gdcm_image.GetNeedByteSwap():
                numpy_dtype = numpy_dtype.newbyteorder('S')

            # Here we need to be careful because in some cases, GDCM reads a
            # buffer that is too large, so we need to make sure we only include
            # the first n_rows * n_columns * dtype_size bytes.

            n_bytes = self.Rows * self.Columns * numpy.dtype(numpy_dtype).itemsize

            if len(pixel_bytearray) > n_bytes:

                # We make sure that all the bytes after are in fact zeros
                padding = pixel_bytearray[n_bytes:]
                if numpy.any(numpy.fromstring(padding, numpy.byte)):
                    pixel_bytearray = pixel_bytearray[:n_bytes]
                else:
                    # We revert to the old behavior which should then result
                    #   in a Numpy error later on.
                    pass

        pixel_array = numpy.fromstring(pixel_bytearray, dtype=numpy_dtype)

        # Note the following reshape operations return a new *view* onto
        #   pixel_array, but don't copy the data
        if 'NumberOfFrames' in self and self.NumberOfFrames > 1:
            if self.SamplesPerPixel > 1:
                # TODO: Handle Planar Configuration attribute
                assert self.PlanarConfiguration == 0
                pixel_array = pixel_array.reshape(self.NumberOfFrames,
                                                  self.Rows, self.Columns,
                                                  self.SamplesPerPixel)
            else:
                pixel_array = pixel_array.reshape(self.NumberOfFrames,
                                                  self.Rows, self.Columns)
        else:
            if self.SamplesPerPixel > 1:
                if self.BitsAllocated == 8:
                    if self.PlanarConfiguration == 0:
                        pixel_array = pixel_array.reshape(self.Rows,
                                                          self.Columns,
                                                          self.SamplesPerPixel)
                    else:
                        pixel_array = pixel_array.reshape(self.SamplesPerPixel,
                                                          self.Rows,
                                                          self.Columns)
                        pixel_array = pixel_array.transpose(1, 2, 0)
                else:
                    raise NotImplementedError("This code only handles "
                                              "SamplesPerPixel > 1 if Bits "
                                              "Allocated = 8")
            else:
                pixel_array = pixel_array.reshape(self.Rows, self.Columns)
        return pixel_array

    def _compressed_pixel_data_numpy(self):
        """Return a NumPy array of the Pixel Data.

        NumPy is a numerical package for python. It is used if available.

        Returns
        -------
        numpy.ndarray
            The Pixel Data as an array.

        Raises
        ------
        TypeError
            If no Pixel Data element in the dataset.
        ImportError
            If cannot import numpy.
        """
        if 'PixelData' not in self:
            raise TypeError("No pixel data found in this dataset.")

        if not have_numpy:
            msg = "The Numpy package is required to use pixel_array, and " \
                  "numpy could not be imported."
            raise ImportError(msg)

        # determine the type used for the array
        need_byteswap = (self.is_little_endian != sys_is_little_endian)

        # Make NumPy format code, e.g. "uint16", "int32" etc
        # from two pieces of info:
        #    self.PixelRepresentation -- 0 for unsigned, 1 for signed;
        #    self.BitsAllocated -- 8, 16, or 32
        format_str = '%sint%d' % (('u', '')[self.PixelRepresentation],
                                  self.BitsAllocated)
        try:
            numpy_format = numpy.dtype(format_str)
        except TypeError:
            msg = ("Data type not understood by NumPy: "
                   "format='%s', PixelRepresentation=%d, BitsAllocated=%d")
            raise TypeError(msg % (format_str, self.PixelRepresentation,
                                   self.BitsAllocated))
        if self.file_meta.TransferSyntaxUID in pydicom.uid.PILSupportedCompressedPixelTransferSyntaxes:
            UncompressedPixelData = self._get_PIL_supported_compressed_pixeldata()
        elif self.file_meta.TransferSyntaxUID in pydicom.uid.JPEGLSSupportedCompressedPixelTransferSyntaxes:
            UncompressedPixelData = self._get_jpeg_ls_supported_compressed_pixeldata()
        else:
            msg = "The transfer syntax {0} is not currently supported.".format(self.file_meta.TransferSyntaxUID)
            raise NotImplementedError(msg)

        # Have correct Numpy format, so create the NumPy array
        arr = numpy.fromstring(UncompressedPixelData, numpy_format)

        # XXX byte swap - may later handle this in read_file!!?
        if need_byteswap:
            arr.byteswap(True)  # True means swap in-place, don't make a new copy
        # Note the following reshape operations return a new *view* onto arr, but don't copy the data
        if 'NumberOfFrames' in self and self.NumberOfFrames > 1:
            if self.SamplesPerPixel > 1:
                arr = arr.reshape(self.NumberOfFrames, self.Rows, self.Columns,
                                  self.SamplesPerPixel)
            else:
                arr = arr.reshape(self.NumberOfFrames, self.Rows, self.Columns)
        else:
            if self.SamplesPerPixel > 1:
                if self.BitsAllocated == 8:
                    if self.PlanarConfiguration == 0:
                        arr = arr.reshape(self.Rows, self.Columns,
                                          self.SamplesPerPixel)
                    else:
                        arr = arr.reshape(self.SamplesPerPixel, self.Rows,
                                          self.Columns)
                        arr = arr.transpose(1, 2, 0)
                else:
                    raise NotImplementedError("This code only handles "
                                              "SamplesPerPixel > 1 if Bits "
                                              "Allocated = 8")
            else:
                arr = arr.reshape(self.Rows, self.Columns)
        if (self.file_meta.TransferSyntaxUID in pydicom.uid.JPEG2000CompressedPixelTransferSyntaxes and self.BitsStored == 16):
            # WHY IS THIS EVEN NECESSARY??
            arr &= 0x7FFF
        return arr

    def _get_PIL_supported_compressed_pixeldata(self):
        """Use PIL to decompress compressed Pixel Data.

        Returns
        -------
        bytes or str
            The decompressed Pixel Data

        Raises
        ------
        ImportError
            If PIL is not available.
        NotImplementedError
            If unable to decompress the Pixel Data.
        """
        if not have_pillow:
            msg = "The pillow package is required to use pixel_array for " \
                  "this transfer syntax {0}, and pillow could not be " \
                  "imported.".format(self.file_meta.TransferSyntaxUID)
            raise ImportError(msg)
        # decompress here
        if self.file_meta.TransferSyntaxUID in pydicom.uid.JPEGLossyCompressedPixelTransferSyntaxes:
            if self.BitsAllocated > 8:
                raise NotImplementedError("JPEG Lossy only supported if Bits "
                                          "Allocated = 8")
            generic_jpeg_file_header = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00\x01\x00\x01\x00\x00'
            frame_start_from = 2
        elif self.file_meta.TransferSyntaxUID in pydicom.uid.JPEG2000CompressedPixelTransferSyntaxes:
            generic_jpeg_file_header = b''
            # generic_jpeg_file_header = b'\x00\x00\x00\x0C\x6A\x50\x20\x20\x0D\x0A\x87\x0A'
            frame_start_from = 0
        else:
            generic_jpeg_file_header = b''
            frame_start_from = 0
        try:
            UncompressedPixelData = ''
            if 'NumberOfFrames' in self and self.NumberOfFrames > 1:
                # multiple compressed frames
                CompressedPixelDataSeq = pydicom.encaps.decode_data_sequence(self.PixelData)
                for frame in CompressedPixelDataSeq:
                    data = generic_jpeg_file_header + frame[frame_start_from:]
                    fio = io.BytesIO(data)
                    try:
                        decompressed_image = PILImg.open(fio)
                    except IOError as e:
                        raise NotImplementedError(e.message)
                    UncompressedPixelData += decompressed_image.tobytes()
            else:
                # single compressed frame
                UncompressedPixelData = pydicom.encaps.defragment_data(self.PixelData)
                UncompressedPixelData = generic_jpeg_file_header + UncompressedPixelData[frame_start_from:]
                try:
                    fio = io.BytesIO(UncompressedPixelData)
                    decompressed_image = PILImg.open(fio)
                except IOError as e:
                    raise NotImplementedError(e.message)
                UncompressedPixelData = decompressed_image.tobytes()
        except:
            raise
        return UncompressedPixelData

    def _get_jpeg_ls_supported_compressed_pixeldata(self):
        """Use jpeg_ls to decompress compressed Pixel Data.

        Returns
        -------
        bytes or str
            The decompressed Pixel Data

        Raises
        ------
        ImportError
            If jpeg_ls is not available.
        """
        if not have_jpeg_ls:
            msg = "The jpeg_ls package is required to use pixel_array for " \
                  "this transfer syntax {0}, and jpeg_ls could not be " \
                  "imported.".format(self.file_meta.TransferSyntaxUID)
            raise ImportError(msg)
        # decompress here
        UncompressedPixelData = ''
        if 'NumberOfFrames' in self and self.NumberOfFrames > 1:
            # multiple compressed frames
            CompressedPixelDataSeq = pydicom.encaps.decode_data_sequence(self.PixelData)
            # print len(CompressedPixelDataSeq)
            for frame in CompressedPixelDataSeq:
                decompressed_image = jpeg_ls.decode(numpy.fromstring(frame, dtype=numpy.uint8))
                UncompressedPixelData += decompressed_image.tobytes()
        else:
            # single compressed frame
            CompressedPixelData = pydicom.encaps.defragment_data(self.PixelData)
            decompressed_image = jpeg_ls.decode(numpy.fromstring(CompressedPixelData, dtype=numpy.uint8))
            UncompressedPixelData = decompressed_image.tobytes()
        return UncompressedPixelData

    # Use by pixel_array property
    def _get_pixel_array(self):
        """Convert the Pixel Data to a numpy array.

        Returns
        -------
        numpy.ndarray
            The array containing the Pixel Data.
        """
        # Check if already have converted to a NumPy array
        # Also check if self.PixelData has changed. If so, get new NumPy array
        already_have = True
        if not hasattr(self, "_pixel_array"):
            already_have = False
        elif self._pixel_id != id(self.PixelData):
            already_have = False
        if not already_have and not self._is_uncompressed_transfer_syntax():
            try:
                # print("Pixel Data is compressed")
                self._pixel_array = self._compressed_pixel_data_numpy()
                self._pixel_id = id(self.PixelData)  # is this guaranteed to work if memory is re-used??
                return self._pixel_array
            except IOError:
                logger.info("Pillow or JPLS did not support this transfer syntax")
        if not already_have:
            self._pixel_array = self._pixel_data_numpy()
            self._pixel_id = id(self.PixelData)  # is this guaranteed to work if memory is re-used??
        return self._pixel_array

    @property
    def pixel_array(self):
        """Return the Pixel Data as a NumPy array.

        Returns
        -------
        numpy.ndarray
            The Pixel Data (7FE0,0010) as a NumPy ndarray.
        """
        try:
            return self._get_pixel_array()
        except AttributeError:
            t, e, tb = sys.exc_info()
            val = PropertyError("AttributeError in pixel_array property: " +
                                e.args[0])
            compat.reraise(PropertyError, val, tb)

    # Format strings spec'd according to python string formatting options
    #    See http://docs.python.org/library/stdtypes.html#string-formatting-operations
    default_element_format = "%(tag)s %(name)-35.35s %(VR)s: %(repval)s"
    default_sequence_element_format = "%(tag)s %(name)-35.35s %(VR)s: %(repval)s"

    def formatted_lines(self, element_format=default_element_format,
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
            # This is the dictionary of names that can be used in the format string
            elem_dict = dict([(x, getattr(data_element, x)()
                               if callable(getattr(data_element, x))
                               else getattr(data_element, x))
                              for x in dir(data_element) if not x.startswith("_")])
            if data_element.VR == "SQ":
                yield sequence_element_format % elem_dict
            else:
                yield element_format % elem_dict

    def _pretty_str(self, indent=0, top_level_only=False):
        """Return a string of the DataElements in the Dataset, with indented levels.

        This private method is called by the __str__() method for handling
        print statements or str(dataset), and the __repr__() method.
        It is also used by top(), which is the reason for the top_level_only flag.
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
                if data_element.VR == "SQ":   # a sequence
                    strings.append(indent_str + str(data_element.tag) +
                                   "  %s   %i item(s) ---- "
                                   %(data_element.description(),
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
        """Write the Dataset to a file.

        When saving a new Dataset, you need to add the following attributes:
        -file_meta : Dataset or None
        -is_implicit_VR : bool
        -is_little_endian : bool
        -preamble : bytes (optional)
        When saving a FileDataset that has been read from file these attributes
        should already be present.

        Parameters
        ----------
        filename : str
            Name of file to save new DICOM file to.
        write_like_original : bool
            If True (default), preserves the following information from
            the Dataset:
            -preamble -- if no preamble in read file, than not used here
            -file_meta -- if writer did not do file meta information,
                then don't write here either
            -seq.is_undefined_length -- if original had delimiters, write them
                now too, instead of the more sensible length characters.
            -is_undefined_length_sequence_item -- for datasets that belong to a
                sequence, write the undefined length delimiters if that is
                what the original had.
            If False, produces a "nicer" DICOM file for other readers,
                where all lengths are explicit.

        See Also
        --------
        pydicom.filewriter.write_file
            Write a DICOM file from a FileDataset instance.

        Notes
        -----
        Set Dataset.preamble if you want something other than 128 0-bytes.
        If the dataset was read from an existing DICOM file, then its preamble
        was stored at read time. It is up to the user to ensure the preamble is
        still correct for its purposes.

        If there is no 'Transfer Syntax UID' element in the file_meta Dataset,
        then set Dataset.is_implicit_VR (bool) and Dataset.is_little_endian
        (bool) to automatically determine the transfer syntax used to write the
        file.
        """
        pydicom.write_file(filename, self, write_like_original)

    def __setattr__(self, name, value):
        """Intercept any attempts to set a value for an instance attribute.

        If name is a DICOM descriptive string (cleaned with CleanName), then
        set the corresponding tag and DataElement.
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
        tag = tag_for_name(name)
        if tag is not None:  # successfully mapped name to a tag
            if tag not in self:  # don't have this tag yet->create the data_element instance
                VR = dictionaryVR(tag)
                data_element = DataElement(tag, VR, value)
            else:  # already have this data_element, just changing its value
                data_element = self[tag]
                data_element.value = value
            # Now have data_element - store it in this dict
            self[tag] = data_element
        else:  # name not in dicom dictionary - setting a non-dicom instance attribute
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
        ValueError
            If the `key` value doesn't match DataElement.tag.
        """
        # OK if is subclass, e.g. DeferredDataElement
        if not isinstance(value, (DataElement, RawDataElement)):
            raise TypeError("Dataset contents must be DataElement instances.")
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
                if isinstance(data_element, RawDataElement):
                    data_element = DataElement_from_raw(data_element,
                                                        self._character_set)
                data_element.private_creator = self[private_creator_tag].value
        dict.__setitem__(self, tag, data_element)

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
                # 'tag in self' below needed in case callback deleted data_element
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
    def __init__(self, filename_or_obj, dataset, preamble=None, file_meta=None,
                 is_implicit_VR=True, is_little_endian=True):
        """Initialize a Dataset read from a DICOM file.

        Parameters
        ----------
        filename_or_obj : str or None
            Full path and filename to the file. Use None if is a BytesIO.
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
            self.fileobj_type = filename_or_obj.__class__  # use __class__ python <2.7?; http://docs.python.org/reference/datamodel.html
            if getattr(filename_or_obj, "name", False):
                self.filename = filename_or_obj.name
            elif getattr(filename_or_obj, "filename", False):  # gzip python <2.7?
                self.filename = filename_or_obj.filename
            else:
                self.filename = None  # e.g. came from BytesIO or something file-like
        self.timestamp = None
        if stat_available and self.filename and os.path.exists(self.filename):
            statinfo = os.stat(self.filename)
            self.timestamp = statinfo.st_mtime
