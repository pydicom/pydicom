# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Benchmarks for the encaps module."""
import pytest

from pydicom import dcmread
from pydicom.encaps import (
    fragment_frame,
    itemise_frame,
    encapsulate,
    decode_data_sequence
)


class TimeFragmentFrame:
    """Time tests for the encaps.fragment_frame function."""
    @pytest.fixture(autouse=True)
    def setup(self, emri_jpeg_2k_lossless_name):
        """Setup the test"""
        ds = dcmread(emri_jpeg_2k_lossless_name)
        self.test_data = decode_data_sequence(ds.PixelData)
        assert len(self.test_data) == 10
        self.no_runs = 1000

    def time_fragment_single(self):
        """Time fragmenting each frame into 1 fragment."""
        for ii in range(self.no_runs):
            for fragment in fragment_frame(self.test_data[0], 1):
                pass

    def time_fragment_ten(self):
        """Time fragmenting each frame into 10 fragments."""
        for ii in range(self.no_runs):
            for fragment in fragment_frame(self.test_data[0], 10):
                pass


class TimeItemiseFrame:
    """Time tests for the encaps.itemise_frame function."""
    @pytest.fixture(autouse=True)
    def setup(self, emri_jpeg_2k_lossless_name):
        """Setup the test"""
        ds = dcmread(emri_jpeg_2k_lossless_name)
        self.test_data = decode_data_sequence(ds.PixelData)
        assert len(self.test_data) == 10
        self.no_runs = 1000

    def time_itemise_single(self):
        """Time itemising a frame into 1 fragment."""
        for ii in range(self.no_runs):
            for item in itemise_frame(self.test_data[0], 1):
                pass

    def time_itemise_ten(self):
        """Time itemising a frame into 10 fragments."""
        for ii in range(self.no_runs):
            for item in itemise_frame(self.test_data[0], 10):
                pass


class TimeEncapsulate:
    """Time tests for the encaps.encapsulate function."""
    @pytest.fixture(autouse=True)
    def setup(self, emri_jpeg_2k_lossless_name):
        """Setup the test"""
        ds = dcmread(emri_jpeg_2k_lossless_name)
        self.test_data = decode_data_sequence(ds.PixelData)
        assert len(self.test_data) == 10
        self.no_runs = 1000

    def time_encapsulate_single_bot(self):
        """Time encapsulating frames with 1 fragment per frame."""
        for ii in range(self.no_runs):
            encapsulate(self.test_data, 1, has_bot=True)

    def time_encapsulate_ten_bot(self):
        """Time encapsulating frames with 10 fragments per frame."""
        for ii in range(self.no_runs):
            encapsulate(self.test_data, 10, has_bot=True)

    def time_encapsulate_single_nobot(self):
        """Time encapsulating frames with 1 fragment per frame."""
        for ii in range(self.no_runs):
            encapsulate(self.test_data, 1, has_bot=False)

    def time_encapsulate_ten_nobot(self):
        """Time encapsulating frames with 10 fragments per frame."""
        for ii in range(self.no_runs):
            encapsulate(self.test_data, 10, has_bot=False)
