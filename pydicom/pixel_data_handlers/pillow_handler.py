# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Use the `pillow <https://python-pillow.org/>`_ Python package
to decode *Pixel Data*.
"""

import io
import logging

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
    pydicom.uid.JPEG2000Lossless,
]
PillowJPEG2000TransferSyntaxes = [
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
        # multiple compressed frames
        for frame in decode_data_sequence(ds.PixelData):
            decompressed_image = Image.open(io.BytesIO(frame))
            pixel_bytes.extend(decompressed_image.tobytes())
    else:
        # single compressed frame
        pixel_data = defragment_data(ds.PixelData)
        decompressed_image = Image.open(io.BytesIO(pixel_data))
        pixel_bytes.extend(decompressed_image.tobytes())

    logger.debug("Successfully read %s pixel bytes", len(pixel_bytes))

    arr = numpy.frombuffer(pixel_bytes, pixel_dtype(ds))

    if (transfer_syntax in PillowJPEG2000TransferSyntaxes and
            ds.BitsStored == 16):
        # WHY IS THIS EVEN NECESSARY??
        arr &= 0x7FFF

    if should_change_PhotometricInterpretation_to_RGB(ds):
        ds.PhotometricInterpretation = "RGB"

    return arr
