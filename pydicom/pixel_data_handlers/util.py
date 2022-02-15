import sys
from typing import Any
import warnings

from pydicom.pixels import (
    apply_color_lut as _apply_color_lut,
    apply_modality_lut as _apply_modality_lut,
    apply_voi_lut as _apply_voi_lut,
    convert_color_space as _convert_color_space,
    apply_voi as _apply_voi,
    apply_windowing as _apply_windowing,
    pack_bits as _pack_bits,
    unpack_bits as _unpack_bits,
    apply_rescale as _apply_rescale,
)

_deprecations = {
    "apply_color_lut": _apply_color_lut,
    "apply_modality_lut": _apply_modality_lut,
    "apply_voi_lut": _apply_voi_lut,
    "convert_color_space": _convert_color_space,
    "apply_voi": _apply_voi,
    "apply_windowing": _apply_windowing,
    "pack_bits": _pack_bits,
    "unpack_bits": _unpack_bits,
    "apply_rescale": _apply_rescale,
}


def __getattr__(name: str) -> Any:
    if name in _deprecations:
        warnings.warn(
            f"Importing '{name}' from 'pydicom.pixel_data_handlers.util' is "
            f"deprecated, import from 'pydicom.pixels' instead",
            DeprecationWarning,
        )

        return _deprecations[name]

    raise AttributeError(f"module {__name__} has no attribute {name}")


if sys.version_info[:2] < (3, 7):
    apply_color_lut = _apply_color_lut
    apply_modality_lut = _apply_modality_lut
    apply_voi_lut = _apply_voi_lut
    convert_color_space = _convert_color_space
    apply_voi = _apply_voi
    apply_windowing = _apply_windowing
    pack_bits = _pack_bits
    unpack_bits = _unpack_bits
    apply_rescale = _apply_rescale
