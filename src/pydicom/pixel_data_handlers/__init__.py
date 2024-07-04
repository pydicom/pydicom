# TODO: remove module in v4.0
from typing import Any

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
    pack_bits as _pack_bits,
    unpack_bits as _unpack_bits,
)


_DEPRECATED = {
    "apply_color_lut": _apply_color_lut,
    "apply_modality_lut": _apply_modality_lut,
    "apply_rescale": _apply_modality_lut,
    "apply_voi_lut": _apply_voi_lut,
    "apply_voi": _apply_voi,
    "apply_windowing": _apply_windowing,
    "convert_color_space": _convert_color_space,
    "pack_bits": _pack_bits,
    "unpack_bits": _unpack_bits,
}
_DEPRECATED_UTIL = {
    "expand_ybr422": _expand_ybr422,
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

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
