# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Use the `GDCM <http://gdcm.sourceforge.net/>`_ Python package to decode
pixel transfer syntaxes.
"""

import sys

try:
    import numpy
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

try:
    import gdcm
    HAVE_GDCM = True
    HAVE_GDCM_IN_MEMORY_SUPPORT = hasattr(gdcm.DataElement,
                                          'SetByteStringValue')
except ImportError:
    HAVE_GDCM = False
    HAVE_GDCM_IN_MEMORY_SUPPORT = False

import pydicom.uid
from pydicom.pixel_data_handlers.util import get_expected_length, pixel_dtype


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
    """Return ``True`` if the handler has its dependencies met."""
    return HAVE_NP and HAVE_GDCM


def needs_to_convert_to_RGB(dicom_dataset):
    """Return ``True`` if the *Pixel Data* should to be converted from YCbCr to
    RGB.

    This affects JPEG transfer syntaxes.
    """
    should_convert = (dicom_dataset.file_meta.TransferSyntaxUID in
                      should_convert_these_syntaxes_to_RGB)
    should_convert &= dicom_dataset.SamplesPerPixel == 3
    return False


def should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
    """Return ``True`` if the *Photometric Interpretation* should be changed
    to RGB.

    This affects JPEG transfer syntaxes.
    """
    should_change = (dicom_dataset.file_meta.TransferSyntaxUID in
                     should_convert_these_syntaxes_to_RGB)
    should_change &= dicom_dataset.SamplesPerPixel == 3
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


def create_data_element(dicom_dataset):
    """Return a ``gdcm.DataElement`` for the *Pixel Data*.

    Parameters
    ----------
    dicom_dataset : dataset.Dataset
        The :class:`~pydicom.dataset.Dataset` containing the *Pixel
        Data*.

    Returns
    -------
    gdcm.DataElement
        The converted *Pixel Data* element.
    """
    data_element = gdcm.DataElement(gdcm.Tag(0x7fe0, 0x0010))
    if dicom_dataset.file_meta.TransferSyntaxUID.is_compressed:
        if getattr(dicom_dataset, 'NumberOfFrames', 1) > 1:
            pixel_data_sequence = pydicom.encaps.decode_data_sequence(
                dicom_dataset.PixelData)
        else:
            pixel_data_sequence = [
                pydicom.encaps.defragment_data(dicom_dataset.PixelData)
            ]

        fragments = gdcm.SequenceOfFragments.New()
        for pixel_data in pixel_data_sequence:
            fragment = gdcm.Fragment()
            fragment.SetByteStringValue(pixel_data)
            fragments.AddFragment(fragment)
        data_element.SetValue(fragments.__ref__())
    else:
        data_element.SetByteStringValue(dicom_dataset.PixelData)

    return data_element


def create_image(dicom_dataset, data_element):
    """Return a ``gdcm.Image``.

    Parameters
    ----------
    dicom_dataset : dataset.Dataset
        The :class:`~pydicom.dataset.Dataset` containing the Image
        Pixel module.
    data_element : gdcm.DataElement
        The ``gdcm.DataElement`` *Pixel Data* element.

    Returns
    -------
    gdcm.Image
    """
    image = gdcm.Image()
    number_of_frames = getattr(dicom_dataset, 'NumberOfFrames', 1)
    image.SetNumberOfDimensions(2 if number_of_frames == 1 else 3)
    image.SetDimensions(
        (dicom_dataset.Columns, dicom_dataset.Rows, number_of_frames))
    image.SetDataElement(data_element)
    pi_type = gdcm.PhotometricInterpretation.GetPIType(
        dicom_dataset.PhotometricInterpretation)
    image.SetPhotometricInterpretation(
        gdcm.PhotometricInterpretation(pi_type))
    ts_type = gdcm.TransferSyntax.GetTSType(
        str.__str__(dicom_dataset.file_meta.TransferSyntaxUID))
    image.SetTransferSyntax(gdcm.TransferSyntax(ts_type))
    pixel_format = gdcm.PixelFormat(
        dicom_dataset.SamplesPerPixel, dicom_dataset.BitsAllocated,
        dicom_dataset.BitsStored, dicom_dataset.HighBit,
        dicom_dataset.PixelRepresentation)
    image.SetPixelFormat(pixel_format)
    if 'PlanarConfiguration' in dicom_dataset:
        image.SetPlanarConfiguration(dicom_dataset.PlanarConfiguration)
    return image


def create_image_reader(filename):
    """Return a ``gdcm.ImageReader``.

    Parameters
    ----------
    filename: str or unicode
        The path to the DICOM dataset.

    Returns
    -------
    gdcm.ImageReader
    """
    image_reader = gdcm.ImageReader()
    image_reader.SetFileName(filename)
    return image_reader


def get_pixeldata(dicom_dataset):
    """Use the GDCM package to decode *Pixel Data*.

    Returns
    -------
    numpy.ndarray
        A correctly sized (but not shaped) array of the entire data volume

    Raises
    ------
    ImportError
        If the required packages are not available.
    TypeError
        If the image could not be read by GDCM or if the *Pixel Data* type is
        unsupported.
    AttributeError
        If the decoded amount of data does not match the expected amount.
    """

    if not HAVE_GDCM:
        msg = ("GDCM requires both the gdcm package and numpy "
               "and one or more could not be imported")
        raise ImportError(msg)

    if HAVE_GDCM_IN_MEMORY_SUPPORT:
        gdcm_data_element = create_data_element(dicom_dataset)
        gdcm_image = create_image(dicom_dataset, gdcm_data_element)
    else:
        gdcm_image_reader = create_image_reader(dicom_dataset.filename)
        if not gdcm_image_reader.Read():
            raise TypeError("GDCM could not read DICOM image")
        gdcm_image = gdcm_image_reader.GetImage()

    # GDCM returns char* as type str. Python 3 decodes this to
    # unicode strings by default.
    # The SWIG docs mention that they always decode byte streams
    # as utf-8 strings for Python 3, with the `surrogateescape`
    # error handler configured.
    # Therefore, we can encode them back to their original bytearray
    # representation on Python 3 by using the same parameters.

    pixel_bytearray = gdcm_image.GetBuffer().encode(
        "utf-8", "surrogateescape")

    # Here we need to be careful because in some cases, GDCM reads a
    # buffer that is too large, so we need to make sure we only include
    # the first n_rows * n_columns * dtype_size bytes.
    expected_length_bytes = get_expected_length(dicom_dataset)
    if dicom_dataset.PhotometricInterpretation == 'YBR_FULL_422':
        # GDCM has already resampled the pixel data, see PS3.3 C.7.6.3.1.2
        expected_length_bytes = expected_length_bytes // 2 * 3

    if len(pixel_bytearray) > expected_length_bytes:
        # We make sure that all the bytes after are in fact zeros
        padding = pixel_bytearray[expected_length_bytes:]
        if numpy.any(numpy.frombuffer(padding, numpy.byte)):
            pixel_bytearray = pixel_bytearray[:expected_length_bytes]
        else:
            # We revert to the old behavior which should then result
            #   in a Numpy error later on.
            pass

    numpy_dtype = pixel_dtype(dicom_dataset)
    pixel_array = numpy.frombuffer(pixel_bytearray, dtype=numpy_dtype)

    expected_length_pixels = get_expected_length(dicom_dataset, 'pixels')
    if pixel_array.size != expected_length_pixels:
        raise AttributeError("Amount of pixel data %d does "
                             "not match the expected data %d" %
                             (pixel_array.size, expected_length_pixels))

    if should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
        dicom_dataset.PhotometricInterpretation = "RGB"

    return pixel_array.copy()
