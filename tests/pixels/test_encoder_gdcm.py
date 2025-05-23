"""Tests for encoding pixel data with GDCM."""

import sys

import pytest

from pydicom import dcmread
from pydicom.data import get_testdata_file
from pydicom.pixels.encoders import RLELosslessEncoder
from pydicom.pixels.encoders.base import EncodeRunner
from pydicom.pixels.encoders.gdcm import _rle_encode as gdcm_rle_encode
from pydicom.pixels.decoders.native import _rle_decode_frame
from pydicom.pixels.utils import reshape_pixel_array, _convert_rle_endianness
from pydicom.uid import RLELossless, JPEG2000, ExplicitVRLittleEndian


try:
    import gdcm
    import numpy as np
    from gdcm import Version

    GDCM_VERSION = [int(c) for c in Version.GetVersion().split(".")]
    HAVE_GDCM = True
except ImportError:
    HAVE_GDCM = False
    GDCM_VERSION = [0, 0, 0]

# EXPL: Explicit VR Little Endian
EXPL_8_1_1F = get_testdata_file("OBXXXX1A.dcm")
EXPL_8_3_1F = get_testdata_file("SC_rgb.dcm")
EXPL_16_1_1F = get_testdata_file("MR_small.dcm")
EXPL_16_3_1F = get_testdata_file("SC_rgb_16bit.dcm")
EXPL_32_1_1F = get_testdata_file("rtdose_1frame.dcm")
EXPL_32_3_1F = get_testdata_file("SC_rgb_32bit.dcm")


@pytest.mark.skipif(not HAVE_GDCM, reason="GDCM plugin is not available")
class TestRLELossless:
    """Tests for encoding RLE Lossless."""

    def test_cycle_u8_1s_1f(self):
        """Test an encode/decode cycle for 8-bit 1 sample/pixel."""
        ds = dcmread(EXPL_8_1_1F)
        ref = ds.pixel_array
        assert ds.BitsAllocated == 8
        assert ds.SamplesPerPixel == 1
        assert ds.PixelRepresentation == 0
        assert ds.PhotometricInterpretation == "PALETTE COLOR"

        enc = RLELosslessEncoder
        encoded = enc.encode(ds, idx=0, encoding_plugin="gdcm")
        decoded = _rle_decode_frame(
            encoded, ds.Rows, ds.Columns, ds.SamplesPerPixel, ds.BitsAllocated
        )
        arr = np.frombuffer(decoded, "|u1")

        assert np.array_equal(ref.ravel(), arr)

    def test_cycle_u8_3s_1f(self):
        """Test an encode/decode cycle for 8-bit 3 sample/pixel."""
        ds = dcmread(EXPL_8_3_1F)
        ref = ds.pixel_array
        assert ds.BitsAllocated == 8
        assert ds.SamplesPerPixel == 3
        assert ds.PixelRepresentation == 0
        assert ds.PhotometricInterpretation == "RGB"
        assert ds.PlanarConfiguration == 0

        enc = RLELosslessEncoder
        encoded = enc.encode(ds, idx=0, encoding_plugin="gdcm")
        decoded = _rle_decode_frame(
            encoded, ds.Rows, ds.Columns, ds.SamplesPerPixel, ds.BitsAllocated
        )
        arr = np.frombuffer(decoded, "|u1")
        # The decoded data is planar configuration 1
        ds.PlanarConfiguration = 1
        arr = reshape_pixel_array(ds, arr)

        assert np.array_equal(ref, arr)

    def test_cycle_i16_1s_1f(self):
        """Test an encode/decode cycle for 16-bit 1 sample/pixel."""
        ds = dcmread(EXPL_16_1_1F)
        ref = ds.pixel_array
        assert ds.BitsAllocated == 16
        assert ds.SamplesPerPixel == 1
        assert ds.PixelRepresentation == 1
        assert ds.PhotometricInterpretation == "MONOCHROME2"

        enc = RLELosslessEncoder
        encoded = enc.encode(ds, idx=0, encoding_plugin="gdcm")
        decoded = _rle_decode_frame(
            encoded, ds.Rows, ds.Columns, ds.SamplesPerPixel, ds.BitsAllocated
        )

        arr = np.frombuffer(decoded, "<i2")
        arr = reshape_pixel_array(ds, arr)

        assert np.array_equal(ref, arr)

    def test_cycle_u16_3s_1f(self):
        """Test an encode/decode cycle for 16-bit 3 sample/pixel."""
        ds = dcmread(EXPL_16_3_1F)
        ref = ds.pixel_array
        assert ds.BitsAllocated == 16
        assert ds.SamplesPerPixel == 3
        assert ds.PixelRepresentation == 0
        assert ds.PhotometricInterpretation == "RGB"
        assert ds.PlanarConfiguration == 0

        enc = RLELosslessEncoder
        encoded = enc.encode(ds, idx=0, encoding_plugin="gdcm")
        decoded = _rle_decode_frame(
            encoded, ds.Rows, ds.Columns, ds.SamplesPerPixel, ds.BitsAllocated
        )
        arr = np.frombuffer(decoded, "<u2")
        # The decoded data is planar configuration 1
        ds.PlanarConfiguration = 1
        arr = reshape_pixel_array(ds, arr)

        assert np.array_equal(ref, arr)

    def test_cycle_u32_1s_1f(self):
        """Test an encode/decode cycle for 32-bit 1 sample/pixel."""
        ds = dcmread(EXPL_32_1_1F)
        ref = ds.pixel_array
        assert ds.BitsAllocated == 32
        assert ds.SamplesPerPixel == 1
        assert ds.PixelRepresentation == 0
        assert ds.PhotometricInterpretation == "MONOCHROME2"

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

        enc = RLELosslessEncoder
        encoded = enc.encode(
            ds.PixelData,
            encoding_plugin="gdcm",
            validate=False,
            **kwargs,
        )
        decoded = _rle_decode_frame(
            encoded, ds.Rows, ds.Columns, ds.SamplesPerPixel, ds.BitsAllocated
        )
        arr = np.frombuffer(decoded, "<u4")
        arr = reshape_pixel_array(ds, arr)

        assert np.array_equal(ref, arr)

    def test_cycle_u32_3s_1f(self):
        """Test an encode/decode cycle for 32-bit 3 sample/pixel."""
        ds = dcmread(EXPL_32_3_1F)
        ref = ds.pixel_array
        assert ds.BitsAllocated == 32
        assert ds.SamplesPerPixel == 3
        assert ds.PixelRepresentation == 0
        assert ds.PhotometricInterpretation == "RGB"
        assert ds.PlanarConfiguration == 0

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

        enc = RLELosslessEncoder
        encoded = enc.encode(
            ds.PixelData,
            encoding_plugin="gdcm",
            validate=False,
            **kwargs,
        )
        decoded = _rle_decode_frame(
            encoded, ds.Rows, ds.Columns, ds.SamplesPerPixel, ds.BitsAllocated
        )
        arr = np.frombuffer(decoded, "<u4")
        # The decoded data is planar configuration 1
        ds.PlanarConfiguration = 1
        arr = reshape_pixel_array(ds, arr)

        assert np.array_equal(ref, arr)

    def test_invalid_byteorder_raises(self):
        """Test that big endian source raises exception."""
        ds = dcmread(EXPL_8_1_1F)

        msg = (
            r"Unable to encode as exceptions were raised by all available "
            "plugins:\n  gdcm: Unsupported option \"byteorder = '>'\""
        )
        with pytest.raises(RuntimeError, match=msg):
            RLELosslessEncoder.encode(ds, encoding_plugin="gdcm", byteorder=">")

    def test_above_32bit_raises(self):
        """Test that > 32-bit Bits Allocated raises exception."""
        ds = dcmread(EXPL_8_1_1F)
        enc = RLELosslessEncoder
        kwargs = {
            "rows": ds.Rows,
            "columns": 100,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": ds.PixelRepresentation,
            "bits_allocated": 64,
            "bits_stored": ds.BitsStored,
            "number_of_frames": 1,
        }

        msg = (
            r"Unable to encode as exceptions were raised by all available "
            "plugins:\n  gdcm: Unable to encode more than 32-bit data"
        )
        with pytest.raises(RuntimeError, match=msg):
            enc.encode(ds.PixelData, encoding_plugin="gdcm", validate=False, **kwargs)

    def test_encoding_failure_raises(self):
        """Test that a encoding failure result raises an exception"""
        kwargs = {
            "rows": 1,
            "columns": 1,
            "samples_per_pixel": 1,
            "bits_allocated": 8,
            "bits_stored": 8,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "photometric_interpretation": "PALETTE COLOR",
            "transfer_syntax_uid": ExplicitVRLittleEndian,
        }
        runner = EncodeRunner(RLELossless)
        runner.set_options(**kwargs)
        msg = "Unexpected number of fragments found in the 'Pixel Data'"
        with pytest.raises(RuntimeError, match=msg):
            gdcm_rle_encode(b"\x00", runner)

    def test_no_sequence_raises(self):
        """Test that no sequence of fragments raises an exception"""
        kwargs = {
            "rows": 1,
            "columns": 1,
            "samples_per_pixel": 1,
            "bits_allocated": 8,
            "bits_stored": 8,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "photometric_interpretation": "PALETTE COLOR",
        }
        runner = EncodeRunner(JPEG2000)
        runner.set_options(**kwargs)
        msg = r"ImageChangeTransferSyntax.Change\(\) returned a failure result"
        with pytest.raises(RuntimeError, match=msg):
            gdcm_rle_encode(b"\x00", runner)

    def test_invalid_photometric_interpretation_raises(self):
        """Test an invalid photometric interpretation raises exception"""
        kwargs = {
            "rows": 1,
            "columns": 1,
            "samples_per_pixel": 1,
            "bits_allocated": 8,
            "bits_stored": 8,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "photometric_interpretation": "PALETTES COLOR",
        }
        runner = EncodeRunner(RLELossless)
        runner.set_options(**kwargs)
        msg = "Invalid photometric interpretation 'PALETTES COLOR'"
        with pytest.raises(ValueError, match=msg):
            gdcm_rle_encode(b"\x00", runner)

    @pytest.mark.skipif(sys.byteorder != "little", reason="Running on BE system")
    def test_endianness_conversion(self):
        """Test that the endianness is changed when required."""
        # Normally this would be on big endian systems, but we force it to happen
        #   on little endian so it can be covered by the tests
        ds = dcmread(EXPL_8_1_1F)

        kwargs = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "bits_allocated": ds.BitsAllocated,
            "bits_stored": ds.BitsStored,
            "pixel_representation": ds.PixelRepresentation,
            "number_of_frames": 1,
            "photometric_interpretation": ds.PhotometricInterpretation,
        }
        runner = EncodeRunner(RLELossless)
        runner.set_options(**kwargs)
        unconverted = gdcm_rle_encode(ds.PixelData, runner)

        def foo(*args, **kwargs):
            return True

        runner._test_for = foo
        converted = gdcm_rle_encode(ds.PixelData, runner)
        assert converted == _convert_rle_endianness(unconverted, 1, ">")
