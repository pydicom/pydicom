# attribute.py
"""Define the Attribute class - elements within a dataset.

Attributes have a dicom value representation VR, a value multiplicity VM,
and a value (attribute.value).
"""
#
# Copyright 2008, Darcy Mason
# This file is part of pydicom.
#
# pydicom is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# pydicom is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License (license.txt) for more details 

from dicom.datadict import dictionaryHasTag, dictionaryDescription
from dicom.tag import Tag
from dicom.UID import UID

# Helper functions:
def isMultiValue(value):
    """Helper function: return True if 'value' is 'list-like'."""
    if isString(value):
        return 0
    try:
        value[0]
    except:
        return 0
    return 1
    
def isString(val):
    """Helper function: return True if val is a string."""
    try:
        val + ""
    except:
        return 0
    return 1

def isStringOrStringList(val):
    """Return true if val consists only of strings. val may be a list/tuple."""
    if isMultiValue(val):
        for item in val:
            if not isString(item):
                return 0
        return 1
    else:  # single value - test for a string
        return isString(val)            

_backslash = "\\"  # double '\' because it is used as escape chr in Python

class Attribute(object):
    """Contain and manipulate a Dicom attribute, having a tag, VR, VM and value.
    
    Most user code will not create attributes using this class directly,
    but rather through 'named tags' in Dataset objects.
    See the Dataset class for a description of how Datasets, Sequences,
    and Attributes work.
    
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
        """Create an attribute instance.
        
        Most user code should instead use 'Named tags' (see Dataset class)
        to create attributes, for which only the value is supplied,
        and the VR and tag are determined from the dicom dictionary.
        
        tag -- dicom (group, element) tag in any form accepted by Tag class.
        VR -- dicom value representation (see DICOM standard part 6)
        value -- the value of the attribute. One of the following:
            - a single string value
            - a number
            - a list or tuple with all strings or all numbers
            - a multi-value string with backslash separator
        file_value_tell -- used internally by Dataset, to store the write
            position for ReplaceAttributeValue method
            
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
            'UL','US', 'OW/OB']:
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
            """The value (possibly multiple values) of this attribute.""")

    def _getVM(self):
        """Get method for VM property"""
        if isMultiValue(self.value):
            return len(self.value)
        else:
            return 1
    VM = property(_getVM, doc =
            """The number of values in the attribute's 'value'""")
    
    def _convert_value(self, val):
        """Convert Dicom string values if possible to e.g. numbers. Handle the case
        of multiple value attributes"""
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
        """Handle str(attribute)."""
        if (self.VR in ['OB', 'OW', 'OW/OB', 'US or SS or OW', 'US or SS'] 
                  and len(self.value) > self.maxBytesToDisplay):
            repVal = "Array of %d bytes" % len(self.value)
        elif hasattr(self, 'string_value'): # for VR of IS or DS 
            repVal = repr(self.string_value)
        elif isinstance(self.value, UID):
            repVal = self.value.name
        # elif isinstance(self.value, unicode):
            # try:
                # repVal = "'%s'" % self.value
            # except UnicodeEncodeError:
                # repVal = unicode.__repr__(self.value)
        else:
            repVal = repr(self.value)
        if self.showVR:
            s = "%s %-*s %s: %s" % (str(self.tag), self.descripWidth,
                            self.description()[:self.descripWidth], self.VR, repVal)
        else:
            s = "%s %-*s %s" % (str(self.tag), self.descripWidth,
                            self.description()[:self.descripWidth], repVal)
            
        return s
    
    def __getitem__(self, key):
        """Returns the item from my value's Sequence, if it is one."""
        try:
            return self.value[key]
        except TypeError:
            raise TypeError, "Attribute value is unscriptable (not a Sequence)"
        
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
        """Handle repr(attribute)"""
        if self.VR == "SQ":
            return repr(self.value)
        else:
            return str(self)
    
