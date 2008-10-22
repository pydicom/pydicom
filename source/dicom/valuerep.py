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

class PersonName(str):
    """Subclass python str so have human-friendly VRs of Person Name (PN)

    Name is parsed into the following properties:
    single-byte, ideographic, and phonetic components (PS3.5-2008 6.2.1)
    family_name,
    given_name,
    middle_name,
    name_prefix,
    name_suffix
    
    """
    def __init__(self, val):
        """Initialize the PN properties"""
        # Note normally use __new__ on subclassing an immutable, but here we just want 
        #    to do some pre-processing for properties
        
        # PS 3.5-2008 section 6.2 (p.28)  and 6.2.1 describes PN. Briefly:
        #  single-byte-characters=ideographic characters=phonetic-characters
        # (each with?):
        #   family-name-complex^Given-name-complex^Middle-name^name-prefix^name-suffix
        
        # Start with None for all components of the name
        (self.family_name, self.given_name, self.middle_name, 
           self.name_prefix, self.name_suffix) = (None, None, None, None, None)

        components_string = val + "=="  # force the 3 components if trailing ones not defined
        components = components_string.split("=")[:3]
        self.single_byte, self.ideographic, self.phonetic = components
        if self.single_byte:
            name_string = self.single_byte+"^^^^" # in case missing trailing items are left out
            parts = name_string.split("^")[:5]
            (self.family_name, self.given_name, self.middle_name,
                               self.name_prefix, self.name_suffix) = parts
        # XXX need to process the ideographic or phonetic components?
        
    def family_comma_given(self):
        """Return name as 'Family-name, Given-name'"""
        return self.formatted("%(family_name)s, %(given_name)s")
    def formatted(self, format):
        """Return a formatted string according to the format pattern
        
        Use "...%(property)...%(property)..." where property is one of
           family_name, given_name, middle_name, name_prefix, name_suffix
        """
        return format % self.__dict__
        