# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Use the `pillow <https://python-pillow.org/>`_ Python package
to decode *Pixel Data*.
"""

import io
import logging
from struct import unpack
import warnings

try:
    import numpy
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

try:
    import PIL
    from PIL import Image, features
    HAVE_PIL = True
    HAVE_JPEG = features.check_codec("jpg")
    HAVE_JPEG2K = features.check_codec("jpg_2000")
except ImportError:
    HAVE_PIL = False
    HAVE_JPEG = False
    HAVE_JPEG2K = False

from pydicom.encaps import defragment_data, decode_data_sequence
from pydicom.pixel_data_handlers.util import pixel_dtype
import pydicom.uid


logger = logging.getLogger('pydicom')

PillowSupportedTransferSyntaxes = [
    pydicom.uid.JPEGBaseline,
    pydicom.uid.JPEGLossless,
    pydicom.uid.JPEGExtended,
    pydicom.uid.JPEG2000,
    pydicom.uid.JPEG2000Lossless,
]
PillowJPEG2000TransferSyntaxes = [
    pydicom.uid.JPEG2000,
    pydicom.uid.JPEG2000Lossless,
]
PillowJPEGTransferSyntaxes = [
    pydicom.uid.JPEGBaseline,
    pydicom.uid.JPEGExtended,
]

HANDLER_NAME = 'Pillow'

DEPENDENCIES = {
    'numpy': ('http://www.numpy.org/', 'NumPy'),
    'PIL': ('https://python-pillow.org/', 'Pillow'),
}


def is_available():
    """Return ``True`` if the handler has its dependencies met."""
    return HAVE_NP and HAVE_PIL


def supports_transfer_syntax(transfer_syntax):
    """Return ``True`` if the handler supports the `transfer_syntax`.

    Parameters
    ----------
    transfer_syntax : uid.UID
        The Transfer Syntax UID of the *Pixel Data* that is to be used with
        the handler.
    """
    return transfer_syntax in PillowSupportedTransferSyntaxes


def needs_to_convert_to_RGB(ds):
    """Return ``True`` if the *Pixel Data* should to be converted from YCbCr to
    RGB.

    This affects JPEG transfer syntaxes.
    """
    return False


def should_change_PhotometricInterpretation_to_RGB(ds):
    """Return ``True`` if the *Photometric Interpretation* should be changed
    to RGB.

    This affects JPEG transfer syntaxes.
    """
    should_change = ds.SamplesPerPixel == 3
    return False


def get_pixeldata(ds):
    """Return a :class:`numpy.ndarray` of the *Pixel Data*.

    Parameters
    ----------
    ds : Dataset
        The :class:`Dataset` containing an Image Pixel module and the
        *Pixel Data* to be decompressed and returned.

    Returns
    -------
    numpy.ndarray
       The contents of (7FE0,0010) *Pixel Data* as a 1D array.

    Raises
    ------
    ImportError
        If Pillow is not available.
    NotImplementedError
        If the transfer syntax is not supported
    """
    logger.debug("Trying to use Pillow to read pixel array "
                 "(has pillow = %s)", HAVE_PIL)
    transfer_syntax = ds.file_meta.TransferSyntaxUID
    if not HAVE_PIL:
        msg = ("The pillow package is required to use pixel_array for "
               "this transfer syntax {0}, and pillow could not be "
               "imported.".format(transfer_syntax.name))
        raise ImportError(msg)

    if not HAVE_JPEG and transfer_syntax in PillowJPEGTransferSyntaxes:
        msg = ("this transfer syntax {0}, can not be read because "
               "Pillow lacks the jpeg decoder plugin"
               .format(transfer_syntax.name))
        raise NotImplementedError(msg)

    if not HAVE_JPEG2K and transfer_syntax in PillowJPEG2000TransferSyntaxes:
        msg = ("this transfer syntax {0}, can not be read because "
               "Pillow lacks the jpeg 2000 decoder plugin"
               .format(transfer_syntax.name))
        raise NotImplementedError(msg)

    if transfer_syntax not in PillowSupportedTransferSyntaxes:
        msg = ("this transfer syntax {0}, can not be read because "
               "Pillow does not support this syntax"
               .format(transfer_syntax.name))
        raise NotImplementedError(msg)

    if transfer_syntax in PillowJPEGTransferSyntaxes:
        logger.debug("This is a JPEG lossy format")
        if ds.BitsAllocated > 8:
            raise NotImplementedError("JPEG Lossy only supported if "
                                      "Bits Allocated = 8")
    elif transfer_syntax in PillowJPEG2000TransferSyntaxes:
        logger.debug("This is a JPEG 2000 format")
    else:
        logger.debug("This is a another pillow supported format")

    pixel_bytes = bytearray()
    if getattr(ds, 'NumberOfFrames', 1) > 1:
        j2k_precision = None
        # multiple compressed frames
        for frame in decode_data_sequence(ds.PixelData):
            im = Image.open(io.BytesIO(frame))
            if 'YBR' in ds.PhotometricInterpretation:
                im.draft('YCbCr', (ds.Rows, ds.Columns))
            pixel_bytes.extend(im.tobytes())

            if not j2k_precision:
                j2k_precision = _get_j2k_precision(frame)
    else:
        # single compressed frame
        pixel_data = defragment_data(ds.PixelData)
        im = Image.open(io.BytesIO(pixel_data))
        if 'YBR' in ds.PhotometricInterpretation:
            im.draft('YCbCr', (ds.Rows, ds.Columns))
        pixel_bytes.extend(im.tobytes())

        j2k_precision = _get_j2k_precision(pixel_data)

    logger.debug("Successfully read %s pixel bytes", len(pixel_bytes))

    arr = numpy.frombuffer(pixel_bytes, pixel_dtype(ds))

    if transfer_syntax in PillowJPEG2000TransferSyntaxes:
        # See #693 for justification of flipping MSB and bit shifting
        if ds.BitsAllocated == 16 and ds.PixelRepresentation == 1:
            # WHY IS THIS EVEN NECESSARY??
            # Flip MSb: b10000000 00000000
            arr ^= 0x8000

        if j2k_precision and j2k_precision != ds.BitsStored:
            warnings.warn(
                "The sample bit depth of the JPEG 2000 pixel data doesn't "
                "match the (0028,0101) 'Bits Stored' value ({} vs {} bit). "
                "You may have to update the 'Bits Stored' value with "
                "the sample bit depth in order to get the correct pixel data"
                .format(j2k_precision, ds.BitsStored)
            )

        shift = ds.BitsAllocated - ds.BitsStored
        logger.debug("Shifting right by {} bits".format(shift))
        numpy.right_shift(arr, shift, out=arr)

    if should_change_PhotometricInterpretation_to_RGB(ds):
        ds.PhotometricInterpretation = "RGB"

    return arr


def _get_j2k_precision(bs):
    """Parse `bs` and return the bit depth of the JPEG2K component samples.

    Parameters
    ----------
    bs : bytes
        The JPEG 2000 (ISO/IEC 154444) data to be parsed.

    Returns
    -------
    int or None
        The bit depth (precision) of the component samples if available,
        ``None`` otherwise.
    """
    try:
        # First 2 bytes must be the SOC marker - if not then wrong format
        if bs[0:2] != b'\xff\x4f':
            return

        # SIZ is required to be the second marker - Figure A-3 in 15444-1
        if bs[2:4] != b'\xff\x51':
            return

        # See 15444-1 A.5.1 for format of the SIZ box and contents
        ssiz = bs[42:43]
        if ssiz[0] & (1 << 7):
            # Signed
            return (ssiz[0] & 0x7F) + 1
        else:
            # Unsigned
            return ssiz[0] + 1
    except IndexError:
        return
