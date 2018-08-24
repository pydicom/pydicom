# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Utility functions used in the pixel data handlers."""

import sys

try:
    import numpy as np
    HAVE_NP = True
except:
    HAVE_NP = False


sys_is_little_endian = (sys.byteorder == 'little')


def dtype_corrected_for_endianess(is_little_endian, numpy_dtype):
    """Adapts the given numpy data type for changing the endianess of the
    dataset, if needed.

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
            If `is_little_endian` id None, e.g. not initialized.

        Returns
        -------
        numpy.dtype
            The numpy data type to be used for the pixel data, considering
            the endianess.
    """
    if is_little_endian is None:
        raise ValueError("Dataset attribute 'is_little_endian' "
                         "has to be set before writing the dataset")

    if is_little_endian != sys_is_little_endian:
        return numpy_dtype.newbyteorder('S')

    return numpy_dtype


def reshape_pixel_array(ds, arr):
    """

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
        A reshaped array containing the pixel data.
    """
    nr_frames = getattr(ds, 'NumberOfFrames', 1)
    planar_configuration = getattr(ds, 'PlanarConfiguration', 0)
    nr_samples = ds.SamplesPerPixel

    # With samples per pixel of 1 the pixel data is organised as
    # Frame 1:
    #   Plane 1
    #     1st row, 1st column; 1st row, 2nd column; ...
    #     2nd row, 1st column; 2nd row, 2nd column; ...
    #     ...
    # Frame 2:
    #   Plane 1 (N rows, M columns)
    #     (1, 1); (1, 2); ... (1, M)
    #     (2, 1); (2, 2); ...; (2, M)
    #     ...
    #     (N, 1); (N, 2); ...; (N, M)

    # For Planar Configuration of 0, each plane is organised as (e.g. for RGB)
    #   R(1, 1); G(1, 1); B(1, 1); R(1, 2); G(1, 2); B(1, 2) ...
    #   R(2, 1); G(2, 1); B(2, 1); R(2, 2); G(2, 2); B(2, 2) ...
    # In other words, each colour plane is sent non-contiguously

    # For Planar Configuration of 1, each plane is organised as (e.g. for RGB)
    #   R(1, 1); R(1, 2); ... R(N, M)
    #   G(1, 1); G(1, 2); ... G(N, M)
    #   B(1, 1); B(1, 2); ... B(N, M)
    # In other words, each colour plane is sent contiguously

    # Planar configuration is not meaningful for compressed transfer syntaxes

    if nr_frames < 1 or nr_samples < 1 or planar_configuration not in [0, 1]:
        raise

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
                # FIXME
                arr = arr.reshape(nr_samples, ds.Rows, ds.Columns)
                arr = arr.transpose(1, 2, 0)
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


def convert_YBR_to_RGB(arr_ybr):
    """Return an ndarray converted from YCbCr to RGB colour space.

    Parameters
    ----------
    arr_ybr : numpy.ndarray
        An ndarray of an image in YCbCr (luminance, chrominance) space.

    Returns
    -------
    numpy.ndarray
        The ndarray in RGB colour space.
    """
    if not HAVE_NP:
        raise NotImplementedError(
            "Numpy is required to convert the color space."
        )

    orig_dtype = arr_ybr.dtype

    # Conversion from PhotometricInterpretation of YBR to RGB
    #   PS3.3 C.7.6.3.1.2
    # https://en.wikipedia.org/wiki/YCbCr#JPEG_conversion
    ybr_to_rgb = numpy.asarray(
        [[1.0, +0.000000, +1.402000],
         [1.0, -0.344136, -0.714136],
         [1.0, +1.772000, +0.000000]], dtype=numpy.float)

    arr_ybr = arr_ybr.astype(numpy.float)
    arr_ybr -= [0, 128, 128]
    # Why copy?
    arr_ybr = numpy.dot(arr_ybr, ybr_to_rgb.T.copy())

    return arr_ybr.astype(orig_dtype)


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
