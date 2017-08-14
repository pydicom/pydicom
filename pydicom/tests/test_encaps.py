# Copyright 2008-2017 pydicom authors. See LICENSE file for details.
"""Test for encaps.py"""

import pytest

from pydicom.encaps import (get_pixel_data_fragments, get_frame_offsets,
                            get_pixel_data_frames)
from pydicom.filebase import DicomBytesIO


def assert_raises_regex(type_error, message, func, *args, **kwargs):
    """Taken from https://github.com/glemaitre/specio, BSD 3 license."""
    with pytest.raises(type_error) as excinfo:
        func(*args, **kwargs)
    excinfo.match(message)


class TestGetPixelDataFragments(object):
    """Test encaps.get_pixel_data_fragments"""
    def test_item_undefined_length(self):
        """Test exception raised if item length undefined."""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\xFF\xFF\xFF\xFF' \
                     b'\x00\x00\x00\x01'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert_raises_regex(ValueError,
                            "Undefined item length at offset 4 when "
                            "parsing the encapsulated pixel data "
                            "fragments.",
                            get_pixel_data_fragments, fp)

    def test_item_sequence_delimiter(self):
        """Test that the fragments are returned if seq delimiter hit."""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\xFE\xFF\xDD\xE0' \
                     b'\x00\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x02\x00\x00\x00'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        fragments = get_pixel_data_fragments(fp)
        assert fragments == [b'\x01\x00\x00\x00']

    def test_item_bad_tag(self):
        """Test exception raised if item has unexpected tag"""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\x10\x00\x10\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x02\x00\x00\x00'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        with pytest.raises(ValueError) as excinfo:
            get_pixel_data_fragments(fp)
        # For some reason matching the messages fails using assert_raises_regex
        # It looks like the conversion of the tag to str is the issue
        assert str(excinfo.value) == ("Unexpected tag '(0010, 0010)' at "
                                      "offset 12 when parsing the "
                                      "encapsulated pixel data fragment "
                                      "items.")

    def test_single_fragment_no_delimiter(self):
        """Test single fragment is returned OK"""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        fragments = get_pixel_data_fragments(fp)
        assert fragments == [b'\x01\x00\x00\x00']

    def test_multi_fragments_no_delimiter(self):
        """Test multi fragments are returned OK"""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x06\x00\x00\x00' \
                     b'\x01\x02\x03\x04\x05\x06'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        fragments = get_pixel_data_fragments(fp)
        assert fragments == [b'\x01\x00\x00\x00', b'\x01\x02\x03\x04\x05\x06']

    def test_single_fragment_delimiter(self):
        """Test single fragment is returned OK with sequence delimiter item"""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\xFE\xFF\xDD\xE0'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        fragments = get_pixel_data_fragments(fp)
        assert fragments == [b'\x01\x00\x00\x00']

    def test_multi_fragments_delimiter(self):
        """Test multi fragments are returned OK with sequence delimiter item"""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x06\x00\x00\x00' \
                     b'\x01\x02\x03\x04\x05\x06' \
                     b'\xFE\xFF\xDD\xE0'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        fragments = get_pixel_data_fragments(fp)
        assert fragments == [b'\x01\x00\x00\x00', b'\x01\x02\x03\x04\x05\x06']


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
        # For some reason matching the messages fails using assert_raises_regex
        # It looks like the conversion of the tag to str is the issue
        with pytest.raises(ValueError) as excinfo:
            get_frame_offsets(fp)
        assert str(excinfo.value) == ("Unexpected tag '(fffe, e100)' when "
                                      "parsing the Basic Table Offset item.")

    def test_bad_length_multiple(self):
        """Test raises exception if the item length is not a multiple of 4."""
        # Length 10
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x0A\x00\x00\x00' \
                     b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert_raises_regex(ValueError,
                            "The length of the Basic Offset Table item is not "
                            "a multiple of 4.",
                            get_frame_offsets, fp)

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
                     b'\x00\x00\x00\x00'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert [0] == get_frame_offsets(fp)


class TestGetPixelDataFrames(object):
    """Test encaps.get_pixel_data_frames"""
    def test_no_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragments"""
        pass

    def test_no_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        pass

    def test_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragment"""
        pass

    def test_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        pass

    def test_multi_frame_one_to_one(self):
        """Test a multi-frame image where each frame is one fragment"""
        pass

    def test_multi_frame_three_to_one(self):
        """Test a multi-frame image where each frame is three fragments"""
        pass

    def test_multi_frame_varied_ratio(self):
        """Test a multi-frame image where each frames is random fragments"""
        pass


