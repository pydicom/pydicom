# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Use the gdcm python package to decode pixel transfer syntaxes."""

import sys

try:
    import numpy
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

try:
    import gdcm
    HAVE_GDCM = True
except ImportError:
    HAVE_GDCM = False

import pydicom
from pydicom import compat


HANDLER_NAME = 'GDCM'

DEPENDENCIES = {
    'numpy': ('http://www.numpy.org/', 'NumPy'),
    'gdcm': ('http://gdcm.sourceforge.net/wiki/index.php/Main_Page', 'GDCM'),
}

SUPPORTED_TRANSFER_SYNTAXES = [
    pydicom.uid.JPEGBaseline,
    pydicom.uid.JPEGExtended,
    pydicom.uid.JPEGLosslessP14,
    pydicom.uid.JPEGLossless,
    pydicom.uid.JPEGLSLossless,
    pydicom.uid.JPEGLSLossy,
    pydicom.uid.JPEG2000Lossless,
    pydicom.uid.JPEG2000,
]

should_convert_these_syntaxes_to_RGB = [
    pydicom.uid.JPEGBaseline, ]


def is_available():
    """Return True if the handler has its dependencies met."""
    return HAVE_NP and HAVE_GDCM


def needs_to_convert_to_RGB(dicom_dataset):
    should_convert = (dicom_dataset.file_meta.TransferSyntaxUID in
                      should_convert_these_syntaxes_to_RGB)
    should_convert &= dicom_dataset.SamplesPerPixel == 3
    return False


def should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
    should_change = (dicom_dataset.file_meta.TransferSyntaxUID in
                     should_convert_these_syntaxes_to_RGB)
    should_change &= dicom_dataset.SamplesPerPixel == 3
    return False


def supports_transfer_syntax(transfer_syntax):
    """
    Returns
    -------
    bool
        True if this pixel data handler might support this transfer syntax.

        False to prevent any attempt to try to use this handler
        to decode the given transfer syntax
    """
    return transfer_syntax in SUPPORTED_TRANSFER_SYNTAXES


def get_pixeldata(dicom_dataset):
    """
    Use the GDCM package to decode the PixelData attribute

    Returns
    -------
    numpy.ndarray

        A correctly sized (but not shaped) numpy array
        of the entire data volume

    Raises
    ------
    ImportError
        if the required packages are not available

    TypeError
        if the image could not be read by GDCM
        if the pixel data type is unsupported

    AttributeError
        if the decoded amount of data does not match the expected amount
    """

    # read the file using GDCM
    # FIXME this should just use dicom_dataset.PixelData
    # instead of dicom_dataset.filename
    #       but it is unclear how this should be achieved using GDCM
    if not HAVE_GDCM:
        msg = ("GDCM requires both the gdcm package and numpy "
               "and one or more could not be imported")
        raise ImportError(msg)

    gdcm_image_reader = gdcm.ImageReader()
    if compat.in_py2:
        if isinstance(dicom_dataset.filename, unicode):
            gdcm_image_reader.SetFileName(
                dicom_dataset.filename.encode(sys.getfilesystemencoding()))
        else:
            gdcm_image_reader.SetFileName(dicom_dataset.filename)
    else:
        # python 3
        gdcm_image_reader.SetFileName(dicom_dataset.filename)

    if not gdcm_image_reader.Read():
        raise TypeError("GDCM could not read DICOM image")

    gdcm_image = gdcm_image_reader.GetImage()

    # determine the correct numpy datatype
    gdcm_numpy_typemap = {
        gdcm.PixelFormat.INT8:     numpy.int8,
        gdcm.PixelFormat.UINT8:    numpy.uint8,
        gdcm.PixelFormat.UINT16:   numpy.uint16,
        gdcm.PixelFormat.INT16:    numpy.int16,
        gdcm.PixelFormat.UINT32:   numpy.uint32,
        gdcm.PixelFormat.INT32:    numpy.int32,
        gdcm.PixelFormat.FLOAT32:  numpy.float32,
        gdcm.PixelFormat.FLOAT64:  numpy.float64
    }
    gdcm_pixel_format = gdcm_image.GetPixelFormat().GetScalarType()
    if gdcm_pixel_format in gdcm_numpy_typemap:
        numpy_dtype = gdcm_numpy_typemap[gdcm_pixel_format]
    else:
        raise TypeError('{0} is not a GDCM supported '
                        'pixel format'.format(gdcm_pixel_format))

    # GDCM returns char* as type str. Under Python 2 `str` are
    # byte arrays by default. Python 3 decodes this to
    # unicode strings by default.
    # The SWIG docs mention that they always decode byte streams
    # as utf-8 strings for Python 3, with the `surrogateescape`
    # error handler configured.
    # Therefore, we can encode them back to their original bytearray
    # representation on Python 3 by using the same parameters.
    pixel_bytearray = gdcm_image.GetBuffer()
    if sys.version_info >= (3, 0):
        pixel_bytearray = pixel_bytearray.encode("utf-8",
                                                 "surrogateescape")

    # if GDCM indicates that a byte swap is in order, make
    #   sure to inform numpy as well
    if gdcm_image.GetNeedByteSwap():
        numpy_dtype = numpy_dtype.newbyteorder('S')

    # Here we need to be careful because in some cases, GDCM reads a
    # buffer that is too large, so we need to make sure we only include
    # the first n_rows * n_columns * dtype_size bytes.

    n_bytes = (dicom_dataset.Rows *
               dicom_dataset.Columns *
               numpy.dtype(numpy_dtype).itemsize)
    try:
        n_bytes *= dicom_dataset.NumberOfFrames
    except Exception:
        pass
    try:
        n_bytes *= dicom_dataset.SamplesPerPixel
    except Exception:
        pass

    if len(pixel_bytearray) > n_bytes:
        # We make sure that all the bytes after are in fact zeros
        padding = pixel_bytearray[n_bytes:]
        if numpy.any(numpy.frombuffer(padding, numpy.byte)):
            pixel_bytearray = pixel_bytearray[:n_bytes]
        else:
            # We revert to the old behavior which should then result
            #   in a Numpy error later on.
            pass

    pixel_array = numpy.frombuffer(pixel_bytearray, dtype=numpy_dtype)

    length_of_pixel_array = pixel_array.nbytes
    expected_length = dicom_dataset.Rows * dicom_dataset.Columns

    expected_length *= dicom_dataset.get("NumberOfFrames", 1)
    expected_length *= dicom_dataset.get("SamplesPerPixel", 1)

    if dicom_dataset.BitsAllocated > 8:
        expected_length *= (dicom_dataset.BitsAllocated // 8)

    if length_of_pixel_array != expected_length:
        raise AttributeError("Amount of pixel data %d does "
                             "not match the expected data %d" %
                             (length_of_pixel_array, expected_length))

    if should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
        dicom_dataset.PhotometricInterpretation = "RGB"

    return pixel_array.copy()
