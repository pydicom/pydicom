# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Use the numpy package to decode pixel transfer syntaxes.

**Supported transfer syntaxes**

* 1.2.840.10008.1.2 : Implicit VR Little Endian
* 1.2.840.10008.1.2.1 : Explicit VR Little Endian
* 1.2.840.10008.1.2.1.99 : Deflated Explicit VR Little Endian
* 1.2.840.10008.1.2.2 : Explicit VR Big Endian

**Supported Data**

The numpy handler supports the conversion of data in the (7fe0,0010)
*Pixel Data* element to a numpy ndarray provided the related Image Pixel module
elements have values given in the table below.

+-----------------------------------------+-----------------------+-----------+
| Element                                 | Supported Values      |           |
+-------------+---------------------------+                       |           |
| Tag         | Keyword                   |                       |           |
+=============+===========================+=======================+===========+
| (0028,0102) | PixelRepresentation       | 0, 1                  | Required  |
+-------------+---------------------------+-----------------------+-----------+
| (0028,0011) | BitsAllocated             | 1, 8, 16, 32, 64, 128 | Required  |
+-------------+---------------------------+-----------------------+-----------+
| (0028,0002) | SamplesPerPixel           | 1, 2, 3, ..., N       | Required  |
+-------------+---------------------------+-----------------------+-----------+
| (0028,0004) | PhotometricInterpretation | MONOCHROME1           | Required  |
|             |                           | MONOCHROME2           |           |
|             |                           | PALETTE COLOR         |           |
|             |                           | RGB                   |           |
|             |                           | YBR_FULL              |           |
|             |                           | YBR_FULL_422          |           |
|             |                           | YBR_PARTIAL_422       |           |
|             |                           | YBR_PARTIAL_420       |           |
|             |                           | YBR_ICT               |           |
|             |                           | YBR_RCT               |           |
+-------------+---------------------------+-----------------------+-----------+
| (0028,0008) | NumberOfFrames            | 1, 2, ..., N          | Optional  |
+-------------+---------------------------+-----------------------+-----------+
| (0028,0006) | PlanarConfiguration       | 0, 1                  | Optional  |
+-------------+---------------------------+-----------------------+-----------+

"""

from platform import python_implementation
from sys import byteorder

import numpy as np

from pydicom import compat
from pydicom.pixel_data_handlers.util import dtype_corrected_for_endianess
from pydicom.uid import (
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian,
    ExplicitVRBigEndian,
)


SUPPORTED_TRANSFER_SYNTAXES = [
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian,
    ExplicitVRBigEndian,
]


def supports_transfer_syntax(ds):
    """Return True if the handler supports the transfer syntax used in `ds`."""
    return ds.file_meta.TransferSyntaxUID in SUPPORTED_TRANSFER_SYNTAXES


def needs_to_convert_to_RGB(ds):
    """Return True if FIXME."""
    return False


def should_change_PhotometricInterpretation_to_RGB(ds):
    """Return True if FIXME."""
    return False


def _get_expected_length(ds, units='bytes'):
    """Return the expected length (in bytes or pixels) of the pixel data.

    +-----------------------------------+------+-------------+
    | Element                           | Type | Required or |
    +-------------+---------------------+      | optional    |
    | Tag         | Keyword             |      |             |
    +=============+=====================+======+=============+
    | (0028,0002) | SamplesPerPixel     | 1    | Required    |
    +-------------+---------------------+------+-------------+
    | (0028,0008) | NumberOfFrames      | 1C   | Optional    |
    +-------------+---------------------+------+-------------+
    | (0028,0010) | Rows                | 1    | Required    |
    +-------------+---------------------+------+-------------+
    | (0028,0011) | Columns             | 1    | Required    |
    +-------------+---------------------+------+-------------+
    | (0028,0100) | BitsAllocated       | 1    | Required    |
    +-------------+---------------------+------+-------------+

    Parameters
    ----------
    ds : dataset.Dataset
        The DICOM dataset containing the Image Pixel module to get the length
        of the Pixel data.
    units : str, optional
        If 'bytes' then returns the expected length of the Pixel Data (in
        bytes and NOT including an odd length trailing NULL padding byte). If
        'pixels' then returns the expected length of the Pixel Data in terms of
        the total number of pixels (default 'bytes').

    Returns
    -------
    int
        The expected length of the Pixel Data in either bytes or pixels.
    """
    length = ds.Rows * ds.Columns * ds.SamplesPerPixel
    length *= getattr(ds, 'NumberOfFrames', 1)

    if units == 'pixels':
        return length

    # Correct for the number of bytes per pixel
    if ds.BitsAllocated == 1:
        # Determine the nearest whole number of bytes needed to contain
        #   1-bit pixel data
        # e.g. 10 x 10 1-bit pixels is 100 bits, which are
        #   packed into 12.5 -> 13 bytes
        length = length // 8 + (length % 8 > 0)
    elif ds.BitsAllocated > 8:
        length *= ds.BitsAllocated // 8

    return length


def _pixel_dtype(ds):
    """Return a numpy dtype for the dataset in `ds`.

    Suitable for use with IODs containing the Image Pixel module.

    +-----------------------------------+----------+--------------+
    | Element                           | Type     | Supported    |
    +-------------+---------------------+          | values       |
    | Tag         | Keyword             |          |              |
    +=============+=====================+==========+==============+
    | (0028,0101) | BitsAllocated       | Required | 1, 8, 16, 32 |
    |             |                     |          | 64, 128, 256 |
    +-------------+---------------------+----------+--------------+
    | (0028,0103) | PixelRepresentation | Required | 0, 1         |
    +-------------+---------------------+----------+--------------+

    Parameters
    ----------
    ds : dataset.Dataset
        The DICOM dataset containing the pixel data you wish to get the
        numpy dtype for.

    Returns
    -------
    np.dtype
        A numpy dtype suitable for containing the dataset's pixel data.

    Raises
    ------
    AttributeError
        If the dataset is missing elements required to determine the dtype.
    NotImplementedError
        If the pixel data is of a type that isn't supported by either numpy
        or pydicom.
    """
    # Ensure that the dataset's endianness attribute has been set
    if ds.is_little_endian is None:
        ds.is_little_endian = ds.file_meta.TransferSyntaxUID.is_little_endian

    # Check that the dataset has the required elements
    keywords = ['BitsAllocated', 'PixelRepresentation']
    missing = [elem for elem in keywords if elem not in ds]
    if missing:
        raise AttributeError(
            'Unable to determine the data type to use to contain the '
            'Pixel Data as the following required elements are '
            'missing from the dataset: ' + ', '.join(missing)
        )

    # (0028,0103) Pixel Representation, US, 1
    #   Data representation of the pixel samples
    #   0x0000 - unsigned int
    #   0x0001 - 2's complement (signed int)
    if ds.PixelRepresentation == 0:
        type_str = 'uint'
    elif ds.PixelRepresentation == 1:
        type_str = 'int'
    else:
        raise NotImplementedError(
            "Unable to determine the data type to use to contain the "
            "Pixel Data as a value of '{}' for '(0028,0103) Pixel "
            "Representation' is not supported"
            .format(ds.PixelRepresentation)
        )

    # (0028,0100) Bits Allocated, US, 1
    #   The number of bits allocated for each pixel sample
    #   PS3.5 8.1.1: Bits Allocated shall either be 1 or a multiple of 8
    #  i.e. 1, 8, 16, 24, 32, 40, ...
    #   numpy v1.13.0 supports 8, 16, 32, 64, 128, 256
    if ds.BitsAllocated == 1:
        type_str += '8'
    elif ds.BitsAllocated % 8 == 0:
        type_str += str(ds.BitsAllocated)
    else:
        raise NotImplementedError(
            "Unable to determine the data type to use to contain the "
            "Pixel Data as a value of '{}' for '(0028,0100) Bits "
            "Allocated' is not supported".format(ds.BitsAllocated)
        )

    # Check to see if the dtype is valid for numpy
    try:
        dtype = np.dtype(type_str)
    except TypeError:
        raise NotImplementedError(
            "The data type '{}' needed to contain the Pixel Data is not "
            "supported by numpy".format(type_str)
        )

    # Correct for endianness
    if ds.is_little_endian != (byteorder == 'little'):
        # 'S' swap from current to opposite
        dtype = dtype.newbyteorder('S')

    return dtype


def _pack_bits(arr):
    """Pack a numpy ndarray into 1-bit pixel data."""
    pass


def _unpack_bits(bytestream, force=False):
    """Unpack BitsAllocated = 1 packed pixel data.

    Parameters
    ----------
    bytestream : bytes
        The 1-bit packed pixel data.

    Returns
    -------
    numpy.ndarray

    Notes
    -----
    The implementation for PyPy is much slower.

    References
    ----------
    DICOM Standard, Part 5, Section 8.1.1 and Annex D
    """
    if 'PyPy' not in python_implementation():
        # e.g. b'\xC0\x09' -> [192, 9]
        arr = np.frombuffer(bytestream, dtype='uint8')
        # -> [1 1 0 0 0 0 0 0 0 0 0 0 1 0 0 1]
        arr = np.unpackbits(arr)
        # -> [[1 1 0 0 0 0 0 0],
        #     [0 0 0 0 1 0 0 1]]
        arr = np.reshape(arr, (-1, 8))
        # -> [[0 0 0 0 0 0 1 1],
        #     [1 0 0 1 0 0 0 0]]
        arr = np.fliplr(arr)
    else:
        # Slow!
        # if single bits are used for binary representation, a uint8 array
        # has to be converted to a binary-valued array (that is 8 times bigger)
        bit = 0
        arr = np.ndarray(shape=(actual_length * 8), dtype='uint8')
        # bit-packed pixels are packed from the right; i.e., the first pixel
        #  in the image frame corresponds to the first from the right bit of
        #  the first byte of the packed PixelData!
        #  See the following for details:
        #  * DICOM 3.5 Sect 8.1.1 (explanation of bit ordering)
        #  * DICOM Annex D (examples of encoding)
        for byte in bytestream:
            if compat.in_py2:
                byte = ord(byte)

            for bit in range(bit, bit + 8):
                pixel_array[bit] = byte & 1
                byte >>= 1

            bit += 1

        arr = arr[:expected_bit_length]

    return arr


def get_pixeldata(ds):
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
    np.ndarray
       The contents of the Pixel Data element (7FE0,0010) as an ndarray.
    """
    transfer_syntax = ds.file_meta.TransferSyntaxUID
    if transfer_syntax not in SUPPORTED_TRANSFER_SYNTAXES:
        raise NotImplementedError(
            "Pixel Data is compressed in a format pydicom does not yet "
            "handle. Cannot return array. Pydicom might be able to convert "
            "the pixel data using GDCM if it is installed."
        )

    # Check required elements
    required_elements = ['PixelData', 'BitsAllocated', 'Rows', 'Columns',
                         'PixelRepresentation', 'SamplesPerPixel']
    missing = [elem for elem in required_elements if elem not in ds]
    if missing:
        raise AttributeError(
            "Unable to convert the Pixel Data as the following required "
            "elements are missing from the dataset: " + ", ".join(missing)
        )

    # Calculate the expected length of the pixel data (in bytes)
    #   Note: this does not include the trailing null byte for odd length data
    expected_len = _get_expected_length(ds)

    # Check that the actual length of the pixel data is as expected
    actual_length = len(ds.PixelData)
    # Correct for the trailing NULL byte padding for odd length data
    if actual_length != (expected_len + expected_len % 2):
        raise ValueError(
            "The length of the Pixel Data in the dataset doesn't match the "
            "expected amount ({0} vs. {1} bytes). The dataset may be "
            "corrupted or there may be an error in the pixel data handler."
            .format(actual_length, expected_len + expected_len % 2)
        )

    # Unpack the pixel data into an ndarray
    if ds.BitsAllocated > 1 :
        nr_pixels = _get_expected_length(ds, units='pixels')
        arr = _unpack_bits(ds.PixelData[:nr_pixels])
    else:
        arr = np.frombuffer(ds.PixelData[:expected_len], dtype=_pixel_dtype(ds))

    if should_change_PhotometricInterpretation_to_RGB(ds):
        ds.PhotometricInterpretation = "RGB"

    return arr
