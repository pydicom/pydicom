# dataelem.py
"""Define the DataElement class - elements within a dataset.

DataElements have a DICOM value representation VR, a value multiplicity VM,
and a value.
"""
#
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com
#

import logging
logger = logging.getLogger('pydicom')

from dicom.datadict import dictionaryHasTag, dictionaryDescription
from dicom.tag import Tag
from dicom.UID import UID

# os.stat is only available on Unix and Windows
# Not sure if on other platforms the import fails, or the call to it??
stat_available = True
try:
    from os import stat
except:
    stat_available = False
import os.path

from dicom.filebase import DicomFile
import warnings

# Helper functions:
def isMultiValue(value):
    """Helper function: return True if 'value' is 'list-like'."""
    if isString(value):
        return False
    try:
        value[0]
    except:
        return False
    return True
    
def isString(val):
    """Helper function: return True if val is a string."""
    try:
        val + ""
    except:
        return False
    return True

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
    but rather through 'named tags' in Dataset objects.
    See the Dataset class for a description of how Datasets, Sequences,
    and DataElements work.
    
    Class Data
    ----------
    For string display (via __str__), the following are used:
    
    descripWidth -- maximum width of description field (default 35).
    maxBytesToDisplay -- longer data will display "array of # bytes" (default 16).
    showVR -- True (default) to include the dicom VR just before the value.
    """
    descripWidth = 35  
    maxBytesToDisplay = 16  
    showVR = 1
    def __init__(self, tag, VR, value, file_value_tell=None):
        """Create a data element instance.
        
        Most user code should instead use 'Named tags' (see Dataset class)
        to create data_elements, for which only the value is supplied,
        and the VR and tag are determined from the dicom dictionary.
        
        tag -- dicom (group, element) tag in any form accepted by Tag class.
        VR -- dicom value representation (see DICOM standard part 6)
        value -- the value of the data element. One of the following:
            - a single string value
            - a number
            - a list or tuple with all strings or all numbers
            - a multi-value string with backslash separator
        file_value_tell -- used internally by Dataset, to store the write
            position for ReplaceDataElementValue method
            
        """
        self.tag = Tag(tag)
        self.VR = VR  # Note!: you must set VR before setting value
        self.value = value
        self.file_tell = file_value_tell
    def _getvalue(self):
        """Get method for 'value' property"""
        return self._value
    def _setvalue(self, val):
        """Set method for 'value' property"""
        # Check if is a string with multiple values separated by '\'
        # If so, turn them into a list of separate strings
        if isString(val) and self.VR not in \
           ['UT','ST','LT', 'FL','FD','AT','OB','OW','OF','SL','SQ','SS',
            'UL', 'OW/OB', 'UN'] and 'US' not in self.VR: # latter covers 'US or SS' etc
            if _backslash in val: 
                val = val.split(_backslash)  
        self._value = self._convert_value(val)
        if self.VR in ['IS', 'DS']:  # a number as a text string
            # If IS/DS need to store number but keep string also
            # If already a string, str(..) will have not change it
            if self.VM > 1:
                self.string_value = [str(x) for x in val]
            else:
                self.string_value = str(val)
    value = property(_getvalue, _setvalue, doc=
            """The value (possibly multiple values) of this data_element.""")

    def _getVM(self):
        """Get method for VM property"""
        if isMultiValue(self.value):
            return len(self.value)
        else:
            return 1
    VM = property(_getVM, doc =
            """The number of values in the data_element's 'value'""")
    
    def _convert_value(self, val):
        """Convert Dicom string values if possible to e.g. numbers. Handle the case
        of multiple value data_elements"""
        if self.VR=='SQ': # a sequence - leave it alone
            return val
        # if the value is a list, convert each element
        try:
            val.append
        except AttributeError: # not a list
            return self._convert(val)
        else:
            returnvalue = []
            for subval in val:
                returnvalue.append(self._convert(subval))
            return returnvalue

    def _convert(self, val):
        """Take the string from dicom stream and convert to number, etc if possible"""
        try:
            if self.VR in ['IS'] and val:
                return int(str(val))  # str(val) so does not truncate a float without error
            elif self.VR in ['DS'] and val:
                return float(val) 
            else: # is either a string or a type 2 optionally blank string
                return val # this means a "numeric" value could be empty string ""
        except TypeError:
            print "Could not convert value '%s' to VR '%s' in tag %s" \
                                % (repr(val), self.VR, self.tag)
        except ValueError:
            print "Could not convert value '%s' to VR '%s' in tag %s" \
                                % (repr(val), self.VR, self.tag)
            
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
        
    def _get_repval(self):
        """Return a str representation of the current value for use in __str__"""
        if (self.VR in ['OB', 'OW', 'OW/OB', 'US or SS or OW', 'US or SS'] 
                  and len(self.value) > self.maxBytesToDisplay):
            repVal = "Array of %d bytes" % len(self.value)
        elif hasattr(self, 'string_value'): # for VR of IS or DS 
            repVal = repr(self.string_value)
        elif isinstance(self.value, UID):
            repVal = self.value.name
        else:
            repVal = repr(self.value)  # will tolerate unicode too
        return repVal
    repval = property(_get_repval)
    
    def __unicode__(self):
        """Return unicode representation of this data_element"""
        if isinstance(self.value, unicode):
            # start with the string rep then replace the value part with the unicode
            strVal = str(self)
            uniVal = unicode(strVal.replace(self.repval, "")) + self.value
            return uniVal
        else:
            return unicode(str(self))
        
    def __getitem__(self, key):
        """Returns the item from my value's Sequence, if it is one."""
        try:
            return self.value[key]
        except TypeError:
            raise TypeError, "DataElement value is unscriptable (not a Sequence)"
    
    def _get_name(self):
        return self.description()
    name = property(_get_name)
    
    def description(self):
        """Return the DICOM dictionary description for this dicom tag."""
        if dictionaryHasTag(self.tag):
            name = dictionaryDescription(self.tag)
        elif self.tag.isPrivate:
            name = "Private tag data"
        elif self.tag.element == 0:  # implied Group Length dicom versions < 3
            name = "Group Length"
        else:
            name = ""
        return name

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
        self._value = None # flag as unread
        
        # Check current file object and save info needed for read later
        if not isinstance(fp, DicomFile):
            raise NotImplementedError, "Deferred read is only available for DicomFile objects"
        self.fp_isImplicitVR = fp.isImplicitVR
        self.fp_isLittleEndian = fp.isLittleEndian
        self.filepath = fp.name
        self.file_mtime = file_mtime
        self.data_element_tell = data_element_tell
        self.length = length
    def _get_repval(self):
        if self._value is None:
            return "Deferred read: length %d" % self.length
        else:
            return DataElement._get_repval(self)
    repval = property(_get_repval)
    
    def _getvalue(self):
        """Get method for 'value' property"""
        # Must now read the value if haven't already
        if self._value is None:
            self.read_value()
        return DataElement._getvalue(self)
    def _setvalue(self, val):
        DataElement._setvalue(self, val)
    value = property(_getvalue, _setvalue)
    
    def read_value(self):
        """Read the previously deferred value from the file into memory"""
        # If already read in, don't do again
        if self._value is not None:
            return
        logger.debug("Reading deferred element %s" % str(self.tag))
        # Check that the file is the same as when originally read
        if not os.path.exists(self.filepath):
            raise IOError, "Deferred read -- original file '%s' is missing" % self.filepath
        if stat_available:
            statinfo = stat(self.filepath)
            if statinfo.st_mtime != self.file_mtime:
                warnings.warn("Deferred read warning -- file modification time has changed.")
        
        # Open the file, position to the right place
        fp = DicomFile(self.filepath, 'rb')
        fp.defer_size = None
        fp.isLittleEndian = self.fp_isLittleEndian
        fp.isImplicitVR = self.fp_isImplicitVR
        fp.seek(self.data_element_tell)
        
        # Read the data element and check matches what was stored before
        from dicom.filereader import read_data_element
        data_elem = read_data_element(fp)
        fp.close()
        if data_elem.VR != self.VR:
            raise ValueError, "Deferred read VR '%s' does not match original '%s'" % (data_elem.VR, self.VR)
        if data_elem.tag != self.tag:
            raise ValueError, "Deferred read tag %s does not match original %s" % (str(data_elem.tag), str(self.tag))
        
        # Everything is ok, now this object should act like usual DataElement
        self._value = data_elem._value
        
        
class Attribute(DataElement):
    """Deprecated -- use DataElement instead"""
    def __init__(self, tag, VR, value, file_value_tell=None):
        warnings.warn("The Attribute class is deprecated and will be removed in pydicom 1.0. Use DataElement", DeprecationWarning)
        DataElement.__init__(self, tag, VR, value, file_value_tell)