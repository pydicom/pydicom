# Copyright 2008-2021 pydicom authors. See LICENSE file for details.
"""Tests for the 'pydicom' encoder plugin."""


import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom import dcmread, Dataset
from pydicom.data import get_testdata_file
from pydicom.dataset import FileMetaDataset
from pydicom.encaps import get_frame
from pydicom.pixels.encoders import RLELosslessEncoder
from pydicom.pixels.encoders.base import EncodeRunner
from pydicom.pixels.encoders.native import _encode_frame, _encode_segment, _encode_row
from pydicom.pixels.decoders.rle import _rle_decode_frame, _rle_decode_segment
from pydicom.pixels.utils import reshape_pixel_array
from pydicom.uid import RLELossless


# EXPL: Explicit VR Little Endian
# RLE: RLE Lossless
# 8/8-bit, 1 sample/pixel, 1 frame
EXPL_8_1_1F = get_testdata_file("OBXXXX1A.dcm")
RLE_8_1_1F = get_testdata_file("OBXXXX1A_rle.dcm")
# 8/8-bit, 3 sample/pixel, 1 frame
EXPL_8_3_1F = get_testdata_file("SC_rgb.dcm")
# 8/8-bit, 3 sample/pixel, 2 frame
EXPL_8_3_2F = get_testdata_file("SC_rgb_2frame.dcm")
# 16/16-bit, 1 sample/pixel, 1 frame
EXPL_16_1_1F = get_testdata_file("MR_small.dcm")
# 16/16-bit, 3 sample/pixel, 1 frame
EXPL_16_3_1F = get_testdata_file("SC_rgb_16bit.dcm")
# 32/32-bit, 1 sample/pixel, 1 frame
EXPL_32_1_1F = get_testdata_file("rtdose_1frame.dcm")
# 32/32-bit, 3 sample/pixel, 1 frame
EXPL_32_3_1F = get_testdata_file("SC_rgb_32bit.dcm")


# Tests for RLE encoding
REFERENCE_ENCODE_ROW = [
    # Input, output
    ([], b""),
    # Replicate run tests
    # 2 (min) replicate
    ([0] * 2, b"\xff\x00"),
    ([0] * 3, b"\xfe\x00"),
    ([0] * 64, b"\xc1\x00"),
    ([0] * 127, b"\x82\x00"),
    # 128 (max) replicate
    ([0] * 128, b"\x81\x00"),
    # 128 (max) replicate, 1 (min) literal
    ([0] * 129, b"\x81\x00\x00\x00"),
    # 128 (max) replicate, 2 (min) replicate
    ([0] * 130, b"\x81\x00\xff\x00"),
    # 128 (max) x 5 replicates
    ([0] * 128 * 5, b"\x81\x00" * 5),
    # Literal run tests
    # 1 (min) literal
    ([0], b"\x00\x00"),
    ([0, 1], b"\x01\x00\x01"),
    ([0, 1, 2], b"\x02\x00\x01\x02"),
    ([0, 1] * 32, b"\x3f" + b"\x00\x01" * 32),
    # 127 literal
    ([0, 1] * 63 + [2], b"\x7e" + b"\x00\x01" * 63 + b"\x02"),
    # 128 literal (max)
    ([0, 1] * 64, b"\x7f" + b"\x00\x01" * 64),
    # 128 (max) literal, 1 (min) literal
    ([0, 1] * 64 + [2], b"\x7f" + b"\x00\x01" * 64 + b"\x00\x02"),
    # 128 (max) x 5 literals
    ([0, 1] * 64 * 5, (b"\x7f" + b"\x00\x01" * 64) * 5),
    # Combination run tests
    # 1 (min) literal, 1 (min) replicate
    ([0, 1, 1], b"\x00\x00\xff\x01"),
    # 1 (min) literal, 128 (max) replicate
    ([0] + [1] * 128, b"\x00\x00\x81\x01"),
    # 128 (max) literal, 2 (min) replicate
    ([0, 1] * 64 + [2] * 2, b"\x7f" + b"\x00\x01" * 64 + b"\xff\x02"),
    # 128 (max) literal, 128 (max) replicate
    ([0, 1] * 64 + [2] * 128, b"\x7f" + b"\x00\x01" * 64 + b"\x81\x02"),
    # 2 (min) replicate, 1 (min) literal
    ([0, 0, 1], b"\xff\x00\x00\x01"),
    # 2 (min) replicate, 128 (max) literal
    ([0, 0] + [1, 2] * 64, b"\xff\x00\x7f" + b"\x01\x02" * 64),
    # 128 (max) replicate, 1 (min) literal
    ([0] * 128 + [1], b"\x81\x00\x00\x01"),
    # 128 (max) replicate, 128 (max) literal
    ([0] * 128 + [1, 2] * 64, b"\x81\x00\x7f" + b"\x01\x02" * 64),
]


class TestEncodeRow:
    """Tests for rle_handler._encode_row."""

    @pytest.mark.parametrize("src, output", REFERENCE_ENCODE_ROW)
    def test_encode(self, src, output):
        """Test encoding an empty row."""
        assert output == _encode_row(src)


@pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
class TestEncodeFrame:
    """Tests for rle_handler._encode_frame."""

    def setup_method(self):
        """Setup the tests."""
        # Create a dataset skeleton for use in the cycle tests
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2"
        ds.Rows = 2
        ds.Columns = 4
        ds.SamplesPerPixel = 3
        ds.PlanarConfiguration = 1
        self.ds = ds

    def test_cycle_8bit_1sample(self):
        """Test an encode/decode cycle for 8-bit 1 sample/pixel."""
        ds = dcmread(EXPL_8_1_1F)
        ref = ds.pixel_array
        assert 8 == ds.BitsAllocated
        assert 1 == ds.SamplesPerPixel

        kwargs = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": ds.PixelRepresentation,
            "bits_allocated": ds.BitsAllocated,
            "bits_stored": ds.BitsStored,
            "number_of_frames": 1,
        }
        runner = EncodeRunner(RLELossless)
        runner.set_options(**kwargs)

        encoded = _encode_frame(ds.PixelData, runner)
        decoded = _rle_decode_frame(
            encoded, ds.Rows, ds.Columns, ds.SamplesPerPixel, ds.BitsAllocated
        )
        arr = np.frombuffer(decoded, "|u1")
        arr = reshape_pixel_array(ds, arr)

        assert np.array_equal(ref, arr)

    def test_cycle_8bit_3sample(self):
        """Test an encode/decode cycle for 8-bit 3 sample/pixel."""
        ds = dcmread(EXPL_8_3_1F)
        ref = ds.pixel_array
        assert ds.BitsAllocated == 8
        assert ds.SamplesPerPixel == 3
        assert ds.PixelRepresentation == 0

        kwargs = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": ds.PixelRepresentation,
            "bits_allocated": ds.BitsAllocated,
            "bits_stored": ds.BitsStored,
            "number_of_frames": 1,
            "planar_configuration": ds.PlanarConfiguration,
        }
        runner = EncodeRunner(RLELossless)
        runner.set_options(**kwargs)

        encoded = _encode_frame(ds.PixelData, runner)
        decoded = _rle_decode_frame(
            encoded, ds.Rows, ds.Columns, ds.SamplesPerPixel, ds.BitsAllocated
        )
        # The decoded data is planar configuration 1
        ds.PlanarConfiguration = 1
        arr = np.frombuffer(decoded, "|u1")
        arr = reshape_pixel_array(ds, arr)

        assert np.array_equal(ref, arr)

    def test_cycle_16bit_1sample(self):
        """Test an encode/decode cycle for 16-bit 1 sample/pixel."""
        ds = dcmread(EXPL_16_1_1F)
        ref = ds.pixel_array
        assert 16 == ds.BitsAllocated
        assert 1 == ds.SamplesPerPixel

        kwargs = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": ds.PixelRepresentation,
            "bits_allocated": ds.BitsAllocated,
            "bits_stored": ds.BitsStored,
            "number_of_frames": 1,
        }
        runner = EncodeRunner(RLELossless)
        runner.set_options(**kwargs)

        encoded = _encode_frame(ds.PixelData, runner)
        decoded = _rle_decode_frame(
            encoded, ds.Rows, ds.Columns, ds.SamplesPerPixel, ds.BitsAllocated
        )
        arr = np.frombuffer(decoded, "<u2")
        arr = reshape_pixel_array(ds, arr)

        assert np.array_equal(ref, arr)

    def test_cycle_16bit_3sample(self):
        """Test an encode/decode cycle for 16-bit 3 sample/pixel."""
        ds = dcmread(EXPL_16_3_1F)
        ref = ds.pixel_array
        assert ds.BitsAllocated == 16
        assert ds.SamplesPerPixel == 3
        assert ds.PixelRepresentation == 0

        kwargs = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": ds.PixelRepresentation,
            "bits_allocated": ds.BitsAllocated,
            "bits_stored": ds.BitsStored,
            "number_of_frames": 1,
            "planar_configuration": ds.PlanarConfiguration,
        }
        runner = EncodeRunner(RLELossless)
        runner.set_options(**kwargs)

        encoded = _encode_frame(ds.PixelData, runner)
        decoded = _rle_decode_frame(
            encoded, ds.Rows, ds.Columns, ds.SamplesPerPixel, ds.BitsAllocated
        )
        # The decoded data is planar configuration 1
        ds.PlanarConfiguration = 1
        arr = np.frombuffer(decoded, "<u2")
        arr = reshape_pixel_array(ds, arr)

        assert np.array_equal(ref, arr)

    def test_cycle_32bit_1sample(self):
        """Test an encode/decode cycle for 32-bit 1 sample/pixel."""
        ds = dcmread(EXPL_32_1_1F)
        ref = ds.pixel_array
        assert 32 == ds.BitsAllocated
        assert 1 == ds.SamplesPerPixel

        kwargs = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": ds.PixelRepresentation,
            "bits_allocated": ds.BitsAllocated,
            "bits_stored": ds.BitsStored,
            "number_of_frames": 1,
        }
        runner = EncodeRunner(RLELossless)
        runner.set_options(**kwargs)

        encoded = _encode_frame(ds.PixelData, runner)
        decoded = _rle_decode_frame(
            encoded, ds.Rows, ds.Columns, ds.SamplesPerPixel, ds.BitsAllocated
        )
        arr = np.frombuffer(decoded, "<u4")
        arr = reshape_pixel_array(ds, arr)

        assert np.array_equal(ref, arr)

    def test_cycle_32bit_3sample(self):
        """Test an encode/decode cycle for 32-bit 3 sample/pixel."""
        ds = dcmread(EXPL_32_3_1F)
        ref = ds.pixel_array
        assert ds.BitsAllocated == 32
        assert ds.SamplesPerPixel == 3
        assert ds.PixelRepresentation == 0

        kwargs = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": ds.PixelRepresentation,
            "bits_allocated": ds.BitsAllocated,
            "bits_stored": ds.BitsStored,
            "number_of_frames": 1,
            "planar_configuration": ds.PlanarConfiguration,
        }
        runner = EncodeRunner(RLELossless)
        runner.set_options(**kwargs)

        encoded = _encode_frame(ds.PixelData, runner)
        decoded = _rle_decode_frame(
            encoded, ds.Rows, ds.Columns, ds.SamplesPerPixel, ds.BitsAllocated
        )
        # The decoded data is planar configuration 1
        ds.PlanarConfiguration = 1
        arr = np.frombuffer(decoded, "<u4")
        arr = reshape_pixel_array(ds, arr)

        assert np.array_equal(ref, arr)

    def test_16_segments_raises(self):
        """Test trying to encode more than 15 segments raises exception."""
        arr = np.asarray(
            [[[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]]], dtype="uint8"
        )
        assert (1, 1, 16) == arr.shape
        assert 1 == arr.dtype.itemsize

        kwargs = {
            "rows": 1,
            "columns": 1,
            "samples_per_pixel": 16,
            "bits_allocated": 8,
        }
        runner = EncodeRunner(RLELossless)
        runner.set_options(**kwargs)

        msg = (
            r"Unable to encode as the DICOM standard only allows "
            r"a maximum of 15 segments in RLE encoded data"
        )
        with pytest.raises(ValueError, match=msg):
            _encode_frame(arr.tobytes(), runner)

    def test_15_segment(self):
        """Test encoding 15 segments works as expected."""
        arr = np.asarray(
            [[[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]]], dtype="uint8"
        )
        assert (1, 1, 15) == arr.shape
        assert 1 == arr.dtype.itemsize

        kwargs = {
            "rows": 1,
            "columns": 1,
            "samples_per_pixel": 15,
            "bits_allocated": 8,
        }
        runner = EncodeRunner(RLELossless)
        runner.set_options(**kwargs)

        encoded = _encode_frame(arr.tobytes(), runner)
        header = (
            b"\x0f\x00\x00\x00"
            b"\x40\x00\x00\x00"
            b"\x42\x00\x00\x00"
            b"\x44\x00\x00\x00"
            b"\x46\x00\x00\x00"
            b"\x48\x00\x00\x00"
            b"\x4a\x00\x00\x00"
            b"\x4c\x00\x00\x00"
            b"\x4e\x00\x00\x00"
            b"\x50\x00\x00\x00"
            b"\x52\x00\x00\x00"
            b"\x54\x00\x00\x00"
            b"\x56\x00\x00\x00"
            b"\x58\x00\x00\x00"
            b"\x5a\x00\x00\x00"
            b"\x5c\x00\x00\x00"
        )
        assert header == encoded[:64]
        assert (
            b"\x00\x01\x00\x02\x00\x03\x00\x04\x00\x05\x00\x06"
            b"\x00\x07\x00\x08\x00\x09\x00\x0a\x00\x0b\x00\x0c"
            b"\x00\x0d\x00\x0e\x00\x0f"
        ) == encoded[64:]

    def test_single_row_1sample(self):
        """Test encoding a single row of 1 sample/pixel data."""
        # Rows 1, Columns 5, SamplesPerPixel 1
        arr = np.asarray([[0, 1, 2, 3, 4]], dtype="uint8")
        kwargs = {
            "rows": 1,
            "columns": 5,
            "samples_per_pixel": 1,
            "bits_allocated": 8,
        }
        runner = EncodeRunner(RLELossless)
        runner.set_options(**kwargs)

        encoded = _encode_frame(arr.tobytes(), runner)
        header = b"\x01\x00\x00\x00\x40\x00\x00\x00" + b"\x00" * 56
        assert header == encoded[:64]
        assert b"\x04\x00\x01\x02\x03\x04" == encoded[64:]

    def test_single_row_3sample(self):
        """Test encoding a single row of 3 samples/pixel data."""
        # Rows 1, Columns 5, SamplesPerPixel 3
        arr = np.asarray(
            [[[0, 0, 0], [1, 1, 1], [2, 2, 2], [3, 3, 3], [4, 4, 4]]], dtype="uint8"
        )
        assert (1, 5, 3) == arr.shape
        kwargs = {
            "rows": 1,
            "columns": 5,
            "samples_per_pixel": 3,
            "bits_allocated": 8,
        }
        runner = EncodeRunner(RLELossless)
        runner.set_options(**kwargs)

        encoded = _encode_frame(arr.tobytes(), runner)
        header = (
            b"\x03\x00\x00\x00"
            b"\x40\x00\x00\x00"
            b"\x46\x00\x00\x00"
            b"\x4c\x00\x00\x00"
        )
        header += b"\x00" * (64 - len(header))
        assert header == encoded[:64]
        assert (
            b"\x04\x00\x01\x02\x03\x04"
            b"\x04\x00\x01\x02\x03\x04"
            b"\x04\x00\x01\x02\x03\x04"
        ) == encoded[64:]

    def test_invalid_byteorder_raises(self):
        """Test big endian `src` raises an exception."""
        kwargs = {
            "rows": 1,
            "columns": 5,
            "samples_per_pixel": 3,
            "bits_allocated": 8,
            "byteorder": ">",
        }
        runner = EncodeRunner(RLELossless)
        runner.set_options(**kwargs)

        msg = r"Unsupported option \"byteorder = '>'\""
        with pytest.raises(ValueError, match=msg):
            _encode_frame(b"", runner)


class TestEncodeSegment:
    """Tests for rle_handler._encode_segment."""

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_one_row(self):
        """Test encoding data that contains only a single row."""
        ds = dcmread(RLE_8_1_1F)
        pixel_data = get_frame(ds.PixelData, 0)
        decoded = _rle_decode_segment(pixel_data[64:])
        assert ds.Rows * ds.Columns == len(decoded)
        arr = np.frombuffer(decoded, "uint8").reshape(ds.Rows, ds.Columns)

        # Re-encode a single row of the decoded data
        row = arr[0]
        assert (ds.Columns,) == row.shape
        encoded = _encode_segment(row.tobytes(), columns=ds.Columns)

        # Decode the re-encoded data and check that it's the same
        redecoded = _rle_decode_segment(encoded)
        assert ds.Columns == len(redecoded)
        assert decoded[: ds.Columns] == redecoded

    def test_cycle(self):
        """Test the decoded data remains the same after encoding/decoding."""
        ds = dcmread(RLE_8_1_1F)
        pixel_data = get_frame(ds.PixelData, 0)
        decoded = _rle_decode_segment(pixel_data[64:])
        assert ds.Rows * ds.Columns == len(decoded)
        # Re-encode the decoded data
        encoded = _encode_segment(decoded, columns=ds.Columns)

        # Decode the re-encoded data and check that it's the same
        redecoded = _rle_decode_segment(encoded)
        assert ds.Rows * ds.Columns == len(redecoded)
        assert decoded == redecoded
