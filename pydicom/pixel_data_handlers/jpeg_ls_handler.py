# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""
Use the `jpeg_ls (CharPyLS) <https://github.com/Who8MyLunch/CharPyLS>`_ Python
package to decode *Pixel Data*.
"""

try:
    import numpy
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

try:
    import jpeg_ls
    HAVE_JPEGLS = True
except ImportError:
    HAVE_JPEGLS = False

import pydicom.encaps
from pydicom.pixel_data_handlers.util import dtype_corrected_for_endianness
import pydicom.uid


HANDLER_NAME = 'JPEG-LS'

DEPENDENCIES = {
    'numpy': ('http://www.numpy.org/', 'NumPy'),
    'jpeg_ls': ('https://github.com/Who8MyLunch/CharPyLS', 'CharPyLS'),
}

SUPPORTED_TRANSFER_SYNTAXES = [
    pydicom.uid.JPEGLSLossless,
    pydicom.uid.JPEGLSLossy,
]


def is_available():
    """Return ``True`` if the handler has its dependencies met."""
    return HAVE_NP and HAVE_JPEGLS


def needs_to_convert_to_RGB(dicom_dataset):
    """Return ``True`` if the *Pixel Data* should to be converted from YCbCr to
    RGB.

    This affects JPEG transfer syntaxes.
    """
    return False


def should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
    """Return ``True`` if the *Photometric Interpretation* should be changed
    to RGB.

    This affects JPEG transfer syntaxes.
    """
    should_change = dicom_dataset.SamplesPerPixel == 3
    return False


def supports_transfer_syntax(transfer_syntax):
    """Return ``True`` if the handler supports the `transfer_syntax`.

    Parameters
    ----------
    transfer_syntax : uid.UID
        The Transfer Syntax UID of the *Pixel Data* that is to be used with
        the handler.
    """
    return transfer_syntax in SUPPORTED_TRANSFER_SYNTAXES


def get_pixeldata(dicom_dataset):
    """Return the *Pixel Data* as a :class:`numpy.ndarray`.

    Returns
    -------
    numpy.ndarray
        A correctly sized (but not shaped) numpy array of the *Pixel Data*.

    Raises
    ------
    ImportError
        If the required packages are not available.
    NotImplementedError
        If the transfer syntax is not supported.
    TypeError
        If the pixel data type is unsupported.
    """
    if (dicom_dataset.file_meta.TransferSyntaxUID
            not in SUPPORTED_TRANSFER_SYNTAXES):
        msg = ("The jpeg_ls does not support "
               "this transfer syntax {0}.".format(
                   dicom_dataset.file_meta.TransferSyntaxUID.name))
        raise NotImplementedError(msg)

    if not HAVE_JPEGLS:
        msg = ("The jpeg_ls package is required to use pixel_array "
               "for this transfer syntax {0}, and jpeg_ls could not "
               "be imported.".format(
                   dicom_dataset.file_meta.TransferSyntaxUID.name))
        raise ImportError(msg)
    # Make NumPy format code, e.g. "uint16", "int32" etc
    # from two pieces of info:
    # dicom_dataset.PixelRepresentation -- 0 for unsigned, 1 for signed;
    # dicom_dataset.BitsAllocated -- 8, 16, or 32
    if dicom_dataset.PixelRepresentation == 0:
        format_str = 'uint{}'.format(dicom_dataset.BitsAllocated)
    elif dicom_dataset.PixelRepresentation == 1:
        format_str = 'int{}'.format(dicom_dataset.BitsAllocated)
    else:
        format_str = 'bad_pixel_representation'
    try:
        numpy_format = numpy.dtype(format_str)
    except TypeError:
        msg = ("Data type not understood by NumPy: "
               "format='{}', PixelRepresentation={}, "
               "BitsAllocated={}".format(
                   format_str,
                   dicom_dataset.PixelRepresentation,
                   dicom_dataset.BitsAllocated))
        raise TypeError(msg)

    numpy_format = dtype_corrected_for_endianness(
        dicom_dataset.is_little_endian, numpy_format)

    # decompress here
    UncompressedPixelData = bytearray()
    if ('NumberOfFrames' in dicom_dataset and
            dicom_dataset.NumberOfFrames > 1):
        # multiple compressed frames
        CompressedPixelDataSeq = pydicom.encaps.decode_data_sequence(
            dicom_dataset.PixelData)
        # print len(CompressedPixelDataSeq)
        for frame in CompressedPixelDataSeq:
            decompressed_image = jpeg_ls.decode(
                numpy.frombuffer(frame, dtype=numpy.uint8))
            UncompressedPixelData.extend(decompressed_image.tobytes())
    else:
        # single compressed frame
        CompressedPixelData = pydicom.encaps.defragment_data(
            dicom_dataset.PixelData)
        decompressed_image = jpeg_ls.decode(
            numpy.frombuffer(CompressedPixelData, dtype=numpy.uint8))
        UncompressedPixelData.extend(decompressed_image.tobytes())

    pixel_array = numpy.frombuffer(UncompressedPixelData, numpy_format)
    if should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
        dicom_dataset.PhotometricInterpretation = "RGB"

    return pixel_array
