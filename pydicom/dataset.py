# dataset.py
"""Module for Dataset class

Overview of Dicom object model:

Dataset(derived class of Python's dict class)
   contains DataElement instances (DataElement is a class with tag, VR, value)
     the value can be a Sequence instance
        (Sequence is derived from Python's list),
     or just a regular value like a number, string, etc.,
     or a list of regular values, e.g. a 3d coordinate
            Sequence's are a list of Datasets (note recursive nature here)

"""
#
# Copyright (c) 2008-2013 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com
#
import sys
from sys import byteorder
sys_is_little_endian = (byteorder == 'little')
import logging
logger = logging.getLogger('pydicom')
import inspect  # for __dir__

from dicom.charset import default_encoding, convert_encodings
from dicom.datadict import dictionaryVR
from dicom.datadict import tag_for_name, all_names_for_tag
from dicom.tag import Tag, BaseTag
from dicom.dataelem import DataElement, DataElement_from_raw, RawDataElement
from dicom.UID import NotCompressedPixelTransferSyntaxes
from dicom.tagtools import tag_in_exception
import os.path

import io

import dicom  # for write_file
import dicom.charset

have_numpy = True
try:
    import numpy
except:
    have_numpy = False

stat_available = True
try:
    from os import stat
except:
    stat_available = False


class PropertyError(Exception):
    """For AttributeErrors caught in a property, so do not go to __getattr__"""
    #  http://docs.python.org/release/3.1.3/tutorial/errors.html#tut-userexceptions
    pass


class Dataset(dict):
    """A collection (dictionary) of Dicom `DataElement` instances.

    Example of two ways to retrieve or set values:

    1. dataset[0x10, 0x10].value --> patient's name
    2. dataset.PatientName --> patient's name

    Example (2) uses DICOM "keywords", defined starting in 2011 standard.
    PatientName is not actually a member of the object, but unknown member
    requests are checked against the DICOM dictionary. If the name matches a
    DicomDictionary descriptive string, the corresponding tag is used
    to look up or set the `DataElement` instance's value.

    :attribute indent_chars: for string display, the characters used to indent
       nested Data Elements (e.g. sequence items). Default is three spaces.

    """
    indent_chars = "   "

    def __init__(self, *args, **kwargs):
        self._parent_encoding = kwargs.get('parent_encoding', default_encoding)
        dict.__init__(self, *args)

    def add(self, data_element):
        """Equivalent to dataset[data_element.tag] = data_element."""
        self[data_element.tag] = data_element

    def add_new(self, tag, VR, value):
        """Create a new DataElement instance and add it to this Dataset."""
        data_element = DataElement(tag, VR, value)
        # use data_element.tag since DataElement verified it
        self[data_element.tag] = data_element

    def data_element(self, name):
        """Return the full data_element instance for the given descriptive name

        :param name: a DICOM keyword
        :returns: a DataElement instance in this dataset with the given name
                If the tag for that name is not found, returns None
        """
        tag = tag_for_name(name)
        if tag:
            return self[tag]
        return None

    def __contains__(self, name):
        """Extend dict.__contains__() to handle DICOM keywords.

        This is called for code like: ``if 'SliceLocation' in dataset``.

        """
        if isinstance(name, (str, unicode)):
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
        """Apply character set decoding to all data elements.

        See DICOM PS3.5-2008 6.1.1.
        """
        # Find specific character set. 'ISO_IR 6' is default
        # May be multi-valued, but let dicom.charset handle all logic on that
        dicom_character_set = self._character_set

        # Shortcut to the decode function in dicom.charset
        decode_data_element = dicom.charset.decode

        # Callback for walk(), to decode the chr strings if necessary
        # This simply calls the dicom.charset.decode function
        def decode_callback(ds, data_element):
            if data_element.VR == 'SQ':
                [dset.decode() for dset in data_element.value]
            else:
                decode_data_element(data_element, dicom_character_set)

        self.walk(decode_callback, recursive=False)

    def __delattr__(self, name):
        """Intercept requests to delete an attribute by name, e.g. del ds.name

        If name is a DICOM keyword, then delete the corresponding tag
           and data_element. Else, delete an instance (python) attribute
           as any other class would do

        """
        # First check if a valid DICOM keyword and if we have that data element
        tag = tag_for_name(name)
        if tag and tag in self:
            dict.__delitem__(self, tag)  # direct to dict as we know we have key
        # If not a DICOM name in this dataset, check for regular instance name
        #   can't do delete directly, that will call __delattr__ again
        elif name in self.__dict__:
            del self.__dict__[name]
        # Not found, raise an error in same style as python does
        else:
            raise AttributeError(name)

    def __delitem__(self, key):
        """Intercept requests to delete an attribute by key, e.g. del ds[tag]"""
        # Assume is a standard tag (for speed in common case)
        try:
            dict.__delitem__(self, key)
        # If not a standard tag, than convert to Tag and try again
        except KeyError:
            tag = Tag(key)
            dict.__delitem__(self, tag)

    def __dir__(self):
        """Give a list of attributes available in the dataset

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
        """Return an alphabetical list of data_element keywords in the dataset.

        Intended mainly for use in interactive Python sessions.
        :param filters: zero or more string arguments to the function. Used for
                        case-insensitive match to any part of the DICOM name.
        :returns: All data_element names in this dataset matching the filters.
                If no filters, return all DICOM keywords in the dataset
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

    def get(self, key, default=None):
        """Extend dict.get() to handle DICOM keywords"""
        if isinstance(key, (str, unicode)):
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
        """Intercept requests for unknown Dataset python-attribute names.

        If the name matches a Dicom keyword,
        return the value for the data_element with the corresponding tag.

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
        """
        :return:
        """
        char_set = self.get('SpecificCharacterSet', None)

        if not char_set:
            char_set = self._parent_encoding
        else:
            char_set = convert_encodings(char_set)

        return char_set

    def __getitem__(self, key):
        """Operator for dataset[key] request."""
        tag = Tag(key)
        data_elem = dict.__getitem__(self, tag)

        if isinstance(data_elem, DataElement):
            return data_elem
        elif isinstance(data_elem, tuple):
            # If a deferred read, then go get the value now
            if data_elem.value is None:
                from dicom.filereader import read_deferred_data_element
                data_elem = read_deferred_data_element(self.fileobj_type,
                                                       self.filename, self.timestamp, data_elem)

            if tag != (0x08, 0x05):
                character_set = self._character_set
            else:
                character_set = default_encoding
            # Not converted from raw form read from file yet; do so now
            self[tag] = DataElement_from_raw(data_elem, character_set)
        return dict.__getitem__(self, tag)

    def get_item(self, key):
        """Return the raw data element if possible.
        It will be raw if the user has never accessed the value,
        or set their own value.
        Note if the data element is a deferred-read element,
        then it is read and converted before being returned
        """
        tag = Tag(key)
        data_elem = dict.__getitem__(self, tag)
        # If a deferred read, return using __getitem__ to read and convert it
        if isinstance(data_elem, tuple) and data_elem.value is None:
            return self[key]
        return data_elem

    def group_dataset(self, group):
        """Return a Dataset containing only data_elements of a certain group.

        :param group:  the group part of a dicom (group, element) tag.
        :returns:  a dataset instance containing data elements of the group
                    specified
        """
        ds = Dataset()
        ds.update(dict([(tag, data_element) for tag, data_element in self.items()
                        if tag.group == group]))
        return ds

    def __iter__(self):
        """Method to iterate through the dataset, returning data_elements.
        e.g.:
        for data_element in dataset:
            do_something...
        The data_elements are returned in DICOM order,
        i.e. in increasing order by tag value.
        Sequence items are returned as a single data_element; it is up to the
           calling code to recurse into the Sequence items if desired
        """
        # Note this is different than the underlying dict class,
        #        which returns the key of the key:value mapping.
        #   Here the value is returned (but data_element.tag has the key)
        taglist = sorted(self.keys())
        for tag in taglist:
            yield self[tag]

    def _pixel_data_numpy(self):
        """Return a NumPy array of the pixel data.

        NumPy is a numerical package for python. It is used if available.

        :raises TypeError: if no pixel data in this dataset.
        :raises ImportError: if cannot import numpy.

        """
        if 'PixelData' not in self:
            raise TypeError("No pixel data found in this dataset.")

        if not have_numpy:
            msg = "The Numpy package is required to use pixel_array, and numpy could not be imported.\n"
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
            raise TypeError(msg % (numpy_format, self.PixelRepresentation,
                            self.BitsAllocated))

        # Have correct Numpy format, so create the NumPy array
        arr = numpy.fromstring(self.PixelData, numpy_format)

        # XXX byte swap - may later handle this in read_file!!?
        if need_byteswap:
            arr.byteswap(True)  # True means swap in-place, don't make a new copy
        # Note the following reshape operations return a new *view* onto arr, but don't copy the data
        if 'NumberOfFrames' in self and self.NumberOfFrames > 1:
            if self.SamplesPerPixel > 1:
                arr = arr.reshape(self.SamplesPerPixel, self.NumberOfFrames, self.Rows, self.Columns)
            else:
                arr = arr.reshape(self.NumberOfFrames, self.Rows, self.Columns)
        else:
            if self.SamplesPerPixel > 1:
                if self.BitsAllocated == 8:
                    arr = arr.reshape(self.SamplesPerPixel, self.Rows, self.Columns)
                else:
                    raise NotImplementedError("This code only handles SamplesPerPixel > 1 if Bits Allocated = 8")
            else:
                arr = arr.reshape(self.Rows, self.Columns)
        return arr

    # Use by pixel_array property
    def _get_pixel_array(self):
        # Check if pixel data is in a form we know how to make into an array
        # XXX uses file_meta here, should really only be thus for FileDataset
        if self.file_meta.TransferSyntaxUID not in NotCompressedPixelTransferSyntaxes:
            raise NotImplementedError("Pixel Data is compressed in a format pydicom does not yet handle. Cannot return array")

        # Check if already have converted to a NumPy array
        # Also check if self.PixelData has changed. If so, get new NumPy array
        already_have = True
        if not hasattr(self, "_pixel_array"):
            already_have = False
        elif self._pixel_id != id(self.PixelData):
            already_have = False
        if not already_have:
            self._pixel_array = self._pixel_data_numpy()
            self._pixel_id = id(self.PixelData)  # is this guaranteed to work if memory is re-used??
        return self._pixel_array

    @property
    def pixel_array(self):
        """Return the pixel data as a NumPy array"""
        try:
            return self._get_pixel_array()
        except AttributeError:
            t, e, tb = sys.exc_info()
            raise PropertyError("AttributeError in pixel_array property: " +
                                e.args[0]), None, tb

    # Format strings spec'd according to python string formatting options
    #    See http://docs.python.org/library/stdtypes.html#string-formatting-operations
    default_element_format = "%(tag)s %(name)-35.35s %(VR)s: %(repval)s"
    default_sequence_element_format = "%(tag)s %(name)-35.35s %(VR)s: %(repval)s"

    def formatted_lines(self, element_format=default_element_format,
                        sequence_element_format=default_sequence_element_format,
                        indent_format=None):
        """A generator to give back a formatted string representing each line
        one at a time. Example:
            for line in dataset.formatted_lines("%(name)s=%(repval)s", "SQ:%(name)s=%(repval)s"):
                print(line)
        See the source code for default values which illustrate some of the names that can be used in the
        format strings
        indent_format -- not used in current version. Placeholder for future functionality.
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
        """Return a string of the data_elements in this dataset, with indented levels.

        This private method is called by the __str__() method
        for handling print statements or str(dataset), and the __repr__() method.
        It is also used by top(), which is the reason for the top_level_only flag.
        This function recurses, with increasing indentation levels.

        """
        strings = []
        indent_str = self.indent_chars * indent
        nextindent_str = self.indent_chars * (indent + 1)
        for data_element in self:
            with tag_in_exception(data_element.tag):
                if data_element.VR == "SQ":   # a sequence
                    strings.append(indent_str + str(data_element.tag) + "  %s   %i item(s) ---- " % (data_element.description(), len(data_element.value)))
                    if not top_level_only:
                        for dataset in data_element.value:
                            strings.append(dataset._pretty_str(indent + 1))
                            strings.append(nextindent_str + "---------")
                else:
                    strings.append(indent_str + repr(data_element))
        return "\n".join(strings)

    def remove_private_tags(self):
        """Remove all Dicom private tags in this dataset and those contained within."""
        def RemoveCallback(dataset, data_element):
            """Internal method to use as callback to walk() method."""
            if data_element.tag.is_private:
                # can't del self[tag] - won't be right dataset on recursion
                del dataset[data_element.tag]
        self.walk(RemoveCallback)

    def save_as(self, filename, write_like_original=True):
        """Write the dataset to a file.

        :param filename: full path and filename to save the file to
        :write_like_original: see dicom.filewriter.write_file for info on this parameter.
        """
        dicom.write_file(filename, self, write_like_original)

    def __setattr__(self, name, value):
        """Intercept any attempts to set a value for an instance attribute.

        If name is a dicom descriptive string (cleaned with CleanName),
        then set the corresponding tag and data_element.
        Else, set an instance (python) attribute as any other class would do.

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
            self.__dict__[name] = value

    def __setitem__(self, key, value):
        """Operator for dataset[key]=value. Check consistency, and deal with private tags"""
        if not isinstance(value, (DataElement, RawDataElement)):  # ok if is subclass, e.g. DeferredDataElement
            raise TypeError("Dataset contents must be DataElement instances.\n"
                            "To set a data_element value use data_element.value=val")
        tag = Tag(value.tag)
        if key != tag:
            raise ValueError("data_element.tag must match the dictionary key")

        data_element = value
        if tag.is_private:
            # See PS 3.5-2008 section 7.8.1 (p. 44) for how blocks are reserved
            logger.debug("Setting private tag %r" % tag)
            private_block = tag.elem >> 8
            private_creator_tag = Tag(tag.group, private_block)
            if private_creator_tag in self and tag != private_creator_tag:
                if isinstance(data_element, RawDataElement):
                    data_element = DataElement_from_raw(data_element, self._character_set)
                data_element.private_creator = self[private_creator_tag].value
        dict.__setitem__(self, tag, data_element)

    def __str__(self):
        """Handle str(dataset)."""
        return self._pretty_str()

    def top(self):
        """Show the DICOM tags, but only the top level; do not recurse into Sequences"""
        return self._pretty_str(top_level_only=True)

    def trait_names(self):
        """Return a list of valid names for auto-completion code
        Used in IPython, so that data element names can be found
        and offered for autocompletion on the IPython command line
        """
        return dir(self)  # only valid python >=2.6, else use self.__dir__()

    def update(self, dictionary):
        """Extend dict.update() to handle DICOM keywords."""
        for key, value in dictionary.items():
            if isinstance(key, (str, unicode)):
                setattr(self, key, value)
            else:
                self[Tag(key)] = value

    def iterall(self):
        """Iterate through the dataset, yielding all data elements.

        Unlike Dataset.__iter__, this *does* recurse into sequences,
        and so returns all data elements as if the file were "flattened".
        """
        for data_element in self:
            yield data_element
            if data_element.VR == "SQ":
                sequence = data_element.value
                for dataset in sequence:
                    for elem in dataset.iterall():
                        yield elem

    def walk(self, callback, recursive=True):
        """Call the given function for all dataset data_elements (recurses).

        Visit all data_elements, recurse into sequences and their datasets (if specified),
        The callback function is called for each data_element
            (including SQ element).
        Can be used to perform an operation on certain types of data_elements.
        E.g., `remove_private_tags`() finds all private tags and deletes them.

        :param callback: a callable taking two arguments: a dataset, and
                         a data_element belonging to that dataset.
        :param recursive: a boolean indicating whether to recurse into Sequences

        `DataElement`s will come back in DICOM order (by increasing tag number
        within their dataset)

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
    def __init__(self, filename_or_obj, dataset, preamble=None, file_meta=None,
                 is_implicit_VR=True, is_little_endian=True):
        """Initialize a dataset read from a DICOM file

        :param filename: full path and filename to the file. Use None if is a BytesIO.
        :param dataset: some form of dictionary, usually a Dataset from read_dataset()
        :param preamble: the 128-byte DICOM preamble
        :param file_meta: the file meta info dataset, as returned by _read_file_meta,
                or an empty dataset if no file meta information is in the file
        :param is_implicit_VR: True if implicit VR transfer syntax used; False if explicit VR. Default is True.
        :param is_little_endian: True if little-endian transfer syntax used; False if big-endian. Default is True.
        """
        Dataset.__init__(self, dataset)
        self.preamble = preamble
        self.file_meta = file_meta
        self.is_implicit_VR = is_implicit_VR
        self.is_little_endian = is_little_endian
        if isinstance(filename_or_obj, basestring):
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
            statinfo = stat(self.filename)
            self.timestamp = statinfo.st_mtime
