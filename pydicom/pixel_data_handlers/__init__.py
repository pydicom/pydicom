
from typing import Any

from pydicom.pixels import (
    apply_color_lut,
    apply_modality_lut,
    apply_voi_lut,
    convert_color_space,
    apply_voi,
    apply_windowing,
    pack_bits,
    unpack_bits,
    apply_rescale,
)


_deprecations = {
    "apply_color_lut": apply_color_lut,
    "apply_modality_lut": apply_modality_lut,
    "apply_voi_lut": apply_voi_lut,
    "convert_color_space": convert_color_space,
    "apply_voi": apply_voi,
    "apply_windowing": apply_windowing,
    "pack_bits": pack_bits,
    "unpack_bits": unpack_bits,
    "apply_rescale": apply_rescale,
}


def __getattr__(name: str) -> Any:
    if name in _deprecations:
        fn = _deprecations[name]
        warnings.warn(
            f"Importing '{name}' from 'pydicom.pixel_data_handlers' is "
            f"deprecated, import from 'pydicom.pixels' instead",
            DeprecationWarning,
        )

        return globals()[fn]

    raise AttributeError(f"module {__name__} has no attribute {name}")
