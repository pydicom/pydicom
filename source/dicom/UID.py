# UID.py
"""Dicom Unique identifiers"""
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

from _UID_dict import UID_dictionary

class UID(str):
    """Subclass python string so have human-friendly UIDS
    
    Use like: 
        uid = UID('1.2.840.10008.1.2.4.50')
    then
        uid.name, uid.type, uid.info, and uid.isRetired all return
           values from the UID_dictionary
           
    String representation (__str__) will be the name,
    __repr__ will be the full 1.2.840....
    """
    def __init__(self, val):
        """Initialize the UID properties"""
        # Note normally use __new__ on subclassing an immutable, but here we just want 
        #    to do some pre-processing against the UID dictionary.
        #   "My" string can never change so is safe
        if self in UID_dictionary:
            self.name, self.type, self.info, retired = UID_dictionary[self]
            self.isRetired = bool(retired)
        else:
            self.name = self
            self.type, self.info, isRetired = (None, None, None)
            
    def __str__(self):
        """Return the human-friendly name for this UID"""
        return self.name
        
    def __eq__(self, other):
        """Override string equality so either name or UID number match passes"""
        if str.__eq__(self, other):
            return True
        if str.__eq__(self.name, other):
            return True
        return False

ExplicitVRLittleEndian = UID('1.2.840.10008.1.2.1')
ImplicitVRLittleEndian = UID('1.2.840.10008.1.2')
DeflatedExplicitVRLittleEndian = UID('1.2.840.10008.1.2.1.99')
ExplicitVRBigEndian = UID('1.2.840.10008.1.2.2')

        
# Many thanks to the Medical Connections for offering free valid UIDs (http://www.medicalconnections.co.uk/FreeUID.html)
# Their service was used to obtain the following root UID for pydicom:
root = '1.2.826.0.1.3680043.8.498.'
pydicom_UIDs = {
    root + '1': 'ImplementationClassUID',
    
    }
    