# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Use the numpy package to convert supported pixel data to an ndarray.

**Supported transfer syntaxes**

* 1.2.840.10008.1.2 : Implicit VR Little Endian
* 1.2.840.10008.1.2.1 : Explicit VR Little Endian
* 1.2.840.10008.1.2.1.99 : Deflated Explicit VR Little Endian
* 1.2.840.10008.1.2.2 : Explicit VR Big Endian

**Supported data**

The numpy handler supports the conversion of data in the (7fe0,0010)
*Pixel Data* element to a numpy ndarray provided the related Image Pixel module
elements have values given in the table below.

+------------------------------------------------+--------------+----------+
| Element                                        | Supported    |          |
+-------------+---------------------------+------+ values       |          |
| Tag         | Keyword                   | Type |              |          |
+=============+===========================+======+==============+==========+
| (0028,0002) | SamplesPerPixel           | 1    | 1, 2, 3, N   | Required |
+-------------+---------------------------+------+--------------+----------+
| (0028,0006) | PlanarConfiguration       | 1C   | 0, 1         | Optional |
+-------------+---------------------------+------+--------------+----------+
| (0028,0008) | NumberOfFrames            | 1C   | 1, 2, N      | Optional |
+-------------+---------------------------+------+--------------+----------+
| (0028,0010) | Rows                      | 1    | 1, 2, N      | Required |
+-------------+---------------------------+------+--------------+----------+
| (0028,0011) | Columns                   | 1    | 1, 2, N      | Required |
+-------------+---------------------------+------+--------------+----------+
| (0028,0100) | BitsAllocated             | 1    | 1, 8, 16, 32 | Required |
+-------------+---------------------------+------+--------------+----------+
| (0028,0103) | PixelRepresentation       | 1    | 0, 1         | Required |
+-------------+---------------------------+------+--------------+----------+

"""

from platform import python_implementation
from sys import byteorder

import numpy as np

from pydicom.compat import in_py2 as IN_PYTHON2
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
    """Return True if the pixel data should to be converted from YCbCr to RGB.

    This affects JPEG transfer syntaxes.
    """
    return False


def should_change_PhotometricInterpretation_to_RGB(ds):
    """Return True if the PhotometricInterpretation should be changed to RGB.

    This affects JPEG transfer syntaxes.
    """
    return False


def get_expected_length(ds, unit='bytes'):
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
        The DICOM dataset containing the Image Pixel module and pixel data.
    unit : str, optional
        If 'bytes' then returns the expected length of the Pixel Data in
        whole bytes and NOT including an odd length trailing NULL padding
        byte. If 'pixels' then returns the expected length of the Pixel Data
        in terms of the total number of pixels (default 'bytes').

    Returns
    -------
    int
        The expected length of the pixel data in either whole bytes or pixels,
        excluding the NULL trailing padding byte for odd length data.
    """
    length = ds.Rows * ds.Columns * ds.SamplesPerPixel
    length *= getattr(ds, 'NumberOfFrames', 1)

    if unit == 'pixels':
        return length

    # Correct for the number of bytes per pixel
    bits_allocated = ds.BitsAllocated
    if bits_allocated == 1:
        # Determine the nearest whole number of bytes needed to contain
        #   1-bit pixel data. e.g. 10 x 10 1-bit pixels is 100 bits, which
        #   are packed into 12.5 -> 13 bytes
        length = length // 8 + (length % 8 > 0)
    else:
        length *= bits_allocated // 8

    return length


def pixel_dtype(ds):
    """Return a numpy dtype for the pixel data in dataset in `ds`.

    Suitable for use with IODs containing the Image Pixel module.

    +------------------------------------------+--------------+
    | Element                                  | Supported    |
    +-------------+---------------------+------+ values       |
    | Tag         | Keyword             | Type |              |
    +=============+=====================+======+==============+
    | (0028,0101) | BitsAllocated       | 1    | 1, 8, 16, 32 |
    +-------------+---------------------+------+--------------+
    | (0028,0103) | PixelRepresentation | 1    | 0, 1         |
    +-------------+---------------------+------+--------------+

    Parameters
    ----------
    ds : dataset.Dataset
        The DICOM dataset containing the pixel data you wish to get the
        numpy dtype for.

    Returns
    -------
    numpy.dtype
        A numpy dtype suitable for containing the dataset's pixel data.

    Raises
    ------
    NotImplementedError
        If the pixel data is of a type that isn't supported by either numpy
        or pydicom.
    """
    if ds.is_little_endian is None:
        ds.is_little_endian = ds.file_meta.TransferSyntaxUID.is_little_endian

    # (0028,0103) Pixel Representation, US, 1
    #   Data representation of the pixel samples
    #   0x0000 - unsigned int
    #   0x0001 - 2's complement (signed int)
    pixel_repr = ds.PixelRepresentation
    if pixel_repr == 0:
        dtype_str = 'uint'
    elif pixel_repr == 1:
        dtype_str = 'int'
    else:
        raise NotImplementedError(
            "Unable to determine the data type to use to contain the "
            "Pixel Data as a value of '{}' for '(0028,0103) Pixel "
            "Representation' is not supported".format(pixel_repr)
        )

    # (0028,0100) Bits Allocated, US, 1
    #   The number of bits allocated for each pixel sample
    #   PS3.5 8.1.1: Bits Allocated shall either be 1 or a multiple of 8
    #   For bit packed data we use uint8
    bits_allocated = ds.BitsAllocated
    if bits_allocated == 1:
        dtype_str = 'uint8'
    elif bits_allocated > 0 and bits_allocated % 8 == 0:
        dtype_str += str(bits_allocated)
    else:
        raise NotImplementedError(
            "Unable to determine the data type to use to contain the "
            "Pixel Data as a value of '{}' for '(0028,0100) Bits "
            "Allocated' is not supported".format(bits_allocated)
        )

    # Check to see if the dtype is valid for numpy
    try:
        dtype = np.dtype(dtype_str)
    except TypeError:
        raise NotImplementedError(
            "The data type '{}' needed to contain the Pixel Data is not "
            "supported by numpy".format(dtype_str)
        )

    # Correct for endianness of the system vs endianness of the dataset
    if ds.is_little_endian != (byteorder == 'little'):
        # 'S' swap from current to opposite
        dtype = dtype.newbyteorder('S')

    return dtype


def pack_bits(arr):
    """Pack a binary numpy ndarray into bytes for use with Pixel Data.

    Should be used in conjunction with (0028,0100) *BitsAllocated* = 1.

    Parameters
    ----------
    arr : numpy.ndarray
        The ndarray containing 1-bit data as ints. The array must only contain
        integer values of 0 and 1 and must have an 'uint' or 'int' dtype. For
        the sake of efficiency its recommended that the array length be a
        multiple of 8 (i.e. that any empty bit-padding to round out the byte
        has already been added).

    Returns
    -------
    bytes
        The bit packed data.

    Raises
    ------
    ValueError
        If `arr` contains anything other than 0 or 1.

    References
    ----------
    DICOM Standard, Part 5, Section 8.1.1 and Annex D
    """
    if arr.shape == (0,):
        return bytes()

    # Test array
    if not np.array_equal(arr, arr.astype(bool)):
        raise ValueError(
            "Only binary arrays (containing ones or zeroes) can be packed."
        )

    if len(arr.shape) > 1:
        raise ValueError("Only 1D arrays are supported.")

    # The array length must be a multiple of 8, pad the end
    if arr.shape[0] % 8:
        arr = np.append(arr, np.zeros(8 - arr.shape[0] % 8))

    # Reshape so each row is 8 bits
    arr = np.reshape(arr, (-1, 8))
    if 'PyPy' not in python_implementation():
        arr = np.fliplr(arr)
        arr = np.packbits(arr.astype('uint8'))
        bytestream = arr.tostring()
    else:
        # Implementation for PyPy as it lacks np.packbits
        def _convert_to_decimal(x):
            """Return a decimal from the length 8 binary array."""
            return np.sum(x * [1, 2, 4, 8, 16, 32, 64, 128])

        arr = np.apply_along_axis(_convert_to_decimal, axis=1, arr=arr)
        bytestream = arr.astype('uint8').tostring()

    return bytestream


def unpack_bits(bytestream):
    """Unpack bit packed pixel data into a numpy ndarray.

    Suitable for use when (0028,0011) *Bits Allocated* is 1.

    Parameters
    ----------
    bytestream : bytes
        The bit packed pixel data.

    Returns
    -------
    numpy.ndarray
        The unpacked pixel data as a 1D array.

    Notes
    -----
    The implementation for PyPy is roughly 100 times slower than the
    standard ``numpy.unpackbits`` method.

    References
    ----------
    DICOM Standard, Part 5, Section 8.1.1 and Annex D
    """
    if 'PyPy' not in python_implementation():
        # Thanks to @sbrodehl (#643)
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
        # -> [0 0 0 0 0 0 1 1 1 0 0 1 0 0 0 0]
        arr = np.ravel(arr)
    else:
        # Slow!
        # if single bits are used for binary representation, a uint8 array
        # has to be converted to a binary-valued array (that is 8 times bigger)
        bit = 0
        arr = np.ndarray(shape=(len(bytestream) * 8), dtype='uint8')
        # bit-packed pixels are packed from the right; i.e., the first pixel
        #  in the image frame corresponds to the first from the right bit of
        #  the first byte of the packed PixelData!
        for byte in bytestream:
            if IN_PYTHON2:
                byte = ord(byte)

            for bit in range(bit, bit + 8):
                arr[bit] = byte & 1
                byte >>= 1

            bit += 1

    return arr


def get_pixeldata(ds):
    """Return an ndarray of the Pixel Data.

    Parameters
    ----------
    ds : dataset.Dataset
        The DICOM dataset containing an Image Pixel module and the Pixel Data
        to be converted.

    Returns
    -------
    np.ndarray
        The contents of the Pixel Data element (7FE0,0010) as a 1D array.

    Raises
    ------
    AttributeError
        If the dataset is missing a required element.
    NotImplementedError
        If the dataset contains pixel data in an unsupported format.
    ValueError
        If the actual length of the pixel data doesn't match the expected
        length.
    """
    transfer_syntax = ds.file_meta.TransferSyntaxUID
    # The check of transfer syntax must be first
    if transfer_syntax not in SUPPORTED_TRANSFER_SYNTAXES:
        raise NotImplementedError(
            "Unable to convert the pixel data as the transfer syntax "
            "is not supported by the numpy pixel data handler."
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
    #   Note: this does NOT include the trailing null byte for odd length data
    expected_len = get_expected_length(ds)

    # Check that the actual length of the pixel data is as expected
    actual_length = len(ds.PixelData)
    # Correct for the trailing NULL byte padding for odd length data
    if actual_length != (expected_len + expected_len % 2):
        raise ValueError(
            "The length of the Pixel Data in the dataset doesn't match the "
            "expected amount ({0} vs. {1} bytes). The dataset may be "
            "corrupted or there may be an issue with the pixel data handler."
            .format(actual_length, expected_len + expected_len % 2)
        )

    # Unpack the pixel data into a 1D ndarray
    if ds.BitsAllocated == 1:
        # Skip any trailing padding bits
        nr_pixels = get_expected_length(ds, unit='pixels')
        arr = unpack_bits(ds.PixelData)[:nr_pixels]
    else:
        # Skip the trailing padding byte if present
        arr = np.frombuffer(ds.PixelData[:expected_len],
                            dtype=pixel_dtype(ds))

    if should_change_PhotometricInterpretation_to_RGB(ds):
        ds.PhotometricInterpretation = "RGB"

    return arr
