
from pydicom.pixel_data_handlers.util import (
    apply_color_lut, apply_modality_lut, apply_voi_lut, convert_color_space,
)

apply_rescale = apply_modality_lut
apply_windowing = apply_voi_lut
