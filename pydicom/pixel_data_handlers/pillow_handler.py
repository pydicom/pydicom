# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Use the `pillow <https://python-pillow.org/>`_ Python package
to decode *Pixel Data*.
"""

import io
import logging
from typing import TYPE_CHECKING, cast, Tuple
import warnings

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
from pydicom.encaps import defragment_data, decode_data_sequence
from pydicom.jpeg import parse_jpeg, parse_jpeg2k
from pydicom.pixel_data_handlers.util import pixel_dtype
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
    # return ds.SamplesPerPixel == 3
    return False


def _decompress_single_frame(
    src: bytes,
    tsyntax: str,
    photometric_interpretation: str,
    shape: Tuple[int, int, int],
) -> "Image":
    """Decompresses a single frame of an encapsulated Pixel Data element.

    Parameters
    ----------
    src : bytes
        The compressed pixel data.
    tsyntax : str
        The corresponding *Transfer Syntax UID*.
    photometric_interpretation : str
        The *Photometric Interpretation* from the corresponding dataset.
    shape : Tuple[int, int, int]
        The (rows, columns, samples per pixel).

    Returns
    -------
    PIL.Image
        Decompressed pixel data
    """
    im = Image.open(io.BytesIO(src))
    if tsyntax in PillowJPEG2000TransferSyntaxes or shape[2] == 1:
        return im

    cs = None

    # Parse the JPEG codestream for the APP and SOF markers
    param = parse_jpeg(src)
    print(param)

    # APP0 JFIF implies YCbCr
    # https://www.w3.org/Graphics/JPEG/jfif3.pdf
    if "APPn" in param:
        if param["APPn"].get(b"\xFF\xE0", b"").startswith(b"JFIF"):
            cs = "YCbCr"

    # ISO/IEC 10918-1 (ITU T.81)
    # https://www.w3.org/Graphics/JPEG/itu-t81.pdf
    if "SOF" in param:
        # If any components are subsampled then it's very likely not RGB
        c_ss = [x[1] != 1 or x[2] != 1 for x in param["SOF"]["Components"]]
        if any(c_ss):
            cs = "YCbCr"

        # Some applications use the SOF marker's component IDs to flag
        #   the colour components
        c_ids = [x[0] for x in param["SOF"]["Components"]]
        if c_ids in ([b"R", b"G", b"B"], [b"r", b"g", b"b"]):
            cs = "RGB"

    # APP14 (Adobe)
    # ISO/IEC 10918-6 (ITU T.872): JPEG Printing Extensions
    # http://www.itu.int/rec/T-REC-T.872-201206-I/en
    # Section 6.5.3:
    #   AP12 is assumed to contain a single-byte transform flag as:
    #     0: CMYK (if 4 components) or RGB (if 3 components)
    #     1: YCbCr (3 components)
    #     2: YCCK (4 components)
    # In Image.info, "adobe_transform" is the APP14 AP12 value as int
    if "adobe_transform" in im.info:
        cs = "RGB" if im.info["adobe_transform"] == 0 else "YCbCr"

    # We want to return the pixel data in the color space specified by
    #   *Photometric Interpretation*, with a warning if that color space
    #   doesn't actually match that of the encoded source data

    # The possibilities are:
    #   cs    | PI  -> transform    | return | warn
    #   ------+---------------------+--------+-----
    #   None  | RGB -> YCbCr to RGB | RGB    |
    #   None  | YBR -> (none)       | YBR    |
    #   YCbCr | RGB -> YCbCr to RGB | RGB    | yes
    #   YCbCr | YBR -> (none)       | YBR    |
    #   RGB   | RGB -> (none)       | RGB    |
    #   RGB   | YBR -> RGB to YCbCr | YBR    | yes

    if photometric_interpretation == "RGB" and cs is None:
        # Source data is either YCbCr (most likely) or RGB (less likely)
        # Assume *Photometric Interpretation* is correct:
        # * If the decoded pixel data is correct then source is RGB
        # * If the decoded pixel data is incorrect then source is YCbCr
        #   but this can be fixed by user applying YCbCr -> RGB transform
        # Source data is RGB - no transform
        #im.tile = [("jpeg", im.tile[0][1], im.tile[0][2], ("YCbCr", ""))]
        #im.mode = "YCbCr"
        #im.rawmode = "YCbCr"
        im.draft("YCbCr", (shape[0], shape[1]))
        return im

    if photometric_interpretation == "RGB" and cs == "YCbCr":
        # Source data is YCbCr - transform to RGB and warn
        # YBR_FULL_422 is only a valid recommendation if we don't
        #   support JPEGLosslessP14 and JPEGLosslessSV1
        warnings.warn(
            "A mismatch was found between the JPEG codestream and dataset "
            "'Photometric Interpretation' value. If the decoded pixel data "
            "is in the RGB color space then the 'Photometric Interpretation' "
            "should be 'YBR_FULL_422'"
        )
        return im

    if "YBR" in photometric_interpretation and cs in (None, "YCbCr"):
        # Source data is YCbCr - no transform
        im.draft("YCbCr", (shape[0], shape[1]))
        return im

    if cs == "RGB" and photometric_interpretation == "RGB":
        # Source data is RGB - no transform
        # im.tile = [("jpeg", im.tile[0][1], im.tile[0][2], ("YCbCr", ""))]
        # im.mode = "YCbCr"
        # im.rawmode = "YCbCr"
        #im.draft("RGB", (shape[0], shape[1]))
        im.draft("YCbCr", (shape[0], shape[1]))
        return im

    # Source data is RGB - transform to YBR and warn
    warnings.warn(
        "The JPEG codestream indicates the encoded pixel data is "
        "in the RGB color space, but the (0028,0004) "
        f"'Photometric Interpretation' is '{photometric_interpretation}'."
        "The pixel data will be returned in the YCbCr colour space, but "
        "it's recommended that you change the 'Photometric "
        "Interpretation' to 'RGB'"
    )
    # Uh, how do I convert here...
    im.tile = [("jpeg", im.tile[0][1], im.tile[0][2], ("RGB", ""))]
    im.mode = "RGB"
    im.rawmode = "RGB"
    # ?
    im.draft("YCbCr", (shape[0], shape[1]))
    return im


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

    photometric_interpretation = cast(str, ds.PhotometricInterpretation)
    rows = cast(int, ds.Rows)
    columns = cast(int, ds.Columns)
    bits_stored = cast(int, ds.BitsStored)
    bits_allocated = cast(int, ds.BitsAllocated)
    nr_frames = getattr(ds, 'NumberOfFrames', 1) or 1
    samples_per_pixel = cast(int, ds.SamplesPerPixel)

    pixel_bytes = bytearray()
    if nr_frames > 1:
        j2k_precision, j2k_sign = None, None
        # multiple compressed frames
        for frame in decode_data_sequence(ds.PixelData):
            im = _decompress_single_frame(
                frame,
                transfer_syntax,
                photometric_interpretation,
                (rows, columns, samples_per_pixel),
            )
            # if 'YBR' in photometric_interpretation:
            #     im.draft('YCbCr', (rows, columns))
            pixel_bytes.extend(im.tobytes())

            if not j2k_precision:
                params = parse_jpeg2k(frame)
                j2k_precision = cast(
                    int, params.setdefault("precision", bits_stored)
                )
                j2k_sign = params.setdefault("is_signed", None)

    else:
        # single compressed frame
        pixel_data = defragment_data(ds.PixelData)
        im = _decompress_single_frame(
            pixel_data,
            transfer_syntax,
            photometric_interpretation,
            (rows, columns, samples_per_pixel),
        )
        # if 'YBR' in photometric_interpretation:
        #     im.draft('YCbCr', (rows, columns))
        pixel_bytes.extend(im.tobytes())

        params = parse_jpeg2k(pixel_data)
        j2k_precision = cast(int, params.setdefault("precision", bits_stored))
        j2k_sign = params.setdefault("is_signed", None)

    logger.debug(f"Successfully read {len(pixel_bytes)} pixel bytes")

    arr = numpy.frombuffer(pixel_bytes, pixel_dtype(ds))

    if transfer_syntax in PillowJPEG2000TransferSyntaxes:
        # Pillow converts N-bit data to 8- or 16-bit unsigned data,
        # See Pillow src/libImaging/Jpeg2KDecode.c::j2ku_gray_i
        shift = bits_allocated - bits_stored
        if j2k_precision and j2k_precision != bits_stored:
            warnings.warn(
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
                    arr -= 2**(bits_allocated - 1)

                if shift:
                    arr = numpy.right_shift(arr, shift)
        else:
            # Corrections based on dataset elements
            if ds.PixelRepresentation == 1:
                arr -= 2**(bits_allocated - 1)

            if shift:
                arr = numpy.right_shift(arr, shift)

    if should_change_PhotometricInterpretation_to_RGB(ds):
        ds.PhotometricInterpretation = "RGB"

    return cast("numpy.ndarray", arr)
