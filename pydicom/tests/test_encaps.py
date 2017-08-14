# Copyright 2008-2017 pydicom authors. See LICENSE file for details.
"""Test for encaps.py"""

import pytest

from pydicom.encaps import (get_pixel_data_fragments, get_frame_offsets,
                            get_pixel_data_frames)
from pydicom.filebase import DicomBytesIO


class TestGetPixelDataFragments(object):
    """Test encaps.get_pixel_data_fragments"""
    pass


class TestGetFrameOffsets(object):
    """Test encaps.get_frame_offsets"""
    def test_bad_tag(self):
        """Test raises exception if no item tag."""
        # (fffe,e100)
        bytestream = b'\xFE\xFF\x00\xE1' \
                     b'\x08\x00\x00\x00' \
                     b'\x01\x02\x03\x04\x05\x06\x07\x08'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        pytest.raises(ValueError, get_frame_offsets, fp)

    def test_bad_length(self):
        """Test raises exception if the item length is not a multiple of 4."""
        # Length 10
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x0A\x00\x00\x00' \
                     b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        pytest.raises(ValueError, get_frame_offsets, fp)

    def test_zero_length(self):
        """Test reading BOT with zero length"""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x00\x00\x00\x00'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert [] == get_frame_offsets(fp)

    def test_multi_frame(self):
        """Test reading multi-frame BOT item"""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x10\x00\x00\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\x66\x13\x00\x00' \
                     b'\xF4\x25\x00\x00' \
                     b'\xFE\x37\x00\x00'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert [0, 4966, 9716, 14334] == get_frame_offsets(fp)

    def test_single_frame(self):
        """Test reading single-frame BOT item"""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x00\x00\x00\x00'  # Offset 1: 0
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert [0] == get_frame_offsets(fp)


class TestGetPixelDataFrames(object):
    """Test encaps.get_pixel_data_frames"""
    pass
