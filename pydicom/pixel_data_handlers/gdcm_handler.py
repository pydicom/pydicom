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


def _create_data_element(dicom_dataset):
    data_element = gdcm.DataElement(gdcm.Tag(0x7fe0, 0x0010))
    if dicom_dataset.file_meta.TransferSyntaxUID.is_compressed:
        if ('NumberOfFrames' in dicom_dataset
                and dicom_dataset.NumberOfFrames > 1):
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

        number_of_frames = len(pixel_data_sequence)
    else:
        data_element.SetByteStringValue(dicom_dataset.PixelData)
        number_of_frames = 1

    return data_element, number_of_frames


def _create_image(dicom_dataset, data_element, number_of_frames):
    image = gdcm.Image()
    image.SetNumberOfDimensions(2 if number_of_frames == 1 else 3)
    image.SetDimensions(
        (dicom_dataset.Rows, dicom_dataset.Columns, number_of_frames))
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
    image.SetRows(dicom_dataset.Rows)
    image.SetColumns(dicom_dataset.Columns)
    if 'PlanarConfiguration' in dicom_dataset:
        image.SetPlanarConfiguration(dicom_dataset.PlanarConfiguration)
    return image


def _determine_numpy_dtype(dicom_dataset, gdcm_image):
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
    gdcm_scalar_type = gdcm_image.GetPixelFormat().GetScalarType()
    if gdcm_scalar_type in gdcm_numpy_typemap:
        numpy_dtype = numpy.dtype(gdcm_numpy_typemap[gdcm_scalar_type])
    else:
        raise TypeError('{0} is not a GDCM supported '
                        'pixel format'.format(gdcm_scalar_type))

    if not dicom_dataset.is_little_endian:
        numpy_dtype = numpy_dtype.newbyteorder()

    return numpy_dtype


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

    if not HAVE_GDCM:
        msg = ("GDCM requires both the gdcm package and numpy "
               "and one or more could not be imported")
        raise ImportError(msg)

    gdcm_data_element, number_of_frames = _create_data_element(dicom_dataset)
    gdcm_image = _create_image(dicom_dataset, gdcm_data_element,
                               number_of_frames)

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
        pixel_bytearray = pixel_bytearray.encode("utf-8", "surrogateescape")

    # Here we need to be careful because in some cases, GDCM reads a
    # buffer that is too large, so we need to make sure we only include
    # the first n_rows * n_columns * dtype_size bytes.
    numpy_dtype = _determine_numpy_dtype(dicom_dataset, gdcm_image)
    samples_per_pixel = dicom_dataset.get("SamplesPerPixel", 1)
    n_bytes = (dicom_dataset.Rows * dicom_dataset.Columns
               * numpy.dtype(numpy_dtype).itemsize * number_of_frames
               * samples_per_pixel)

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
    expected_length = (dicom_dataset.Rows * dicom_dataset.Columns
                       * number_of_frames * samples_per_pixel)

    if dicom_dataset.BitsAllocated > 8:
        expected_length *= (dicom_dataset.BitsAllocated // 8)

    if length_of_pixel_array != expected_length:
        raise AttributeError("Amount of pixel data %d does "
                             "not match the expected data %d" %
                             (length_of_pixel_array, expected_length))

    if should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
        dicom_dataset.PhotometricInterpretation = "RGB"

    return pixel_array.copy()
