# Copyright 2008-2017 pydicom authors. See LICENSE file for details.
"""Test for encaps.py"""

import pytest

from pydicom.encaps import (generate_pixel_data_fragment, get_frame_offsets,
                            generate_pixel_data_frame, generate_pixel_data,
                            decode_data_sequence, defragment_data, read_item)
from pydicom.filebase import DicomBytesIO


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
        with pytest.raises(ValueError,
                           match="Unexpected tag '\(fffe, e100\)' when "
                                 "parsing the Basic Table Offset item."):
            get_frame_offsets(fp)

    def test_bad_length_multiple(self):
        """Test raises exception if the item length is not a multiple of 4."""
        # Length 10
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x0A\x00\x00\x00' \
                     b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        with pytest.raises(ValueError,
                           match="The length of the Basic Offset Table item"
                                 " is not a multiple of 4."):
            get_frame_offsets(fp)

    def test_zero_length(self):
        """Test reading BOT with zero length"""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x00\x00\x00\x00'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert [0] == get_frame_offsets(fp)

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

    def test_not_little_endian(self):
        """Test reading big endian raises exception"""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x00\x00\x00\x00'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = False
        with pytest.raises(ValueError,
                           match="'fp.is_little_endian' must be True"):
            get_frame_offsets(fp)


class TestGeneratePixelDataFragment(object):
    """Test encaps.generate_pixel_data_fragment"""
    def test_item_undefined_length(self):
        """Test exception raised if item length undefined."""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\xFF\xFF\xFF\xFF' \
                     b'\x00\x00\x00\x01'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        fragments = generate_pixel_data_fragment(fp)
        with pytest.raises(ValueError,
                           match="Undefined item length at offset 4 when "
                                 "parsing the encapsulated pixel data "
                                 "fragments."):
            next(fragments)
        pytest.raises(StopIteration, next, fragments)

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
        fragments = generate_pixel_data_fragment(fp)
        assert next(fragments) == b'\x01\x00\x00\x00'
        pytest.raises(StopIteration, next, fragments)

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
        fragments = generate_pixel_data_fragment(fp)
        assert next(fragments) == b'\x01\x00\x00\x00'
        with pytest.raises(ValueError,
                           match="Unexpected tag '\(0010, 0010\)' at offset "
                                 "12 when parsing the encapsulated pixel data "
                                 "fragment items."):
            next(fragments)
        pytest.raises(StopIteration, next, fragments)

    def test_single_fragment_no_delimiter(self):
        """Test single fragment is returned OK"""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        fragments = generate_pixel_data_fragment(fp)
        assert next(fragments) == b'\x01\x00\x00\x00'
        pytest.raises(StopIteration, next, fragments)

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
        fragments = generate_pixel_data_fragment(fp)
        assert next(fragments) == b'\x01\x00\x00\x00'
        assert next(fragments) == b'\x01\x02\x03\x04\x05\x06'
        pytest.raises(StopIteration, next, fragments)

    def test_single_fragment_delimiter(self):
        """Test single fragment is returned OK with sequence delimiter item"""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\xFE\xFF\xDD\xE0'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        fragments = generate_pixel_data_fragment(fp)
        assert next(fragments) == b'\x01\x00\x00\x00'
        pytest.raises(StopIteration, next, fragments)

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
        fragments = generate_pixel_data_fragment(fp)
        assert next(fragments) == b'\x01\x00\x00\x00'
        assert next(fragments) == b'\x01\x02\x03\x04\x05\x06'
        pytest.raises(StopIteration, next, fragments)

    def test_not_little_endian(self):
        """Test reading big endian raises exception"""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = False
        fragments = generate_pixel_data_fragment(fp)
        with pytest.raises(ValueError,
                           match="'fp.is_little_endian' must be True"):
            next(fragments)
        pytest.raises(StopIteration, next, fragments)


class TestGeneratePixelDataFrames(object):
    """Test encaps.generate_pixel_data_frames"""
    def test_empty_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragments"""
        # 1 frame, 1 fragment long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x00\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00'
        frames = generate_pixel_data_frame(bytestream)
        assert next(frames) == b'\x01\x00\x00\x00'
        pytest.raises(StopIteration, next, frames)

    def test_empty_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x00\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x03\x00\x00\x00'
        frames = generate_pixel_data_frame(bytestream)
        assert next(frames) == (
            b'\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00'
        )
        pytest.raises(StopIteration, next, frames)

    def test_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragment"""
        # 1 frame, 1 fragment long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00'
        frames = generate_pixel_data_frame(bytestream)
        assert next(frames) == b'\x01\x00\x00\x00'
        pytest.raises(StopIteration, next, frames)

    def test_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x03\x00\x00\x00'
        frames = generate_pixel_data_frame(bytestream)
        assert next(frames) == (
            b'\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00'
        )
        pytest.raises(StopIteration, next, frames)

    def test_multi_frame_one_to_one(self):
        """Test a multi-frame image where each frame is one fragment"""
        # 3 frames, each 1 fragment long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x0C\x00\x00\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\x0C\x00\x00\x00' \
                     b'\x18\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x03\x00\x00\x00'
        frames = generate_pixel_data_frame(bytestream)
        assert next(frames) == b'\x01\x00\x00\x00'
        assert next(frames) == b'\x02\x00\x00\x00'
        assert next(frames) == b'\x03\x00\x00\x00'
        pytest.raises(StopIteration, next, frames)

    def test_multi_frame_three_to_one(self):
        """Test a multi-frame image where each frame is three fragments"""
        # 2 frames, each 3 fragments long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x0C\x00\x00\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\x20\x00\x00\x00' \
                     b'\x40\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00'
        frames = generate_pixel_data_frame(bytestream)
        assert next(frames) == (
            b'\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00'
        )
        assert next(frames) == (
            b'\x02\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00'
        )
        assert next(frames) == (
            b'\x03\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00'
        )
        pytest.raises(StopIteration, next, frames)

    def test_multi_frame_varied_ratio(self):
        """Test a multi-frame image where each frames is random fragments"""
        # 3 frames, 1st is 1 fragment, 2nd is 3 fragments, 3rd is 2 fragments
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x0C\x00\x00\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\x0E\x00\x00\x00' \
                     b'\x32\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x06\x00\x00\x00\x01\x00\x00\x00\x00\x01' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x02\x00\x00\x00\x02\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x06\x00\x00\x00\x03\x00\x00\x00\x00\x02' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00\x03\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x02\x00\x00\x00\x02\x04'
        frames = generate_pixel_data_frame(bytestream)
        assert next(frames) == b'\x01\x00\x00\x00\x00\x01'
        assert next(frames) == (
            b'\x02\x00\x02\x00\x00\x00\x03\x00\x00\x00\x00\x02'
        )
        assert next(frames) == b'\x03\x00\x00\x00\x02\x04'
        pytest.raises(StopIteration, next, frames)


class TestGeneratePixelData(object):
    """Test encaps.generate_pixel_data"""
    def test_empty_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragments"""
        # 1 frame, 1 fragment long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x00\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00'
        frames = generate_pixel_data(bytestream)
        assert next(frames) == (b'\x01\x00\x00\x00', )
        pytest.raises(StopIteration, next, frames)

    def test_empty_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x00\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x03\x00\x00\x00'
        frames = generate_pixel_data(bytestream)
        assert next(frames) == (b'\x01\x00\x00\x00',
                                b'\x02\x00\x00\x00',
                                b'\x03\x00\x00\x00')
        pytest.raises(StopIteration, next, frames)

    def test_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragment"""
        # 1 frame, 1 fragment long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00'
        frames = generate_pixel_data(bytestream)
        assert next(frames) == (b'\x01\x00\x00\x00', )
        pytest.raises(StopIteration, next, frames)

    def test_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x03\x00\x00\x00'
        frames = generate_pixel_data(bytestream)
        assert next(frames) == (b'\x01\x00\x00\x00',
                                b'\x02\x00\x00\x00',
                                b'\x03\x00\x00\x00')
        pytest.raises(StopIteration, next, frames)

    def test_multi_frame_one_to_one(self):
        """Test a multi-frame image where each frame is one fragment"""
        # 3 frames, each 1 fragment long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x0C\x00\x00\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\x0C\x00\x00\x00' \
                     b'\x18\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x03\x00\x00\x00'
        frames = generate_pixel_data(bytestream)
        assert next(frames) == (b'\x01\x00\x00\x00', )
        assert next(frames) == (b'\x02\x00\x00\x00', )
        assert next(frames) == (b'\x03\x00\x00\x00', )
        pytest.raises(StopIteration, next, frames)

    def test_multi_frame_three_to_one(self):
        """Test a multi-frame image where each frame is three fragments"""
        # 2 frames, each 3 fragments long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x0C\x00\x00\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\x20\x00\x00\x00' \
                     b'\x40\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00'
        frames = generate_pixel_data(bytestream)
        assert next(frames) == (b'\x01\x00\x00\x00',
                                b'\x02\x00\x00\x00',
                                b'\x03\x00\x00\x00')
        assert next(frames) == (b'\x02\x00\x00\x00',
                                b'\x02\x00\x00\x00',
                                b'\x03\x00\x00\x00')
        assert next(frames) == (b'\x03\x00\x00\x00',
                                b'\x02\x00\x00\x00',
                                b'\x03\x00\x00\x00')
        pytest.raises(StopIteration, next, frames)

    def test_multi_frame_varied_ratio(self):
        """Test a multi-frame image where each frames is random fragments"""
        # 3 frames, 1st is 1 fragment, 2nd is 3 fragments, 3rd is 2 fragments
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x0C\x00\x00\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\x0E\x00\x00\x00' \
                     b'\x32\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x06\x00\x00\x00\x01\x00\x00\x00\x00\x01' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x02\x00\x00\x00\x02\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x06\x00\x00\x00\x03\x00\x00\x00\x00\x02' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00\x03\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x02\x00\x00\x00\x02\x04'
        frames = generate_pixel_data(bytestream)
        assert next(frames) == (b'\x01\x00\x00\x00\x00\x01', )
        assert next(frames) == (b'\x02\x00', b'\x02\x00\x00\x00',
                                b'\x03\x00\x00\x00\x00\x02')
        assert next(frames) == (b'\x03\x00\x00\x00', b'\x02\x04')
        pytest.raises(StopIteration, next, frames)


class TestDecodeDataSequence(object):
    """Test encaps.decode_data_sequence"""
    def test_empty_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragments"""
        # 1 frame, 1 fragment long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x00\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00'
        frames = decode_data_sequence(bytestream)
        assert frames == [b'\x01\x00\x00\x00']

    def test_empty_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x00\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x03\x00\x00\x00'
        frames = decode_data_sequence(bytestream)
        assert frames == [b'\x01\x00\x00\x00',
                          b'\x02\x00\x00\x00',
                          b'\x03\x00\x00\x00']

    def test_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragment"""
        # 1 frame, 1 fragment long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00'
        frames = decode_data_sequence(bytestream)
        assert frames == [b'\x01\x00\x00\x00']

    def test_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x03\x00\x00\x00'
        frames = decode_data_sequence(bytestream)
        assert frames == [b'\x01\x00\x00\x00',
                          b'\x02\x00\x00\x00',
                          b'\x03\x00\x00\x00']

    def test_multi_frame_one_to_one(self):
        """Test a multi-frame image where each frame is one fragment"""
        # 3 frames, each 1 fragment long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x0C\x00\x00\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\x0C\x00\x00\x00' \
                     b'\x18\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x03\x00\x00\x00'
        frames = decode_data_sequence(bytestream)
        assert frames == [b'\x01\x00\x00\x00',
                          b'\x02\x00\x00\x00',
                          b'\x03\x00\x00\x00']

    def test_multi_frame_three_to_one(self):
        """Test a multi-frame image where each frame is three fragments"""
        # 2 frames, each 3 fragments long
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x0C\x00\x00\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\x20\x00\x00\x00' \
                     b'\x40\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00'
        frames = decode_data_sequence(bytestream)
        assert frames == [
            b'\x01\x00\x00\x00', b'\x02\x00\x00\x00', b'\x03\x00\x00\x00',
            b'\x02\x00\x00\x00', b'\x02\x00\x00\x00', b'\x03\x00\x00\x00',
            b'\x03\x00\x00\x00', b'\x02\x00\x00\x00', b'\x03\x00\x00\x00'
        ]

    def test_multi_frame_varied_ratio(self):
        """Test a multi-frame image where each frames is random fragments"""
        # 3 frames, 1st is 1 fragment, 2nd is 3 fragments, 3rd is 2 fragments
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x0C\x00\x00\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\x0E\x00\x00\x00' \
                     b'\x32\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x06\x00\x00\x00\x01\x00\x00\x00\x00\x01' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x02\x00\x00\x00\x02\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x06\x00\x00\x00\x03\x00\x00\x00\x00\x02' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00\x03\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x02\x00\x00\x00\x02\x04'
        frames = decode_data_sequence(bytestream)
        assert frames == [
            b'\x01\x00\x00\x00\x00\x01', b'\x02\x00', b'\x02\x00\x00\x00',
            b'\x03\x00\x00\x00\x00\x02', b'\x03\x00\x00\x00', b'\x02\x04'
        ]


class TestDefragmentData(object):
    """Test encaps.defragment_data"""
    def test_defragment(self):
        """Test joining fragmented data works"""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x00\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x02\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x03\x00\x00\x00'
        reference = b'\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00'
        assert defragment_data(bytestream) == reference


class TestReadItem(object):
    """Test encaps.read_item"""
    def test_item_undefined_length(self):
        """Test exception raised if item length undefined."""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\xFF\xFF\xFF\xFF' \
                     b'\x00\x00\x00\x01'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        with pytest.raises(ValueError,
                           match="Encapsulated data fragment had Undefined "
                                 "Length at data position 0x4"):
            read_item(fp)

    def test_item_sequence_delimiter(self):
        """Test non-zero length seq delimiter reads correctly."""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\xFE\xFF\xDD\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x02\x00\x00\x00'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert read_item(fp) == b'\x01\x00\x00\x00'
        assert read_item(fp) is None
        assert read_item(fp) == b'\x02\x00\x00\x00'

    def test_item_sequence_delimiter_zero_length(self):
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
        assert read_item(fp) == b'\x01\x00\x00\x00'
        assert read_item(fp) is None
        assert read_item(fp) == b'\x02\x00\x00\x00'

    def test_item_bad_tag(self):
        """Test item is read if it has an unexpected tag"""
        # This should raise an exception instead
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\x10\x00\x10\x00' \
                     b'\x04\x00\x00\x00' \
                     b'\xFF\x00\xFF\x00' \
                     b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x02\x00\x00\x00'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert read_item(fp) == b'\x01\x00\x00\x00'
        assert read_item(fp) == b'\xFF\x00\xFF\x00'
        assert read_item(fp) == b'\x02\x00\x00\x00'

    def test_single_fragment_no_delimiter(self):
        """Test single fragment is returned OK"""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert read_item(fp) == b'\x01\x00\x00\x00'

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
        assert read_item(fp) == b'\x01\x00\x00\x00'
        assert read_item(fp) == b'\x01\x02\x03\x04\x05\x06'

    def test_single_fragment_delimiter(self):
        """Test single fragment is returned OK with sequence delimiter item"""
        bytestream = b'\xFE\xFF\x00\xE0' \
                     b'\x04\x00\x00\x00' \
                     b'\x01\x00\x00\x00' \
                     b'\xFE\xFF\xDD\xE0'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert read_item(fp) == b'\x01\x00\x00\x00'

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
        assert read_item(fp) == b'\x01\x00\x00\x00'
        assert read_item(fp) == b'\x01\x02\x03\x04\x05\x06'
