# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Use the `pillow <https://python-pillow.org/>`_ Python package
to decode *Pixel Data*.
"""

import io
import logging
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


def _decompress_single_frame(data, transfer_syntax, photometric_interpretation):
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
    bytes
        Decompressed pixel data

    """
    fio = io.BytesIO(data)
    try:
        image = Image.open(fio)
        # This hack ensures that RGB color images, which were not
        # color transformed (i.e. not transformed into YCbCr color space)
        # upon JPEG compression are decompressed correctly.
        # Since Pillow assumes that images were transformed into YCbCr color
        # space prior to compression, setting the value of "mode" to YCbCr
        # signals Pillow to not apply any color transformation upon
        # decompression.
        if (transfer_syntax in PillowJPEGTransferSyntaxes and
            photometric_interpretation == 'RGB'):
            color_mode = 'YCbCr'
            image.tile = [(
                'jpeg',
                image.tile[0][1],
                image.tile[0][2],
                (color_mode, ''),
            )]
            image.mode = color_mode
            image.rawmode = color_mode
    except IOError as e:
        raise NotImplementedError(e.strerror)
    return image.tobytes()


def get_pixeldata(dicom_dataset):
    """Use Pillow to decompress compressed Pixel Data.

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
        # Pillow converts N-bit data to 8- or 16-bit unsigned data
        # See Pillow src/libImaging/Jpeg2KDecode.c::j2ku_gray_i
        if ds.PixelRepresentation == 1:
            # Pillow converts signed data to unsigned
            #   so we need to undo this conversion
            arr -= 2**(ds.BitsAllocated - 1)

        if j2k_precision and j2k_precision != ds.BitsStored:
            warnings.warn(
                "The (0028,0101) 'Bits Stored' value doesn't match the "
                "sample bit depth of the JPEG2000 pixel data ({} vs {} bit). "
                "It's recommended that you first change the 'Bits Stored' "
                "value to match the JPEG2000 bit depth in order to get the "
                "correct pixel data".format(ds.BitsStored, j2k_precision)
            )

        shift = ds.BitsAllocated - ds.BitsStored
        if shift:
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
        The JPEG 2000 (ISO/IEC 15444) data to be parsed.

    Returns
    -------
    int or None
        The bit depth (precision) of the component samples if available,
        ``None`` otherwise.
    """
    try:
        UncompressedPixelData = bytearray()
        if ('NumberOfFrames' in dicom_dataset and
                dicom_dataset.NumberOfFrames > 1):
            # multiple compressed frames
            CompressedPixelDataSeq = \
                pydicom.encaps.decode_data_sequence(
                    dicom_dataset.PixelData)
            for frame in CompressedPixelDataSeq:
                data = generic_jpeg_file_header + \
                    frame[frame_start_from:]
                uncompressed_data = _decompress_single_frame(
                    data,
                    transfer_syntax,
                    dicom_dataset.PhotometricInterpretation
                )
                UncompressedPixelData.extend(uncompressed_data)
        else:
            # single compressed frame
            pixel_data = pydicom.encaps.defragment_data(
                dicom_dataset.PixelData)
            pixel_data = generic_jpeg_file_header + \
                pixel_data[frame_start_from:]
            uncompressed_data = _decompress_single_frame(
                pixel_data,
                transfer_syntax,
                dicom_dataset.PhotometricInterpretation
            )
            UncompressedPixelData.extend(uncompressed_data)
    except Exception:
        raise

    logger.debug(
        "Successfully read %s pixel bytes", len(UncompressedPixelData)
    )

    pixel_array = numpy.frombuffer(UncompressedPixelData, numpy_format)

    if (transfer_syntax in
            PillowJPEG2000TransferSyntaxes and
            dicom_dataset.BitsStored == 16):
        # WHY IS THIS EVEN NECESSARY??
        pixel_array &= 0x7FFF

    if should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
        dicom_dataset.PhotometricInterpretation = "RGB"

    return pixel_array
