# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Use the `pillow <https://python-pillow.org/>`_ Python package
to decode *Pixel Data*.
"""

import io
import logging
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:  # pragma: no cover
    from pydicom.dataset import Dataset

try:
    import numpy

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

try:
    from PIL import Image, features

    HAVE_PIL = True
    HAVE_JPEG = features.check_codec("jpg")
    HAVE_JPEG2K = features.check_codec("jpg_2000")
except ImportError:
    HAVE_PIL = False
    HAVE_JPEG = False
    HAVE_JPEG2K = False

from pydicom import config
from pydicom.encaps import generate_frames
from pydicom.misc import warn_and_log
from pydicom.pixels.utils import (
    pixel_dtype,
    get_j2k_parameters,
    get_nr_frames,
)
from pydicom.uid import (
    UID,
    JPEG2000,
    JPEG2000Lossless,
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
)


logger = logging.getLogger("pydicom")


PillowJPEG2000TransferSyntaxes = [JPEG2000, JPEG2000Lossless]
PillowJPEGTransferSyntaxes = [JPEGBaseline8Bit, JPEGExtended12Bit]
PillowSupportedTransferSyntaxes = (
    PillowJPEGTransferSyntaxes + PillowJPEG2000TransferSyntaxes
)


HANDLER_NAME = "Pillow"
DEPENDENCIES = {
    "numpy": ("https://numpy.org/", "NumPy"),
    "PIL": ("https://python-pillow.org/", "Pillow"),
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
    # return ds.SamplesPerPixel == 3
    return False


def _decompress_single_frame(
    data: bytes, transfer_syntax: str, photometric_interpretation: str
) -> "Image":
    """Decompresses a single frame of an encapsulated Pixel Data element.

    Parameters
    ----------
    data: bytes
        Compressed pixel data
    transfer_syntax: str
        Transfer Syntax UID
    photometric_interpretation: str
        Photometric Interpretation

    Returns
    -------
    PIL.Image
        Decompressed pixel data

    """
    fio = io.BytesIO(data)
    image = Image.open(fio)
    # This hack ensures that RGB color images, which were not
    # color transformed (i.e. not transformed into YCbCr color space)
    # upon JPEG compression are decompressed correctly.
    # Since Pillow assumes that images were transformed into YCbCr color
    # space prior to compression, setting the value of "mode" to YCbCr
    # signals Pillow to not apply any color transformation upon
    # decompression.
    if (
        transfer_syntax in PillowJPEGTransferSyntaxes
        and photometric_interpretation == "RGB"
        and "adobe_transform" not in image.info
    ):
        image.draft("YCbCr", image.size)
    return image


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
            f"{JPEGExtended12Bit} - {JPEGExtended12Bit.name} is only supported "
            "by Pillow if (0028,0100) Bits Allocated = 8"
        )

    photometric_interpretation = cast(str, ds.PhotometricInterpretation)
    rows = cast(int, ds.Rows)
    columns = cast(int, ds.Columns)
    bits_stored = cast(int, ds.BitsStored)
    bits_allocated = cast(int, ds.BitsAllocated)
    nr_frames = get_nr_frames(ds, warn=False)

    pixel_bytes = bytearray()
    j2k_precision, j2k_sign = None, None
    for frame in generate_frames(ds.PixelData, number_of_frames=nr_frames):
        im = _decompress_single_frame(
            frame, transfer_syntax, photometric_interpretation
        )
        if "YBR" in photometric_interpretation:
            im.draft("YCbCr", (rows, columns))
        pixel_bytes.extend(im.tobytes())

        if not j2k_precision:
            params = get_j2k_parameters(frame)
            j2k_precision = cast(int, params.setdefault("precision", bits_stored))
            j2k_sign = params.setdefault("is_signed", None)

    logger.debug(f"Successfully read {len(pixel_bytes)} pixel bytes")

    arr = numpy.frombuffer(pixel_bytes, pixel_dtype(ds))

    if transfer_syntax in PillowJPEG2000TransferSyntaxes:
        # Pillow converts N-bit data to 8- or 16-bit unsigned data,
        # See Pillow src/libImaging/Jpeg2KDecode.c::j2ku_gray_i
        shift = bits_allocated - bits_stored
        if j2k_precision and j2k_precision != bits_stored:
            warn_and_log(
                f"The (0028,0101) 'Bits Stored' value ({bits_stored}-bit) "
                f"doesn't match the JPEG 2000 data ({j2k_precision}-bit). "
                f"It's recommended that you change the 'Bits Stored' value"
            )

        if config.APPLY_J2K_CORRECTIONS and j2k_precision:
            # Corrections based on J2K data
            shift = bits_allocated - j2k_precision
            if not j2k_sign and j2k_sign != ds.PixelRepresentation:
                # Convert unsigned J2K data to 2's complement
                arr = numpy.right_shift(arr, shift)
            else:
                if ds.PixelRepresentation == 1:
                    # Pillow converts signed data to unsigned
                    #   so we need to undo this conversion
                    arr -= numpy.uint32(2 ** (bits_allocated - 1))

                if shift:
                    arr = numpy.right_shift(arr, shift)
        else:
            # Corrections based on dataset elements
            if ds.PixelRepresentation == 1:
                arr -= numpy.uint32(2 ** (bits_allocated - 1))

            if shift:
                arr = numpy.right_shift(arr, shift)

    if should_change_PhotometricInterpretation_to_RGB(ds):
        ds.PhotometricInterpretation = "RGB"

    return cast("numpy.ndarray", arr)
