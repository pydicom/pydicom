# Copyright 2008-2021 pydicom authors. See LICENSE file for details.
"""Benchmarks for the utils.convert_colour_space function.

Requires asv and numpy.
"""

import numpy as np

from pydicom import dcmread
from pydicom.data import get_testdata_file
from pydicom.pixel_data_handlers import convert_color_space

# 32/32, 3 sample/pixel, 2 frame
EXPL_32_3_2F = get_testdata_file("SC_rgb_32bit_2frame.dcm")


class TimeConversion:
    """Time tests for colour space conversions."""
    def setup(self):
        """Setup the tests."""
        self.no_runs = 100

        self.arr_large = np.ones((10, 1024, 1024, 3), dtype=np.uint8)
        self.arr_32_3_2f = dcmread(EXPL_32_3_2F).pixel_array

    def time_ybr_rgb_32_3_2f(self):
        """Time converting YBR to RGB."""
        for ii in range(self.no_runs):
            convert_color_space(self.arr_32_3_2f, "YBR_FULL", "RGB")

    def time_rgb_ybr_32_3_2f(self):
        """Time converting RGB to YBR."""
        for ii in range(self.no_runs):
            convert_color_space(self.arr_32_3_2f, "RGB", "YBR_FULL")

    def time_ybr_rgb_large(self):
        """Time converting YBR to RGB."""
        for ii in range(1):
            convert_color_space(
                self.arr_large, "YBR_FULL", "RGB", per_frame=True
            )

    def time_rgb_ybr_large(self):
        """Time converting RGB to YBR."""
        for ii in range(1):
            convert_color_space(
                self.arr_large, "RGB", "YBR_FULL", per_frame=True
            )
