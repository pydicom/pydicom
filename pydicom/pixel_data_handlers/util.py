# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Utility functions used in the pixel data handlers."""

from sys import byteorder

try:
    import numpy as np
    HAVE_NP = True
except ImportError:
    HAVE_NP = False


def convert_color_space(arr, current, desired):
    """Convert the image(s) in `arr` from one color space to another.

    Parameters
    ----------
    arr : numpy.ndarray
        The image(s) as an ndarray with shape (frames, rows, columns, planes)
        or (rows, columns, planes).
    current : str
        The current color space, should be a valid value for (0028,0004)
        *Photometric Interpretation*. One of 'RGB', 'YBR_FULL'.
    desired : str
        The desired color space, should be a valid value for (0028,0004)
        *Photometric Interpretation*. One of 'RGB', 'YBR_FULL'.

    Returns
    -------
    numpy.ndarray
        The image(s) converted to the desired color space.
    """
    if not HAVE_NP:
        raise ImportError(
            "Numpy is required to convert the color space."
        )

    # No change needed
    if current == desired:
        return arr

    _converters = {
        'YBR_FULL': {
            'RGB': _convert_YBR_FULL_to_RGB
        },
        'RGB': {
            'YBR_FULL': _convert_RGB_to_YBR_FULL,
        }
    }
    try:
        converter = _converters[current][desired]
    except KeyError:
        raise NotImplementedError(
            "Conversion from {0} to {1} is not supported."
            .format(current, desired)
        )

    return converter(arr)


def dtype_corrected_for_endianness(is_little_endian, numpy_dtype):
    """Return a numpy dtype corrected for system and dataset endianness.

    Parameters
    ----------
    is_little_endian : bool
        The endianess of the affected dataset.
    numpy_dtype : numpy.dtype
        The numpy data type used for the pixel data without considering
        endianess.

    Raises
    ------
    ValueError
        If `is_little_endian` is None, e.g. not initialized.

    Returns
    -------
    numpy.dtype
        The numpy data type to be used for the pixel data, considering
        the endianess.
    """
    if is_little_endian is None:
        raise ValueError("Dataset attribute 'is_little_endian' "
                         "has to be set before writing the dataset")

    if is_little_endian != (byteorder == 'little'):
        return numpy_dtype.newbyteorder('S')

    return numpy_dtype


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
    if not HAVE_NP:
        raise ImportError("Numpy is required to determine the dtype.")

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
        raise ValueError(
            "Unable to determine the data type to use to contain the "
            "Pixel Data as a value of '{}' for '(0028,0103) Pixel "
            "Representation' is invalid".format(pixel_repr)
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
        raise ValueError(
            "Unable to determine the data type to use to contain the "
            "Pixel Data as a value of '{}' for '(0028,0100) Bits "
            "Allocated' is invalid".format(bits_allocated)
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


def reshape_pixel_array(ds, arr):
    """Return a reshaped ndarray `arr`.

    +------------------------------------------+-----------+----------+
    | Element                                  | Supported |          |
    +-------------+---------------------+------+ values    |          |
    | Tag         | Keyword             | Type |           |          |
    +=============+=====================+======+===========+==========+
    | (0028,0002) | SamplesPerPixel     | 1    | N > 0     | Required |
    +-------------+---------------------+------+-----------+----------+
    | (0028,0006) | PlanarConfiguration | 1C   | 0, 1      | Optional |
    +-------------+---------------------+------+-----------+----------+
    | (0028,0008) | NumberOfFrames      | 1C   | N > 0     | Optional |
    +-------------+---------------------+------+-----------+----------+
    | (0028,0010) | Rows                | 1    | N > 0     | Required |
    +-------------+---------------------+------+-----------+----------+
    | (0028,0011) | Columns             | 1    | N > 0     | Required |
    +-------------+---------------------+------+-----------+----------+

    (0028,0008) *Number of Frames* is required when the pixel data contains
    more than 1 frame. (0028,0006) *Planar Configuration* is required when
    (0028,0002) *Samples per Pixel* is greater than 1. For certain
    compressed transfer syntaxes it is always taken to be either 0 or 1 as
    shown in the table below.

    +---------------------------------------------+-----------------------+
    | Transfer Syntax                             | Planar Configuration  |
    +------------------------+--------------------+                       |
    | UID                    | Name               |                       |
    +========================+====================+=======================+
    | 1.2.840.10008.1.2.4.50 | JPEG Baseline      | 0                     |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.57 | JPEG Lossless,     | 0                     |
    |                        | Non-hierarchical   |                       |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.70 | JPEG Lossless,     | 0                     |
    |                        | Non-hierarchical,  |                       |
    |                        | SV1                |                       |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.80 | JPEG-LS Lossless   | 1                     |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.81 | JPEG-LS Lossy      | 1                     |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.90 | JPEG 2000 Lossless | 0                     |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.91 | JPEG 2000 Lossy    | 0                     |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.5    | RLE Lossless       | 1                     |
    +------------------------+--------------------+-----------------------+

    Parameters
    ----------
    ds : dataset.Dataset
        The dataset containing the Image Pixel module corresponding to the
        pixel data in `arr`.
    arr : numpy.ndarray
        The 1D array containing the pixel data.

    Returns
    -------
    numpy.ndarray
        A reshaped array containing the pixel data. The shape of the array
        depends on the contents of the dataset:

        * For single frame, single sample data (rows, columns)
        * For single frame, multi-sample data (rows, columns, planes)
        * For multi-frame, single sample data (frames, rows, columns)
        * For multi-frame, multi-sample data (frames, rows, columns, planes)

    References
    ----------

    * DICOM Standard, Part 3, Annex C.7.6.3.1
    * DICOM Standard, Part 4, Sections 8.2.1-4
    """
    if not HAVE_NP:
        raise ImportError("Numpy is required to reshape the pixel array.")

    nr_frames = getattr(ds, 'NumberOfFrames', 1)
    nr_samples = ds.SamplesPerPixel

    if nr_frames < 1:
        raise ValueError(
            "Unable to reshape the pixel array as a value of {} for "
            "(0028,0008) 'Number of Frames' is invalid."
            .format(nr_frames)
        )

    if nr_samples < 1:
        raise ValueError(
            "Unable to reshape the pixel array as a value of {} for "
            "(0028,0002) 'Samples per Pixel' is invalid."
            .format(nr_samples)
        )

    # Valid values for Planar Configuration are dependent on transfer syntax
    if nr_samples > 1:
        transfer_syntax = ds.file_meta.TransferSyntaxUID
        if transfer_syntax in ['1.2.840.10008.1.2.4.50',
                               '1.2.840.10008.1.2.4.57',
                               '1.2.840.10008.1.2.4.70',
                               '1.2.840.10008.1.2.4.90',
                               '1.2.840.10008.1.2.4.91']:
            planar_configuration = 0
        elif transfer_syntax in ['1.2.840.10008.1.2.4.80',
                                 '1.2.840.10008.1.2.4.81',
                                 '1.2.840.10008.1.2.5']:
            planar_configuration = 1
        else:
            planar_configuration = ds.PlanarConfiguration

        if planar_configuration not in [0, 1]:
            raise ValueError(
                "Unable to reshape the pixel array as a value of {} for "
                "(0028,0006) 'Planar Configuration' is invalid."
                .format(planar_configuration)
            )

    if nr_frames > 1:
        # Multi-frame
        if nr_samples == 1:
            # Single plane
            arr = arr.reshape(nr_frames, ds.Rows, ds.Columns)
        else:
            # Multiple planes, usually 3
            if planar_configuration == 0:
                arr = arr.reshape(nr_frames, ds.Rows, ds.Columns, nr_samples)
            else:
                arr = arr.reshape(nr_frames, nr_samples, ds.Rows, ds.Columns)
                arr = arr.transpose(0, 2, 3, 1)
    else:
        # Single frame
        if nr_samples == 1:
            # Single plane
            arr = arr.reshape(ds.Rows, ds.Columns)
        else:
            # Multiple planes, usually 3
            if planar_configuration == 0:
                arr = arr.reshape(ds.Rows, ds.Columns, nr_samples)
            else:
                arr = arr.reshape(nr_samples, ds.Rows, ds.Columns)
                arr = arr.transpose(1, 2, 0)

    return arr


def _convert_RGB_to_YBR_FULL(arr):
    """Return an ndarray converted from RGB to YBR_FULL color space.

    Parameters
    ----------
    arr : numpy.ndarray
        An ndarray of an 8-bit per channel images in RGB color space.

    Returns
    -------
    numpy.ndarray
        The array in YBR_FULL color space.

    References
    ----------

    * DICOM Standard, Part 3, Annex C.7.6.3.1.2
    * ISO/IEC 10918-5:2012, Section 7
    """
    orig_dtype = arr.dtype
    arr = arr.astype(np.float)

    rgb_to_ybr = np.asarray(
        [[+0.299, +0.587, +0.114],
         [-0.299, -0.587, +0.886],
         [+0.701, -0.587, -0.114]], dtype=np.float)

    arr = np.dot(arr, rgb_to_ybr.T)
    if len(arr.shape) == 4:
        # Multi-frame
        arr[:, :, :, 1] /= 1.772
        arr[:, :, :, 2] /= 1.402
    else:
        # Single frame
        arr[:, :, 1] /= 1.772
        arr[:, :, 2] /= 1.402

    arr += [0, 128, 128]

    # Round(x) -> floor of (arr + 0.5)
    arr = np.floor(arr + 0.5)
    # Max(0, arr) -> 0 if 0 >= arr, arr otherwise
    arr[np.where(arr < 0)] = 0
    # Min(arr, 255) -> arr if arr <= 255, 255 otherwise
    arr[np.where(arr > 255)] = 255

    return arr.astype(orig_dtype)


def _convert_YBR_FULL_to_RGB(arr):
    """Return an ndarray converted from YBR_FULL to RGB color space.

    Parameters
    ----------
    arr : numpy.ndarray
        An ndarray of an 8-bit per channel images in YBR_FULL color space.

    Returns
    -------
    numpy.ndarray
        The array in RGB color space.

    References
    ----------

    * DICOM Standard, Part 3, Annex C.7.6.3.1.2
    * ISO/IEC 10918-5:2012, Section 7
    """
    orig_dtype = arr.dtype

    ybr_to_rgb = np.asarray(
        [[1.0, +0.0, +1.402],
         [1.0, -0.114 * 1.772 / 0.587, -0.299 * 1.402 / 0.587],
         [1.0, +1.772, +0.0]], dtype=np.float)

    arr = arr.astype(np.float)
    arr -= [0, 128, 128]
    arr = np.dot(arr, ybr_to_rgb.T)

    # Round(x) -> floor of (arr + 0.5)
    arr = np.floor(arr + 0.5)
    # Max(0, arr) -> 0 if 0 >= arr, arr otherwise
    arr[np.where(arr < 0)] = 0
    # Min(arr, 255) -> arr if arr <= 255, 255 otherwise
    arr[np.where(arr > 255)] = 255

    return arr.astype(orig_dtype)
