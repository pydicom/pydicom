# UID.py
"""Dicom Unique identifiers"""
# Copyright (c) 2008-2014 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

import os
import uuid
import random
import hashlib
import re

from pydicom._uid_dict import UID_dictionary
from pydicom import compat


valid_uid_re = '^(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*$'
'''Regular expression that matches valid UIDs. Does not enforce 64 char limit.
'''

valid_prefix_re = '^(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*\.$'
'''Regular expression that matches valid UID prefixes. Does not enforce length
constraints.
'''


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
            if isinstance(val, compat.string_types):
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

            >>> invalid_uid = pydicom.uid.UID('1.2.345.')
            >>> invalid_uid.is_valid(invalid_uid)
            InvalidUID: 'UID is a valid format: 1.2.345.'
            >>> valid_uid = pydicom.UID.UID('1.2.123')

        '''
        if len(self) > 64:
            raise InvalidUID('UID is more than 64 chars long')
        if not re.match(valid_uid_re, self):
            raise InvalidUID('UID is not a valid format: %s' % self)

    # For python 3, any override of __cmp__ or __eq__ immutable requires
    #   explicit redirect of hash function to the parent class
    #   See http://docs.python.org/dev/3.0/reference/datamodel.html#object.__hash__

    def __hash__(self):
        return super(UID, self).__hash__()

ExplicitVRLittleEndian = UID('1.2.840.10008.1.2.1')
ImplicitVRLittleEndian = UID('1.2.840.10008.1.2')
DeflatedExplicitVRLittleEndian = UID('1.2.840.10008.1.2.1.99')
ExplicitVRBigEndian = UID('1.2.840.10008.1.2.2')
JPEGBaseLineLossy8bit = UID('1.2.840.10008.1.2.4.50')
JPEGBaseLineLossy12bit = UID('1.2.840.10008.1.2.4.51')
JPEGLossless = UID('1.2.840.10008.1.2.4.70')
JPEGLSLossless = UID('1.2.840.10008.1.2.4.80')
JPEGLSLossy = UID('1.2.840.10008.1.2.4.81')
JPEG2000Lossless = UID('1.2.840.10008.1.2.4.90')
JPEG2000Lossy = UID('1.2.840.10008.1.2.4.91')

UncompressedPixelTransferSyntaxes = [ExplicitVRLittleEndian,
                                     ImplicitVRLittleEndian,
                                     DeflatedExplicitVRLittleEndian,
                                     ExplicitVRBigEndian, ]

JPEGLSSupportedCompressedPixelTransferSyntaxes = [JPEGLSLossless,
                                                  JPEGLSLossy, ]

PILSupportedCompressedPixelTransferSyntaxes = [JPEGBaseLineLossy8bit,
                                               JPEGLossless,
                                               JPEGBaseLineLossy12bit,
                                               JPEG2000Lossless,
                                               JPEG2000Lossy, ]
JPEG2000CompressedPixelTransferSyntaxes = [JPEG2000Lossless,
                                           JPEG2000Lossy, ]
JPEGLossyCompressedPixelTransferSyntaxes = [JPEGBaseLineLossy8bit,
                                            JPEGBaseLineLossy12bit, ]
NotCompressedPixelTransferSyntaxes = [ExplicitVRLittleEndian,
                                      ImplicitVRLittleEndian,
                                      DeflatedExplicitVRLittleEndian,
                                      ExplicitVRBigEndian]

# Many thanks to the Medical Connections for offering free valid UIDs (http://www.medicalconnections.co.uk/FreeUID.html)
# Their service was used to obtain the following root UID for pydicom:
pydicom_root_UID = '1.2.826.0.1.3680043.8.498.'
pydicom_uids = {
    pydicom_root_UID + '1': 'ImplementationClassUID',
}


def generate_uid(prefix=pydicom_root_UID, entropy_srcs=None):
    '''
    Generate a dicom unique identifier by joining the `prefix` and the result
    from hashing the list of strings `entropy_srcs` and truncating the result
    to 64 characters.

    If the `prefix` is ``None`` it will be set to the generic prefix '2.25.' as
    described on `David Clunie's website
    <http://www.dclunie.com/medical-image-faq/html/part2.html#UID>`_. If the
    `entropy_srcs` are ``None`` random data will be used, otherwise the result
    is deterministic (providing the same values will result in the same UID).

    The SHA512 hash function that is used should make the `entropy_srcs`
    unrecoverable from the resulting UID.

    Usage example::

        >>> pydicom.uid.generate_uid()
        1.2.826.0.1.3680043.8.498.2913212949509824014974371514
        >>> pydicom.uid.generate_uid(None)
        2.25.31215762025423160614120088028604965760

    This method is inspired from the work of `DCMTK
    <http://dicom.offis.de/dcmtk.php.en>`_.

    :param prefix: The site root UID. Default to pydicom root UID.
    :param entropy_srcs: A list of one of more strings that are hashed to
    generate the suffix
    '''
    max_uid_len = 64

    if prefix is None:
        prefix = '2.25.'
    else:
        if len(prefix) > max_uid_len - 1:
            raise ValueError("The prefix must be less than 63 chars")
        if not re.match(valid_prefix_re, prefix):
            raise ValueError("The prefix is not in a valid format")
    avail_digits = max_uid_len - len(prefix)

    if entropy_srcs is None:
        entropy_srcs = [str(uuid.uuid1()),  # 128-bit from MAC/time/randomness
                        str(os.getpid()),  # Current process ID
                        hex(random.getrandbits(64))  # 64 bits randomness
                        ]
    hash_val = hashlib.sha512(''.join(entropy_srcs).encode('utf-8'))

    # Convert this to an int with the maximum available digits
    dicom_uid = prefix + str(int(hash_val.hexdigest(), 16))[:avail_digits]

    return UID(dicom_uid)
