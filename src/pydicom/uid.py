# Copyright 2008-2022 pydicom authors. See LICENSE file for details.
"""Functions for handling DICOM unique identifiers (UIDs)"""

import hashlib
import re
import secrets
import uuid

from pydicom import config
from pydicom._uid_dict import UID_dictionary
from pydicom.config import disable_value_validation
from pydicom.valuerep import STR_VR_REGEXES, validate_value


class UID(str):
    """Human friendly UIDs as a Python :class:`str` subclass.

    **Private Transfer Syntaxes**

    If creating a private transfer syntax UID, then you must also use
    :meth:`~pydicom.UID.set_private_encoding` to set the corresponding
    dataset encoding.

    Examples
    --------

    General usage::

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
      >>> uid.keyword
      JPEGBaseline8Bit

    Setting the encoding to explicit VR little endian for a private transfer
    syntax::

      >>> uid = UID("1.2.3.4")
      >>> uid.set_private_encoding(False, True)

    """

    _PRIVATE_TS_ENCODING: tuple[bool, bool]

    def __new__(
        cls: type["UID"], val: str, validation_mode: int | None = None
    ) -> "UID":
        """Setup new instance of the class.

        Parameters
        ----------
        val : str or pydicom.uid.UID
            The UID string to use to create the UID object.
        validation_mode : int
            Defines if values are validated and how validation errors are
            handled.

        Returns
        -------
        pydicom.uid.UID
            The UID object.
        """
        if isinstance(val, str):
            if validation_mode is None:
                validation_mode = config.settings.reading_validation_mode
            validate_value("UI", val, validation_mode)

            uid = super().__new__(cls, val.strip())
            if hasattr(val, "_PRIVATE_TS_ENCODING"):
                uid._PRIVATE_TS_ENCODING = val._PRIVATE_TS_ENCODING

            return uid

        raise TypeError("A UID must be created from a string")

    @property
    def is_implicit_VR(self) -> bool:
        """Return ``True`` if an implicit VR transfer syntax UID."""
        if self.is_transfer_syntax:
            if not self.is_private:
                # Implicit VR Little Endian
                if self == "1.2.840.10008.1.2":
                    return True

                # Explicit VR Little Endian
                # Explicit VR Big Endian
                # Deflated Explicit VR Little Endian
                # All encapsulated transfer syntaxes
                return False

            return self._PRIVATE_TS_ENCODING[0]

        raise ValueError("UID is not a transfer syntax.")

    @property
    def is_little_endian(self) -> bool:
        """Return ``True`` if a little endian transfer syntax UID."""
        if self.is_transfer_syntax:
            if not self.is_private:
                # Explicit VR Big Endian
                if self == "1.2.840.10008.1.2.2":
                    return False

                # Explicit VR Little Endian
                # Implicit VR Little Endian
                # Deflated Explicit VR Little Endian
                # All encapsulated transfer syntaxes
                return True

            return self._PRIVATE_TS_ENCODING[1]

        raise ValueError("UID is not a transfer syntax.")

    @property
    def is_transfer_syntax(self) -> bool:
        """Return ``True`` if a transfer syntax UID."""
        if not self.is_private:
            return self.type == "Transfer Syntax"

        return hasattr(self, "_PRIVATE_TS_ENCODING")

    @property
    def is_deflated(self) -> bool:
        """Return ``True`` if a deflated transfer syntax UID."""
        if self.is_transfer_syntax:
            # Deflated Explicit VR Little Endian
            if self == "1.2.840.10008.1.2.1.99":
                return True

            # Explicit VR Little Endian
            # Implicit VR Little Endian
            # Explicit VR Big Endian
            # All encapsulated transfer syntaxes
            return False

        raise ValueError("UID is not a transfer syntax.")

    @property
    def is_encapsulated(self) -> bool:
        """Return ``True`` if an encasulated transfer syntax UID."""
        return self.is_compressed

    @property
    def is_compressed(self) -> bool:
        """Return ``True`` if a compressed transfer syntax UID."""
        if self.is_transfer_syntax:
            # Explicit VR Little Endian
            # Implicit VR Little Endian
            # Explicit VR Big Endian
            # Deflated Explicit VR Little Endian
            if self in [
                "1.2.840.10008.1.2",
                "1.2.840.10008.1.2.1",
                "1.2.840.10008.1.2.2",
                "1.2.840.10008.1.2.1.99",
            ]:
                return False

            # All encapsulated transfer syntaxes
            return True

        raise ValueError("UID is not a transfer syntax.")

    @property
    def keyword(self) -> str:
        """Return the UID keyword from the UID dictionary."""
        if str(self) in UID_dictionary:
            return UID_dictionary[self][4]

        return ""

    @property
    def name(self) -> str:
        """Return the UID name from the UID dictionary."""
        uid_string = str(self)
        if uid_string in UID_dictionary:
            return UID_dictionary[self][0]

        return uid_string

    @property
    def type(self) -> str:
        """Return the UID type from the UID dictionary."""
        if str(self) in UID_dictionary:
            return UID_dictionary[self][1]

        return ""

    @property
    def info(self) -> str:
        """Return the UID info from the UID dictionary."""
        if str(self) in UID_dictionary:
            return UID_dictionary[self][2]

        return ""

    @property
    def is_retired(self) -> bool:
        """Return ``True`` if the UID is retired, ``False`` otherwise or if
        private.
        """
        if str(self) in UID_dictionary:
            return bool(UID_dictionary[self][3])

        return False

    @property
    def is_private(self) -> bool:
        """Return ``True`` if the UID isn't an officially registered DICOM
        UID.
        """
        return self[:14] != "1.2.840.10008."

    @property
    def is_valid(self) -> bool:
        """Return ``True`` if `self` is a valid UID, ``False`` otherwise."""
        if len(self) <= 64 and re.match(RE_VALID_UID, self):
            return True

        return False

    def set_private_encoding(self, implicit_vr: bool, little_endian: bool) -> None:
        """Set the corresponding dataset encoding for a privately defined transfer
        syntax.

        .. versionadded:: 3.0

        Parameters
        ----------
        implicit_vr : bool
            ``True`` if the corresponding dataset encoding uses implicit VR,
            ``False`` for explicit VR.
        little_endian : bool
            ``True`` if the corresponding dataset encoding uses little endian
            byte order, ``False`` for big endian byte order.
        """
        self._PRIVATE_TS_ENCODING = (implicit_vr, little_endian)


# Many thanks to the Medical Connections for offering free
# valid UIDs (https://www.medicalconnections.co.uk/FreeUID.html)
# Their service was used to obtain the following root UID for pydicom:
PYDICOM_ROOT_UID = "1.2.826.0.1.3680043.8.498."
"""pydicom's root UID ``'1.2.826.0.1.3680043.8.498.'``"""
PYDICOM_IMPLEMENTATION_UID = UID(f"{PYDICOM_ROOT_UID}1")
"""
pydicom's (0002,0012) *Implementation Class UID*
``'1.2.826.0.1.3680043.8.498.1'``
"""

# Regexes for valid UIDs and valid UID prefixes
RE_VALID_UID = STR_VR_REGEXES["UI"]
"""Regex for a valid UID"""
RE_VALID_UID_PREFIX = re.compile(r"^(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*\.$")
"""Regex for a valid UID prefix"""


with disable_value_validation():
    # Pre-defined Transfer Syntax UIDs (for convenience)
    ImplicitVRLittleEndian = UID("1.2.840.10008.1.2")
    """1.2.840.10008.1.2"""
    ExplicitVRLittleEndian = UID("1.2.840.10008.1.2.1")
    """1.2.840.10008.1.2.1"""
    DeflatedExplicitVRLittleEndian = UID("1.2.840.10008.1.2.1.99")
    """1.2.840.10008.1.2.1.99"""
    ExplicitVRBigEndian = UID("1.2.840.10008.1.2.2")
    """1.2.840.10008.1.2.2"""
    JPEGBaseline8Bit = UID("1.2.840.10008.1.2.4.50")
    """1.2.840.10008.1.2.4.50"""
    JPEGExtended12Bit = UID("1.2.840.10008.1.2.4.51")
    """1.2.840.10008.1.2.4.51"""
    JPEGLossless = UID("1.2.840.10008.1.2.4.57")
    """1.2.840.10008.1.2.4.57"""
    JPEGLosslessSV1 = UID("1.2.840.10008.1.2.4.70")
    """1.2.840.10008.1.2.4.70"""
    JPEGLSLossless = UID("1.2.840.10008.1.2.4.80")
    """1.2.840.10008.1.2.4.80"""
    JPEGLSNearLossless = UID("1.2.840.10008.1.2.4.81")
    """1.2.840.10008.1.2.4.81"""
    JPEG2000Lossless = UID("1.2.840.10008.1.2.4.90")
    """1.2.840.10008.1.2.4.90"""
    JPEG2000 = UID("1.2.840.10008.1.2.4.91")
    """1.2.840.10008.1.2.4.91"""
    JPEG2000MCLossless = UID("1.2.840.10008.1.2.4.92")
    """1.2.840.10008.1.2.4.92"""
    JPEG2000MC = UID("1.2.840.10008.1.2.4.93")
    """1.2.840.10008.1.2.4.93"""
    MPEG2MPML = UID("1.2.840.10008.1.2.4.100")
    """1.2.840.10008.1.2.4.100"""
    MPEG2MPMLF = UID("1.2.840.10008.1.2.4.100.1")
    """1.2.840.10008.1.2.4.100.1"""
    MPEG2MPHL = UID("1.2.840.10008.1.2.4.101")
    """1.2.840.10008.1.2.4.101"""
    MPEG2MPHLF = UID("1.2.840.10008.1.2.4.101.1")
    """1.2.840.10008.1.2.4.101.1"""
    MPEG4HP41 = UID("1.2.840.10008.1.2.4.102")
    """1.2.840.10008.1.2.4.102"""
    MPEG4HP41F = UID("1.2.840.10008.1.2.4.102.1")
    """1.2.840.10008.1.2.4.102.1"""
    MPEG4HP41BD = UID("1.2.840.10008.1.2.4.103")
    """1.2.840.10008.1.2.4.103"""
    MPEG4HP41BDF = UID("1.2.840.10008.1.2.4.103.1")
    """1.2.840.10008.1.2.4.103.1"""
    MPEG4HP422D = UID("1.2.840.10008.1.2.4.104")
    """1.2.840.10008.1.2.4.104"""
    MPEG4HP422DF = UID("1.2.840.10008.1.2.4.104.1")
    """1.2.840.10008.1.2.4.104.1"""
    MPEG4HP423D = UID("1.2.840.10008.1.2.4.105")
    """1.2.840.10008.1.2.4.105"""
    MPEG4HP423DF = UID("1.2.840.10008.1.2.4.105.1")
    """1.2.840.10008.1.2.4.105.1"""
    MPEG4HP42STEREO = UID("1.2.840.10008.1.2.4.106")
    """1.2.840.10008.1.2.4.106"""
    MPEG4HP42STEREOF = UID("1.2.840.10008.1.2.4.106.1")
    """1.2.840.10008.1.2.4.106.1"""
    HEVCMP51 = UID("1.2.840.10008.1.2.4.107")
    """1.2.840.10008.1.2.4.107"""
    HEVCM10P51 = UID("1.2.840.10008.1.2.4.108")
    """1.2.840.10008.1.2.4.108"""
    HTJ2KLossless = UID("1.2.840.10008.1.2.4.201")
    """1.2.840.10008.1.2.4.201"""
    HTJ2KLosslessRPCL = UID("1.2.840.10008.1.2.4.202")
    """1.2.840.10008.1.2.4.202"""
    HTJ2K = UID("1.2.840.10008.1.2.4.203")
    """1.2.840.10008.1.2.4.203"""
    JPIPHTJ2KReferenced = UID("1.2.840.10008.1.2.4.204")
    """1.2.840.10008.1.2.4.204"""
    JPIPHTJ2KReferencedDeflate = UID("1.2.840.10008.1.2.4.205")
    """1.2.840.10008.1.2.4.205"""
    RLELossless = UID("1.2.840.10008.1.2.5")
    """1.2.840.10008.1.2.5"""
    SMPTEST211020UncompressedProgressiveActiveVideo = UID("1.2.840.10008.1.2.7.1")
    """1.2.840.10008.1.2.7.1"""
    SMPTEST211020UncompressedInterlacedActiveVideo = UID("1.2.840.10008.1.2.7.2")
    """1.2.840.10008.1.2.7.2"""
    SMPTEST211030PCMDigitalAudio = UID("1.2.840.10008.1.2.7.3")
    """1.2.840.10008.1.2.7.3"""

AllTransferSyntaxes = [
    ImplicitVRLittleEndian,
    ExplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian,
    ExplicitVRBigEndian,
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEGLossless,
    JPEGLosslessSV1,
    JPEGLSLossless,
    JPEGLSNearLossless,
    JPEG2000Lossless,
    JPEG2000,
    JPEG2000MCLossless,
    JPEG2000MC,
    MPEG2MPML,
    MPEG2MPMLF,
    MPEG2MPHL,
    MPEG2MPHLF,
    MPEG4HP41,
    MPEG4HP41F,
    MPEG4HP41BD,
    MPEG4HP41BDF,
    MPEG4HP422D,
    MPEG4HP422DF,
    MPEG4HP423D,
    MPEG4HP423DF,
    MPEG4HP42STEREO,
    MPEG4HP42STEREOF,
    HEVCMP51,
    HEVCM10P51,
    HTJ2KLossless,
    HTJ2KLosslessRPCL,
    HTJ2K,
    JPIPHTJ2KReferenced,
    JPIPHTJ2KReferencedDeflate,
    RLELossless,
    SMPTEST211020UncompressedProgressiveActiveVideo,
    SMPTEST211020UncompressedInterlacedActiveVideo,
    SMPTEST211030PCMDigitalAudio,
]
"""All non-retired transfer syntaxes and *Explicit VR Big Endian*."""

JPEGTransferSyntaxes = [
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEGLossless,
    JPEGLosslessSV1,
]
"""JPEG (ISO/IEC 10918-1) transfer syntaxes"""

JPEGLSTransferSyntaxes = [JPEGLSLossless, JPEGLSNearLossless]
"""JPEG-LS (ISO/IEC 14495-1) transfer syntaxes."""

JPEG2000TransferSyntaxes = [
    JPEG2000Lossless,
    JPEG2000,
    JPEG2000MCLossless,
    JPEG2000MC,
    HTJ2KLossless,
    HTJ2KLosslessRPCL,
    HTJ2K,
]
"""JPEG 2000 (ISO/IEC 15444-1) transfer syntaxes."""

MPEGTransferSyntaxes = [
    MPEG2MPML,
    MPEG2MPMLF,
    MPEG2MPHL,
    MPEG2MPHLF,
    MPEG4HP41,
    MPEG4HP41F,
    MPEG4HP41BD,
    MPEG4HP41BDF,
    MPEG4HP422D,
    MPEG4HP422DF,
    MPEG4HP423D,
    MPEG4HP423DF,
    MPEG4HP42STEREO,
    MPEG4HP42STEREOF,
    HEVCMP51,
    HEVCM10P51,
]
"""MPEG transfer syntaxes."""

RLETransferSyntaxes = [RLELossless]
"""RLE transfer syntaxes."""

UncompressedTransferSyntaxes = [
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian,
    ExplicitVRBigEndian,
]
"""Uncompressed (native) transfer syntaxes."""

PrivateTransferSyntaxes = []
"""Private transfer syntaxes added using the
:func:`~pydicom.uid.register_transfer_syntax` function.
"""


def register_transfer_syntax(
    uid: str | UID,
    implicit_vr: bool | None = None,
    little_endian: bool | None = None,
) -> UID:
    """Register a private transfer syntax with the :mod:`~pydicom.uid` module
    so it can be used when reading datasets with :func:`~pydicom.filereader.dcmread`.

    .. versionadded: 3.0

    Parameters
    ----------
    uid : str | pydicom.uid.UID
        A UID which may or may not have had the corresponding dataset encoding
        set using :meth:`~pydicom.uid.UID.set_private_encoding`.
    implicit_vr : bool, optional
        If ``True`` then the transfer syntax uses implicit VR encoding, otherwise
        if ``False`` then it uses explicit VR encoding. Required when `uid` has
        not had the encoding set using :meth:`~pydicom.uid.UID.set_private_encoding`.
    little_endian : bool, optional
        If ``True`` then the transfer syntax uses little endian encoding, otherwise
        if ``False`` then it uses big endian encoding. Required when `uid` has
        not had the encoding set using :meth:`~pydicom.uid.UID.set_private_encoding`.

    Returns
    -------
    pydicom.uid.UID
        The registered UID.
    """
    uid = UID(uid)

    if None in (implicit_vr, little_endian) and not uid.is_transfer_syntax:
        raise ValueError(
            "The corresponding dataset encoding for 'uid' must be set using "
            "the 'implicit_vr' and 'little_endian' arguments"
        )

    if implicit_vr is not None and little_endian is not None:
        uid.set_private_encoding(implicit_vr, little_endian)

    if uid not in PrivateTransferSyntaxes:
        PrivateTransferSyntaxes.append(uid)

    return uid


_MAX_PREFIX_LENGTH = 54


def generate_uid(
    prefix: str | None = PYDICOM_ROOT_UID,
    entropy_srcs: list[str] | None = None,
) -> UID:
    """Return a 64 character UID which starts with `prefix`.

    .. versionchanged:: 3.0

       * When `entropy_srcs` is ``None`` the suffix is now generated using
         :func:`~secrets.randbelow`
       * The maximum length of `prefix` is now 54 characters

    Parameters
    ----------
    prefix : str or None, optional
        The UID prefix to use when creating the UID. Default is the *pydicom*
        root UID ``'1.2.826.0.1.3680043.8.498.'``. If `prefix` is ``None`` then
        a prefix of ``'2.25.'`` will be used with the integer form of a UUID
        generated using the :func:`uuid.uuid4` algorithm.
    entropy_srcs : list of str, optional
        If `prefix` is used then the `prefix` will be appended with a
        SHA512 hash of the supplied :class:`list` which means the result is
        deterministic and should make the original data unrecoverable. If
        `entropy_srcs` isn't used then a random number from
        :func:`secrets.randbelow` will be appended to the `prefix`. If `prefix`
        is ``None`` then `entropy_srcs` has no effect.

    Returns
    -------
    pydicom.uid.UID
        A DICOM UID of up to 64 characters.

    Raises
    ------
    ValueError
        If `prefix` is invalid or greater than 54 characters.

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

    References
    ----------

    * DICOM Standard, Part 5, :dcm:`Chapters 9<part05/chapter_9.html>` and
      :dcm:`Annex B<part05/chapter_B.html>`
    * ISO/IEC 9834-8/`ITU-T X.667 <https://www.itu.int/rec/T-REC-X.667-201210-I/en>`_
    """
    if prefix is None:
        # UUID -> as 128-bit int -> max 39 characters long
        return UID(f"2.25.{uuid.uuid4().int}")

    if len(prefix) > _MAX_PREFIX_LENGTH:
        raise ValueError(
            f"The 'prefix' should be no more than {_MAX_PREFIX_LENGTH} characters long"
        )

    if not re.match(RE_VALID_UID_PREFIX, prefix):
        raise ValueError(
            "The 'prefix' is not valid for use with a UID, see Part 5, Section "
            "9.1 of the DICOM Standard"
        )

    if entropy_srcs is None:
        maximum = 10 ** (64 - len(prefix))
        # randbelow is in [0, maximum)
        # {prefix}.0, and {prefix}0 are both valid
        return UID(f"{prefix}{secrets.randbelow(maximum)}"[:64])

    hash_val = hashlib.sha512("".join(entropy_srcs).encode("utf-8"))

    # Convert this to an int with the maximum available digits
    return UID(f"{prefix}{int(hash_val.hexdigest(), 16)}"[:64])


# Only auto-generated Storage SOP Class UIDs below - do not edit manually


MediaStorageDirectoryStorage = UID("1.2.840.10008.1.3.10")
"""1.2.840.10008.1.3.10"""
ComputedRadiographyImageStorage = UID("1.2.840.10008.5.1.4.1.1.1")
"""1.2.840.10008.5.1.4.1.1.1"""
DigitalXRayImageStorageForPresentation = UID("1.2.840.10008.5.1.4.1.1.1.1")
"""1.2.840.10008.5.1.4.1.1.1.1"""
DigitalXRayImageStorageForProcessing = UID("1.2.840.10008.5.1.4.1.1.1.1.1")
"""1.2.840.10008.5.1.4.1.1.1.1.1"""
DigitalMammographyXRayImageStorageForPresentation = UID("1.2.840.10008.5.1.4.1.1.1.2")
"""1.2.840.10008.5.1.4.1.1.1.2"""
DigitalMammographyXRayImageStorageForProcessing = UID("1.2.840.10008.5.1.4.1.1.1.2.1")
"""1.2.840.10008.5.1.4.1.1.1.2.1"""
DigitalIntraOralXRayImageStorageForPresentation = UID("1.2.840.10008.5.1.4.1.1.1.3")
"""1.2.840.10008.5.1.4.1.1.1.3"""
DigitalIntraOralXRayImageStorageForProcessing = UID("1.2.840.10008.5.1.4.1.1.1.3.1")
"""1.2.840.10008.5.1.4.1.1.1.3.1"""
EncapsulatedPDFStorage = UID("1.2.840.10008.5.1.4.1.1.104.1")
"""1.2.840.10008.5.1.4.1.1.104.1"""
EncapsulatedCDAStorage = UID("1.2.840.10008.5.1.4.1.1.104.2")
"""1.2.840.10008.5.1.4.1.1.104.2"""
EncapsulatedSTLStorage = UID("1.2.840.10008.5.1.4.1.1.104.3")
"""1.2.840.10008.5.1.4.1.1.104.3"""
EncapsulatedOBJStorage = UID("1.2.840.10008.5.1.4.1.1.104.4")
"""1.2.840.10008.5.1.4.1.1.104.4"""
EncapsulatedMTLStorage = UID("1.2.840.10008.5.1.4.1.1.104.5")
"""1.2.840.10008.5.1.4.1.1.104.5"""
GrayscaleSoftcopyPresentationStateStorage = UID("1.2.840.10008.5.1.4.1.1.11.1")
"""1.2.840.10008.5.1.4.1.1.11.1"""
SegmentedVolumeRenderingVolumetricPresentationStateStorage = UID(
    "1.2.840.10008.5.1.4.1.1.11.10"
)
"""1.2.840.10008.5.1.4.1.1.11.10"""
MultipleVolumeRenderingVolumetricPresentationStateStorage = UID(
    "1.2.840.10008.5.1.4.1.1.11.11"
)
"""1.2.840.10008.5.1.4.1.1.11.11"""
VariableModalityLUTSoftcopyPresentationStateStorage = UID(
    "1.2.840.10008.5.1.4.1.1.11.12"
)
"""1.2.840.10008.5.1.4.1.1.11.12"""
ColorSoftcopyPresentationStateStorage = UID("1.2.840.10008.5.1.4.1.1.11.2")
"""1.2.840.10008.5.1.4.1.1.11.2"""
PseudoColorSoftcopyPresentationStateStorage = UID("1.2.840.10008.5.1.4.1.1.11.3")
"""1.2.840.10008.5.1.4.1.1.11.3"""
BlendingSoftcopyPresentationStateStorage = UID("1.2.840.10008.5.1.4.1.1.11.4")
"""1.2.840.10008.5.1.4.1.1.11.4"""
XAXRFGrayscaleSoftcopyPresentationStateStorage = UID("1.2.840.10008.5.1.4.1.1.11.5")
"""1.2.840.10008.5.1.4.1.1.11.5"""
GrayscalePlanarMPRVolumetricPresentationStateStorage = UID(
    "1.2.840.10008.5.1.4.1.1.11.6"
)
"""1.2.840.10008.5.1.4.1.1.11.6"""
CompositingPlanarMPRVolumetricPresentationStateStorage = UID(
    "1.2.840.10008.5.1.4.1.1.11.7"
)
"""1.2.840.10008.5.1.4.1.1.11.7"""
AdvancedBlendingPresentationStateStorage = UID("1.2.840.10008.5.1.4.1.1.11.8")
"""1.2.840.10008.5.1.4.1.1.11.8"""
VolumeRenderingVolumetricPresentationStateStorage = UID("1.2.840.10008.5.1.4.1.1.11.9")
"""1.2.840.10008.5.1.4.1.1.11.9"""
XRayAngiographicImageStorage = UID("1.2.840.10008.5.1.4.1.1.12.1")
"""1.2.840.10008.5.1.4.1.1.12.1"""
EnhancedXAImageStorage = UID("1.2.840.10008.5.1.4.1.1.12.1.1")
"""1.2.840.10008.5.1.4.1.1.12.1.1"""
XRayRadiofluoroscopicImageStorage = UID("1.2.840.10008.5.1.4.1.1.12.2")
"""1.2.840.10008.5.1.4.1.1.12.2"""
EnhancedXRFImageStorage = UID("1.2.840.10008.5.1.4.1.1.12.2.1")
"""1.2.840.10008.5.1.4.1.1.12.2.1"""
PositronEmissionTomographyImageStorage = UID("1.2.840.10008.5.1.4.1.1.128")
"""1.2.840.10008.5.1.4.1.1.128"""
LegacyConvertedEnhancedPETImageStorage = UID("1.2.840.10008.5.1.4.1.1.128.1")
"""1.2.840.10008.5.1.4.1.1.128.1"""
XRay3DAngiographicImageStorage = UID("1.2.840.10008.5.1.4.1.1.13.1.1")
"""1.2.840.10008.5.1.4.1.1.13.1.1"""
XRay3DCraniofacialImageStorage = UID("1.2.840.10008.5.1.4.1.1.13.1.2")
"""1.2.840.10008.5.1.4.1.1.13.1.2"""
BreastTomosynthesisImageStorage = UID("1.2.840.10008.5.1.4.1.1.13.1.3")
"""1.2.840.10008.5.1.4.1.1.13.1.3"""
BreastProjectionXRayImageStorageForPresentation = UID("1.2.840.10008.5.1.4.1.1.13.1.4")
"""1.2.840.10008.5.1.4.1.1.13.1.4"""
BreastProjectionXRayImageStorageForProcessing = UID("1.2.840.10008.5.1.4.1.1.13.1.5")
"""1.2.840.10008.5.1.4.1.1.13.1.5"""
EnhancedPETImageStorage = UID("1.2.840.10008.5.1.4.1.1.130")
"""1.2.840.10008.5.1.4.1.1.130"""
BasicStructuredDisplayStorage = UID("1.2.840.10008.5.1.4.1.1.131")
"""1.2.840.10008.5.1.4.1.1.131"""
IntravascularOpticalCoherenceTomographyImageStorageForPresentation = UID(
    "1.2.840.10008.5.1.4.1.1.14.1"
)
"""1.2.840.10008.5.1.4.1.1.14.1"""
IntravascularOpticalCoherenceTomographyImageStorageForProcessing = UID(
    "1.2.840.10008.5.1.4.1.1.14.2"
)
"""1.2.840.10008.5.1.4.1.1.14.2"""
CTImageStorage = UID("1.2.840.10008.5.1.4.1.1.2")
"""1.2.840.10008.5.1.4.1.1.2"""
EnhancedCTImageStorage = UID("1.2.840.10008.5.1.4.1.1.2.1")
"""1.2.840.10008.5.1.4.1.1.2.1"""
LegacyConvertedEnhancedCTImageStorage = UID("1.2.840.10008.5.1.4.1.1.2.2")
"""1.2.840.10008.5.1.4.1.1.2.2"""
NuclearMedicineImageStorage = UID("1.2.840.10008.5.1.4.1.1.20")
"""1.2.840.10008.5.1.4.1.1.20"""
CTDefinedProcedureProtocolStorage = UID("1.2.840.10008.5.1.4.1.1.200.1")
"""1.2.840.10008.5.1.4.1.1.200.1"""
CTPerformedProcedureProtocolStorage = UID("1.2.840.10008.5.1.4.1.1.200.2")
"""1.2.840.10008.5.1.4.1.1.200.2"""
ProtocolApprovalStorage = UID("1.2.840.10008.5.1.4.1.1.200.3")
"""1.2.840.10008.5.1.4.1.1.200.3"""
XADefinedProcedureProtocolStorage = UID("1.2.840.10008.5.1.4.1.1.200.7")
"""1.2.840.10008.5.1.4.1.1.200.7"""
XAPerformedProcedureProtocolStorage = UID("1.2.840.10008.5.1.4.1.1.200.8")
"""1.2.840.10008.5.1.4.1.1.200.8"""
InventoryStorage = UID("1.2.840.10008.5.1.4.1.1.201.1")
"""1.2.840.10008.5.1.4.1.1.201.1"""
UltrasoundMultiFrameImageStorage = UID("1.2.840.10008.5.1.4.1.1.3.1")
"""1.2.840.10008.5.1.4.1.1.3.1"""
ParametricMapStorage = UID("1.2.840.10008.5.1.4.1.1.30")
"""1.2.840.10008.5.1.4.1.1.30"""
MRImageStorage = UID("1.2.840.10008.5.1.4.1.1.4")
"""1.2.840.10008.5.1.4.1.1.4"""
EnhancedMRImageStorage = UID("1.2.840.10008.5.1.4.1.1.4.1")
"""1.2.840.10008.5.1.4.1.1.4.1"""
MRSpectroscopyStorage = UID("1.2.840.10008.5.1.4.1.1.4.2")
"""1.2.840.10008.5.1.4.1.1.4.2"""
EnhancedMRColorImageStorage = UID("1.2.840.10008.5.1.4.1.1.4.3")
"""1.2.840.10008.5.1.4.1.1.4.3"""
LegacyConvertedEnhancedMRImageStorage = UID("1.2.840.10008.5.1.4.1.1.4.4")
"""1.2.840.10008.5.1.4.1.1.4.4"""
RTImageStorage = UID("1.2.840.10008.5.1.4.1.1.481.1")
"""1.2.840.10008.5.1.4.1.1.481.1"""
RTPhysicianIntentStorage = UID("1.2.840.10008.5.1.4.1.1.481.10")
"""1.2.840.10008.5.1.4.1.1.481.10"""
RTSegmentAnnotationStorage = UID("1.2.840.10008.5.1.4.1.1.481.11")
"""1.2.840.10008.5.1.4.1.1.481.11"""
RTRadiationSetStorage = UID("1.2.840.10008.5.1.4.1.1.481.12")
"""1.2.840.10008.5.1.4.1.1.481.12"""
CArmPhotonElectronRadiationStorage = UID("1.2.840.10008.5.1.4.1.1.481.13")
"""1.2.840.10008.5.1.4.1.1.481.13"""
TomotherapeuticRadiationStorage = UID("1.2.840.10008.5.1.4.1.1.481.14")
"""1.2.840.10008.5.1.4.1.1.481.14"""
RoboticArmRadiationStorage = UID("1.2.840.10008.5.1.4.1.1.481.15")
"""1.2.840.10008.5.1.4.1.1.481.15"""
RTRadiationRecordSetStorage = UID("1.2.840.10008.5.1.4.1.1.481.16")
"""1.2.840.10008.5.1.4.1.1.481.16"""
RTRadiationSalvageRecordStorage = UID("1.2.840.10008.5.1.4.1.1.481.17")
"""1.2.840.10008.5.1.4.1.1.481.17"""
TomotherapeuticRadiationRecordStorage = UID("1.2.840.10008.5.1.4.1.1.481.18")
"""1.2.840.10008.5.1.4.1.1.481.18"""
CArmPhotonElectronRadiationRecordStorage = UID("1.2.840.10008.5.1.4.1.1.481.19")
"""1.2.840.10008.5.1.4.1.1.481.19"""
RTDoseStorage = UID("1.2.840.10008.5.1.4.1.1.481.2")
"""1.2.840.10008.5.1.4.1.1.481.2"""
RoboticRadiationRecordStorage = UID("1.2.840.10008.5.1.4.1.1.481.20")
"""1.2.840.10008.5.1.4.1.1.481.20"""
RTRadiationSetDeliveryInstructionStorage = UID("1.2.840.10008.5.1.4.1.1.481.21")
"""1.2.840.10008.5.1.4.1.1.481.21"""
RTTreatmentPreparationStorage = UID("1.2.840.10008.5.1.4.1.1.481.22")
"""1.2.840.10008.5.1.4.1.1.481.22"""
EnhancedRTImageStorage = UID("1.2.840.10008.5.1.4.1.1.481.23")
"""1.2.840.10008.5.1.4.1.1.481.23"""
EnhancedContinuousRTImageStorage = UID("1.2.840.10008.5.1.4.1.1.481.24")
"""1.2.840.10008.5.1.4.1.1.481.24"""
RTPatientPositionAcquisitionInstructionStorage = UID("1.2.840.10008.5.1.4.1.1.481.25")
"""1.2.840.10008.5.1.4.1.1.481.25"""
RTStructureSetStorage = UID("1.2.840.10008.5.1.4.1.1.481.3")
"""1.2.840.10008.5.1.4.1.1.481.3"""
RTBeamsTreatmentRecordStorage = UID("1.2.840.10008.5.1.4.1.1.481.4")
"""1.2.840.10008.5.1.4.1.1.481.4"""
RTPlanStorage = UID("1.2.840.10008.5.1.4.1.1.481.5")
"""1.2.840.10008.5.1.4.1.1.481.5"""
RTBrachyTreatmentRecordStorage = UID("1.2.840.10008.5.1.4.1.1.481.6")
"""1.2.840.10008.5.1.4.1.1.481.6"""
RTTreatmentSummaryRecordStorage = UID("1.2.840.10008.5.1.4.1.1.481.7")
"""1.2.840.10008.5.1.4.1.1.481.7"""
RTIonPlanStorage = UID("1.2.840.10008.5.1.4.1.1.481.8")
"""1.2.840.10008.5.1.4.1.1.481.8"""
RTIonBeamsTreatmentRecordStorage = UID("1.2.840.10008.5.1.4.1.1.481.9")
"""1.2.840.10008.5.1.4.1.1.481.9"""
DICOSCTImageStorage = UID("1.2.840.10008.5.1.4.1.1.501.1")
"""1.2.840.10008.5.1.4.1.1.501.1"""
DICOSDigitalXRayImageStorageForPresentation = UID("1.2.840.10008.5.1.4.1.1.501.2.1")
"""1.2.840.10008.5.1.4.1.1.501.2.1"""
DICOSDigitalXRayImageStorageForProcessing = UID("1.2.840.10008.5.1.4.1.1.501.2.2")
"""1.2.840.10008.5.1.4.1.1.501.2.2"""
DICOSThreatDetectionReportStorage = UID("1.2.840.10008.5.1.4.1.1.501.3")
"""1.2.840.10008.5.1.4.1.1.501.3"""
DICOS2DAITStorage = UID("1.2.840.10008.5.1.4.1.1.501.4")
"""1.2.840.10008.5.1.4.1.1.501.4"""
DICOS3DAITStorage = UID("1.2.840.10008.5.1.4.1.1.501.5")
"""1.2.840.10008.5.1.4.1.1.501.5"""
DICOSQuadrupoleResonanceStorage = UID("1.2.840.10008.5.1.4.1.1.501.6")
"""1.2.840.10008.5.1.4.1.1.501.6"""
UltrasoundImageStorage = UID("1.2.840.10008.5.1.4.1.1.6.1")
"""1.2.840.10008.5.1.4.1.1.6.1"""
EnhancedUSVolumeStorage = UID("1.2.840.10008.5.1.4.1.1.6.2")
"""1.2.840.10008.5.1.4.1.1.6.2"""
PhotoacousticImageStorage = UID("1.2.840.10008.5.1.4.1.1.6.3")
"""1.2.840.10008.5.1.4.1.1.6.3"""
EddyCurrentImageStorage = UID("1.2.840.10008.5.1.4.1.1.601.1")
"""1.2.840.10008.5.1.4.1.1.601.1"""
EddyCurrentMultiFrameImageStorage = UID("1.2.840.10008.5.1.4.1.1.601.2")
"""1.2.840.10008.5.1.4.1.1.601.2"""
RawDataStorage = UID("1.2.840.10008.5.1.4.1.1.66")
"""1.2.840.10008.5.1.4.1.1.66"""
SpatialRegistrationStorage = UID("1.2.840.10008.5.1.4.1.1.66.1")
"""1.2.840.10008.5.1.4.1.1.66.1"""
SpatialFiducialsStorage = UID("1.2.840.10008.5.1.4.1.1.66.2")
"""1.2.840.10008.5.1.4.1.1.66.2"""
DeformableSpatialRegistrationStorage = UID("1.2.840.10008.5.1.4.1.1.66.3")
"""1.2.840.10008.5.1.4.1.1.66.3"""
SegmentationStorage = UID("1.2.840.10008.5.1.4.1.1.66.4")
"""1.2.840.10008.5.1.4.1.1.66.4"""
SurfaceSegmentationStorage = UID("1.2.840.10008.5.1.4.1.1.66.5")
"""1.2.840.10008.5.1.4.1.1.66.5"""
TractographyResultsStorage = UID("1.2.840.10008.5.1.4.1.1.66.6")
"""1.2.840.10008.5.1.4.1.1.66.6"""
RealWorldValueMappingStorage = UID("1.2.840.10008.5.1.4.1.1.67")
"""1.2.840.10008.5.1.4.1.1.67"""
SurfaceScanMeshStorage = UID("1.2.840.10008.5.1.4.1.1.68.1")
"""1.2.840.10008.5.1.4.1.1.68.1"""
SurfaceScanPointCloudStorage = UID("1.2.840.10008.5.1.4.1.1.68.2")
"""1.2.840.10008.5.1.4.1.1.68.2"""
SecondaryCaptureImageStorage = UID("1.2.840.10008.5.1.4.1.1.7")
"""1.2.840.10008.5.1.4.1.1.7"""
MultiFrameSingleBitSecondaryCaptureImageStorage = UID("1.2.840.10008.5.1.4.1.1.7.1")
"""1.2.840.10008.5.1.4.1.1.7.1"""
MultiFrameGrayscaleByteSecondaryCaptureImageStorage = UID("1.2.840.10008.5.1.4.1.1.7.2")
"""1.2.840.10008.5.1.4.1.1.7.2"""
MultiFrameGrayscaleWordSecondaryCaptureImageStorage = UID("1.2.840.10008.5.1.4.1.1.7.3")
"""1.2.840.10008.5.1.4.1.1.7.3"""
MultiFrameTrueColorSecondaryCaptureImageStorage = UID("1.2.840.10008.5.1.4.1.1.7.4")
"""1.2.840.10008.5.1.4.1.1.7.4"""
VLEndoscopicImageStorage = UID("1.2.840.10008.5.1.4.1.1.77.1.1")
"""1.2.840.10008.5.1.4.1.1.77.1.1"""
VideoEndoscopicImageStorage = UID("1.2.840.10008.5.1.4.1.1.77.1.1.1")
"""1.2.840.10008.5.1.4.1.1.77.1.1.1"""
VLMicroscopicImageStorage = UID("1.2.840.10008.5.1.4.1.1.77.1.2")
"""1.2.840.10008.5.1.4.1.1.77.1.2"""
VideoMicroscopicImageStorage = UID("1.2.840.10008.5.1.4.1.1.77.1.2.1")
"""1.2.840.10008.5.1.4.1.1.77.1.2.1"""
VLSlideCoordinatesMicroscopicImageStorage = UID("1.2.840.10008.5.1.4.1.1.77.1.3")
"""1.2.840.10008.5.1.4.1.1.77.1.3"""
VLPhotographicImageStorage = UID("1.2.840.10008.5.1.4.1.1.77.1.4")
"""1.2.840.10008.5.1.4.1.1.77.1.4"""
VideoPhotographicImageStorage = UID("1.2.840.10008.5.1.4.1.1.77.1.4.1")
"""1.2.840.10008.5.1.4.1.1.77.1.4.1"""
OphthalmicPhotography8BitImageStorage = UID("1.2.840.10008.5.1.4.1.1.77.1.5.1")
"""1.2.840.10008.5.1.4.1.1.77.1.5.1"""
OphthalmicPhotography16BitImageStorage = UID("1.2.840.10008.5.1.4.1.1.77.1.5.2")
"""1.2.840.10008.5.1.4.1.1.77.1.5.2"""
StereometricRelationshipStorage = UID("1.2.840.10008.5.1.4.1.1.77.1.5.3")
"""1.2.840.10008.5.1.4.1.1.77.1.5.3"""
OphthalmicTomographyImageStorage = UID("1.2.840.10008.5.1.4.1.1.77.1.5.4")
"""1.2.840.10008.5.1.4.1.1.77.1.5.4"""
WideFieldOphthalmicPhotographyStereographicProjectionImageStorage = UID(
    "1.2.840.10008.5.1.4.1.1.77.1.5.5"
)
"""1.2.840.10008.5.1.4.1.1.77.1.5.5"""
WideFieldOphthalmicPhotography3DCoordinatesImageStorage = UID(
    "1.2.840.10008.5.1.4.1.1.77.1.5.6"
)
"""1.2.840.10008.5.1.4.1.1.77.1.5.6"""
OphthalmicOpticalCoherenceTomographyEnFaceImageStorage = UID(
    "1.2.840.10008.5.1.4.1.1.77.1.5.7"
)
"""1.2.840.10008.5.1.4.1.1.77.1.5.7"""
OphthalmicOpticalCoherenceTomographyBscanVolumeAnalysisStorage = UID(
    "1.2.840.10008.5.1.4.1.1.77.1.5.8"
)
"""1.2.840.10008.5.1.4.1.1.77.1.5.8"""
VLWholeSlideMicroscopyImageStorage = UID("1.2.840.10008.5.1.4.1.1.77.1.6")
"""1.2.840.10008.5.1.4.1.1.77.1.6"""
DermoscopicPhotographyImageStorage = UID("1.2.840.10008.5.1.4.1.1.77.1.7")
"""1.2.840.10008.5.1.4.1.1.77.1.7"""
ConfocalMicroscopyImageStorage = UID("1.2.840.10008.5.1.4.1.1.77.1.8")
"""1.2.840.10008.5.1.4.1.1.77.1.8"""
ConfocalMicroscopyTiledPyramidalImageStorage = UID("1.2.840.10008.5.1.4.1.1.77.1.9")
"""1.2.840.10008.5.1.4.1.1.77.1.9"""
LensometryMeasurementsStorage = UID("1.2.840.10008.5.1.4.1.1.78.1")
"""1.2.840.10008.5.1.4.1.1.78.1"""
AutorefractionMeasurementsStorage = UID("1.2.840.10008.5.1.4.1.1.78.2")
"""1.2.840.10008.5.1.4.1.1.78.2"""
KeratometryMeasurementsStorage = UID("1.2.840.10008.5.1.4.1.1.78.3")
"""1.2.840.10008.5.1.4.1.1.78.3"""
SubjectiveRefractionMeasurementsStorage = UID("1.2.840.10008.5.1.4.1.1.78.4")
"""1.2.840.10008.5.1.4.1.1.78.4"""
VisualAcuityMeasurementsStorage = UID("1.2.840.10008.5.1.4.1.1.78.5")
"""1.2.840.10008.5.1.4.1.1.78.5"""
SpectaclePrescriptionReportStorage = UID("1.2.840.10008.5.1.4.1.1.78.6")
"""1.2.840.10008.5.1.4.1.1.78.6"""
OphthalmicAxialMeasurementsStorage = UID("1.2.840.10008.5.1.4.1.1.78.7")
"""1.2.840.10008.5.1.4.1.1.78.7"""
IntraocularLensCalculationsStorage = UID("1.2.840.10008.5.1.4.1.1.78.8")
"""1.2.840.10008.5.1.4.1.1.78.8"""
MacularGridThicknessAndVolumeReportStorage = UID("1.2.840.10008.5.1.4.1.1.79.1")
"""1.2.840.10008.5.1.4.1.1.79.1"""
OphthalmicVisualFieldStaticPerimetryMeasurementsStorage = UID(
    "1.2.840.10008.5.1.4.1.1.80.1"
)
"""1.2.840.10008.5.1.4.1.1.80.1"""
OphthalmicThicknessMapStorage = UID("1.2.840.10008.5.1.4.1.1.81.1")
"""1.2.840.10008.5.1.4.1.1.81.1"""
CornealTopographyMapStorage = UID("1.2.840.10008.5.1.4.1.1.82.1")
"""1.2.840.10008.5.1.4.1.1.82.1"""
BasicTextSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.11")
"""1.2.840.10008.5.1.4.1.1.88.11"""
EnhancedSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.22")
"""1.2.840.10008.5.1.4.1.1.88.22"""
ComprehensiveSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.33")
"""1.2.840.10008.5.1.4.1.1.88.33"""
Comprehensive3DSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.34")
"""1.2.840.10008.5.1.4.1.1.88.34"""
ExtensibleSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.35")
"""1.2.840.10008.5.1.4.1.1.88.35"""
ProcedureLogStorage = UID("1.2.840.10008.5.1.4.1.1.88.40")
"""1.2.840.10008.5.1.4.1.1.88.40"""
MammographyCADSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.50")
"""1.2.840.10008.5.1.4.1.1.88.50"""
KeyObjectSelectionDocumentStorage = UID("1.2.840.10008.5.1.4.1.1.88.59")
"""1.2.840.10008.5.1.4.1.1.88.59"""
ChestCADSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.65")
"""1.2.840.10008.5.1.4.1.1.88.65"""
XRayRadiationDoseSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.67")
"""1.2.840.10008.5.1.4.1.1.88.67"""
RadiopharmaceuticalRadiationDoseSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.68")
"""1.2.840.10008.5.1.4.1.1.88.68"""
ColonCADSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.69")
"""1.2.840.10008.5.1.4.1.1.88.69"""
ImplantationPlanSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.70")
"""1.2.840.10008.5.1.4.1.1.88.70"""
AcquisitionContextSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.71")
"""1.2.840.10008.5.1.4.1.1.88.71"""
SimplifiedAdultEchoSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.72")
"""1.2.840.10008.5.1.4.1.1.88.72"""
PatientRadiationDoseSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.73")
"""1.2.840.10008.5.1.4.1.1.88.73"""
PlannedImagingAgentAdministrationSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.74")
"""1.2.840.10008.5.1.4.1.1.88.74"""
PerformedImagingAgentAdministrationSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.75")
"""1.2.840.10008.5.1.4.1.1.88.75"""
EnhancedXRayRadiationDoseSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.76")
"""1.2.840.10008.5.1.4.1.1.88.76"""
WaveformAnnotationSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.77")
"""1.2.840.10008.5.1.4.1.1.88.77"""
TwelveLeadECGWaveformStorage = UID("1.2.840.10008.5.1.4.1.1.9.1.1")
"""1.2.840.10008.5.1.4.1.1.9.1.1"""
GeneralECGWaveformStorage = UID("1.2.840.10008.5.1.4.1.1.9.1.2")
"""1.2.840.10008.5.1.4.1.1.9.1.2"""
AmbulatoryECGWaveformStorage = UID("1.2.840.10008.5.1.4.1.1.9.1.3")
"""1.2.840.10008.5.1.4.1.1.9.1.3"""
General32bitECGWaveformStorage = UID("1.2.840.10008.5.1.4.1.1.9.1.4")
"""1.2.840.10008.5.1.4.1.1.9.1.4"""
HemodynamicWaveformStorage = UID("1.2.840.10008.5.1.4.1.1.9.2.1")
"""1.2.840.10008.5.1.4.1.1.9.2.1"""
CardiacElectrophysiologyWaveformStorage = UID("1.2.840.10008.5.1.4.1.1.9.3.1")
"""1.2.840.10008.5.1.4.1.1.9.3.1"""
BasicVoiceAudioWaveformStorage = UID("1.2.840.10008.5.1.4.1.1.9.4.1")
"""1.2.840.10008.5.1.4.1.1.9.4.1"""
GeneralAudioWaveformStorage = UID("1.2.840.10008.5.1.4.1.1.9.4.2")
"""1.2.840.10008.5.1.4.1.1.9.4.2"""
ArterialPulseWaveformStorage = UID("1.2.840.10008.5.1.4.1.1.9.5.1")
"""1.2.840.10008.5.1.4.1.1.9.5.1"""
RespiratoryWaveformStorage = UID("1.2.840.10008.5.1.4.1.1.9.6.1")
"""1.2.840.10008.5.1.4.1.1.9.6.1"""
MultichannelRespiratoryWaveformStorage = UID("1.2.840.10008.5.1.4.1.1.9.6.2")
"""1.2.840.10008.5.1.4.1.1.9.6.2"""
RoutineScalpElectroencephalogramWaveformStorage = UID("1.2.840.10008.5.1.4.1.1.9.7.1")
"""1.2.840.10008.5.1.4.1.1.9.7.1"""
ElectromyogramWaveformStorage = UID("1.2.840.10008.5.1.4.1.1.9.7.2")
"""1.2.840.10008.5.1.4.1.1.9.7.2"""
ElectrooculogramWaveformStorage = UID("1.2.840.10008.5.1.4.1.1.9.7.3")
"""1.2.840.10008.5.1.4.1.1.9.7.3"""
SleepElectroencephalogramWaveformStorage = UID("1.2.840.10008.5.1.4.1.1.9.7.4")
"""1.2.840.10008.5.1.4.1.1.9.7.4"""
BodyPositionWaveformStorage = UID("1.2.840.10008.5.1.4.1.1.9.8.1")
"""1.2.840.10008.5.1.4.1.1.9.8.1"""
ContentAssessmentResultsStorage = UID("1.2.840.10008.5.1.4.1.1.90.1")
"""1.2.840.10008.5.1.4.1.1.90.1"""
MicroscopyBulkSimpleAnnotationsStorage = UID("1.2.840.10008.5.1.4.1.1.91.1")
"""1.2.840.10008.5.1.4.1.1.91.1"""
RTBrachyApplicationSetupDeliveryInstructionStorage = UID("1.2.840.10008.5.1.4.34.10")
"""1.2.840.10008.5.1.4.34.10"""
RTBeamsDeliveryInstructionStorage = UID("1.2.840.10008.5.1.4.34.7")
"""1.2.840.10008.5.1.4.34.7"""
HangingProtocolStorage = UID("1.2.840.10008.5.1.4.38.1")
"""1.2.840.10008.5.1.4.38.1"""
ColorPaletteStorage = UID("1.2.840.10008.5.1.4.39.1")
"""1.2.840.10008.5.1.4.39.1"""
GenericImplantTemplateStorage = UID("1.2.840.10008.5.1.4.43.1")
"""1.2.840.10008.5.1.4.43.1"""
ImplantAssemblyTemplateStorage = UID("1.2.840.10008.5.1.4.44.1")
"""1.2.840.10008.5.1.4.44.1"""
ImplantTemplateGroupStorage = UID("1.2.840.10008.5.1.4.45.1")
"""1.2.840.10008.5.1.4.45.1"""
