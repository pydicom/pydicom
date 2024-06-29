# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
# TODO: remove module in v4.0
"""Utility functions used in the pixel data handlers."""

from sys import byteorder
from typing import Any

try:
    import numpy as np
except ImportError:
    pass

from pydicom import config
from pydicom.misc import warn_and_log


from pydicom.pixels.processing import (
    apply_color_lut as _apply_color_lut,
    apply_modality_lut as _apply_modality_lut,
    apply_voi_lut as _apply_voi_lut,
    apply_voi as _apply_voi,
    apply_windowing as _apply_windowing,
    convert_color_space as _convert_color_space,
)
from pydicom.pixels.utils import (
    expand_ybr422 as _expand_ybr422,
    get_expected_length as _get_expected_length,
    get_image_pixel_ids as _get_image_pixel_ids,
    get_j2k_parameters as _get_j2k_parameters,
    get_nr_frames as _get_nr_frames,
    pack_bits as _pack_bits,
    pixel_dtype as _pixel_dtype,
    reshape_pixel_array as _reshape_pixel_array,
    unpack_bits as _unpack_bits,
)


def _dtype_corrected_for_endianness(
    is_little_endian: bool, numpy_dtype: "np.dtype"
) -> "np.dtype":
    """Return a :class:`numpy.dtype` corrected for system and :class:`Dataset`
    endianness.

    .. deprecated:: 3.0

        This function will be removed in v4.0.

    Parameters
    ----------
    is_little_endian : bool
        The endianness of the affected :class:`~pydicom.dataset.Dataset`.
    numpy_dtype : numpy.dtype
        The numpy data type used for the *Pixel Data* without considering
        endianness.

    Raises
    ------
    ValueError
        If `is_little_endian` is ``None``, e.g. not initialized.

    Returns
    -------
    numpy.dtype
        The numpy data type used for the *Pixel Data* without considering
        endianness.
    """
    if is_little_endian is None:
        raise ValueError(
            "Dataset attribute 'is_little_endian' "
            "has to be set before writing the dataset"
        )

    if is_little_endian != (byteorder == "little"):
        return numpy_dtype.newbyteorder("S")

    return numpy_dtype


_DEPRECATED = {
    "apply_color_lut": _apply_color_lut,
    "apply_modality_lut": _apply_modality_lut,
    "apply_voi_lut": _apply_voi_lut,
    "apply_voi": _apply_voi,
    "apply_windowing": _apply_windowing,
    "convert_color_space": _convert_color_space,
    "pack_bits": _pack_bits,
    "unpack_bits": _unpack_bits,
}
_DEPRECATED_UTIL = {
    "expand_ybr422": _expand_ybr422,
    "get_expected_length": _get_expected_length,
    "get_image_pixel_ids": _get_image_pixel_ids,
    "get_j2k_parameters": _get_j2k_parameters,
    "get_nr_frames": _get_nr_frames,
    "pixel_dtype": _pixel_dtype,
    "reshape_pixel_array": _reshape_pixel_array,
}


def __getattr__(name: str) -> Any:
    if name in _DEPRECATED and not config._use_future:
        msg = (
            "The 'pydicom.pixel_data_handlers' module will be removed "
            f"in v4.0, please use 'from pydicom.pixels import {name}' instead"
        )
        warn_and_log(msg, DeprecationWarning)
        return _DEPRECATED[name]

    if name in _DEPRECATED_UTIL and not config._use_future:
        msg = (
            "The 'pydicom.pixel_data_handlers' module will be removed "
            f"in v4.0, please use 'from pydicom.pixels.utils import {name}' instead"
        )
        warn_and_log(msg, DeprecationWarning)
        return _DEPRECATED_UTIL[name]

    if name == "dtype_corrected_for_endianness" and not config._use_future:
        msg = (
            "'dtype_corrected_for_endianness' is deprecated and will be "
            "removed in v4.0"
        )
        warn_and_log(msg, DeprecationWarning)
        return _dtype_corrected_for_endianness

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
