# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Functions for handling DICOM unique identifiers (UIDs)"""

import os
import uuid
import random
import hashlib
import re

from pydicom._uid_dict import UID_dictionary

# Many thanks to the Medical Connections for offering free
# valid UIDs (http://www.medicalconnections.co.uk/FreeUID.html)
# Their service was used to obtain the following root UID for pydicom:
PYDICOM_ROOT_UID = '1.2.826.0.1.3680043.8.498.'
"""pydicom's root UID ``'1.2.826.0.1.3680043.8.498.'``"""
PYDICOM_IMPLEMENTATION_UID = PYDICOM_ROOT_UID + '1'
"""
pydicom's (0002,0012) *Implementation Class UID*
``'1.2.826.0.1.3680043.8.498.1'``
"""

# Regexes for valid UIDs and valid UID prefixes
RE_VALID_UID = r'^(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*$'
"""Regex for a valid UID"""
RE_VALID_UID_PREFIX = r'^(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*\.$'
"""Regex for a valid UID prefix"""


class UID(str):
    """Human friendly UIDs as a Python :class:`str` subclass.

    Examples
    --------

    >>> from pydicom.uid import UID
    >>> uid = UID('1.2.840.10008.1.2.4.50')
    >>> uid
    '1.2.840.10008.1.2.4.50'
    >>> uid.is_implicit_VR
    False
    >>> uid.is_little_endian
    True
    >>> uid.is_transfer_syntax
    True
    >>> uid.name
    'JPEG Baseline (Process 1)'
    """
    def __new__(cls, val):
        """Setup new instance of the class.

        Parameters
        ----------
        val : str or pydicom.uid.UID
            The UID string to use to create the UID object.

        Returns
        -------
        pydicom.uid.UID
            The UID object.
        """
        # Don't repeat if already a UID class then may get the name that
        #   str(uid) gives rather than the dotted number
        if isinstance(val, UID):
            return val

        if isinstance(val, str):
            return super(UID, cls).__new__(cls, val.strip())

        raise TypeError("UID must be a string")

    @property
    def is_implicit_VR(self):
        """Return ``True`` if an implicit VR transfer syntax UID."""
        if self.is_transfer_syntax:
            # Implicit VR Little Endian
            if self == '1.2.840.10008.1.2':
                return True

            # Explicit VR Little Endian
            # Explicit VR Big Endian
            # Deflated Explicit VR Little Endian
            # All encapsulated transfer syntaxes
            return False

        raise ValueError('UID is not a transfer syntax.')

    @property
    def is_little_endian(self):
        """Return ``True`` if a little endian transfer syntax UID."""
        if self.is_transfer_syntax:
            # Explicit VR Big Endian
            if self == '1.2.840.10008.1.2.2':
                return False

            # Explicit VR Little Endian
            # Implicit VR Little Endian
            # Deflated Explicit VR Little Endian
            # All encapsulated transfer syntaxes
            return True

        raise ValueError('UID is not a transfer syntax.')

    @property
    def is_transfer_syntax(self):
        """Return ``True`` if a transfer syntax UID."""
        if not self.is_private:
            return self.type == "Transfer Syntax"

        raise ValueError("Can't determine UID type for private UIDs.")

    @property
    def is_deflated(self):
        """Return ``True`` if a deflated transfer syntax UID."""
        if self.is_transfer_syntax:
            # Deflated Explicit VR Little Endian
            if self == '1.2.840.10008.1.2.1.99':
                return True

            # Explicit VR Little Endian
            # Implicit VR Little Endian
            # Explicit VR Big Endian
            # All encapsulated transfer syntaxes
            return False

        raise ValueError('UID is not a transfer syntax.')

    @property
    def is_encapsulated(self):
        """Return ``True`` if an encasulated transfer syntax UID."""
        return self.is_compressed

    @property
    def is_compressed(self):
        """Return ``True`` if a compressed transfer syntax UID."""
        if self.is_transfer_syntax:
            # Explicit VR Little Endian
            # Implicit VR Little Endian
            # Explicit VR Big Endian
            # Deflated Explicit VR Little Endian
            if self in ['1.2.840.10008.1.2', '1.2.840.10008.1.2.1',
                        '1.2.840.10008.1.2.2', '1.2.840.10008.1.2.1.99']:
                return False

            # All encapsulated transfer syntaxes
            return True

        raise ValueError('UID is not a transfer syntax.')

    @property
    def name(self):
        """Return the UID name from the UID dictionary."""
        uid_string = str.__str__(self)
        if uid_string in UID_dictionary:
            return UID_dictionary[self][0]

        return uid_string

    @property
    def type(self):
        """Return the UID type from the UID dictionary."""
        if str.__str__(self) in UID_dictionary:
            return UID_dictionary[self][1]

        return ''

    @property
    def info(self):
        """Return the UID info from the UID dictionary."""
        if str.__str__(self) in UID_dictionary:
            return UID_dictionary[self][2]

        return ''

    @property
    def is_retired(self):
        """Return ``True`` if the UID is retired, ``False`` otherwise or if
        private.
        """
        if str.__str__(self) in UID_dictionary:
            return bool(UID_dictionary[self][3])

        return False

    @property
    def is_private(self):
        """Return ``True`` if the UID isn't an officially registered DICOM
        UID.
        """
        if self[:13] == '1.2.840.10008':
            return False

        return True

    @property
    def is_valid(self):
        """Return ``True`` if `self` is a valid UID, ``False`` otherwise."""
        if len(self) <= 64 and re.match(RE_VALID_UID, self):
            return True

        return False


# Pre-defined Transfer Syntax UIDs (for convenience)
ImplicitVRLittleEndian = UID('1.2.840.10008.1.2')
"""1.2.840.10008.1.2"""
ExplicitVRLittleEndian = UID('1.2.840.10008.1.2.1')
"""1.2.840.10008.1.2.1"""
DeflatedExplicitVRLittleEndian = UID('1.2.840.10008.1.2.1.99')
"""1.2.840.10008.1.2.1.99"""
ExplicitVRBigEndian = UID('1.2.840.10008.1.2.2')
"""1.2.840.10008.1.2.2"""
JPEGBaseline = UID('1.2.840.10008.1.2.4.50')
"""1.2.840.10008.1.2.4.50"""
JPEGExtended = UID('1.2.840.10008.1.2.4.51')
"""1.2.840.10008.1.2.4.51"""
JPEGLosslessP14 = UID('1.2.840.10008.1.2.4.57')
"""1.2.840.10008.1.2.4.57"""
JPEGLossless = UID('1.2.840.10008.1.2.4.70')
"""1.2.840.10008.1.2.4.70"""
JPEGLSLossless = UID('1.2.840.10008.1.2.4.80')
"""1.2.840.10008.1.2.4.80"""
JPEGLSLossy = UID('1.2.840.10008.1.2.4.81')
"""1.2.840.10008.1.2.4.81"""
JPEG2000Lossless = UID('1.2.840.10008.1.2.4.90')
"""1.2.840.10008.1.2.4.90"""
JPEG2000 = UID('1.2.840.10008.1.2.4.91')
"""1.2.840.10008.1.2.4.91"""
JPEG2000MultiComponentLossless = UID('1.2.840.10008.1.2.4.92')
"""1.2.840.10008.1.2.4.92"""
JPEG2000MultiComponent = UID('1.2.840.10008.1.2.4.93')
"""1.2.840.10008.1.2.4.93"""
RLELossless = UID('1.2.840.10008.1.2.5')
"""1.2.840.10008.1.2.5"""

UncompressedPixelTransferSyntaxes = [
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian,
    ExplicitVRBigEndian,
]

JPEGLSSupportedCompressedPixelTransferSyntaxes = [
    JPEGLSLossless,
    JPEGLSLossy,
]

PILSupportedCompressedPixelTransferSyntaxes = [
    JPEGBaseline,
    JPEGLossless,
    JPEGExtended,
    JPEG2000Lossless,
    JPEG2000,
]

JPEG2000CompressedPixelTransferSyntaxes = [
    JPEG2000Lossless,
    JPEG2000,
]

JPEGLossyCompressedPixelTransferSyntaxes = [
    JPEGBaseline,
    JPEGExtended,
]


RLECompressedLosslessSyntaxes = [
    RLELossless
]


def generate_uid(prefix=PYDICOM_ROOT_UID, entropy_srcs=None):
    """Return a 64 character UID which starts with `prefix`.

    .. versionchanged:: 1.3

       When `prefix` is ``None`` a conformant UUID suffix of up to
       39 characters will be used instead of a hashed value.

    Parameters
    ----------
    prefix : str or None
        The UID prefix to use when creating the UID. Default is the *pydicom*
        root UID ``'1.2.826.0.1.3680043.8.498.'``. If ``None`` then a prefix of
        ``'2.25.'`` will be used with the integer form of a UUID generated
        using the :func:`uuid.uuid4` algorithm.
    entropy_srcs : list of str or None
        If `prefix` is not ``None``, then `prefix` will be appended with a
        SHA512 hash of the :class:`list` which means the result is
        deterministic and should make the original data unrecoverable. If
        ``None`` random data will be used (default).

    Returns
    -------
    pydicom.uid.UID
        A DICOM UID of up to 64 characters.

    Raises
    ------
    ValueError
        If `prefix` is invalid or greater than 63 characters.

    Examples
    --------

    >>> from pydicom.uid import generate_uid
    >>> generate_uid()
    1.2.826.0.1.3680043.8.498.22463838056059845879389038257786771680
    >>> generate_uid(prefix=None)
    2.25.167161297070865690102504091919570542144
    >>> generate_uid(entropy_srcs=['lorem', 'ipsum'])
    1.2.826.0.1.3680043.8.498.87507166259346337659265156363895084463
    >>> generate_uid(entropy_srcs=['lorem', 'ipsum'])
    1.2.826.0.1.3680043.8.498.87507166259346337659265156363895084463
    """
    if prefix is None:
        # UUID -> as 128-bit int -> max 39 characters long
        return UID('2.25.{}'.format(uuid.uuid4().int))

    max_uid_len = 64
    if len(prefix) > max_uid_len - 1:
        raise ValueError("The prefix must be less than 63 chars")
    if not re.match(RE_VALID_UID_PREFIX, prefix):
        raise ValueError("The prefix is not in a valid format")

    avail_digits = max_uid_len - len(prefix)

    if entropy_srcs is None:
        entropy_srcs = [
            str(uuid.uuid1()),  # 128-bit from MAC/time/randomness
            str(os.getpid()),  # Current process ID
            hex(random.getrandbits(64))  # 64 bits randomness
        ]
    hash_val = hashlib.sha512(''.join(entropy_srcs).encode('utf-8'))

    # Convert this to an int with the maximum available digits
    dicom_uid = prefix + str(int(hash_val.hexdigest(), 16))[:avail_digits]

    return UID(dicom_uid)
