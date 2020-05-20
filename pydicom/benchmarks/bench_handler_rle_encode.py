# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Encoding benchmarks for the rle_handler module."""

import numpy as np

from pydicom import dcmread
from pydicom.data import get_testdata_files
from pydicom.pixel_data_handlers.rle_handler import (
    rle_encode_frame,
    _rle_encode_segment,
)

# 8/8-bit, 1 sample/pixel, 1 frame
EXPL_8_1_1F = get_testdata_files("OBXXXX1A.dcm")[0]
# 8/8-bit, 3 sample/pixel, 1 frame
EXPL_8_3_1F = get_testdata_files("SC_rgb.dcm")[0]
# 16/16-bit, 1 sample/pixel, 1 frame
EXPL_16_1_1F = get_testdata_files("MR_small.dcm")[0]
# 16/16-bit, 3 sample/pixel, 1 frame
EXPL_16_3_1F = get_testdata_files("SC_rgb_16bit.dcm")[0]
# 32/32-bit, 1 sample/pixel, 1 frame
EXPL_32_1_1F = get_testdata_files("rtdose_1frame.dcm")[0]
# 32/32-bit, 3 sample/pixel, 1 frame
EXPL_32_3_1F = get_testdata_files("SC_rgb_32bit.dcm")[0]


class TimeRLEEncodeSegment:
    """Time tests for rle_handler._rle_encode_segment."""
    def setup(self):
        ds = dcmread(EXPL_8_1_1F)
        self.arr = ds.pixel_array

        self.no_runs = 100

    def time_encode(self):
        """Time encoding a full segment."""
        # Re-encode the decoded data
        for ii in range(self.no_runs):
            _rle_encode_segment(self.arr)


class TimeRLEEncodeFrame:
    """Time tests for rle_handler.rle_encode_frame."""
    def setup(self):
        ds = dcmread(EXPL_8_1_1F)
        self.arr8_1 = ds.pixel_array
        ds = dcmread(EXPL_8_3_1F)
        self.arr8_3 = ds.pixel_array
        ds = dcmread(EXPL_16_1_1F)
        self.arr16_1 = ds.pixel_array
        ds = dcmread(EXPL_16_3_1F)
        self.arr16_3 = ds.pixel_array
        ds = dcmread(EXPL_32_1_1F)
        self.arr32_1 = ds.pixel_array
        ds = dcmread(EXPL_32_3_1F)
        self.arr32_3 = ds.pixel_array

        self.no_runs = 100

    def time_08_1(self):
        """Time encoding 8 bit 1 sample/pixel."""
        for ii in range(self.no_runs):
            rle_encode_frame(self.arr8_1)

    def time_08_3(self):
        """Time encoding 8 bit 3 sample/pixel."""
        for ii in range(self.no_runs):
            rle_encode_frame(self.arr8_3)

    def time_16_1(self):
        """Time encoding 16 bit 1 sample/pixel."""
        for ii in range(self.no_runs):
            rle_encode_frame(self.arr16_1)

    def time_16_3(self):
        """Time encoding 16 bit 3 sample/pixel."""
        for ii in range(self.no_runs):
            rle_encode_frame(self.arr16_3)

    def time_32_1(self):
        """Time encoding 32 bit 1 sample/pixel."""
        for ii in range(self.no_runs):
            rle_encode_frame(self.arr32_1)

    def time_32_3(self):
        """Time encoding 32 bit 3 sample/pixel."""
        for ii in range(self.no_runs):
            rle_encode_frame(self.arr32_3)
