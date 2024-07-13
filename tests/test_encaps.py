# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Test for encaps.py"""

from io import BytesIO
import mmap
from struct import unpack
import tempfile

import pytest

from pydicom import dcmread, config, encaps
from pydicom.data import get_testdata_file
from pydicom.encaps import (
    fragment_frame,
    itemize_frame,
    encapsulate,
    encapsulate_extended,
    parse_basic_offsets,
    parse_fragments,
    generate_fragments,
    generate_fragmented_frames,
    generate_frames,
    get_frame,
    _BufferedItem,
    EncapsulatedBuffer,
    encapsulate_buffer,
    encapsulate_extended_buffer,
)
from pydicom.filebase import DicomBytesIO
from pydicom.fileutil import read_buffer


JP2K_10FRAME_NOBOT = get_testdata_file("emri_small_jpeg_2k_lossless.dcm")


class TestGetFrameOffsets:
    """Test encaps.get_frame_offsets"""

    def setup_method(self):
        with pytest.warns(DeprecationWarning):
            self.func = encaps.get_frame_offsets

    def test_bad_tag(self):
        """Test raises exception if no item tag."""
        # (FFFE,E100)
        bytestream = b"\xFE\xFF\x00\xE1\x08\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08"
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        with pytest.raises(
            ValueError,
            match=r"Unexpected tag '\(FFFE,E100\)' when "
            r"parsing the Basic Offset Table item",
        ):
            self.func(fp)

    def test_bad_length_multiple(self):
        """Test raises exception if the item length is not a multiple of 4."""
        # Length 10
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x0A\x00\x00\x00"
            b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        with pytest.raises(
            ValueError,
            match="The length of the Basic Offset Table item is not a multiple of 4",
        ):
            self.func(fp)

    def test_zero_length(self):
        """Test reading BOT with zero length"""
        bytestream = b"\xFE\xFF\x00\xE0\x00\x00\x00\x00"
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert (False, [0]) == self.func(fp)

    def test_multi_frame(self):
        """Test reading multi-frame BOT item"""
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x10\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x66\x13\x00\x00"
            b"\xF4\x25\x00\x00"
            b"\xFE\x37\x00\x00"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert (True, [0, 4966, 9716, 14334]) == self.func(fp)

    def test_single_frame(self):
        """Test reading single-frame BOT item"""
        bytestream = b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x00\x00\x00\x00"
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert (True, [0]) == self.func(fp)

    def test_not_little_endian(self):
        """Test reading big endian raises exception"""
        bytestream = b"\xFE\xFF\x00\xE0\x00\x00\x00\x00"
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = False
        with pytest.raises(ValueError, match="'fp.is_little_endian' must be True"):
            self.func(fp)


class TestGetNrFragments:
    """Test encaps.get_nr_fragments"""

    def setup_method(self):
        with pytest.warns(DeprecationWarning):
            self.func = encaps.get_nr_fragments

    def test_item_undefined_length(self):
        """Test exception raised if item length undefined."""
        bytestream = b"\xFE\xFF\x00\xE0\xFF\xFF\xFF\xFF\x00\x00\x00\x01"
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        with pytest.raises(ValueError):
            self.func(fp)

    def test_item_sequence_delimiter(self):
        """Test that the fragments are returned if seq delimiter hit."""
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\xDD\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert 1 == self.func(fp)

    def test_item_bad_tag(self):
        """Test exception raised if item has unexpected tag"""
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\x10\x00\x10\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        msg = (
            r"Unexpected tag '\(0010,0010\)' at offset 12 when parsing the "
            r"encapsulated pixel data fragment items"
        )
        with pytest.raises(ValueError, match=msg):
            self.func(fp)

    def test_single_fragment_no_delimiter(self):
        """Test single fragment is returned OK"""
        bytestream = b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert 1 == self.func(fp)

    def test_multi_fragments_no_delimiter(self):
        """Test multi fragments are returned OK"""
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00"
            b"\x01\x02\x03\x04\x05\x06"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert 2 == self.func(fp)

    def test_single_fragment_delimiter(self):
        """Test single fragment is returned OK with sequence delimiter item"""
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\xDD\xE0"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert 1 == self.func(fp)

    def test_multi_fragments_delimiter(self):
        """Test multi fragments are returned OK with sequence delimiter item"""
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00"
            b"\x01\x02\x03\x04\x05\x06"
            b"\xFE\xFF\xDD\xE0"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert 2 == self.func(fp)

    def test_not_little_endian(self):
        """Test reading big endian raises exception"""
        bytestream = b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = False
        with pytest.raises(ValueError, match="'fp.is_little_endian' must be True"):
            self.func(fp)


class TestGeneratePixelDataFragment:
    """Test encaps.generate_pixel_data_fragment"""

    def setup_method(self):
        with pytest.warns(DeprecationWarning):
            self.func = encaps.generate_pixel_data_fragment

    def test_item_undefined_length(self):
        """Test exception raised if item length undefined."""
        bytestream = b"\xFE\xFF\x00\xE0\xFF\xFF\xFF\xFF\x00\x00\x00\x01"
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        fragments = self.func(fp)
        with pytest.raises(
            ValueError,
            match="Undefined item length at offset 4 when "
            "parsing the encapsulated pixel data "
            "fragments",
        ):
            next(fragments)
        pytest.raises(StopIteration, next, fragments)

    def test_item_sequence_delimiter(self):
        """Test that the fragments are returned if seq delimiter hit."""
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\xDD\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        fragments = self.func(fp)
        assert next(fragments) == b"\x01\x00\x00\x00"
        pytest.raises(StopIteration, next, fragments)

    def test_item_bad_tag(self):
        """Test exception raised if item has unexpected tag"""
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\x10\x00\x10\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        fragments = self.func(fp)
        assert next(fragments) == b"\x01\x00\x00\x00"
        with pytest.raises(
            ValueError,
            match=r"Unexpected tag '\(0010,0010\)' at offset "
            r"12 when parsing the encapsulated pixel "
            r"data fragment items",
        ):
            next(fragments)
        pytest.raises(StopIteration, next, fragments)

    def test_single_fragment_no_delimiter(self):
        """Test single fragment is returned OK"""
        bytestream = b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        fragments = self.func(fp)
        assert next(fragments) == b"\x01\x00\x00\x00"
        pytest.raises(StopIteration, next, fragments)

    def test_multi_fragments_no_delimiter(self):
        """Test multi fragments are returned OK"""
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00"
            b"\x01\x02\x03\x04\x05\x06"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        fragments = self.func(fp)
        assert next(fragments) == b"\x01\x00\x00\x00"
        assert next(fragments) == b"\x01\x02\x03\x04\x05\x06"
        pytest.raises(StopIteration, next, fragments)

    def test_single_fragment_delimiter(self):
        """Test single fragment is returned OK with sequence delimiter item"""
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\xDD\xE0"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        fragments = self.func(fp)
        assert next(fragments) == b"\x01\x00\x00\x00"
        pytest.raises(StopIteration, next, fragments)

    def test_multi_fragments_delimiter(self):
        """Test multi fragments are returned OK with sequence delimiter item"""
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00"
            b"\x01\x02\x03\x04\x05\x06"
            b"\xFE\xFF\xDD\xE0"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        fragments = self.func(fp)
        assert next(fragments) == b"\x01\x00\x00\x00"
        assert next(fragments) == b"\x01\x02\x03\x04\x05\x06"
        pytest.raises(StopIteration, next, fragments)

    def test_not_little_endian(self):
        """Test reading big endian raises exception"""
        bytestream = b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = False
        fragments = self.func(fp)
        with pytest.raises(ValueError, match="'fp.is_little_endian' must be True"):
            next(fragments)


class TestGeneratePixelDataFrames:
    """Test encaps.generate_pixel_data_frames"""

    def setup_method(self):
        with pytest.warns(DeprecationWarning):
            self.func = encaps.generate_pixel_data_frame

    def test_empty_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragments"""
        # 1 frame, 1 fragment long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
        )
        frames = self.func(bytestream)
        assert next(frames) == b"\x01\x00\x00\x00"
        pytest.raises(StopIteration, next, frames)

    def test_empty_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        frames = self.func(bytestream, 1)
        assert next(frames) == (b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00")
        pytest.raises(StopIteration, next, frames)

    def test_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragment"""
        # 1 frame, 1 fragment long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
        )
        frames = self.func(bytestream)
        assert next(frames) == b"\x01\x00\x00\x00"
        pytest.raises(StopIteration, next, frames)

    def test_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        frames = self.func(bytestream)
        assert next(frames) == (b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00")
        pytest.raises(StopIteration, next, frames)

    def test_multi_frame_one_to_one(self):
        """Test a multi-frame image where each frame is one fragment"""
        # 3 frames, each 1 fragment long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x0C\x00\x00\x00"
            b"\x18\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        frames = self.func(bytestream)
        assert next(frames) == b"\x01\x00\x00\x00"
        assert next(frames) == b"\x02\x00\x00\x00"
        assert next(frames) == b"\x03\x00\x00\x00"
        pytest.raises(StopIteration, next, frames)

    def test_multi_frame_three_to_one(self):
        """Test a multi-frame image where each frame is three fragments"""
        # 2 frames, each 3 fragments long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x24\x00\x00\x00"
            b"\x48\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
        )
        frames = self.func(bytestream)
        assert next(frames) == b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00"
        assert next(frames) == b"\x02\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00"
        assert next(frames) == b"\x03\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00"
        pytest.raises(StopIteration, next, frames)

    def test_multi_frame_varied_ratio(self):
        """Test a multi-frame image where each frames is random fragments"""
        # 3 frames, 1st is 1 fragment, 2nd is 3 fragments, 3rd is 2 fragments
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x0E\x00\x00\x00"
            b"\x32\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00\x01\x00\x00\x00\x00\x01"
            b"\xFE\xFF\x00\xE0"
            b"\x02\x00\x00\x00\x02\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00\x03\x00\x00\x00\x00\x02"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x02\x00\x00\x00\x02\x04"
        )
        frames = self.func(bytestream)
        assert next(frames) == b"\x01\x00\x00\x00\x00\x01"
        assert next(frames) == (b"\x02\x00\x02\x00\x00\x00\x03\x00\x00\x00\x00\x02")
        assert next(frames) == b"\x03\x00\x00\x00\x02\x04"
        pytest.raises(StopIteration, next, frames)

    def test_empty_bot_multi_fragments_per_frame(self):
        """Test multi-frame where multiple frags per frame and no BOT."""
        # Regression test for #685
        ds = dcmread(JP2K_10FRAME_NOBOT)
        assert 10 == ds.NumberOfFrames
        frame_gen = self.func(ds.PixelData, ds.NumberOfFrames)
        for ii in range(10):
            next(frame_gen)

        with pytest.raises(StopIteration):
            next(frame_gen)


class TestGeneratePixelData:
    """Test encaps.generate_pixel_data"""

    def setup_method(self):
        with pytest.warns(DeprecationWarning):
            self.func = encaps.generate_pixel_data

    def test_empty_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragments"""
        # 1 frame, 1 fragment long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
        )
        frames = self.func(bytestream)
        assert next(frames) == (b"\x01\x00\x00\x00",)
        pytest.raises(StopIteration, next, frames)

    def test_empty_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        frames = self.func(bytestream, 1)
        assert next(frames) == (
            b"\x01\x00\x00\x00",
            b"\x02\x00\x00\x00",
            b"\x03\x00\x00\x00",
        )
        pytest.raises(StopIteration, next, frames)

    def test_empty_bot_no_number_of_frames_raises(self):
        """Test parsing raises if not BOT and no number_of_frames."""
        # 1 frame, 3 fragments long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        msg = (
            r"Unable to determine the frame boundaries for the encapsulated "
            r"pixel data as there is no Basic or Extended Offset Table and the "
            r"number of frames has not been supplied"
        )
        with pytest.raises(ValueError, match=msg):
            next(self.func(bytestream))

    def test_empty_bot_too_few_fragments(self):
        """Test parsing with too few fragments."""
        ds = dcmread(JP2K_10FRAME_NOBOT)
        assert 10 == ds.NumberOfFrames

        msg = (
            "Unable to generate frames from the encapsulated pixel data as "
            "there are fewer fragments than frames; the dataset may be corrupt "
            "or the number of frames may be incorrect"
        )
        with pytest.raises(ValueError, match=msg):
            next(self.func(ds.PixelData, 20))

    def test_empty_bot_multi_fragments_per_frame(self):
        """Test parsing with multiple fragments per frame."""
        # 4 frames in 6 fragments with JPEG EOI marker
        bytestream = (
            b"\xFE\xFF\x00\xE0\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\xFF\xD9"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
        )

        frames = self.func(bytestream, 4)
        for ii in range(4):
            next(frames)

        with pytest.raises(StopIteration):
            next(frames)

    def test_empty_bot_no_marker(self):
        """Test parsing not BOT and no final marker with multi fragments."""
        # 4 frames in 6 fragments with JPEG EOI marker (1 missing EOI)
        bytestream = (
            b"\xFE\xFF\x00\xE0\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xFF\xD9"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\x00\x00"
        )

        frames = self.func(bytestream, 4)
        for ii in range(3):
            next(frames)

        msg = (
            "The end of the encapsulated pixel data has been reached but fewer "
            "frames than expected have been found. Please confirm that the "
            "generated frame data is correct"
        )
        with pytest.warns(UserWarning, match=msg):
            next(frames)

        with pytest.raises(StopIteration):
            next(frames)

    def test_empty_bot_missing_marker(self):
        """Test parsing no BOT and missing marker with multi fragments."""
        # 4 frames in 6 fragments with JPEG EOI marker (1 missing EOI)
        bytestream = (
            b"\xFE\xFF\x00\xE0\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xFF\xD9"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
        )

        msg = (
            "The end of the encapsulated pixel data has been reached but "
            "fewer frames than expected have been found"
        )
        with pytest.warns(UserWarning, match=msg):
            for ii, frame in enumerate(self.func(bytestream, 4)):
                pass

        assert 2 == ii

    def test_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragment"""
        # 1 frame, 1 fragment long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
        )
        frames = self.func(bytestream)
        assert next(frames) == (b"\x01\x00\x00\x00",)
        pytest.raises(StopIteration, next, frames)

    def test_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        frames = self.func(bytestream)
        assert next(frames) == (
            b"\x01\x00\x00\x00",
            b"\x02\x00\x00\x00",
            b"\x03\x00\x00\x00",
        )
        pytest.raises(StopIteration, next, frames)

    def test_multi_frame_one_to_one(self):
        """Test a multi-frame image where each frame is one fragment"""
        # 3 frames, each 1 fragment long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x0C\x00\x00\x00"
            b"\x18\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        frames = self.func(bytestream)
        assert next(frames) == (b"\x01\x00\x00\x00",)
        assert next(frames) == (b"\x02\x00\x00\x00",)
        assert next(frames) == (b"\x03\x00\x00\x00",)
        pytest.raises(StopIteration, next, frames)

    def test_multi_frame_three_to_one(self):
        """Test a multi-frame image where each frame is three fragments"""
        # 2 frames, each 3 fragments long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x24\x00\x00\x00"
            b"\x48\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
        )
        frames = self.func(bytestream)
        assert next(frames) == (
            b"\x01\x00\x00\x00",
            b"\x02\x00\x00\x00",
            b"\x03\x00\x00\x00",
        )
        assert next(frames) == (
            b"\x02\x00\x00\x00",
            b"\x02\x00\x00\x00",
            b"\x03\x00\x00\x00",
        )
        assert next(frames) == (
            b"\x03\x00\x00\x00",
            b"\x02\x00\x00\x00",
            b"\x03\x00\x00\x00",
        )
        pytest.raises(StopIteration, next, frames)

    def test_multi_frame_varied_ratio(self):
        """Test a multi-frame image where each frames is random fragments"""
        # 3 frames, 1st is 1 fragment, 2nd is 3 fragments, 3rd is 2 fragments
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x0E\x00\x00\x00"
            b"\x32\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00\x01\x00\x00\x00\x00\x01"
            b"\xFE\xFF\x00\xE0"
            b"\x02\x00\x00\x00\x02\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00\x03\x00\x00\x00\x00\x02"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x02\x00\x00\x00\x02\x04"
        )
        frames = self.func(bytestream)
        assert next(frames) == (b"\x01\x00\x00\x00\x00\x01",)
        assert next(frames) == (
            b"\x02\x00",
            b"\x02\x00\x00\x00",
            b"\x03\x00\x00\x00\x00\x02",
        )
        assert next(frames) == (b"\x03\x00\x00\x00", b"\x02\x04")
        pytest.raises(StopIteration, next, frames)


class TestDecodeDataSequence:
    """Test encaps.decode_data_sequence"""

    def setup_method(self):
        with pytest.warns(DeprecationWarning):
            self.func = encaps.decode_data_sequence

    def test_empty_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragments"""
        # 1 frame, 1 fragment long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
        )
        frames = self.func(bytestream)
        assert frames == [b"\x01\x00\x00\x00"]

    def test_empty_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        frames = self.func(bytestream)
        assert frames == [b"\x01\x00\x00\x00", b"\x02\x00\x00\x00", b"\x03\x00\x00\x00"]

    def test_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragment"""
        # 1 frame, 1 fragment long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
        )
        frames = self.func(bytestream)
        assert frames == [b"\x01\x00\x00\x00"]

    def test_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        frames = self.func(bytestream)
        assert frames == [b"\x01\x00\x00\x00", b"\x02\x00\x00\x00", b"\x03\x00\x00\x00"]

    def test_multi_frame_one_to_one(self):
        """Test a multi-frame image where each frame is one fragment"""
        # 3 frames, each 1 fragment long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x0C\x00\x00\x00"
            b"\x18\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        frames = self.func(bytestream)
        assert frames == [b"\x01\x00\x00\x00", b"\x02\x00\x00\x00", b"\x03\x00\x00\x00"]

    def test_multi_frame_three_to_one(self):
        """Test a multi-frame image where each frame is three fragments"""
        # 2 frames, each 3 fragments long
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x20\x00\x00\x00"
            b"\x40\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
        )
        frames = self.func(bytestream)
        assert frames == [
            b"\x01\x00\x00\x00",
            b"\x02\x00\x00\x00",
            b"\x03\x00\x00\x00",
            b"\x02\x00\x00\x00",
            b"\x02\x00\x00\x00",
            b"\x03\x00\x00\x00",
            b"\x03\x00\x00\x00",
            b"\x02\x00\x00\x00",
            b"\x03\x00\x00\x00",
        ]

    def test_multi_frame_varied_ratio(self):
        """Test a multi-frame image where each frames is random fragments"""
        # 3 frames, 1st is 1 fragment, 2nd is 3 fragments, 3rd is 2 fragments
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x0E\x00\x00\x00"
            b"\x32\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00\x01\x00\x00\x00\x00\x01"
            b"\xFE\xFF\x00\xE0"
            b"\x02\x00\x00\x00\x02\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00\x03\x00\x00\x00\x00\x02"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x02\x00\x00\x00\x02\x04"
        )
        frames = self.func(bytestream)
        assert frames == [
            b"\x01\x00\x00\x00\x00\x01",
            b"\x02\x00",
            b"\x02\x00\x00\x00",
            b"\x03\x00\x00\x00\x00\x02",
            b"\x03\x00\x00\x00",
            b"\x02\x04",
        ]


class TestDefragmentData:
    """Test encaps.defragment_data"""

    def setup_method(self):
        with pytest.warns(DeprecationWarning):
            self.func = encaps.defragment_data

    def test_defragment(self):
        """Test joining fragmented data works"""
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        reference = b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00"
        assert self.func(bytestream) == reference


class TestReadItem:
    """Test encaps.read_item"""

    def setup_method(self):
        with pytest.warns(DeprecationWarning):
            self.func = encaps.read_item

    def test_item_undefined_length(self):
        """Test exception raised if item length undefined."""
        bytestream = b"\xFE\xFF\x00\xE0\xFF\xFF\xFF\xFF\x00\x00\x00\x01"
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        with pytest.raises(
            ValueError,
            match="Encapsulated data fragment had Undefined "
            "Length at data position 0x4",
        ):
            self.func(fp)

    def test_item_sequence_delimiter(self):
        """Test non-zero length seq delimiter reads correctly."""
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\xDD\xE0"
            b"\x04\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert self.func(fp) == b"\x01\x00\x00\x00"
        assert self.func(fp) is None
        assert self.func(fp) == b"\x02\x00\x00\x00"

    def test_item_sequence_delimiter_zero_length(self):
        """Test that the fragments are returned if seq delimiter hit."""
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\xDD\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert self.func(fp) == b"\x01\x00\x00\x00"
        assert self.func(fp) is None
        assert self.func(fp) == b"\x02\x00\x00\x00"

    def test_item_bad_tag(self):
        """Test item is read if it has an unexpected tag"""
        # This should raise an exception instead
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\x10\x00\x10\x00"
            b"\x04\x00\x00\x00"
            b"\xFF\x00\xFF\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert self.func(fp) == b"\x01\x00\x00\x00"
        assert self.func(fp) == b"\xFF\x00\xFF\x00"
        assert self.func(fp) == b"\x02\x00\x00\x00"

    def test_single_fragment_no_delimiter(self):
        """Test single fragment is returned OK"""
        bytestream = b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert self.func(fp) == b"\x01\x00\x00\x00"

    def test_multi_fragments_no_delimiter(self):
        """Test multi fragments are returned OK"""
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00"
            b"\x01\x02\x03\x04\x05\x06"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert self.func(fp) == b"\x01\x00\x00\x00"
        assert self.func(fp) == b"\x01\x02\x03\x04\x05\x06"

    def test_single_fragment_delimiter(self):
        """Test single fragment is returned OK with sequence delimiter item"""
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\xDD\xE0"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert self.func(fp) == b"\x01\x00\x00\x00"

    def test_multi_fragments_delimiter(self):
        """Test multi fragments are returned OK with sequence delimiter item"""
        bytestream = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00"
            b"\x01\x02\x03\x04\x05\x06"
            b"\xFE\xFF\xDD\xE0"
        )
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert self.func(fp) == b"\x01\x00\x00\x00"
        assert self.func(fp) == b"\x01\x02\x03\x04\x05\x06"


class TestFragmentFrame:
    """Test encaps.fragment_frame."""

    def test_single_fragment_even_data(self):
        """Test 1 fragment from even data"""
        bytestream = b"\xFE\xFF\x00\xE1"
        fragments = fragment_frame(bytestream, nr_fragments=1)
        fragment = next(fragments)
        assert pytest.raises(StopIteration, next, fragments)
        assert fragment == bytestream
        assert len(fragment) == 4

        assert isinstance(fragment, bytes)

    def test_single_fragment_odd_data(self):
        """Test 1 fragment from odd data"""
        bytestream = b"\xFE\xFF\x00"
        fragments = fragment_frame(bytestream, nr_fragments=1)
        fragment = next(fragments)
        assert pytest.raises(StopIteration, next, fragments)
        assert fragment == bytestream + b"\x00"
        assert len(fragment) == 4

    def test_even_fragment_even_data(self):
        """Test even fragments from even data"""
        bytestream = b"\xFE\xFF\x00\xE1"
        # Each fragment should be 2 bytes
        fragments = fragment_frame(bytestream, nr_fragments=2)
        fragment = next(fragments)
        assert fragment == bytestream[:2]
        fragment = next(fragments)
        assert fragment == bytestream[2:]
        assert pytest.raises(StopIteration, next, fragments)

    def test_even_fragment_odd_data(self):
        """Test even fragments from odd data"""
        bytestream = b"\xFE\xFF\x00"
        # First fragment should be 1.5 -> 2 bytes, with the final
        #   fragment 1 byte + 1 byte padding
        fragments = fragment_frame(bytestream, nr_fragments=2)
        fragment = next(fragments)
        assert fragment == b"\xFE\xFF"
        fragment = next(fragments)
        assert fragment == b"\x00\x00"
        assert pytest.raises(StopIteration, next, fragments)

    def test_odd_fragments_even_data(self):
        """Test odd fragments from even data"""
        bytestream = b"\xFE\xFF\x00\xE1" * 31  # 124 bytes
        assert len(bytestream) % 2 == 0
        # Each fragment should be 17.7 -> 18 bytes, with the final
        #   fragment 16 bytes
        fragments = fragment_frame(bytestream, nr_fragments=7)
        for ii in range(6):
            fragment = next(fragments)
            assert len(fragment) == 18

        fragment = next(fragments)
        assert len(fragment) == 16
        assert pytest.raises(StopIteration, next, fragments)

    def test_odd_fragments_odd_data(self):
        """Test odd fragments from odd data"""
        bytestream = b"\xFE\xFF\x00" * 31  # 93 bytes
        assert len(bytestream) % 2 == 1
        # Each fragment should be 13.3 -> 14 bytes, with the final
        #   fragment 9 bytes + 1 byte padding
        fragments = fragment_frame(bytestream, nr_fragments=7)
        for ii in range(6):
            fragment = next(fragments)
            assert len(fragment) == 14
        fragment = next(fragments)
        assert len(fragment) == 10
        assert pytest.raises(StopIteration, next, fragments)

    def test_too_many_fragments_raises(self):
        """Test exception raised if too many fragments."""
        bytestream = b"\xFE\xFF\x00" * 31  # 93 bytes
        # At most we can have 47 fragments
        for fragment in fragment_frame(bytestream, nr_fragments=47):
            pass

        with pytest.raises(ValueError):
            for fragment in fragment_frame(bytestream, nr_fragments=48):
                pass


class TestEncapsulateFrame:
    """Test encaps.itemize_frame."""

    def test_single_item(self):
        """Test encapsulating into one fragment"""
        bytestream = b"\xFE\xFF\x00\xE1"
        item_generator = itemize_frame(bytestream, nr_fragments=1)
        item = next(item_generator)

        assert item == (b"\xfe\xff\x00\xe0\x04\x00\x00\x00\xFE\xFF\x00\xE1")

        pytest.raises(StopIteration, next, item_generator)

    def test_two_items(self):
        """Test encapsulating into two fragments"""
        bytestream = b"\xFE\xFF\x00\xE1"
        item_generator = itemize_frame(bytestream, nr_fragments=2)

        item = next(item_generator)
        assert item == (b"\xfe\xff\x00\xe0\x02\x00\x00\x00\xFE\xFF")

        item = next(item_generator)
        assert item == (b"\xfe\xff\x00\xe0\x02\x00\x00\x00\x00\xe1")

        pytest.raises(StopIteration, next, item_generator)


class TestEncapsulate:
    """Test encaps.encapsulate."""

    def test_encapsulate_single_fragment_per_frame_no_bot(self):
        """Test encapsulating single fragment per frame with no BOT values."""
        ds = dcmread(JP2K_10FRAME_NOBOT)
        frames = [
            f for f in generate_frames(ds.PixelData, number_of_frames=ds.NumberOfFrames)
        ]
        assert len(frames) == 10

        data = encapsulate(frames, fragments_per_frame=1, has_bot=False)
        test_frames = generate_frames(data, number_of_frames=ds.NumberOfFrames)
        for a, b in zip(test_frames, frames):
            assert a == b

        # Original data has no BOT values
        assert data == ds.PixelData

    def test_encapsulate_single_fragment_per_frame_bot(self):
        """Test encapsulating single fragment per frame with BOT values."""
        ds = dcmread(JP2K_10FRAME_NOBOT)
        frames = [
            f for f in generate_frames(ds.PixelData, number_of_frames=ds.NumberOfFrames)
        ]
        assert len(frames) == 10

        data = encapsulate(frames, fragments_per_frame=1, has_bot=True)
        test_frames = generate_frames(data, number_of_frames=ds.NumberOfFrames)
        for a, b in zip(test_frames, frames):
            assert a == b

        fp = DicomBytesIO(data)
        fp.is_little_endian = True
        offsets = parse_basic_offsets(fp)
        assert offsets == [
            0x0000,  # 0
            0x0EEE,  # 3822
            0x1DF6,  # 7670
            0x2CF8,  # 11512
            0x3BFC,  # 15356
            0x4ADE,  # 19166
            0x59A2,  # 22946
            0x6834,  # 26676
            0x76E2,  # 30434
            0x8594,  # 34196
        ]

    def test_encapsulate_bot(self):
        """Test the Basic Offset Table is correct."""
        ds = dcmread(JP2K_10FRAME_NOBOT)
        frames = [
            f for f in generate_frames(ds.PixelData, number_of_frames=ds.NumberOfFrames)
        ]
        assert len(frames) == 10

        data = encapsulate(frames, fragments_per_frame=1, has_bot=True)
        assert data[:56] == (
            b"\xfe\xff\x00\xe0"  # Basic offset table item tag
            b"\x28\x00\x00\x00"  # Basic offset table length
            b"\x00\x00\x00\x00"  # First offset
            b"\xee\x0e\x00\x00"
            b"\xf6\x1d\x00\x00"
            b"\xf8\x2c\x00\x00"
            b"\xfc\x3b\x00\x00"
            b"\xde\x4a\x00\x00"
            b"\xa2\x59\x00\x00"
            b"\x34\x68\x00\x00"
            b"\xe2\x76\x00\x00"
            b"\x94\x85\x00\x00"  # Last offset
            b"\xfe\xff\x00\xe0"  # Next item tag
            b"\xe6\x0e\x00\x00"  # Next item length
        )

    def test_encapsulate_bot_large_raises(self):
        """Test exception raised if too much pixel data for BOT."""

        class FakeBytes(bytes):
            length = -1

            def __len__(self):
                return self.length

            def __getitem__(self, s):
                return b"\x00" * 5

        frame_a = FakeBytes()
        frame_a.length = 2**32 - 1 - 8  # 8 for first BOT item tag/length
        frame_b = FakeBytes()
        frame_b.length = 10
        encapsulate([frame_a, frame_b], has_bot=True)

        frame_a.length = 2**32 - 1 - 7
        msg = (
            r"The total length of the encapsulated frame data \(4294967296 "
            r"bytes\) will be greater than the maximum allowed by the Basic "
        )
        with pytest.raises(ValueError, match=msg):
            encapsulate([frame_a, frame_b], has_bot=True)


class TestEncapsulateExtended:
    """Tests for encaps.encapsulate_extended."""

    def test_encapsulate(self):
        ds = dcmread(JP2K_10FRAME_NOBOT)
        frames = [
            f for f in generate_frames(ds.PixelData, number_of_frames=ds.NumberOfFrames)
        ]
        assert len(frames) == 10

        out = encapsulate_extended(frames)
        # Pixel Data encapsulated OK
        assert isinstance(out[0], bytes)
        test_frames = [
            f for f in generate_frames(out[0], number_of_frames=ds.NumberOfFrames)
        ]
        for a, b in zip(test_frames, frames):
            assert a == b

        # Extended Offset Table is OK
        assert isinstance(out[1], bytes)
        assert [
            0x0000,  # 0
            0x0EEE,  # 3822
            0x1DF6,  # 7670
            0x2CF8,  # 11512
            0x3BFC,  # 15356
            0x4ADE,  # 19166
            0x59A2,  # 22946
            0x6834,  # 26676
            0x76E2,  # 30434
            0x8594,  # 34196
        ] == list(unpack("<10Q", out[1]))

        # Extended Offset Table Lengths are OK
        assert isinstance(out[2], bytes)
        assert [len(f) for f in frames] == list(unpack("<10Q", out[2]))

    def test_encapsulate_odd_length(self):
        """Test encapsulating odd-length frames"""
        frames = [b"\x00", b"\x01", b"\x02"]
        eot_encapsulated, eot, eot_lengths = encapsulate_extended(frames)
        assert unpack(f"<{len(frames)}Q", eot) == (0, 10, 20)
        assert unpack(f"<{len(frames)}Q", eot_lengths) == (2, 2, 2)


def as_bytesio(buffer):
    buffer = BytesIO(buffer)
    buffer.seek(0)
    return buffer


class TestParseBasicOffsets:
    """Tests for parse_basic_offsets()"""

    def test_bad_tag(self):
        """Test raises exception if no item tag."""
        # (FFFE,E100)
        buffer = b"\xFE\xFF\x00\xE1\x08\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08"
        msg = (
            r"Found unexpected tag \(FFFE,E100\) instead of \(FFFE,E000\) when "
            r"parsing the Basic Offset Table item"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            with pytest.raises(ValueError, match=msg):
                parse_basic_offsets(src)

        buffer = b"\xFE\xFF\x00\xE1\x08\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08"
        msg = (
            r"Found unexpected tag \(FEFF,00E1\) instead of \(FFFE,E000\) when "
            r"parsing the Basic Offset Table item"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            with pytest.raises(ValueError, match=msg):
                parse_basic_offsets(src, endianness=">")

    def test_bad_length_multiple(self):
        """Test raises exception if the item length is not a multiple of 4."""
        # Length 10
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x0A\x00\x00\x00"
            b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A"
        )
        msg = "The length of the Basic Offset Table item is not a multiple of 4"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            with pytest.raises(ValueError, match=msg):
                parse_basic_offsets(src)

        buffer = (
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x0A"
            b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            with pytest.raises(ValueError, match=msg):
                parse_basic_offsets(src, endianness=">")

    def test_zero_length(self):
        """Test reading BOT with zero length"""
        # Little endian
        buffer = b"\xFE\xFF\x00\xE0\x00\x00\x00\x00"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert [] == parse_basic_offsets(src)

        assert src.tell() == 8

        # Big endian
        buffer = b"\xFF\xFE\xE0\x00\x00\x00\x00\x00"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert [] == parse_basic_offsets(src, endianness=">")

        assert src.tell() == 8

    def test_multi_frame(self):
        """Test reading multi-frame BOT item"""
        # Little endian
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x10\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x66\x13\x00\x00"
            b"\xF4\x25\x00\x00"
            b"\xFE\x37\x00\x00"
            b"\xFE\xFF\x00\xE0"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert [0, 4966, 9716, 14334] == parse_basic_offsets(src)

        assert src.tell() == 24

        # Big endian
        buffer = (
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x10"
            b"\x00\x00\x00\x00"
            b"\x00\x00\x13\x66"
            b"\x00\x00\x25\xF4"
            b"\x00\x00\x37\xFE"
            b"\xFF\xFE\xE0\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert [0, 4966, 9716, 14334] == parse_basic_offsets(src, endianness=">")

        assert src.tell() == 24

    def test_single_frame(self):
        """Test reading single-frame BOT item"""
        # Little endian
        buffer = b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x00\x00\x00\x00\xFE\xFF\x00\xE0"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert [0] == parse_basic_offsets(src)

        assert src.tell() == 12

        # Big endian
        buffer = b"\xFF\xFE\xE0\x00\x00\x00\x00\x04\x00\x00\x00\x00\xFF\xFE\xE0\x00"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert [0] == parse_basic_offsets(src, endianness=">")

        assert src.tell() == 12


class TestParseFragments:
    """Tests for parse_fragments()"""

    def test_item_undefined_length(self):
        """Test exception raised if item length undefined."""
        buffer = b"\xFE\xFF\x00\xE0\xFF\xFF\xFF\xFF\x00\x00\x00\x01"

        msg = (
            "Undefined item length at offset 4 when "
            "parsing the encapsulated pixel data fragments"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            with pytest.raises(ValueError, match=msg):
                parse_fragments(src)

        buffer = b"\xFF\xFE\xE0\x00\xFF\xFF\xFF\xFF\x00\x00\x00\x01"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            with pytest.raises(ValueError, match=msg):
                parse_fragments(src, endianness=">")

    def test_item_sequence_delimiter(self):
        """Test that the fragments are returned if seq delimiter hit."""
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\xDD\xE0"  # sequence delimiter
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert parse_fragments(src) == (1, [0])

        buffer = (
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x04"
            b"\x00\x00\x00\x01"
            b"\xFF\xFE\xE0\xDD"  # sequence delimiter
            b"\x00\x00\x00\x00"
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x04`"
            b"\x00\x00\x00\x02"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert parse_fragments(src, endianness=">") == (1, [0])

    def test_item_bad_tag(self):
        """Test exception raised if item has unexpected tag"""
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\x10\x00\x10\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
        )
        msg = (
            r"Unexpected tag '\(0010,0010\)' at offset 12 when parsing the "
            r"encapsulated pixel data fragment items"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            with pytest.raises(ValueError, match=msg):
                parse_fragments(src)

        buffer = (
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x04"
            b"\x00\x00\x00\x01"
            b"\x00\x10\x00\x10"
            b"\x00\x00\x00\x00"
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x04"
            b"\x00\x00\x00\x02"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            with pytest.raises(ValueError, match=msg):
                parse_fragments(src, endianness=">")

    def test_item_invalid(self):
        """Test exception raised if sequence is too short"""
        buffer = b"\xFE\xFF\x00\xE0\x04\x00\x00"
        msg = (
            "Unable to determine the length of the item at offset 0 as the end "
            "of the data has been reached - the encapsulated pixel data may "
            "be invalid"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            with pytest.raises(ValueError, match=msg):
                parse_fragments(src)

        buffer = b"\xFF\xFE\xE0\x00\x00\x00\x04"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            with pytest.raises(ValueError, match=msg):
                parse_fragments(src, endianness=">")

    def test_single_fragment_no_delimiter(self):
        """Test single fragment is returned OK"""
        buffer = b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert parse_fragments(src) == (1, [0])

        assert src.tell() == 0

        buffer = b"\xFF\xFE\xE0\x00\x00\x00\x00\x04\x00\x00\x00\x01"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert parse_fragments(src, endianness=">") == (1, [0])

        assert src.tell() == 0

    def test_multi_fragments_no_delimiter(self):
        """Test multi fragments are returned OK"""
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00"
            b"\x01\x02\x03\x04\x05\x06"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert parse_fragments(src) == (2, [0, 12])

        assert src.tell() == 0

        buffer = (
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x04"
            b"\x00\x00\x00\x01"
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x06"
            b"\x01\x02\x03\x04\x05\x06"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert parse_fragments(src, endianness=">") == (2, [0, 12])

        assert src.tell() == 0

    def test_single_fragment_delimiter(self):
        """Test single fragment is returned OK with sequence delimiter item"""
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\xDD\xE0"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert parse_fragments(src) == (1, [0])

        assert src.tell() == 0

        buffer = (
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x04"
            b"\x00\x00\x00\x01"
            b"\xFF\xFE\xE0\xDD"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert parse_fragments(src, endianness=">") == (1, [0])

        assert src.tell() == 0

    def test_multi_fragments_delimiter(self):
        """Test multi fragments are returned OK with sequence delimiter item"""
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00"
            b"\x01\x02\x03\x04\x05\x06"
            b"\xFE\xFF\xDD\xE0"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert parse_fragments(src) == (2, [0, 12])

        assert src.tell() == 0

        buffer = (
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x04"
            b"\x00\x00\x00\x01"
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x06"
            b"\x01\x02\x03\x04\x05\x06"
            b"\xFF\xFE\xE0\xDD"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert parse_fragments(src, endianness=">") == (2, [0, 12])

        assert src.tell() == 0


class TestGenerateFragments:
    """Test generate_fragments()"""

    def test_item_undefined_length(self):
        """Test exception raised if item length undefined."""
        buffer = b"\xFE\xFF\x00\xE0\xFF\xFF\xFF\xFF\x00\x00\x00\x01"
        msg = (
            "Undefined item length at offset 4 when parsing the encapsulated "
            "pixel data fragments"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            fragments = generate_fragments(src)
            with pytest.raises(ValueError, match=msg):
                next(fragments)

            pytest.raises(StopIteration, next, fragments)

        buffer = b"\xFF\xFE\xE0\x00\xFF\xFF\xFF\xFF\x00\x00\x00\x01"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            fragments = generate_fragments(src, endianness=">")
            with pytest.raises(ValueError, match=msg):
                next(fragments)

            pytest.raises(StopIteration, next, fragments)

    def test_item_sequence_delimiter(self):
        """Test that the fragments are returned if seq delimiter hit."""
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\xDD\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            fragments = generate_fragments(src)
            assert next(fragments) == b"\x01\x00\x00\x00"
            pytest.raises(StopIteration, next, fragments)

        buffer = (
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x04"
            b"\x00\x00\x00\x01"
            b"\xFF\xFE\xE0\xDD"
            b"\x00\x00\x00\x00"
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x04"
            b"\x00\x00\x00\x02"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            fragments = generate_fragments(src, endianness=">")
            assert next(fragments) == b"\x00\x00\x00\x01"
            pytest.raises(StopIteration, next, fragments)

    def test_item_bad_tag(self):
        """Test exception raised if item has unexpected tag"""
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\x10\x00\x10\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
        )
        msg = (
            r"Unexpected tag '\(0010,0010\)' at offset 12 when parsing the "
            "encapsulated pixel data fragment items"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            fragments = generate_fragments(src)
            assert next(fragments) == b"\x01\x00\x00\x00"
            with pytest.raises(ValueError, match=msg):
                next(fragments)
            pytest.raises(StopIteration, next, fragments)

        buffer = (
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x04"
            b"\x00\x00\x00\x01"
            b"\x00\x10\x00\x10"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            fragments = generate_fragments(src, endianness=">")
            assert next(fragments) == b"\x00\x00\x00\x01"
            with pytest.raises(ValueError, match=msg):
                next(fragments)
            pytest.raises(StopIteration, next, fragments)

    def test_item_invalid(self):
        """Test exception raised if item is invalid"""
        buffer = b"\xFE\xFF\x00\xE0\x04\x00\x00"
        msg = (
            "Unable to determine the length of the item at offset 0 as the end "
            "of the data has been reached - the encapsulated pixel data may "
            "be invalid"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            fragments = generate_fragments(src)
            with pytest.raises(ValueError, match=msg):
                next(fragments)
            pytest.raises(StopIteration, next, fragments)

        buffer = b"\xFF\xFE\xE0\x00\x00\x00\x04"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            fragments = generate_fragments(src, endianness=">")
            with pytest.raises(ValueError, match=msg):
                next(fragments)
            pytest.raises(StopIteration, next, fragments)

    def test_single_fragment_no_delimiter(self):
        """Test single fragment is returned OK"""
        buffer = b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            fragments = generate_fragments(src)
            assert next(fragments) == b"\x01\x00\x00\x00"
            pytest.raises(StopIteration, next, fragments)

        buffer = b"\xFF\xFE\xE0\x00\x00\x00\x00\x04\x01\x00\x00\x00"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            fragments = generate_fragments(src, endianness=">")
            assert next(fragments) == b"\x01\x00\x00\x00"
            pytest.raises(StopIteration, next, fragments)

    def test_multi_fragments_no_delimiter(self):
        """Test multi fragments are returned OK"""
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00"
            b"\x01\x02\x03\x04\x05\x06"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            fragments = generate_fragments(src)
            assert next(fragments) == b"\x01\x00\x00\x00"
            assert next(fragments) == b"\x01\x02\x03\x04\x05\x06"
            pytest.raises(StopIteration, next, fragments)

        buffer = (
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x04"
            b"\x01\x00\x00\x00"
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x06"
            b"\x01\x02\x03\x04\x05\x06"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            fragments = generate_fragments(src, endianness=">")
            assert next(fragments) == b"\x01\x00\x00\x00"
            assert next(fragments) == b"\x01\x02\x03\x04\x05\x06"
            pytest.raises(StopIteration, next, fragments)

    def test_single_fragment_delimiter(self):
        """Test single fragment is returned OK with sequence delimiter item"""
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\xDD\xE0"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            fragments = generate_fragments(src)
            assert next(fragments) == b"\x01\x00\x00\x00"
            pytest.raises(StopIteration, next, fragments)

        buffer = (
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x04"
            b"\x01\x00\x00\x00"
            b"\xFF\xFE\xE0\xDD"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            fragments = generate_fragments(src, endianness=">")
            assert next(fragments) == b"\x01\x00\x00\x00"
            pytest.raises(StopIteration, next, fragments)

    def test_multi_fragments_delimiter(self):
        """Test multi fragments are returned OK with sequence delimiter item"""
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00"
            b"\x01\x02\x03\x04\x05\x06"
            b"\xFE\xFF\xDD\xE0"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            fragments = generate_fragments(src)
            assert next(fragments) == b"\x01\x00\x00\x00"
            assert next(fragments) == b"\x01\x02\x03\x04\x05\x06"
            pytest.raises(StopIteration, next, fragments)

        buffer = (
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x04"
            b"\x01\x00\x00\x00"
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x06"
            b"\x01\x02\x03\x04\x05\x06"
            b"\xFF\xFE\xE0\xDD"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            fragments = generate_fragments(src, endianness=">")
            assert next(fragments) == b"\x01\x00\x00\x00"
            assert next(fragments) == b"\x01\x02\x03\x04\x05\x06"
            pytest.raises(StopIteration, next, fragments)


class TestGenerateFragmentedFrames:
    """Tests for generate_fragmented_frames()"""

    def test_empty_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragments"""
        # 1 frame, 1 fragment long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_fragmented_frames(src)
            assert next(frames) == (b"\x01\x00\x00\x00",)
            pytest.raises(StopIteration, next, frames)

        buffer = (
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x00"
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x04"
            b"\x01\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_fragmented_frames(src, endianness=">")
            assert next(frames) == (b"\x01\x00\x00\x00",)
            pytest.raises(StopIteration, next, frames)

    def test_empty_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_fragmented_frames(src, number_of_frames=1)
            assert next(frames) == (
                b"\x01\x00\x00\x00",
                b"\x02\x00\x00\x00",
                b"\x03\x00\x00\x00",
            )
            pytest.raises(StopIteration, next, frames)

        buffer = (
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x00"
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x04"
            b"\x01\x00\x00\x00"
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x04"
            b"\x02\x00\x00\x00"
            b"\xFF\xFE\xE0\x00"
            b"\x00\x00\x00\x04"
            b"\x03\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_fragmented_frames(
                buffer, number_of_frames=1, endianness=">"
            )
            assert next(frames) == (
                b"\x01\x00\x00\x00",
                b"\x02\x00\x00\x00",
                b"\x03\x00\x00\x00",
            )
            pytest.raises(StopIteration, next, frames)

    def test_empty_bot_no_number_of_frames_raises(self):
        """Test parsing raises if not BOT and no number_of_frames."""
        # 1 frame, 3 fragments long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        msg = (
            r"Unable to determine the frame boundaries for the encapsulated "
            r"pixel data as there is no Basic or Extended Offset Table and the "
            r"number of frames has not been supplied"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            with pytest.raises(ValueError, match=msg):
                next(generate_fragmented_frames(src))

    def test_empty_bot_too_few_fragments(self):
        """Test parsing with too few fragments."""
        ds = dcmread(JP2K_10FRAME_NOBOT)
        assert 10 == ds.NumberOfFrames

        msg = (
            "Unable to generate frames from the encapsulated pixel data as "
            "there are fewer fragments than frames; the dataset may be corrupt "
            "or the number of frames may be incorrect"
        )
        for func in (bytes, as_bytesio):
            src = func(ds.PixelData)
            with pytest.raises(ValueError, match=msg):
                next(generate_fragmented_frames(src, number_of_frames=20))

    def test_empty_bot_multi_fragments_per_frame(self):
        """Test parsing with multiple fragments per frame."""
        # 4 frames in 6 fragments with JPEG EOI marker
        buffer = (
            b"\xFE\xFF\x00\xE0\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\xFF\xD9"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_fragmented_frames(src, number_of_frames=4)
            for ii in range(4):
                next(frames)

            pytest.raises(StopIteration, next, frames)

    def test_empty_bot_no_marker(self):
        """Test parsing not BOT and no final marker with multi fragments."""
        # 4 frames in 6 fragments with JPEG EOI marker (1 missing EOI)
        buffer = (
            b"\xFE\xFF\x00\xE0\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xFF\xD9"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_fragmented_frames(src, number_of_frames=4)
            for ii in range(3):
                next(frames)

            msg = (
                "The end of the encapsulated pixel data has been reached but fewer "
                "frames than expected have been found. Please confirm that the "
                "generated frame data is correct"
            )
            with pytest.warns(UserWarning, match=msg):
                next(frames)

            pytest.raises(StopIteration, next, frames)

    def test_empty_bot_missing_marker(self):
        """Test parsing no BOT and missing marker with multi fragments."""
        # 4 frames in 6 fragments with JPEG EOI marker (1 missing EOI)
        buffer = (
            b"\xFE\xFF\x00\xE0\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xFF\xD9"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
        )

        msg = (
            "The end of the encapsulated pixel data has been reached but "
            "fewer frames than expected have been found"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            with pytest.warns(UserWarning, match=msg):
                for ii, frame in enumerate(
                    generate_fragmented_frames(src, number_of_frames=4)
                ):
                    pass

            assert 2 == ii

    def test_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragment"""
        # 1 frame, 1 fragment long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_fragmented_frames(src)
            assert next(frames) == (b"\x01\x00\x00\x00",)
            pytest.raises(StopIteration, next, frames)

    def test_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_fragmented_frames(src)
            assert next(frames) == (
                b"\x01\x00\x00\x00",
                b"\x02\x00\x00\x00",
                b"\x03\x00\x00\x00",
            )
            pytest.raises(StopIteration, next, frames)

    def test_multi_frame_one_to_one(self):
        """Test a multi-frame image where each frame is one fragment"""
        # 3 frames, each 1 fragment long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x0C\x00\x00\x00"
            b"\x18\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_fragmented_frames(src)
            assert next(frames) == (b"\x01\x00\x00\x00",)
            assert next(frames) == (b"\x02\x00\x00\x00",)
            assert next(frames) == (b"\x03\x00\x00\x00",)
            pytest.raises(StopIteration, next, frames)

    def test_multi_frame_three_to_one(self):
        """Test a multi-frame image where each frame is three fragments"""
        # 2 frames, each 3 fragments long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x24\x00\x00\x00"
            b"\x48\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_fragmented_frames(src)
            assert next(frames) == (
                b"\x01\x00\x00\x00",
                b"\x02\x00\x00\x00",
                b"\x03\x00\x00\x00",
            )
            assert next(frames) == (
                b"\x02\x00\x00\x00",
                b"\x02\x00\x00\x00",
                b"\x03\x00\x00\x00",
            )
            assert next(frames) == (
                b"\x03\x00\x00\x00",
                b"\x02\x00\x00\x00",
                b"\x03\x00\x00\x00",
            )
            pytest.raises(StopIteration, next, frames)

    def test_multi_frame_varied_ratio(self):
        """Test a multi-frame image where each frame is random fragments"""
        # 3 frames, 1st is 1 fragment, 2nd is 3 fragments, 3rd is 2 fragments
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x0E\x00\x00\x00"
            b"\x32\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00\x01\x00\x00\x00\x00\x01"
            b"\xFE\xFF\x00\xE0"
            b"\x02\x00\x00\x00\x02\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00\x03\x00\x00\x00\x00\x02"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x02\x00\x00\x00\x02\x04"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_fragmented_frames(src)
            assert next(frames) == (b"\x01\x00\x00\x00\x00\x01",)
            assert next(frames) == (
                b"\x02\x00",
                b"\x02\x00\x00\x00",
                b"\x03\x00\x00\x00\x00\x02",
            )
            assert next(frames) == (b"\x03\x00\x00\x00", b"\x02\x04")
            pytest.raises(StopIteration, next, frames)

    def test_eot_single_fragment(self):
        """Test a single-frame image where the frame is one fragment"""
        # 1 frame, 1 fragment long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
        )
        eot = ([0], [4])
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_fragmented_frames(src, extended_offsets=eot)
            assert next(frames) == (b"\x01\x00\x00\x00",)
            pytest.raises(StopIteration, next, frames)

        eot = (  # unsigned long, 8 bytes
            b"\x00\x00\x00\x00\x00\x00\x00\x00",
            b"\x04\x00\x00\x00\x00\x00\x00\x00",
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_fragmented_frames(src, extended_offsets=eot)
            assert next(frames) == (b"\x01\x00\x00\x00",)
            pytest.raises(StopIteration, next, frames)

    def test_eot_multi_frame(self):
        """Test a multi-frame image where each frame is one fragment"""
        # 3 frames, each 1 fragment long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x0C\x00\x00\x00"
            b"\x18\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"  # 0
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"  # 12
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"  # 24
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        eot = ([0, 12, 24], [4, 4, 4])
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_fragmented_frames(src, extended_offsets=eot)
            assert next(frames) == (b"\x01\x00\x00\x00",)
            assert next(frames) == (b"\x02\x00\x00\x00",)
            assert next(frames) == (b"\x03\x00\x00\x00",)
            pytest.raises(StopIteration, next, frames)

        eot = (  # unsigned long, 8 bytes
            b"\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x0C\x00\x00\x00\x00\x00\x00\x00"
            b"\x18\x00\x00\x00\x00\x00\x00\x00",
            b"\x04\x00\x00\x00\x00\x00\x00\x00" * 3,
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_fragmented_frames(src, extended_offsets=eot)
            assert next(frames) == (b"\x01\x00\x00\x00",)
            assert next(frames) == (b"\x02\x00\x00\x00",)
            assert next(frames) == (b"\x03\x00\x00\x00",)
            pytest.raises(StopIteration, next, frames)


class TestGenerateFrames:
    """Tests for generate_frames()"""

    def test_empty_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragments"""
        # 1 frame, 1 fragment long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_frames(src)
            assert next(frames) == b"\x01\x00\x00\x00"
            pytest.raises(StopIteration, next, frames)

    def test_empty_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_frames(src, number_of_frames=1)
            assert next(frames) == (b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00")
            pytest.raises(StopIteration, next, frames)

    def test_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragment"""
        # 1 frame, 1 fragment long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_frames(src)
            assert next(frames) == b"\x01\x00\x00\x00"
            pytest.raises(StopIteration, next, frames)

    def test_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_frames(src)
            assert next(frames) == (b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00")
            pytest.raises(StopIteration, next, frames)

    def test_multi_frame_one_to_one(self):
        """Test a multi-frame image where each frame is one fragment"""
        # 3 frames, each 1 fragment long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x0C\x00\x00\x00"
            b"\x18\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_frames(src)
            assert next(frames) == b"\x01\x00\x00\x00"
            assert next(frames) == b"\x02\x00\x00\x00"
            assert next(frames) == b"\x03\x00\x00\x00"
            pytest.raises(StopIteration, next, frames)

    def test_multi_frame_three_to_one(self):
        """Test a multi-frame image where each frame is three fragments"""
        # 2 frames, each 3 fragments long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x24\x00\x00\x00"
            b"\x48\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_frames(src)
            assert next(frames) == b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00"
            assert next(frames) == b"\x02\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00"
            assert next(frames) == b"\x03\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00"
            pytest.raises(StopIteration, next, frames)

    def test_multi_frame_varied_ratio(self):
        """Test a multi-frame image where each frames is random fragments"""
        # 3 frames, 1st is 1 fragment, 2nd is 3 fragments, 3rd is 2 fragments
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x0E\x00\x00\x00"
            b"\x32\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00\x01\x00\x00\x00\x00\x01"
            b"\xFE\xFF\x00\xE0"
            b"\x02\x00\x00\x00\x02\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00\x03\x00\x00\x00\x00\x02"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x02\x00\x00\x00\x02\x04"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            frames = generate_frames(src)
            assert next(frames) == b"\x01\x00\x00\x00\x00\x01"
            assert next(frames) == (b"\x02\x00\x02\x00\x00\x00\x03\x00\x00\x00\x00\x02")
            assert next(frames) == b"\x03\x00\x00\x00\x02\x04"
            pytest.raises(StopIteration, next, frames)

    def test_empty_bot_single_fragment_per_frame(self):
        """Test multi-frame where multiple frags per frame and no BOT."""
        ds = dcmread(JP2K_10FRAME_NOBOT)
        assert 10 == ds.NumberOfFrames
        for func in (bytes, as_bytesio):
            src = func(ds.PixelData)
            frame_gen = generate_frames(src, number_of_frames=ds.NumberOfFrames)
            for ii in range(10):
                next(frame_gen)

            with pytest.raises(StopIteration):
                next(frame_gen)

    def test_empty_bot_multi_fragments_per_frame(self):
        """Test multi-frame where multiple frags per frame and no BOT."""
        # Regression test for #685
        ds = dcmread(JP2K_10FRAME_NOBOT)
        assert 10 == ds.NumberOfFrames
        for func in (bytes, as_bytesio):
            src = func(ds.PixelData)
            # Note that we will yield 10 frames, not 8
            frame_gen = generate_frames(src, number_of_frames=8)
            for ii in range(10):
                next(frame_gen)

            with pytest.raises(StopIteration):
                next(frame_gen)

    def test_empty_bot_multi_fragments_per_frame_excess_frames(self):
        """Test multi-frame where multiple frags per frame and no BOT."""
        # Regression test for #685
        ds = dcmread(JP2K_10FRAME_NOBOT)
        assert 10 == ds.NumberOfFrames
        msg = (
            "The end of the encapsulated pixel data has been reached but "
            "no JPEG EOI/EOC marker was found, the final frame may be "
            "be invalid"
        )
        excess = b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x00\x01\x02\x03"
        for func in (bytes, as_bytesio):
            src = func(b"".join([ds.PixelData, excess]))
            # Note that we will yield 10 frames, not 8
            frame_gen = generate_frames(src, number_of_frames=8)
            for ii in range(10):
                next(frame_gen)

            with pytest.warns(UserWarning, match=msg):
                frame = next(frame_gen)

            assert frame == b"\x00\x01\x02\x03"

            with pytest.raises(StopIteration):
                next(frame_gen)

    def test_mmap(self):
        """Test with mmapped file."""
        with dcmread(JP2K_10FRAME_NOBOT) as ds:
            elem = ds["PixelData"]
            frames = generate_frames(ds.PixelData, number_of_frames=10)
            for ii in range(8):
                next(frames)
            reference = next(frames)
            assert reference[-10:] == b"\x56\xF7\xFF\x4E\x60\xE3\xDA\x0F\xFF\xD9"

        with open(JP2K_10FRAME_NOBOT, "rb") as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            # Start of BOT is at offset 2352
            mm.seek(elem.file_tell)
            # frame 9 (index 8) starts at offset 32802 and is 3754 bytes long
            frames = generate_frames(mm, number_of_frames=10)
            for ii in range(8):
                next(frames)
            frame = next(frames)
            assert frame == reference
            assert len(frame) == 3754


class TestGetFrame:
    """Tests for get_frame()"""

    def test_empty_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragments"""
        # 1 frame, 1 fragment long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert get_frame(src, 0) == b"\x01\x00\x00\x00"

    def test_empty_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert get_frame(src, 0, number_of_frames=1) == (
                b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00"
            )

    def test_empty_bot_no_number_of_frames_raises(self):
        """Test parsing raises if not BOT and no number_of_frames."""
        # 1 frame, 3 fragments long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        msg = (
            r"Unable to determine the frame boundaries for the encapsulated "
            r"pixel data as there is no basic or extended offset table data "
            r"and the number of frames has not been supplied"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            with pytest.raises(ValueError, match=msg):
                get_frame(src, 0)

    def test_empty_bot_too_few_fragments(self):
        """Test parsing with too few fragments."""
        ds = dcmread(JP2K_10FRAME_NOBOT)
        assert 10 == ds.NumberOfFrames

        msg = "There is insufficient pixel data to contain 12 frames"
        with pytest.raises(ValueError, match=msg):
            get_frame(ds.PixelData, 11, number_of_frames=20)

    def test_empty_bot_multi_fragments_per_frame(self):
        """Test parsing with multiple fragments per frame."""
        # 4 frames in 6 fragments with JPEG EOI marker
        buffer = (
            b"\xFE\xFF\x00\xE0\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\xFF\xD9"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
        )
        msg = "There is insufficient pixel data to contain 5 frames"
        for func in (bytes, as_bytesio):
            src = func(buffer)

            # Note that we can access a single "extra" frame
            assert (
                get_frame(src, 0, number_of_frames=3)
                == b"\x01\x00\x00\x00\x01\xFF\xD9\x00"
            )
            assert get_frame(src, 1, number_of_frames=3) == b"\x01\x00\xFF\xD9"
            assert get_frame(src, 2, number_of_frames=3) == b"\x01\xFF\xD9\x00"
            assert (
                get_frame(src, 3, number_of_frames=3)
                == b"\x01\x00\x00\x00\x01\xFF\xD9\x00"
            )

            with pytest.raises(ValueError, match=msg):
                get_frame(src, 4, number_of_frames=3)

    def test_empty_bot_no_marker(self):
        """Test parsing no BOT and no final marker with multi fragments."""
        # 4 frames in 6 fragments with JPEG EOI marker (1 missing EOI)
        buffer = (
            b"\xFE\xFF\x00\xE0\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xD9\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\xFF\xD9"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\xFF\x00\x00"
        )

        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert (
                get_frame(src, 0, number_of_frames=3)
                == b"\x01\x00\x00\x00\x01\xFF\xD9\x00"
            )
            assert (
                get_frame(src, 1, number_of_frames=3)
                == b"\x01\x00\x00\x00\x01\xFF\xD9\x00"
            )
            assert get_frame(src, 2, number_of_frames=3) == b"\x01\xFF\xFF\xD9"

            msg = (
                "The end of the encapsulated pixel data has been reached but no "
                "JPEG EOI/EOC marker was found, the returned frame data may be invalid"
            )
            with pytest.warns(UserWarning, match=msg):
                assert get_frame(src, 3, number_of_frames=3) == b"\x01\xFF\x00\x00"

            msg = "There is insufficient pixel data to contain 5 frames"
            with pytest.raises(ValueError, match=msg):
                get_frame(src, 4, number_of_frames=3)

    def test_empty_bot_index_greater_than_frames_raises(self):
        """Test multiple fragments, 1 frame raises if index > 0"""
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
        )
        msg = "The 'index' must be 0 if the number of frames is 1"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            with pytest.raises(ValueError, match=msg):
                get_frame(src, 1, number_of_frames=1)

    def test_empty_bot_index_greater_than_multi_frames_raises(self):
        """Test 1:1 fragments:frames raises if index > number of frames"""
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
        )
        msg = (
            "Found 2 frame fragments in the encapsulated pixel data, an "
            "'index' of 2 is invalid"
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            with pytest.raises(ValueError, match=msg):
                get_frame(src, 2, number_of_frames=2)

    def test_bot_single_fragment(self):
        """Test a single-frame image where the frame is one fragment"""
        # 1 frame, 1 fragment long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
        )
        msg = "There aren't enough offsets in the Basic Offset Table for 2 frames"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert get_frame(src, 0) == b"\x01\x00\x00\x00"
            with pytest.raises(ValueError, match=msg):
                get_frame(src, 1)

    def test_bot_triple_fragment_single_frame(self):
        """Test a single-frame image where the frame is three fragments"""
        # 1 frame, 3 fragments long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        msg = "There aren't enough offsets in the Basic Offset Table for 2 frames"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert get_frame(src, 0) == (
                b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00"
            )
            with pytest.raises(ValueError, match=msg):
                get_frame(src, 1)

    def test_multi_frame_one_to_one(self):
        """Test a multi-frame image where each frame is one fragment"""
        # 3 frames, each 1 fragment long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x0C\x00\x00\x00"
            b"\x18\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        msg = "There aren't enough offsets in the Basic Offset Table for 4 frames"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert get_frame(src, 0) == b"\x01\x00\x00\x00"
            assert get_frame(src, 1) == b"\x02\x00\x00\x00"
            assert get_frame(src, 2) == b"\x03\x00\x00\x00"
            with pytest.raises(ValueError, match=msg):
                get_frame(src, 3)

    def test_multi_frame_three_to_one(self):
        """Test a multi-frame image where each frame is three fragments"""
        # 3 frames, each 3 fragments long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x24\x00\x00\x00"
            b"\x48\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x03\x00\x00\x00"
        )
        msg = "There aren't enough offsets in the Basic Offset Table for 4 frames"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert get_frame(src, 0) == (
                b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00"
            )
            assert get_frame(src, 1) == (
                b"\x02\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00"
            )
            assert get_frame(src, 2) == (
                b"\x03\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00"
            )
            with pytest.raises(ValueError, match=msg):
                get_frame(src, 3)

    def test_multi_frame_varied_ratio(self):
        """Test a multi-frame image where each frames is random fragments"""
        # 3 frames, 1st is 1 fragment, 2nd is 3 fragments, 3rd is 2 fragments
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x0C\x00\x00\x00"
            b"\x00\x00\x00\x00"
            b"\x0E\x00\x00\x00"
            b"\x32\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00\x01\x00\x00\x00\x00\x01"
            b"\xFE\xFF\x00\xE0"
            b"\x02\x00\x00\x00\x02\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x06\x00\x00\x00\x03\x00\x00\x00\x00\x02"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00\x03\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x02\x00\x00\x00\x02\x04"
        )
        msg = "There aren't enough offsets in the Basic Offset Table for 4 frames"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert get_frame(src, 0) == b"\x01\x00\x00\x00\x00\x01"
            assert get_frame(src, 1) == (
                b"\x02\x00\x02\x00\x00\x00\x03\x00\x00\x00\x00\x02"
            )
            assert get_frame(src, 2) == b"\x03\x00\x00\x00\x02\x04"
            with pytest.raises(ValueError, match=msg):
                get_frame(src, 3)

    def test_eot_single_fragment(self):
        """Test a single-frame image where the frame is one fragment"""
        # 1 frame, 1 fragment long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
        )
        eot = ([0], [4])
        msg = "Found 1 frame fragment in the encapsulated pixel data, 'index' must be 0"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert get_frame(src, 0, extended_offsets=eot) == b"\x01\x00\x00\x00"
            with pytest.raises(ValueError, match=msg):
                get_frame(src, 1)

        eot = (  # unsigned long, 8 bytes
            b"\x00\x00\x00\x00\x00\x00\x00\x00",
            b"\x04\x00\x00\x00\x00\x00\x00\x00",
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert get_frame(src, 0, extended_offsets=eot) == b"\x01\x00\x00\x00"
            with pytest.raises(ValueError, match=msg):
                get_frame(src, 1)

    def test_eot_multi_fragment(self):
        """Test a single-frame image where the frame is three fragments"""
        # 3 frames, 1 fragments long
        buffer = (
            b"\xFE\xFF\x00\xE0"
            b"\x00\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x01\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x02\x00\x00\x00"
            b"\xFE\xFF\x00\xE0"
            b"\x04\x00\x00\x00"
            b"\x03\x00\x00\x00"
        )
        eot = ([0, 12, 24], [4, 4, 4])
        msg = "There aren't enough offsets in the Extended Offset Table for 4 frames"
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert get_frame(src, 0, extended_offsets=eot) == b"\x01\x00\x00\x00"
            assert get_frame(src, 1, extended_offsets=eot) == b"\x02\x00\x00\x00"
            assert get_frame(src, 2, extended_offsets=eot) == b"\x03\x00\x00\x00"
            with pytest.raises(ValueError, match=msg):
                get_frame(src, 3, extended_offsets=eot)

        eot = (  # unsigned long, 8 bytes
            b"\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x0C\x00\x00\x00\x00\x00\x00\x00"
            b"\x18\x00\x00\x00\x00\x00\x00\x00",
            b"\x04\x00\x00\x00\x00\x00\x00\x00" * 3,
        )
        for func in (bytes, as_bytesio):
            src = func(buffer)
            assert get_frame(src, 0, extended_offsets=eot) == b"\x01\x00\x00\x00"
            assert get_frame(src, 1, extended_offsets=eot) == b"\x02\x00\x00\x00"
            assert get_frame(src, 2, extended_offsets=eot) == b"\x03\x00\x00\x00"
            with pytest.raises(ValueError, match=msg):
                get_frame(src, 3, extended_offsets=eot)

    def test_mmap(self):
        """Test with mmapped file."""
        references = []
        with dcmread(JP2K_10FRAME_NOBOT) as ds:
            elem = ds["PixelData"]
            references.append(get_frame(ds.PixelData, 0, number_of_frames=10))
            assert references[-1][-10:] == b"\x35\x6C\xDC\x6F\x8F\xF9\x43\xBF\xFF\xD9"
            references.append(get_frame(ds.PixelData, 4, number_of_frames=10))
            assert references[-1][-10:] == b"\x68\xFA\x46\x3C\xF9\xC6\xBF\xFF\xD9\x00"
            references.append(get_frame(ds.PixelData, 9, number_of_frames=10))
            assert references[-1][-10:] == b"\xA5\x23\x00\x7B\xD9\x62\x13\x21\xFF\xD9"

        with open(JP2K_10FRAME_NOBOT, "rb") as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            # Start of BOT is at offset 2352
            mm.seek(elem.file_tell)
            # frame 9 (index 8) starts at offset 32802 and is 3754 bytes long
            frame = get_frame(mm, 0, number_of_frames=10)
            assert frame == references[0]
            frame = get_frame(mm, 4, number_of_frames=10)
            assert frame == references[1]
            frame = get_frame(mm, 9, number_of_frames=10)
            assert frame == references[2]


class TestBufferedFrame:
    """Tests for _BufferedItem"""

    def test_init(self):
        """Test creating a new instance"""
        # Even length frame
        b = BytesIO(b"\x00\x01" * 10)
        bf = _BufferedItem(b)
        assert bf.buffer == b
        assert bf.length == 28
        assert bf._item == b"\xFE\xFF\x00\xE0\x14\x00\x00\x00"
        assert not bf._padding

        # Odd-length frame gets padded
        b = BytesIO(b"\x00\x01\x02" * 3)
        bf = _BufferedItem(b)
        assert bf.buffer == b
        assert bf.length == 18
        assert bf._item == b"\xFE\xFF\x00\xE0\x0A\x00\x00\x00"
        assert bf._padding

    def test_read_even(self):
        """Test read() using an even length frame buffer"""
        b = BytesIO(b"\x00\x01" * 10)
        bf = _BufferedItem(b)
        out = bf.read(0, 8192)
        assert b.tell() == 0
        assert out[:8] == b"\xFE\xFF\x00\xE0\x14\x00\x00\x00"
        assert out[8:] == b"\x00\x01" * 10

        out = bf.read(1, 8192)
        assert b.tell() == 0
        assert out[:7] == b"\xFF\x00\xE0\x14\x00\x00\x00"
        assert out[7:] == b"\x00\x01" * 10

        # Offset at end of item value
        out = bf.read(7, 8192)
        assert b.tell() == 0
        assert out[:1] == b"\x00"
        assert out[1:] == b"\x00\x01" * 10

        # Offset at start of frame buffer
        out = bf.read(8, 8192)
        assert b.tell() == 0
        assert out == b"\x00\x01" * 10

        out = bf.read(9, 8192)
        assert b.tell() == 0
        assert out == b"\x01" + b"\x00\x01" * 9

        # Offset at end of frame buffer
        out = bf.read(27, 8192)
        assert b.tell() == 0
        assert out == b"\x01"

        # Offset invalid
        msg = r"Invalid 'start' value '28', must be in the closed interval \[0, 27\]"
        with pytest.raises(ValueError, match=msg):
            bf.read(28, 8192)

        msg = r"Invalid 'start' value '-1', must be in the closed interval \[0, 27\]"
        with pytest.raises(ValueError, match=msg):
            bf.read(-1, 8192)

    def test_read_odd(self):
        """Test read() using an odd length frame buffer"""
        b = BytesIO(b"\x01\x02" * 9 + b"\x01")
        assert len(b.getvalue()) % 2
        bf = _BufferedItem(b)
        out = bf.read(0, 8192)
        assert b.tell() == 0
        assert out[:8] == b"\xFE\xFF\x00\xE0\x14\x00\x00\x00"
        assert out[8:] == b"\x01\x02" * 9 + b"\x01\x00"

        out = bf.read(1, 8192)
        assert b.tell() == 0
        assert out[:7] == b"\xFF\x00\xE0\x14\x00\x00\x00"
        assert out[7:] == b"\x01\x02" * 9 + b"\x01\x00"

        # Offset at end of item value
        out = bf.read(7, 8192)
        assert b.tell() == 0
        assert out[:1] == b"\x00"
        assert out[1:] == b"\x01\x02" * 9 + b"\x01\x00"

        # Offset at start of frame buffer
        out = bf.read(8, 8192)
        assert b.tell() == 0
        assert out == b"\x01\x02" * 9 + b"\x01\x00"

        out = bf.read(9, 8192)
        assert b.tell() == 0
        assert out == b"\x02" + b"\x01\x02" * 8 + b"\x01\x00"

        # Offset at end of frame buffer
        out = bf.read(26, 8192)
        assert b.tell() == 0
        assert out == b"\x01\x00"

        # Offset at padding
        out = bf.read(27, 8192)
        assert b.tell() == 0
        assert out == b"\x00"

        # Offset invalid
        msg = r"Invalid 'start' value '28', must be in the closed interval \[0, 27\]"
        with pytest.raises(ValueError, match=msg):
            bf.read(28, 8192)

        msg = r"Invalid 'start' value '-1', must be in the closed interval \[0, 27\]"
        with pytest.raises(ValueError, match=msg):
            bf.read(-1, 8192)

    def test_read_partial_even(self):
        """Test partial read() using an even length frame buffer"""
        b = BytesIO(b"\x00\x01" * 10)
        bf = _BufferedItem(b)

        out = bf.read(0, size=0)
        assert out == b""

        out = bf.read(0, size=1)
        assert out == b"\xFE"

        out = bf.read(0, size=5)
        assert out == b"\xFE\xFF\x00\xE0\x14"

        out = bf.read(0, size=8)
        assert out[:8] == b"\xFE\xFF\x00\xE0\x14\x00\x00\x00"

        out = bf.read(0, size=9)
        assert out[:8] == b"\xFE\xFF\x00\xE0\x14\x00\x00\x00"
        assert out[8:] == b"\x00"

        out = bf.read(1, size=0)
        assert out[:7] == b""

        # Read to end of item value
        out = bf.read(1, size=7)
        assert out == b"\xFF\x00\xE0\x14\x00\x00\x00"

        # Read past end of item value
        out = bf.read(1, size=8)
        assert out[:7] == b"\xFF\x00\xE0\x14\x00\x00\x00"
        assert out[7:] == b"\x00"

        # Offset at end of item
        out = bf.read(7, size=0)
        assert out == b""

        out = bf.read(7, size=4)
        assert out == b"\x00\x00\x01\x00"

        # Offset at start of frame
        out = bf.read(8, size=5)
        assert out == b"\x00\x01\x00\x01\x00"

        # Offset at end of frame
        out = bf.read(27, size=1)
        assert out == b"\x01"

        # Offset invalid
        msg = r"Invalid 'start' value '28', must be in the closed interval \[0, 27\]"
        with pytest.raises(ValueError, match=msg):
            bf.read(28, size=0)

    def test_read_partial_odd(self):
        """Test partial read() using an odd length frame buffer"""
        b = BytesIO(b"\x01\x02" * 9 + b"\x01")
        assert len(b.getvalue()) % 2
        bf = _BufferedItem(b)

        # Offset at end of frame buffer
        out = bf.read(26, size=1)
        assert out == b"\x01"

        out = bf.read(26, size=2)
        assert out == b"\x01\x00"

        # Offset at padding
        out = bf.read(27, size=1)
        assert out == b"\x00"

        # Offset invalid
        msg = r"Invalid 'start' value '28', must be in the closed interval \[0, 27\]"
        with pytest.raises(ValueError, match=msg):
            bf.read(28, 2)

    def test_empty_buffer(self):
        """Test using an empty buffer"""
        bf = _BufferedItem(BytesIO())
        assert bf.length == 8
        out = bf.read(7, 10)
        assert out == b"\x00"

    def test_too_large_buffer_raises(self):
        """Test exception raised if the buffer is too large."""
        b = FooBuffer()
        b._tell = 2**32 - 1

        msg = "Buffers containing more than 4294967294 bytes are not supported"
        with pytest.raises(ValueError, match=msg):
            _BufferedItem(b)


class FooBuffer(BytesIO):
    _read = b""
    _readable = True
    _seekable = True
    _tell = 0

    def read(self, size):
        return self._read

    def readable(self):
        return self._readable

    def seek(self, offset, whence=0):
        return self._tell

    def seekable(self):
        return self._seekable

    def tell(self):
        return self._tell


class TestEncapsulatedBuffer:
    """Tests for EncapsulatedBuffer"""

    def test_init(self):
        """Test creating a new instance"""
        # Even length frame
        b = BytesIO(b"\x00\x01" * 10)
        eb = EncapsulatedBuffer([b])
        assert eb.encapsulated_length == 36

        msg = (
            "'buffers' must be a list of objects that inherit from 'io.BufferedIOBase'"
        )
        with pytest.raises(TypeError, match=msg):
            EncapsulatedBuffer(b)

    def test_bot_empty(self):
        """Test an empty Basic Offset Table"""
        b = BytesIO(b"\x00\x01" * 10)
        eb = EncapsulatedBuffer([b])
        bot = eb.basic_offset_table
        assert bot == b"\xFE\xFF\x00\xE0\x00\x00\x00\x00"

    def test_bot(self):
        """Test a non-empty Basic Offset Table"""
        eb = EncapsulatedBuffer([BytesIO(b"\xFF")], use_bot=True)
        bot = eb.basic_offset_table
        assert bot == b"\xFE\xFF\x00\xE0\x04\x00\x00\x00\x00\x00\x00\x00"

        eb = EncapsulatedBuffer([BytesIO(b"\xFF"), BytesIO(b"\xFE" * 99)], use_bot=True)
        bot = eb.basic_offset_table
        assert bot[:8] == b"\xFE\xFF\x00\xE0\x08\x00\x00\x00"
        assert bot[8:] == b"\x00\x00\x00\x00\x0A\x00\x00\x00"

        eb = EncapsulatedBuffer(
            [BytesIO(b"\xFF"), BytesIO(b"\xFE" * 99), BytesIO(b"\xFD" * 1024)],
            use_bot=True,
        )
        bot = eb.basic_offset_table
        assert bot[:8] == b"\xFE\xFF\x00\xE0\x0C\x00\x00\x00"
        assert bot[8:] == b"\x00\x00\x00\x00\x0A\x00\x00\x00\x76\x00\x00\x00"

        eb = EncapsulatedBuffer(
            [
                BytesIO(b"\xFF"),
                BytesIO(b"\xFE" * 99),
                BytesIO(b"\xFD" * 1024),
                BytesIO(b"\xFC" * 18),
            ],
            use_bot=True,
        )
        bot = eb.basic_offset_table
        assert bot[:8] == b"\xFE\xFF\x00\xE0\x10\x00\x00\x00"
        assert bot[8:] == (
            b"\x00\x00\x00\x00\x0A\x00\x00\x00\x76\x00\x00\x00\x7E\x04\x00\x00"
        )

    def test_closed(self):
        """Test the closed property"""
        b = BytesIO(b"\xFF")
        eb = EncapsulatedBuffer([b])
        assert not eb.closed

        b.close()
        assert eb.closed

        b = BytesIO(b"\xFF")
        c = BytesIO(b"\xFF")
        d = BytesIO(b"\xFF")
        e = BytesIO(b"\xFF")
        eb = EncapsulatedBuffer([b, c, d, e])
        assert not eb.closed

        e.close()
        assert eb.closed

    def test_seek_tell(self):
        """Test the seek() and tell() methods."""
        eb = EncapsulatedBuffer([BytesIO()])
        # os.SEEK_SET -> offset relative to start
        assert eb.tell() == 0
        assert eb.seek(0, 0) == 0
        assert eb.tell() == 0
        assert eb.seek(8, 0) == 8
        assert eb.tell() == 8
        assert eb.seek(23, 0) == 23
        assert eb.tell() == 23
        assert eb.seek(30, 0) == 30
        assert eb.tell() == 30

        msg = "Negative seek 'offset' value -1"
        with pytest.raises(ValueError, match=msg):
            eb.seek(-1, 0)

        # os.SEEK_CUR -> offset relative to current position
        eb.seek(0, 0)
        assert eb.seek(-1, 1) == 0
        assert eb.tell() == 0
        assert eb.seek(1, 1) == 1
        assert eb.tell() == 1
        eb.seek(0, 0)
        assert eb.seek(30, 1) == 30
        assert eb.tell() == 30

        assert eb.seek(0, 2) == 16
        assert eb.seek(0, 1) == 16
        assert eb.seek(-1, 1) == 15
        assert eb.seek(-15, 1) == 0
        assert eb.seek(-1, 1) == 0

        # os.SEEK_END -> offset relative to end
        assert eb.seek(0, 2) == 16
        assert eb.tell() == 16
        assert eb.seek(-7, 2) == 9
        assert eb.tell() == 9
        assert eb.seek(-15, 2) == 1
        assert eb.seek(-16, 2) == 0
        assert eb.seek(-17, 2) == 0

        msg = "Invalid 'whence' value, should be 0, 1 or 2"
        with pytest.raises(ValueError, match=msg):
            eb.seek(0, 3)

        with pytest.raises(ValueError, match=msg):
            eb.seek(0, -1)

    def test_lengths(self):
        """Test the lengths property"""
        assert EncapsulatedBuffer([BytesIO()]).lengths == [8]
        assert EncapsulatedBuffer([BytesIO(), BytesIO()]).lengths == [8, 8]

        assert EncapsulatedBuffer([BytesIO(b"\x00")]).lengths == [10]
        assert EncapsulatedBuffer([BytesIO(b"\x00\x01")]).lengths == [10]

        assert EncapsulatedBuffer([BytesIO(b"\x00"), BytesIO(b"\x00\x01")]).lengths == [
            10,
            10,
        ]

        assert EncapsulatedBuffer(
            [BytesIO(b"\x00\x01" * 150), BytesIO(b"\x02\x03\x04\x05")]
        ).lengths == [308, 12]
        assert EncapsulatedBuffer(
            [
                BytesIO(b"\x00\x01" * 150),
                BytesIO(b"\x02\x03\x04\x05"),
                BytesIO(b"\x00\x01\x02" * 111),
            ]
        ).lengths == [308, 12, 342]

    def test_offsets(self):
        """Test the offsets property"""
        assert EncapsulatedBuffer([BytesIO()]).offsets == [0]
        assert EncapsulatedBuffer([BytesIO(), BytesIO()]).offsets == [0, 8]

        assert EncapsulatedBuffer([BytesIO(b"\x00")]).offsets == [0]
        assert EncapsulatedBuffer([BytesIO(b"\x00\x01")]).offsets == [0]

        assert EncapsulatedBuffer([BytesIO(b"\x00"), BytesIO(b"\x00\x01")]).offsets == [
            0,
            10,
        ]

        assert EncapsulatedBuffer(
            [BytesIO(b"\x00\x01" * 150), BytesIO(b"\x02\x03\x04\x05")]
        ).offsets == [0, 308]
        assert EncapsulatedBuffer(
            [
                BytesIO(b"\x00\x01" * 150),
                BytesIO(b"\x02\x03\x04\x05"),
                BytesIO(b"\x00\x01\x02" * 111),
            ]
        ).offsets == [0, 308, 320]

    def test_encapsulated_length_empty_bot(self):
        """Test the encapsulated_length property with an empty BOT"""
        assert EncapsulatedBuffer([BytesIO()]).encapsulated_length == 16
        assert EncapsulatedBuffer([BytesIO(), BytesIO()]).encapsulated_length == 24

        assert EncapsulatedBuffer([BytesIO(b"\x00")]).encapsulated_length == 18
        assert EncapsulatedBuffer([BytesIO(b"\x00\x01")]).encapsulated_length == 18

        assert (
            EncapsulatedBuffer(
                [BytesIO(b"\x00"), BytesIO(b"\x00\x01")]
            ).encapsulated_length
            == 28
        )

        assert (
            EncapsulatedBuffer(
                [BytesIO(b"\x00\x01" * 150), BytesIO(b"\x02\x03\x04\x05")]
            ).encapsulated_length
            == 328
        )
        assert (
            EncapsulatedBuffer(
                [
                    BytesIO(b"\x00\x01" * 150),
                    BytesIO(b"\x02\x03\x04\x05"),
                    BytesIO(b"\x00\x01\x02" * 111),
                ]
            ).encapsulated_length
            == 670
        )

    def test_encapsulated_length_bot(self):
        """Test the encapsulated_length property with an empty BOT"""
        # BOT adds 4 bytes per item
        assert EncapsulatedBuffer([BytesIO()], True).encapsulated_length == 16 + 4
        assert (
            EncapsulatedBuffer([BytesIO(), BytesIO()], True).encapsulated_length
            == 24 + 8
        )

        assert (
            EncapsulatedBuffer([BytesIO(b"\x00")], True).encapsulated_length == 18 + 4
        )
        assert (
            EncapsulatedBuffer([BytesIO(b"\x00\x01")], True).encapsulated_length
            == 18 + 4
        )

        assert (
            EncapsulatedBuffer(
                [BytesIO(b"\x00"), BytesIO(b"\x00\x01")], True
            ).encapsulated_length
            == 28 + 8
        )

        assert (
            EncapsulatedBuffer(
                [BytesIO(b"\x00\x01" * 150), BytesIO(b"\x02\x03\x04\x05")], True
            ).encapsulated_length
            == 328 + 8
        )
        assert (
            EncapsulatedBuffer(
                [
                    BytesIO(b"\x00\x01" * 150),
                    BytesIO(b"\x02\x03\x04\x05"),
                    BytesIO(b"\x00\x01\x02" * 111),
                ],
                True,
            ).encapsulated_length
            == 670 + 12
        )

    def test_read(self):
        """Test read()"""
        b = BytesIO(b"\x01\x02" * 10)
        eb = EncapsulatedBuffer([b])
        assert eb.encapsulated_length == 36

        out = eb.read(8)
        assert out == b"\xFE\xFF\x00\xE0\x00\x00\x00\x00"

        eb.seek(0)
        out = eb.read(8192)
        assert len(out) == 36
        # Basic Offset Table with no values
        assert out[:8] == b"\xFE\xFF\x00\xE0\x00\x00\x00\x00"
        # Encapsulated buffer item
        assert out[8:] == b"\xFE\xFF\x00\xE0\x14\x00\x00\x00" + b"\x01\x02" * 10
        assert eb.tell() == 36

        eb = EncapsulatedBuffer(
            [
                BytesIO(b"\x00\x01" * 150),
                BytesIO(b"\x02\x03\x04\x05"),
                BytesIO(b"\x06\x07\x08" * 111),
            ],
        )
        assert eb.encapsulated_length == 670
        assert eb.read(6) == b"\xFE\xFF\x00\xE0\x00\x00"
        assert eb.tell() == 6
        # End of first item tag, first item tag, start of first item value
        assert eb.read(13) == (
            b"\x00\x00" + b"\xFE\xFF\x00\xE0\x2C\x01\x00\x00" + b"\x00\x01\x00"
        )
        assert eb.tell() == 19
        eb.read(294)
        assert eb.tell() == 313
        # End of first item value, second item tag, start of second item value
        assert eb.read(12) == (
            b"\x01\x00\x01" + b"\xFE\xFF\x00\xE0\x04\x00\x00\x00" + b"\x02"
        )
        assert eb.tell() == 325
        # End of second item value, third item tag, start of third item value
        assert eb.read(12) == (
            b"\x03\x04\x05" + b"\xFE\xFF\x00\xE0\x4E\x01\x00\x00" + b"\x06"
        )
        assert eb.tell() == 337
        eb.read(108)
        assert eb.tell() == 445
        # End of third item value, sequence delimiter item
        out = eb.read()
        assert out[222:] == b"\x07\x08\x00"
        assert eb.tell() == 670

        assert eb.read() == b""
        assert eb.tell() == 670

        eb.seek(445, 0)
        out = eb.read()
        assert out[222:] == b"\x07\x08\x00"
        assert eb.tell() == 670

    def test_read_none(self):
        """Test read() when no data available from the buffer."""
        b = FooBuffer()
        b._tell = 20
        eb = EncapsulatedBuffer([b])
        assert eb.encapsulated_length == 36

        # Start of FooBuffer's data
        eb.seek(16)
        assert eb.read(20) == b""

    def test_readable(self):
        """Test readable()"""
        assert EncapsulatedBuffer([BytesIO(b"\x01\x02" * 10)]).readable()

        b = FooBuffer()
        c = FooBuffer()
        d = FooBuffer()
        eb = EncapsulatedBuffer([b, c, d])
        assert eb.readable()
        c._readable = False
        assert not eb.readable()

    def test_seekable(self):
        """Test seekable()"""
        assert EncapsulatedBuffer([BytesIO(b"\x01\x02" * 10)]).seekable()

        b = FooBuffer()
        c = FooBuffer()
        d = FooBuffer()
        eb = EncapsulatedBuffer([b, c, d])
        assert eb.seekable()
        c._seekable = False
        assert not eb.seekable()

    def test_extended_lengths(self):
        """Test the extended_lengths property"""
        eb = EncapsulatedBuffer([BytesIO()])
        assert eb.extended_lengths == b"\x00" * 8
        eb = EncapsulatedBuffer([BytesIO(), BytesIO()])
        assert eb.extended_lengths == b"\x00" * 16
        eb = EncapsulatedBuffer([BytesIO(b"\x00"), BytesIO()])
        assert eb.extended_lengths == b"\x02" + b"\x00" * 15
        eb = EncapsulatedBuffer(
            [
                BytesIO(b"\x00\x01" * 150),
                BytesIO(b"\x02\x03\x04\x05"),
                BytesIO(b"\x00\x01\x02" * 111),
            ],
        )
        out = eb.extended_lengths
        assert out[:8] == b"\x2C\x01" + b"\x00" * 6
        assert out[8:16] == b"\x04" + b"\x00" * 7
        assert out[16:] == b"\x4E\x01" + b"\x00" * 6

    def test_extended_offsets(self):
        """Test the extended_offsets property"""
        eb = EncapsulatedBuffer([BytesIO()])
        assert eb.extended_offsets == b"\x00" * 8
        eb = EncapsulatedBuffer([BytesIO(), BytesIO()])
        assert eb.extended_offsets == b"\x00" * 8 + b"\x08" + b"\x00" * 7
        eb = EncapsulatedBuffer([BytesIO(b"\x00"), BytesIO()])
        assert eb.extended_offsets == b"\x00" * 8 + b"\x0A" + b"\x00" * 7
        eb = EncapsulatedBuffer(
            [
                BytesIO(b"\x00\x01" * 150),
                BytesIO(b"\x02\x03\x04\x05"),
                BytesIO(b"\x00\x01\x02" * 111),
                BytesIO(b"\x00\x01\x02" * 5),
            ],
        )
        out = eb.extended_offsets
        assert out[:8] == b"\x00" * 8
        assert out[8:16] == b"\x34\x01" + b"\x00" * 6
        assert out[16:24] == b"\x40\x01" + b"\x00" * 6
        assert out[24:] == b"\x96\x02" + b"\x00" * 6


class TestEncapsulateBufferFunc:
    """Test encaps.encapsulate_buffer."""

    def test_encapsulate_single_fragment_per_frame_no_bot(self):
        """Test encapsulating single fragment per frame with no BOT values."""
        ds = dcmread(JP2K_10FRAME_NOBOT)
        frames = [
            BytesIO(f)
            for f in generate_frames(ds.PixelData, number_of_frames=ds.NumberOfFrames)
        ]
        assert len(frames) == 10

        data = encapsulate_buffer(frames, has_bot=False)
        assert isinstance(data, EncapsulatedBuffer)
        test_frames = generate_frames(data, number_of_frames=ds.NumberOfFrames)
        for a, b in zip(test_frames, frames):
            assert a == b.getvalue()

        # Original data has no BOT values
        data.seek(0)
        assert b"".join(read_buffer(data)) == ds.PixelData

    def test_encapsulate_single_fragment_per_frame_bot(self):
        """Test encapsulating single fragment per frame with BOT values."""
        ds = dcmread(JP2K_10FRAME_NOBOT)
        frames = [
            BytesIO(f)
            for f in generate_frames(ds.PixelData, number_of_frames=ds.NumberOfFrames)
        ]
        assert len(frames) == 10

        data = encapsulate_buffer(frames, has_bot=True)
        test_frames = generate_frames(data, number_of_frames=ds.NumberOfFrames)
        for a, b in zip(test_frames, frames):
            assert a == b.getvalue()

        data.seek(0)
        fp = DicomBytesIO(b"".join(read_buffer(data)))
        fp.is_little_endian = True
        offsets = parse_basic_offsets(fp)
        assert offsets == [
            0x0000,  # 0
            0x0EEE,  # 3822
            0x1DF6,  # 7670
            0x2CF8,  # 11512
            0x3BFC,  # 15356
            0x4ADE,  # 19166
            0x59A2,  # 22946
            0x6834,  # 26676
            0x76E2,  # 30434
            0x8594,  # 34196
        ]

    def test_encapsulate_bot(self):
        """Test the Basic Offset Table is correct."""
        ds = dcmread(JP2K_10FRAME_NOBOT)
        frames = [
            BytesIO(f)
            for f in generate_frames(ds.PixelData, number_of_frames=ds.NumberOfFrames)
        ]
        assert len(frames) == 10

        data = encapsulate_buffer(frames, has_bot=True)
        assert data.read(56) == (
            b"\xfe\xff\x00\xe0"  # Basic offset table item tag
            b"\x28\x00\x00\x00"  # Basic offset table length
            b"\x00\x00\x00\x00"  # First offset
            b"\xee\x0e\x00\x00"
            b"\xf6\x1d\x00\x00"
            b"\xf8\x2c\x00\x00"
            b"\xfc\x3b\x00\x00"
            b"\xde\x4a\x00\x00"
            b"\xa2\x59\x00\x00"
            b"\x34\x68\x00\x00"
            b"\xe2\x76\x00\x00"
            b"\x94\x85\x00\x00"  # Last offset
            b"\xfe\xff\x00\xe0"  # Next item tag
            b"\xe6\x0e\x00\x00"  # Next item length
        )

    def test_encapsulate_bot_large_raises(self):
        """Test exception raised if too much pixel data for BOT."""

        class FakeBytes(bytes):
            length = -1

            def __len__(self):
                return self.length

            def __getitem__(self, s):
                return b"\x00" * 5

        frame_a = FakeBytes()
        frame_a.length = 2**32 - 1 - 8  # 8 for first BOT item tag/length
        frame_b = FakeBytes()
        frame_b.length = 10
        encapsulate([frame_a, frame_b], has_bot=True)

        frame_a.length = 2**32 - 1 - 7
        msg = (
            r"The total length of the encapsulated frame data \(4294967296 "
            r"bytes\) will be greater than the maximum allowed by the Basic "
        )
        with pytest.raises(ValueError, match=msg):
            encapsulate([frame_a, frame_b], has_bot=True)


class TestEncapsulateExtendedBuffer:
    """Tests for encaps.encapsulate_extended_buffer."""

    def test_encapsulate(self):
        ds = dcmread(JP2K_10FRAME_NOBOT)
        frames = [
            BytesIO(f)
            for f in generate_frames(ds.PixelData, number_of_frames=ds.NumberOfFrames)
        ]
        assert len(frames) == 10

        out = encapsulate_extended_buffer(frames)
        # Pixel Data encapsulated OK
        assert isinstance(out[0], EncapsulatedBuffer)
        test_frames = [
            f for f in generate_frames(out[0], number_of_frames=ds.NumberOfFrames)
        ]
        for a, b in zip(test_frames, frames):
            assert a == b.getvalue()

        # Extended Offset Table is OK
        assert isinstance(out[1], bytes)
        assert [
            0x0000,  # 0
            0x0EEE,  # 3822
            0x1DF6,  # 7670
            0x2CF8,  # 11512
            0x3BFC,  # 15356
            0x4ADE,  # 19166
            0x59A2,  # 22946
            0x6834,  # 26676
            0x76E2,  # 30434
            0x8594,  # 34196
        ] == list(unpack("<10Q", out[1]))

        # Extended Offset Table Lengths are OK
        assert isinstance(out[2], bytes)
        assert [len(f.getvalue()) for f in frames] == list(unpack("<10Q", out[2]))

    def test_encapsulate_odd_length(self):
        """Test encapsulating odd-length frames"""
        frames = [b"\x00", b"\x01", b"\x02"]
        eot_encapsulated, eot, eot_lengths = encapsulate_extended(frames)
        assert unpack(f"<{len(frames)}Q", eot) == (0, 10, 20)
        assert unpack(f"<{len(frames)}Q", eot_lengths) == (2, 2, 2)


@pytest.fixture
def use_future():
    original = config._use_future
    config._use_future = True
    yield
    config._use_future = original


class TestFuture:
    def test_imports_raise(self, use_future):
        with pytest.raises(ImportError):
            from pydicom.encaps import generate_pixel_data_fragment

        with pytest.raises(ImportError):
            from pydicom.encaps import get_frame_offsets

        with pytest.raises(ImportError):
            from pydicom.encaps import get_nr_fragments

        with pytest.raises(ImportError):
            from pydicom.encaps import generate_pixel_data_frame

        with pytest.raises(ImportError):
            from pydicom.encaps import generate_pixel_data

        with pytest.raises(ImportError):
            from pydicom.encaps import decode_data_sequence

        with pytest.raises(ImportError):
            from pydicom.encaps import defragment_data

        with pytest.raises(ImportError):
            from pydicom.encaps import read_item
