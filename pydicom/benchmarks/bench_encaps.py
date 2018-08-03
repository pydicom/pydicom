# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Benchmarks for the encaps module."""

from pydicom import dcmread
from pydicom.data import get_testdata_files
from pydicom.encaps import (
    fragment_frame,
    itemise_frame,
    encapsulate,
    decode_data_sequence
)
from pydicom.filebase import DicomBytesIO


JP2K_10FRAME = get_testdata_files('emri_small_jpeg_2k_lossless.dcm')[0]


class TimeFragmentFrame(object):
    def setup(self):
        """Setup the test"""
        ds = dcmread(JP2K_10FRAME)
        self.test_data = decode_data_sequence(ds.PixelData)
        assert len(self.test_data) == 10
        self.no_runs = 1000

    def time_fragment_single(self):
        """Time fragmenting each frame into a single fragment."""
        for ii in range(self.no_runs):
            fragment_frame(self.test_data[0], 1)

    def time_fragment_double(self):
        """Time fragmenting each frame into two fragments."""
        for ii in range(self.no_runs):
            fragment_frame(self.test_data[0], 2)

    def time_fragment_triple(self):
        """Time fragmenting each frame into three fragments."""
        for ii in range(self.no_runs):
            fragment_frame(self.test_data[0], 3)

    def time_fragment_ten(self):
        """Time fragmenting each frame into ten fragments."""
        for ii in range(self.no_runs):
            fragment_frame(self.test_data[0], 80)


class TimeItemiseFrame(object):
    def setup(self):
        """Setup the test"""
        ds = dcmread(JP2K_10FRAME)
        self.test_data = decode_data_sequence(ds.PixelData)
        assert len(self.test_data) == 10
        self.no_runs = 1000

    def time_itemise_single(self):
        """Time itemising a frame into a single fragment."""
        for ii in range(self.no_runs):
            for item in itemise_frame(self.test_data[0], 1):
                pass

    def time_itemise_double(self):
        """Time itemising a frame into two fragments."""
        for ii in range(self.no_runs):
            for item in itemise_frame(self.test_data[0], 2):
                pass

    def time_itemise_triple(self):
        """Time itemising a frame into three fragments."""
        for ii in range(self.no_runs):
            for item in itemise_frame(self.test_data[0], 3):
                pass


class TimeEncapsulate(object):
    def setup(self):
        """Setup the test"""
        ds = dcmread(JP2K_10FRAME)
        self.test_data = decode_data_sequence(ds.PixelData)
        assert len(self.test_data) == 10
        self.no_runs = 1000

    def time_encapsulate_single_bot(self):
        """Time encapsulating frames with a single fragment per frame."""
        for ii in range(self.no_runs):
            encapsulate(self.test_data, 1, has_bot=True)

    def time_encapsulate_double_bot(self):
        """Time encapsulating frames with two fragments per frame."""
        for ii in range(self.no_runs):
            encapsulate(self.test_data, 2, has_bot=True)

    def time_encapsulate_triple_bot(self):
        """Time encapsulating frames with three fragments per frame."""
        for ii in range(self.no_runs):
            encapsulate(self.test_data, 3, has_bot=True)

    def time_encapsulate_single_nobot(self):
        """Time encapsulating frames with a single fragment per frame."""
        for ii in range(self.no_runs):
            encapsulate(self.test_data, 1, has_bot=False)

    def time_encapsulate_double_nobot(self):
        """Time encapsulating frames with two fragments per frame."""
        for ii in range(self.no_runs):
            encapsulate(self.test_data, 2, has_bot=False)

    def time_encapsulate_triple_nobot(self):
        """Time encapsulating frames with three fragments per frame."""
        for ii in range(self.no_runs):
            encapsulate(self.test_data, 3, has_bot=False)
