# UID.py
#PZ sync 6 Feb 2012
"""Dicom Unique identifiers"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import sys
if sys.hexversion >= 0x02060000 and sys.hexversion < 0x03000000: 
    inPy26 = True
else: 
    inPy26 = False

if sys.hexversion >= 0x03000000: 
    inPy3 = True
    basestring = str
else: 
    inPy3 = False
#PZadd dicom
from dicom._UID_dict import UID_dictionary

class UID(str):
    """Subclass python string so have human-friendly UIDs
    
    Use like: 
        uid = UID('1.2.840.10008.1.2.4.50')
    then
        uid.name, uid.type, uid.info, and uid.is_retired all return
           values from the UID_dictionary
           
    String representation (__str__) will be the name,
    __repr__ will be the full 1.2.840....
    """
    def __new__(cls, val):
        """Set up new instance of the class"""
        # Don't repeat if already a UID class -- then may get the name
        #     that str(uid) gives rather than the dotted number
        if isinstance(val, UID):
            return val
        else:
#PZ no basestring        
            if isinstance(val, basestring):
                return super(UID, cls).__new__(cls, val.strip())
            else:
#PZ 3109/3110            
                raise TypeError( "UID must be a string")
        
    def __init__(self, val):
        """Initialize the UID properties
        
        Sets name, type, info, is_retired, and is_transfer_syntax.
        If UID is a transfer syntax, also sets is_little_endian, is_implicit_VR,
            and is_deflated boolean values.
        """
        # Note normally use __new__ on subclassing an immutable, but here we just want 
        #    to do some pre-processing against the UID dictionary.
        #   "My" string can never change (it is a python immutable), so is safe
#PZ self or val? if self 
        if val in UID_dictionary:
#PZ self or val? in  UID_dictionary[val]
            self.name, self.type, self.info, retired = UID_dictionary[val]
            self.is_retired = bool(retired)
        else:
#PZ self. or val        
            self.name = str.__str__(val)
            self.type, self.info, self.is_retired = (None, None, None)
        
        # If the UID represents a transfer syntax, store info about that syntax
        self.is_transfer_syntax = (self.type == "Transfer Syntax")
        if self.is_transfer_syntax:
            # Assume a transfer syntax, correct it as necessary
            self.is_implicit_VR = True
            self.is_little_endian = True
            self.is_deflated = False
            
            if val == '1.2.840.10008.1.2': # implicit VR little endian
                pass
            elif val == '1.2.840.10008.1.2.1': # ExplicitVRLittleEndian
                self.is_implicit_VR = False
            elif val == '1.2.840.10008.1.2.2': # ExplicitVRBigEndian
                self.is_implicit_VR = False
                self.is_little_endian = False
            elif val == '1.2.840.10008.1.2.1.99':  # DeflatedExplicitVRLittleEndian:
                self.is_deflated = True
                self.is_implicit_VR = False
            else:
                # Any other syntax should be Explicit VR Little Endian,
                #   e.g. all Encapsulated (JPEG etc) are ExplVR-LE by Standard PS 3.5-2008 A.4 (p63)
                self.is_implicit_VR = False
           
    def __str__(self):
        """Return the human-friendly name for this UID"""
        return self.name
        
    def __eq__(self, other):
        """Override string equality so either name or UID number match passes"""
        if str.__eq__(self, other) is True: # 'is True' needed (issue 96)
            return True
        if str.__eq__(self.name, other) is True: # 'is True' needed (issue 96)
            return True
        return False
#PZ overriding __eq__ makes object unhashable so it cannot be used in collections
#PZ http://docs.python.org/release/3.1.3/reference/datamodel.html?highlight=hash
#PZ either define your own or use from the base class
    def __hash__(self):
        return self.name.__hash__()

ExplicitVRLittleEndian = UID('1.2.840.10008.1.2.1')
ImplicitVRLittleEndian = UID('1.2.840.10008.1.2')
DeflatedExplicitVRLittleEndian = UID('1.2.840.10008.1.2.1.99')
ExplicitVRBigEndian = UID('1.2.840.10008.1.2.2')

NotCompressedPixelTransferSyntaxes = [ExplicitVRLittleEndian,
                                      ImplicitVRLittleEndian,
                                      DeflatedExplicitVRLittleEndian,
                                      ExplicitVRBigEndian]
                                      
# Many thanks to the Medical Connections for offering free valid UIDs (http://www.medicalconnections.co.uk/FreeUID.html)
# Their service was used to obtain the following root UID for pydicom:
pydicom_root_UID = '1.2.826.0.1.3680043.8.498.'
pydicom_UIDs = {
    pydicom_root_UID + '1': 'ImplementationClassUID',
    
    }
