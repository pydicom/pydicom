# UID.py
"""Dicom Unique identifiers"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import os
import uuid
import datetime
from math import fabs

from _UID_dict import UID_dictionary


class InvalidUID(Exception):
    '''
    Throw when DICOM UID is invalid

    Example of invalid UID::

        >>> uid = '1.2.123.'
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


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
            if isinstance(val, basestring):
                return super(UID, cls).__new__(cls, val.strip())
            else:
                raise TypeError("UID must be a string")

    def __init__(self, val):
        """Initialize the UID properties

        Sets name, type, info, is_retired, and is_transfer_syntax.
        If UID is a transfer syntax, also sets is_little_endian,
            is_implicit_VR, and is_deflated boolean values.
        """
        # Note normally use __new__ on subclassing an immutable, but here we
        #   just want to do some pre-processing against the UID dictionary.
        #   "My" string can never change (it is a python immutable), so is safe
        if self in UID_dictionary:
            self.name, self.type, self.info, retired = UID_dictionary[self]
            self.is_retired = bool(retired)
        else:
            self.name = str.__str__(self)
            self.type, self.info, self.is_retired = (None, None, None)

        # If the UID represents a transfer syntax, store info about that syntax
        self.is_transfer_syntax = (self.type == "Transfer Syntax")
        if self.is_transfer_syntax:
            # Assume a transfer syntax, correct it as necessary
            self.is_implicit_VR = True
            self.is_little_endian = True
            self.is_deflated = False

            if val == '1.2.840.10008.1.2':  # implicit VR little endian
                pass
            elif val == '1.2.840.10008.1.2.1':  # ExplicitVRLittleEndian
                self.is_implicit_VR = False
            elif val == '1.2.840.10008.1.2.2':  # ExplicitVRBigEndian
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
        if str.__eq__(self, other) is True:  # 'is True' needed (issue 96)
            return True
        if str.__eq__(self.name, other) is True:  # 'is True' needed (issue 96)
            return True
        return False

    def __ne__(self, other):
        return not self == other

    def is_valid(self):
        '''
        Raise an exception is the UID is invalid

        Usage example::

            >>> invalid_uid = dicom.UID.UID('1.2.345.')
            >>> invalid_uid.is_valid(invalid_uid)
            InvalidUID: 'Trailing dot at the end of the UID'
            >>> valid_uid = dicom.UID.UID('1.2.123')

        '''
        if self[-1] == '.':
            raise InvalidUID('Trailing dot at the end of the UID')

    # For python 3, any override of __cmp__ or __eq__ immutable requires
    #   explicit redirect of hash function to the parent class
    #   See http://docs.python.org/dev/3.0/reference/datamodel.html#object.__hash__

    def __hash__(self):
        return super(UID, self).__hash__()

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


def generate_uid(prefix=pydicom_root_UID, truncate=False):
    '''
    Generate a dicom unique identifier based on host id, process id and current
    time. The max lenght of the generated UID is 64 caracters.

    If the given prefix is ``None``, the UID is generated following the method
    described on `David Clunie website
    <http://www.dclunie.com/medical-image-faq/html/part2.html#UID>`_

    Usage example::

        >>> dicom.UID.generate_uid()
        1.2.826.0.1.3680043.8.498.2913212949509824014974371514
        >>> dicom.UID.generate_uid(None)
        2.25.31215762025423160614120088028604965760

    This method is inspired from the work of `DCMTK
    <http://dicom.offis.de/dcmtk.php.en>`_.

    :param prefix: The site root UID. Default to pydicom root UID.
    '''
    max_uid_len = 64

    if prefix is None:
        dicom_uid = '2.25.{0}'.format(uuid.uuid1().int)
    else:
        uid_info = [uuid.getnode(),
                    fabs(os.getpid()),
                    datetime.datetime.today().second,
                    datetime.datetime.today().microsecond]  # nopep8

        suffix = ''.join([str(long(x)) for x in uid_info])
        dicom_uid = ''.join([prefix, suffix])

    if truncate:
        dicom_uid = dicom_uid[:max_uid_len]

    dicom_uid = UID(dicom_uid)

    # This will raise an exception if the UID is invalid
    dicom_uid.is_valid()

    return dicom_uid
