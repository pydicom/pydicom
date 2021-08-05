# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Use the `numpy <https://numpy.org/>`_ package to convert supported pixel
data to a :class:`numpy.ndarray`.

**Supported transfer syntaxes**

* 1.2.840.10008.1.2 : Implicit VR Little Endian
* 1.2.840.10008.1.2.1 : Explicit VR Little Endian
* 1.2.840.10008.1.2.1.99 : Deflated Explicit VR Little Endian
* 1.2.840.10008.1.2.2 : Explicit VR Big Endian

**Supported data**

The numpy handler supports the conversion of data in the (7FE0,0008) *Float
Pixel Data*, (7FE0,0009) *Double Float Pixel Data* and (7FE0,0010)
*Pixel Data* elements to a :class:`~numpy.ndarray` provided the
related :dcm:`Image Pixel<part03/sect_C.7.6.3.html>`, :dcm:`Floating Point
Image Pixel<part03/sect_C.7.6.24.html>` or  :dcm:`Double Floating Point Image
Pixel<part03/sect_C.7.6.25.html>` module elements have values given in the
table below.

+------------------------------------------------+---------------+----------+
| Element                                        | Supported     |          |
+-------------+---------------------------+------+ values        |          |
| Tag         | Keyword                   | Type |               |          |
+=============+===========================+======+===============+==========+
| (0028,0002) | SamplesPerPixel           | 1    | N             | Required |
+-------------+---------------------------+------+---------------+----------+
| (0028,0004) | PhotometricInterpretation | 1    | MONOCHROME1,  | Required |
|             |                           |      | MONOCHROME2,  |          |
|             |                           |      | RGB,          |          |
|             |                           |      | YBR_FULL,     |          |
|             |                           |      | YBR_FULL_422  |          |
+-------------+---------------------------+------+---------------+----------+
| (0028,0006) | PlanarConfiguration       | 1C   | 0, 1          | Optional |
+-------------+---------------------------+------+---------------+----------+
| (0028,0008) | NumberOfFrames            | 1C   | N             | Optional |
+-------------+---------------------------+------+---------------+----------+
| (0028,0010) | Rows                      | 1    | N             | Required |
+-------------+---------------------------+------+---------------+----------+
| (0028,0011) | Columns                   | 1    | N             | Required |
+-------------+---------------------------+------+---------------+----------+
| (0028,0100) | BitsAllocated             | 1    | 1, 8, 16, 32, | Required |
|             |                           |      | 64            |          |
+-------------+---------------------------+------+---------------+----------+
| (0028,0101) | BitsStored                | 1    | 1, 8, 12, 16  | Optional |
+-------------+---------------------------+------+---------------+----------+
| (0028,0103) | PixelRepresentation       | 1C   | 0, 1          | Optional |
+-------------+---------------------------+------+---------------+----------+

"""

from typing import TYPE_CHECKING, cast
import warnings

try:
    import numpy as np
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom.pixel_data_handlers.util import pixel_dtype, get_expected_length
import pydicom.uid

if TYPE_CHECKING:  # pragma: no cover
    from pydicom.dataset import Dataset

HANDLER_NAME = 'Numpy'

DEPENDENCIES = {
    'numpy': ('http://www.numpy.org/', 'NumPy'),
}

SUPPORTED_TRANSFER_SYNTAXES = [
    pydicom.uid.ExplicitVRLittleEndian,
    pydicom.uid.ImplicitVRLittleEndian,
    pydicom.uid.DeflatedExplicitVRLittleEndian,
    pydicom.uid.ExplicitVRBigEndian,
]


def is_available() -> bool:
    """Return ``True`` if the handler has its dependencies met."""
    return HAVE_NP


def supports_transfer_syntax(transfer_syntax: pydicom.uid.UID) -> bool:
    """Return ``True`` if the handler supports the `transfer_syntax`.

    Parameters
    ----------
    transfer_syntax : uid.UID
        The Transfer Syntax UID of the *Pixel Data* that is to be used with
        the handler.
    """
    return transfer_syntax in SUPPORTED_TRANSFER_SYNTAXES


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
    return False


def pack_bits(arr: "np.ndarray", pad: bool = True) -> bytes:
    """Pack a binary :class:`numpy.ndarray` for use with *Pixel Data*.

    .. versionadded:: 1.2

    Should be used in conjunction with (0028,0100) *Bits Allocated* = 1.

    .. versionchanged:: 2.1

        Added the `pad` keyword parameter and changed to allow `arr` to be
        2 or 3D.

    Parameters
    ----------
    arr : numpy.ndarray
        The :class:`numpy.ndarray` containing 1-bit data as ints. `arr` must
        only contain integer values of 0 and 1 and must have an 'uint'  or
        'int' :class:`numpy.dtype`. For the sake of efficiency it's recommended
        that the length of `arr` be a multiple of 8 (i.e. that any empty
        bit-padding to round out the byte has already been added). The input
        `arr` should either be shaped as (rows, columns) or (frames, rows,
        columns) or the equivalent 1D array used to ensure that the packed
        data is in the correct order.
    pad : bool, optional
        If ``True`` (default) then add a null byte to the end of the packed
        data to ensure even length, otherwise no padding will be added.

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
    DICOM Standard, Part 5,
    :dcm:`Section 8.1.1<part05/chapter_8.html#sect_8.1.1>` and
    :dcm:`Annex D<part05/chapter_D.html>`
    """
    if arr.shape == (0,):
        return bytes()

    # Test array
    if not np.array_equal(arr, arr.astype(bool)):
        raise ValueError(
            "Only binary arrays (containing ones or zeroes) can be packed."
        )

    if len(arr.shape) > 1:
        arr = arr.ravel()

    # The array length must be a multiple of 8, pad the end
    if arr.shape[0] % 8:
        arr = np.append(arr, np.zeros(8 - arr.shape[0] % 8))

    # Reshape so each row is 8 bits
    arr = np.reshape(arr, (-1, 8))
    arr = np.fliplr(arr)
    arr = np.packbits(arr.astype('uint8'))

    packed: bytes = arr.tobytes()
    if pad:
        return packed + b'\x00' if len(packed) % 2 else packed

    return packed


def unpack_bits(bytestream: bytes) -> "np.ndarray":
    """Unpack bit packed *Pixel Data* or *Overlay Data* into a
    :class:`numpy.ndarray`.

    Suitable for use when (0028,0011) *Bits Allocated* or (60xx,0100) *Overlay
    Bits Allocated* is 1.

    Parameters
    ----------
    bytestream : bytes
        The bit packed pixel data.

    Returns
    -------
    numpy.ndarray
        The unpacked *Pixel Data* as a 1D array.

    References
    ----------
    DICOM Standard, Part 5,
    :dcm:`Section 8.1.1<part05/chapter_8.html#sect_8.1.1>` and
    :dcm:`Annex D<part05/chapter_D.html>`
    """
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

    return cast("np.ndarray", arr)


def get_pixeldata(ds: "Dataset", read_only: bool = False) -> "np.ndarray":
    """Return a :class:`numpy.ndarray` of the pixel data.

    .. versionchanged:: 1.4

        * Added support for uncompressed pixel data with a *Photometric
          Interpretation* of ``YBR_FULL_422``.
        * Added support for *Float Pixel Data* and *Double Float Pixel Data*


    Parameters
    ----------
    ds : Dataset
        The :class:`Dataset` containing an Image Pixel, Floating Point Image
        Pixel or Double Floating Point Image Pixel module and the
        *Pixel Data*, *Float Pixel Data* or *Double Float Pixel Data* to be
        converted. If (0028,0004) *Photometric Interpretation* is
        `'YBR_FULL_422'` then the pixel data will be
        resampled to 3 channel data as per Part 3, :dcm:`Annex C.7.6.3.1.2
        <part03/sect_C.7.6.3.html#sect_C.7.6.3.1.2>` of the DICOM Standard.
    read_only : bool, optional
        If ``False`` (default) then returns a writeable array that no longer
        uses the original memory. If ``True`` and the value of (0028,0100)
        *Bits Allocated* > 1 then returns a read-only array that uses the
        original memory buffer of the pixel data. If *Bits Allocated* = 1 then
        always returns a writeable array.

    Returns
    -------
    np.ndarray
        The contents of (7FE0,0010) *Pixel Data*, (7FE0,0008) *Float Pixel
        Data* or (7FE0,0009) *Double Float Pixel Data* as a 1D array.

    Raises
    ------
    AttributeError
        If `ds` is missing a required element.
    NotImplementedError
        If `ds` contains pixel data in an unsupported format.
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
    keywords = ['PixelData', 'FloatPixelData', 'DoubleFloatPixelData']
    px_keyword = [kw for kw in keywords if kw in ds]
    if len(px_keyword) != 1:
        raise AttributeError(
            "Unable to convert the pixel data: one of Pixel Data, Float "
            "Pixel Data or Double Float Pixel Data must be present in "
            "the dataset"
        )

    # Attributes required by both Floating Point Image Pixel Module Attributes
    # and Image Pixel Description Macro Attributes
    required_elements = [
        'BitsAllocated', 'Rows', 'Columns',
        'SamplesPerPixel', 'PhotometricInterpretation'
    ]
    if px_keyword[0] == 'PixelData':
        # Attributess required by Image Pixel Description Macro Attributes
        required_elements.extend(['PixelRepresentation', 'BitsStored'])
    missing = [elem for elem in required_elements if elem not in ds]
    if missing:
        raise AttributeError(
            "Unable to convert the pixel data as the following required "
            "elements are missing from the dataset: " + ", ".join(missing)
        )
    if ds.SamplesPerPixel > 1:
        if not hasattr(ds, 'PlanarConfiguration'):
            raise AttributeError(
                "Unable to convert the pixel data as the following "
                "conditionally required element is missing from the dataset: "
                "PlanarConfiguration"
            )

    # May be Pixel Data, Float Pixel Data or Double Float Pixel Data
    pixel_data = getattr(ds, px_keyword[0])

    # Calculate the expected length of the pixel data (in bytes)
    #   Note: this does NOT include the trailing null byte for odd length data
    expected_len = get_expected_length(ds)

    # Check that the actual length of the pixel data is as expected
    actual_length = len(pixel_data)

    # Correct for the trailing NULL byte padding for odd length data
    padded_expected_len = expected_len + expected_len % 2
    if actual_length < padded_expected_len:
        if actual_length == expected_len:
            warnings.warn(
                "The odd length pixel data is missing a trailing padding byte"
            )
        else:
            raise ValueError(
                "The length of the pixel data in the dataset ({} bytes) "
                "doesn't match the expected length ({} bytes). "
                "The dataset may be corrupted or there may be an issue "
                "with the pixel data handler."
                .format(actual_length, padded_expected_len)
            )
    elif actual_length > padded_expected_len:
        # PS 3.5, Section 8.1.1
        msg = (
            "The length of the pixel data in the dataset ({} bytes) indicates "
            "it contains excess padding. {} bytes will be removed from the "
            "end of the data"
            .format(actual_length, actual_length - expected_len)
        )
        # PS 3.3, Annex C.7.6.3
        if ds.PhotometricInterpretation == 'YBR_FULL_422':
            # Check to ensure we do have subsampled YBR 422 data
            ybr_full_length = expected_len / 2 * 3 + expected_len / 2 * 3 % 2
            # >= as may also include excess padding
            if actual_length >= ybr_full_length:
                msg = (
                    "The Photometric Interpretation of the dataset is "
                    "YBR_FULL_422, however the length of the pixel data "
                    "({} bytes) is a third larger than expected ({} bytes) "
                    "which indicates that this may be incorrect. You may "
                    "need to change the Photometric Interpretation to "
                    "the correct value.".format(actual_length, expected_len)
                )
        warnings.warn(msg)

    # Unpack the pixel data into a 1D ndarray
    if ds.BitsAllocated == 1:
        # Skip any trailing padding bits
        nr_pixels = get_expected_length(ds, unit='pixels')
        arr = unpack_bits(pixel_data)[:nr_pixels]
    else:
        # Skip the trailing padding byte(s) if present
        dtype = pixel_dtype(ds, as_float=('Float' in px_keyword[0]))
        arr = np.frombuffer(pixel_data[:expected_len], dtype=dtype)
        if ds.PhotometricInterpretation == 'YBR_FULL_422':
            # PS3.3 C.7.6.3.1.2: YBR_FULL_422 data needs to be resampled
            # Y1 Y2 B1 R1 -> Y1 B1 R1 Y2 B1 R1
            out = np.zeros(expected_len // 2 * 3, dtype=dtype)
            out[::6] = arr[::4]  # Y1
            out[3::6] = arr[1::4]  # Y2
            out[1::6], out[4::6] = arr[2::4], arr[2::4]  # B
            out[2::6], out[5::6] = arr[3::4], arr[3::4]  # R
            arr = out

    if should_change_PhotometricInterpretation_to_RGB(ds):
        ds.PhotometricInterpretation = "RGB"

    if not read_only and ds.BitsAllocated > 1:
        return cast("np.ndarray", arr.copy())

    return cast("np.ndarray", arr)
