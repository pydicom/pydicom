# Copyright 2008-2019 pydicom authors. See LICENSE file for details.
"""Benchmarks for the pixel data utilities."""

from pydicom import dcmread
from pydicom.data import get_testdata_files
from pydicom.pixel_data_handlers.util import convert_color_space


class TimeConvertColorSpace:
    """Benchmarks for utils.convert_color_space()."""
    def setup(self):
        """Setup the benchmark."""
        self.no_runs = 1000

        ds = dcmread(get_testdata_files('SC_rgb_gdcm2k_uncompressed.dcm')[0])
        self.rgb = ds.pixel_array
        ds = dcmread(get_testdata_files('SC_ybr_full_uncompressed.dcm')[0])
        self.ybr_full = ds.pixel_array

    def time_rgb_ybr(self):
        """Time converting from RGB to YBR color space."""
        for ii in range(self.no_runs):
            convert_color_space(self.rgb, 'RGB', 'YBR_FULL')

    def time_ybr_rgb(self):
        """Time converting from YBR to RGB color space."""
        for ii in range(self.no_runs):
            convert_color_space(self.ybr_full, 'YBR_FULL', 'RGB')
