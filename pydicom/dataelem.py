# dataelem.py
"""Define the DataElement class - elements within a dataset.

DataElements have a DICOM value representation VR, a value multiplicity VM,
and a value.
"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom
#
from __future__ import absolute_import
from collections import namedtuple

from pydicom import config  # don't import datetime_conversion directly
from pydicom import compat
from pydicom.config import logger
from pydicom.datadict import dictionary_has_tag, dictionary_description, \
                             dictionary_keyword, dictionary_is_retired
from pydicom.datadict import private_dictionary_description, dictionaryVR
from pydicom.tag import Tag
from pydicom.uid import UID
import pydicom.valuerep  # don't import DS directly as can be changed by config
from pydicom.compat import in_py2

if not in_py2:
    from pydicom.valuerep import PersonName3 as PersonNameUnicode
    PersonName = PersonNameUnicode


# Helper functions:
def isMultiValue(value):
    """Helper function: return True if 'value' is 'list-like'."""
    if isString(value) or isinstance(value, bytes):
        return False
    try:
        iter(value)
    except TypeError:
        return False
    return True


def isString(val):
    """Helper function: return True if val is a string."""
    return isinstance(val, compat.string_types)


def isStringOrStringList(val):
    """Return true if val consists only of strings. val may be a list/tuple."""
    if isMultiValue(val):
        for item in val:
            if not isString(item):
                return False
        return True
    else:  # single value - test for a string
        return isString(val)

_backslash = "\\"  # double '\' because it is used as escape chr in Python


class DataElement(object):
    """Contain and manipulate a Dicom data element, having a tag, VR, VM and value.

    Most user code will not create data elements using this class directly,
    but rather through DICOM keywords in Dataset objects.
    See the Dataset class for a description of how Datasets, Sequences,
    and DataElements work.

    Class Data
    ----------
    For string display (via __str__), the following are used:

    descripWidth -- maximum width of description field (default 35).
    maxBytesToDisplay -- longer data will display "array of # bytes" (default 16).
    showVR -- True (default) to include the dicom VR just before the value.

    Attributes
    ----------
    is_retired : bool
        For officially registered DICOM Data Elements this will be True if the
        retired status as given in PS3.6 Table 6-1 is 'RET'. For private or
        unknown Elements this will always be False
    keyword : str
        For officially registered DICOM Data Elements this will be the Keyword
        as given in PS3.6 Table 6-1. For private or unknown Elements this will
        return an empty string.
    name : str
        For officially registered DICOM Data Elements this will be the Name
        as given in PS3.6 Table 6-1. For private Elements known to pydicom this
        will be the Name in the format '[name]'. For unknown private Elements
        this will be 'Private Creator'. For unknown Elements this will return
        an empty string.
    tag : pydicom.tag.Tag
        The DICOM Tag for the Data Element
    value
        The Data Element's stored value(s)
    VM : int
        The Value Multiplicity of the Data Element's stored value(s)
    VR : str
        The Data Element's Value Representation value
    """
    descripWidth = 35
    maxBytesToDisplay = 16
    showVR = 1

    # Python 2: Classes which define __eq__ should flag themselves as unhashable
    __hash__ = None

    def __init__(self, tag, VR, value, file_value_tell=None,
                 is_undefined_length=False, already_converted=False):
        """Create a data element instance.

        Most user code should instead use DICOM keywords
        to create data_elements, for which only the value is supplied,
        and the VR and tag are determined from the dicom dictionary.

        tag -- dicom (group, element) tag in any form accepted by Tag().
        VR -- dicom value representation (see DICOM standard part 6)
        value -- the value of the data element. One of the following:
            - a single string value
            - a number
            - a list or tuple with all strings or all numbers
            - a multi-value string with backslash separator
        file_value_tell -- used internally by Dataset, to store the write
            position for ReplaceDataElementValue method
        is_undefined_length -- used internally to store whether the length
            field in this data element was 0xFFFFFFFFL, i.e. "undefined length"

        """
        self.tag = Tag(tag)
        self.VR = VR  # Note!: you must set VR before setting value
        if already_converted:
            self._value = value
        else:
            self.value = value  # calls property setter which will convert
        self.file_tell = file_value_tell
        self.is_undefined_length = is_undefined_length

    @property
    def value(self):
        """The value (possibly multiple values) of this data_element"""
        return self._value

    @value.setter
    def value(self, val):
        """Set method for 'value' property"""
        # Check if is a string with multiple values separated by '\'
        # If so, turn them into a list of separate strings
        if isString(val) and self.VR not in \
                ['UT', 'ST', 'LT', 'FL', 'FD', 'AT', 'OB', 'OW', 'OF', 'SL', 'SQ', 'SS',
                 'UL', 'OB/OW', 'OW/OB', 'OB or OW', 'OW or OB', 'UN'] and 'US' not in self.VR:  # latter covers 'US or SS' etc
            if _backslash in val:
                val = val.split(_backslash)
        self._value = self._convert_value(val)

    @property
    def VM(self):
        """The number of values in the data_element's 'value'"""
        if isMultiValue(self.value):
            return len(self.value)
        else:
            return 1

    def _convert_value(self, val):
        """Convert Dicom string values if possible to e.g. numbers. Handle the case
        of multiple value data_elements"""
        if self.VR == 'SQ':  # a sequence - leave it alone
            from pydicom.sequence import Sequence
            if isinstance(val, Sequence):
                return val
            else:
                return Sequence(val)

        # if the value is a list, convert each element
        try:
            val.append
        except AttributeError:  # not a list
            return self._convert(val)
        else:
            returnvalue = []
            for subval in val:
                returnvalue.append(self._convert(subval))
            return returnvalue

    def _convert(self, val):
        """Take the value and convert to number, etc if possible"""
        if self.VR == 'IS':
            return pydicom.valuerep.IS(val)
        elif self.VR == 'DA' and config.datetime_conversion:
            return pydicom.valuerep.DA(val)
        elif self.VR == 'DS':
            return pydicom.valuerep.DS(val)
        elif self.VR == 'DT' and config.datetime_conversion:
            return pydicom.valuerep.DT(val)
        elif self.VR == 'TM' and config.datetime_conversion:
            return pydicom.valuerep.TM(val)
        elif self.VR == "UI":
            return UID(val)
        elif not in_py2 and self.VR == "PN":
            return PersonName(val)
        # Later may need this for PersonName as for UI,
        #    but needs more thought
        # elif self.VR == "PN":
        #    return PersonName(val)
        else:  # is either a string or a type 2 optionally blank string
            return val  # this means a "numeric" value could be empty string ""
        # except TypeError:
            # print "Could not convert value '%s' to VR '%s' in tag %s" \
            # % (repr(val), self.VR, self.tag)
        # except ValueError:
            # print "Could not convert value '%s' to VR '%s' in tag %s" \
            # % (repr(val), self.VR, self.tag)

    def __eq__(self, other):
        """
        Compare `self` and `other` for equality

        Returns
        -------
        bool
            The result if `self` and `other` are the same class
        NotImplemented
            If `other` is not the same class as `self` then returning
            NotImplemented delegates the result to superclass.__eq__(subclass)
        """
        # Faster result if same object
        if other is self:
            return True

        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__

        return NotImplemented

    def __ne__(self, other):
        """ Compare `self` and `other` for inequality """
        return not (self == other)

    def __str__(self):
        """Return str representation of this data_element"""
        repVal = self.repval
        if self.showVR:
            s = "%s %-*s %s: %s" % (str(self.tag), self.descripWidth,
                                    self.description()[:self.descripWidth], self.VR, repVal)
        else:
            s = "%s %-*s %s" % (str(self.tag), self.descripWidth,
                                self.description()[:self.descripWidth], repVal)
        return s

    @property
    def repval(self):
        """Return a str representation of the current value for use in __str__"""
        byte_VRs = ['OB', 'OW', 'OW/OB', 'OW or OB', 'OB or OW', 'US or SS or OW', 'US or SS']
        if (self.VR in byte_VRs and len(self.value) > self.maxBytesToDisplay):
            repVal = "Array of %d bytes" % len(self.value)
        elif hasattr(self, 'original_string'):  # for VR of IS or DS
            repVal = repr(self.original_string)
        elif isinstance(self.value, UID):
            repVal = self.value.name
        else:
            repVal = repr(self.value)  # will tolerate unicode too
        return repVal

    def __unicode__(self):
        """Return unicode representation of this data_element"""
        if isinstance(self.value, compat.text_type):
            # start with the string rep then replace the value part with the unicode
            strVal = str(self)
            uniVal = compat.text_type(strVal.replace(self.repval, "")) + self.value
            return uniVal
        else:
            return compat.text_type(str(self))

    def __getitem__(self, key):
        """Returns the item from my value's Sequence, if it is one."""
        try:
            return self.value[key]
        except TypeError:
            raise TypeError("DataElement value is unscriptable (not a Sequence)")

    @property
    def name(self):
        return self.description()

    def description(self):
        """Return the DICOM dictionary description for this dicom tag."""
        if dictionary_has_tag(self.tag):
            name = dictionary_description(self.tag)
        elif self.tag.is_private:
            name = "Private tag data"  # default
            if hasattr(self, 'private_creator'):
                try:
                    # If have name from private dictionary, use it, but
                    #   but put in square brackets so is differentiated,
                    #   and clear that cannot access it by name
                    name = "[" + private_dictionary_description(self.tag, self.private_creator) + "]"
                except KeyError:
                    pass
            elif self.tag.elem >> 8 == 0:
                name = "Private Creator"
        elif self.tag.element == 0:  # implied Group Length dicom versions < 3
            name = "Group Length"
        else:
            name = ""
        return name

    @property
    def is_retired(self):
        """The data_element's retired status"""
        if dictionary_has_tag(self.tag):
            return dictionary_is_retired(self.tag)
        else:
            return False

    @property
    def keyword(self):
        """The data_element's keyword (if known)"""
        if dictionary_has_tag(self.tag):
            return dictionary_keyword(self.tag)
        else:
            return ''

    def __repr__(self):
        """Handle repr(data_element)"""
        if self.VR == "SQ":
            return repr(self.value)
        else:
            return str(self)


class DeferredDataElement(DataElement):
    """Subclass of DataElement where value is not read into memory until needed"""
    def __init__(self, tag, VR, fp, file_mtime, data_element_tell, length):
        """Store basic info for the data element but value will be read later

        fp -- DicomFile object representing the dicom file being read
        file_mtime -- last modification time on file, used to make sure
           it has not changed since original read
        data_element_tell -- file position at start of data element,
           (not the start of the value part, but start of whole element)
        """
        self.tag = Tag(tag)
        self.VR = VR
        self._value = None  # flag as unread

        # Check current file object and save info needed for read later
        self.fp_is_implicit_VR = fp.is_implicit_VR
        self.fp_is_little_endian = fp.is_little_endian
        self.filepath = fp.name
        self.file_mtime = file_mtime
        self.data_element_tell = data_element_tell
        self.length = length

    @property
    def repval(self):
        if self._value is None:
            return "Deferred read: length %d" % self.length
        else:
            return DataElement.repval.fget(self)

    @property
    def value(self):
        """Get method for 'value' property"""
        # Must now read the value if haven't already
        if self._value is None:
            self.read_value()
        return DataElement.value.fget(self)

    @value.setter
    def value(self, val):
        DataElement.value.fset(self, val)


RawDataElement = namedtuple('RawDataElement',
                            'tag VR length value value_tell is_implicit_VR is_little_endian')


def DataElement_from_raw(raw_data_element, encoding=None):
    """Return a DataElement from a RawDataElement"""
    from pydicom.values import convert_value  # XXX buried here to avoid circular import filereader->Dataset->convert_value->filereader (for SQ parsing)
    raw = raw_data_element

    # If user has hooked into conversion of raw values, call his/her routine
    if config.data_element_callback:
        raw = config.data_element_callback(raw_data_element,
                                           **config.data_element_callback_kwargs)
    VR = raw.VR
    if VR is None:  # Can be if was implicit VR
        try:
            VR = dictionaryVR(raw.tag)
        except KeyError:
            if raw.tag.is_private:
                VR = 'OB'  # just read the bytes, no way to know what they mean
            elif raw.tag.element == 0:  # group length tag implied in versions < 3.0
                VR = 'UL'
            else:
                raise KeyError("Unknown DICOM tag {0:s} - can't look up VR".format(str(raw.tag)))
    try:
        value = convert_value(VR, raw, encoding)
    except NotImplementedError as e:
        raise NotImplementedError("{0:s} in tag {1!r}".format(str(e), raw.tag))
    return DataElement(raw.tag, VR, value, raw.value_tell,
                       raw.length == 0xFFFFFFFF, already_converted=True)
