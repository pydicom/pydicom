# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Utility functions used in the pixel data handlers."""

import sys

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
