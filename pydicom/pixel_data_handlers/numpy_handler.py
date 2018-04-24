"""Use the numpy package to decode pixel transfer syntaxes."""
import sys
import pydicom.uid
from pydicom import compat
have_numpy = True
try:
    import numpy
except ImportError:
    have_numpy = False
    raise

sys_is_little_endian = (sys.byteorder == 'little')

NumpySupportedTransferSyntaxes = [
    pydicom.uid.ExplicitVRLittleEndian,
    pydicom.uid.ImplicitVRLittleEndian,
    pydicom.uid.DeflatedExplicitVRLittleEndian,
    pydicom.uid.ExplicitVRBigEndian,
]


def supports_transfer_syntax(dicom_dataset):
    """
    Returns
    -------
    bool
        True if this pixel data handler might support this transfer syntax.

        False to prevent any attempt to try to use this handler
        to decode the given transfer syntax
    """
    return (dicom_dataset.file_meta.TransferSyntaxUID in
            NumpySupportedTransferSyntaxes)


def needs_to_convert_to_RGB(dicom_dataset):
    return False


def should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
    return False


def get_pixeldata(dicom_dataset):
    """If NumPy is available, return an ndarray of the Pixel Data.
    Raises
    ------
    TypeError
        If there is no Pixel Data or not a supported data type.

    ImportError
        If NumPy isn't found

    NotImplementedError
        if the transfer syntax is not supported

    AttributeError
        if the decoded amount of data does not match the expected amount

    Returns
    -------
    numpy.ndarray
       The contents of the Pixel Data element (7FE0,0010) as an ndarray.
    """
    if (dicom_dataset.file_meta.TransferSyntaxUID not in
            NumpySupportedTransferSyntaxes):
        raise NotImplementedError("Pixel Data is compressed in a "
                                  "format pydicom does not yet handle. "
                                  "Cannot return array. Pydicom might "
                                  "be able to convert the pixel data "
                                  "using GDCM if it is installed.")
    if not have_numpy:
        msg = ("The Numpy package is required to use pixel_array, and "
               "numpy could not be imported.")
        raise ImportError(msg)
    if 'PixelData' not in dicom_dataset:
        raise TypeError("No pixel data found in this dataset.")

    # Make NumPy format code, e.g. "uint16", "int32" etc
    # from two pieces of info:
    # dicom_dataset.PixelRepresentation -- 0 for unsigned, 1 for signed;
    # dicom_dataset.BitsAllocated -- 8, 16, or 32
    if dicom_dataset.BitsAllocated == 1:
        # single bits are used for representation of binary data
        format_str = 'uint8'
    elif dicom_dataset.PixelRepresentation == 0:
        format_str = 'uint{}'.format(dicom_dataset.BitsAllocated)
    elif dicom_dataset.PixelRepresentation == 1:
        format_str = 'int{}'.format(dicom_dataset.BitsAllocated)
    else:
        format_str = 'bad_pixel_representation'
    try:
        numpy_dtype = numpy.dtype(format_str)
    except TypeError:
        msg = ("Data type not understood by NumPy: "
               "format='{}', PixelRepresentation={}, "
               "BitsAllocated={}".format(
                   format_str,
                   dicom_dataset.PixelRepresentation,
                   dicom_dataset.BitsAllocated))
        raise TypeError(msg)

    if dicom_dataset.is_little_endian != sys_is_little_endian:
        numpy_dtype = numpy_dtype.newbyteorder('S')

    pixel_bytearray = dicom_dataset.PixelData

    length_of_pixel_array = len(pixel_bytearray)
    expected_length = dicom_dataset.Rows * dicom_dataset.Columns
    if ('NumberOfFrames' in dicom_dataset and
            dicom_dataset.NumberOfFrames > 1):
        expected_length *= dicom_dataset.NumberOfFrames
    if ('SamplesPerPixel' in dicom_dataset and
            dicom_dataset.SamplesPerPixel > 1):
        expected_length *= dicom_dataset.SamplesPerPixel
    if dicom_dataset.BitsAllocated > 8:
        expected_length *= (dicom_dataset.BitsAllocated // 8)
    elif dicom_dataset.BitsAllocated == 1:
        # need to take the nearest number of bytes that will be needed
        #  to encode expected_length
        expected_bit_length = expected_length
        expected_length = int(expected_length / 8) + (expected_length % 8 > 0)
    padded_length = expected_length
    if expected_length & 1:
        padded_length += 1
    if length_of_pixel_array != padded_length:
        raise AttributeError(
            "Amount of pixel data %d does not "
            "match the expected data %d" %
            (length_of_pixel_array, padded_length))

    # the checks above confirmed the amount of data in PixelData is what
    #  we expect, now we can unpack it
    if dicom_dataset.BitsAllocated == 1:
        # if single bits are used for binary representation, a uint8 array
        # has to be converted to a binary-valued array (that is 8 times bigger)
        bit = 0
        pixel_array = \
            numpy.ndarray(shape=(length_of_pixel_array*8), dtype='uint8')
        # bit-packed pixels are packed from the right; i.e., the first pixel
        #  in the image frame corresponds to the first from the right bit of
        #  the first byte of the packed PixelData!
        #  See the following for details:
        #  * DICOM 3.5 Sect 8.1.1 (explanation of bit ordering)
        #  * DICOM Annex D (examples of encoding)
        for byte in pixel_bytearray:
            if compat.in_py2:
                byte = ord(byte)
            for bit in range(bit, bit+8):
                pixel_array[bit] = byte & 1
                byte >>= 1
            bit += 1
    else:
        pixel_array = numpy.frombuffer(pixel_bytearray, dtype=numpy_dtype)

    if dicom_dataset.BitsAllocated == 1:
        pixel_array = pixel_array[:expected_bit_length]
    elif expected_length != padded_length:
        pixel_array = pixel_array[:expected_length]

    if should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
        dicom_dataset.PhotometricInterpretation = "RGB"
    return pixel_array
