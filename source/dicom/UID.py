# UID.py
"""Dicom Unique identifiers"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

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
    def __new__(cls, val):
        """Set up new instance of the class"""
        # Dont' repeat if already a UID class -- then may get the name
        #     that str(uid) gives rather than the dotted number
        if isinstance(val, UID):
            return val
        else:
            return super(UID, cls).__new__(cls, val)
        
    def __init__(self, val):
        """Initialize the UID properties"""
        # Note normally use __new__ on subclassing an immutable, but here we just want 
        #    to do some pre-processing against the UID dictionary.
        #   "My" string can never change so is safe
        if self in UID_dictionary:
            self.name, self.type, self.info, retired = UID_dictionary[self]
            self.isRetired = bool(retired)
        else:
            self.name = str.__str__(self)
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
class TransferSyntax(str):
    def __init__(self, val):
        pass
