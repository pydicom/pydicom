# valuerep.py
"""Special classes for DICOM value representations (VR)"""
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

from sys import version_info
if version_info[0] < 3:
    bytestring = object

class MultiValue(list):
    """MutliValue is a special list, derived to overwrite the __str__ method
    to display the multi-value list more nicely. Used for Dicom values of
    multiplicity > 1, i.e. strings with the "\" delimiter inside.
    """
    def __str__(self):
        lines = [str(x) for x in self]
        return "[" + ", ".join(lines) + "]"
    __repr__ = __str__

def MultiString(val, valtype=str):
    """Split a string by delimiters if there are any
    
    val -- DICOM string to split up
    valtype -- default str, but can be e.g. UID to overwrite to a specific type
    """
    # Remove trailing blank used to pad to even length
    # 2005.05.25: also check for trailing 0, error made in PET files we are converting
    if val and (val.endswith(' ') or val.endswith('\x00')):
        val = val[:-1]

    splitup = [valtype(x) for x in val.split("\\")]
    if len(splitup) == 1:
        return splitup[0]
    else:
        return MultiValue(splitup)

class PersonNameBase(bytestring):
    """Base class for Person Name classes"""

    def __init__(self, val):
        """Initialize the PN properties"""
        # Note normally use __new__ on subclassing an immutable, but here we just want 
        #    to do some pre-processing for properties
        # PS 3.5-2008 section 6.2 (p.28)  and 6.2.1 describes PN. Briefly:
        #  single-byte-characters=ideographic characters=phonetic-characters
        # (each with?):
        #   family-name-complex^Given-name-complex^Middle-name^name-prefix^name-suffix
        self.parse()

    def formatted(self, format):
        """Return a formatted string according to the format pattern
        
        Use "...%(property)...%(property)..." where property is one of
           family_name, given_name, middle_name, name_prefix, name_suffix
        """
        return format % self.__dict__
    def parse(self):
        """Break down the components and name parts"""
        self.components = self.split("=")
        nComponents = len(self.components)
        self.single_byte = self.components[0]
        self.ideographic = ''
        self.phonetic = ''
        if nComponents > 1:
            self.ideographic = self.components[1]
        if nComponents > 2:
            self.phonetic = self.components[2]
        
        if self.single_byte:
            name_string = self.single_byte+"^^^^" # in case missing trailing items are left out
            parts = name_string.split("^")[:5]
            (self.family_name, self.given_name, self.middle_name,
                               self.name_prefix, self.name_suffix) = parts
        else:
            (self.family_name, self.given_name, self.middle_name, 
                self.name_prefix, self.name_suffix) = ('', '', '', '', '')

    
class PersonName(PersonNameBase, str):
    """Human-friendly class to hold VR of Person Name (PN)

    Name is parsed into the following properties:
    single-byte, ideographic, and phonetic components (PS3.5-2008 6.2.1)
    family_name,
    given_name,
    middle_name,
    name_prefix,
    name_suffix
    
    """
    def family_comma_given(self):
        """Return name as 'Family-name, Given-name'"""
        return self.formatted("%(family_name)s, %(given_name)s")
    # def __str__(self):
        # return str(self.byte_string)
        # XXX need to process the ideographic or phonetic components?
    # def __len__(self):
        # return len(self.byte_string)


        
class PersonNameUnicode(PersonNameBase, unicode):
    """Unicode version of Person Name"""
    def __new__(cls, val, encodings):
        """Return unicode string after conversion of each part
        val -- the PN value to store
        encodings -- a list of python encodings, generally found
                 from dicom.charset.python_encodings mapping
                 of values in DICOM attribute (0008,0005).
        """
        # Make the possible three character encodings explicit:        
        if not isinstance(encodings, list):
            encodings = [encodings]*3
        if len(encodings) == 2:
            encodings.append(encodings[1])
        # print encodings
        components = val.split("=")
        unicomponents = [unicode(components[i],encodings[i]) 
                            for i, component in enumerate(components)]
        new_val = u"=".join(unicomponents)

        return unicode.__new__(cls, new_val)
    def __init__(self, val, encodings):
        self.encodings = encodings
        PersonNameBase.__init__(self, val)
    def family_comma_given(self):
        """Return name as 'Family-name, Given-name'"""
        return self.formatted("%(family_name)u, %(given_name)u")
