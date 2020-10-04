# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Use the `pillow <https://python-pillow.org/>`_ Python package
to decode *Pixel Data*.
"""

import io
import logging
from typing import TYPE_CHECKING
import warnings

if TYPE_CHECKING:
    from pydicom.dataset import Dataset

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

from pydicom import config
from pydicom.encaps import defragment_data, decode_data_sequence
from pydicom.pixel_data_handlers.util import pixel_dtype, get_j2k_parameters
from pydicom.uid import (
    UID, JPEG2000, JPEG2000Lossless, JPEGBaseline8Bit, JPEGExtended12Bit
)


logger = logging.getLogger('pydicom')


PillowJPEG2000TransferSyntaxes = [JPEG2000, JPEG2000Lossless]
PillowJPEGTransferSyntaxes = [JPEGBaseline8Bit, JPEGExtended12Bit]
PillowSupportedTransferSyntaxes = (
    PillowJPEGTransferSyntaxes + PillowJPEG2000TransferSyntaxes
)


HANDLER_NAME = 'Pillow'
DEPENDENCIES = {
    'numpy': ('http://www.numpy.org/', 'NumPy'),
    'PIL': ('https://python-pillow.org/', 'Pillow'),
}


def is_available() -> bool:
    """Return ``True`` if the handler has its dependencies met."""
    return HAVE_NP and HAVE_PIL


def supports_transfer_syntax(transfer_syntax: UID) -> bool:
    """Return ``True`` if the handler supports the `transfer_syntax`.

    Parameters
    ----------
    transfer_syntax : uid.UID
        The Transfer Syntax UID of the *Pixel Data* that is to be used with
        the handler.
    """
    return transfer_syntax in PillowSupportedTransferSyntaxes


def needs_to_convert_to_RGB(ds: "Dataset") -> bool:
    """Return ``True`` if the *Pixel Data* should to be converted from YCbCr to
    RGB.

    This affects JPEG transfer syntaxes.
    """
    return False


def should_change_PhotometricInterpretation_to_RGB(ds: "Dataset") -> bool:
    """Return ``True`` if the *Photometric Interpretation* should be changed
    to RGB.

    This affects JPEG transfer syntaxes.
    """
    should_change = ds.SamplesPerPixel == 3
    return False


def get_pixeldata(ds: "Dataset") -> "numpy.ndarray":
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
    transfer_syntax = ds.file_meta.TransferSyntaxUID

    if not HAVE_PIL:
        raise ImportError(
            f"The pillow package is required to use pixel_array for "
            f"this transfer syntax {transfer_syntax.name}, and pillow could "
            f"not be imported."
        )

    if not HAVE_JPEG and transfer_syntax in PillowJPEGTransferSyntaxes:
        raise NotImplementedError(
            f"The pixel data with transfer syntax {transfer_syntax.name}, "
            f"cannot be read because Pillow lacks the JPEG plugin"
        )

    if not HAVE_JPEG2K and transfer_syntax in PillowJPEG2000TransferSyntaxes:
        raise NotImplementedError(
            f"The pixel data with transfer syntax {transfer_syntax.name}, "
            f"cannot be read because Pillow lacks the JPEG 2000 plugin"
        )

    if transfer_syntax == JPEGExtended12Bit and ds.BitsAllocated != 8:
        raise NotImplementedError(
            f"{JPEGExtended12Bit} - {JPEGExtended12Bit.name} only supported "
            "by Pillow if Bits Allocated = 8"
        )

    pixel_bytes = bytearray()
    if getattr(ds, 'NumberOfFrames', 1) > 1:
        j2k_precision, j2k_sign = None, None
        # multiple compressed frames
        for frame in decode_data_sequence(ds.PixelData):
            im = Image.open(io.BytesIO(frame))
            if 'YBR' in ds.PhotometricInterpretation:
                im.draft('YCbCr', (ds.Rows, ds.Columns))
            pixel_bytes.extend(im.tobytes())

            if not j2k_precision:
                params = get_j2k_parameters(frame)
                j2k_precision = params.setdefault("precision", ds.BitsStored)
                j2k_sign = params.setdefault("is_signed", None)

    else:
        # single compressed frame
        pixel_data = defragment_data(ds.PixelData)
        im = Image.open(io.BytesIO(pixel_data))
        if 'YBR' in ds.PhotometricInterpretation:
            im.draft('YCbCr', (ds.Rows, ds.Columns))
        pixel_bytes.extend(im.tobytes())

        params = get_j2k_parameters(pixel_data)
        j2k_precision = params.setdefault("precision", ds.BitsStored)
        j2k_sign = params.setdefault("is_signed", None)

    logger.debug(f"Successfully read {len(pixel_bytes)} pixel bytes")

    arr = numpy.frombuffer(pixel_bytes, pixel_dtype(ds))

    if transfer_syntax in PillowJPEG2000TransferSyntaxes:
        # Pillow converts N-bit data to 8- or 16-bit unsigned data,
        # See Pillow src/libImaging/Jpeg2KDecode.c::j2ku_gray_i
        shift = ds.BitsAllocated - ds.BitsStored
        if j2k_precision and j2k_precision != ds.BitsStored:
            warnings.warn(
                f"The (0028,0101) 'Bits Stored' value ({ds.BitsStored}-bit) "
                f"doesn't match the JPEG 2000 data ({j2k_precision}-bit). "
                f"It's recommended that you change the 'Bits Stored' value"
            )

        if config.APPLY_J2K_CORRECTIONS and j2k_precision:
            # Corrections based on J2K data
            shift = ds.BitsAllocated - j2k_precision
            if not j2k_sign and j2k_sign != ds.PixelRepresentation:
                # Convert unsigned J2K data to 2's complement
                arr = numpy.right_shift(arr, shift)
            else:
                if ds.PixelRepresentation == 1:
                    # Pillow converts signed data to unsigned
                    #   so we need to undo this conversion
                    arr -= 2**(ds.BitsAllocated - 1)

                if shift:
                    arr = numpy.right_shift(arr, shift)
        else:
            # Corrections based on dataset elements
            if ds.PixelRepresentation == 1:
                arr -= 2**(ds.BitsAllocated - 1)

            if shift:
                arr = numpy.right_shift(arr, shift)

    if should_change_PhotometricInterpretation_to_RGB(ds):
        ds.PhotometricInterpretation = "RGB"

    return arr
