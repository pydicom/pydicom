"""Test the pillow decoder."""

import importlib

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

try:
    from PIL import Image, features
except ImportError:
    pass

from pydicom import dcmread
from pydicom.encaps import encapsulate, get_frame
from pydicom.pixels import get_decoder, convert_color_space
from pydicom.pixels.decoders.pillow import is_available
from pydicom.pixels.utils import unpack_bits, _get_jpg_parameters
from pydicom.uid import (
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEG2000Lossless,
    JPEG2000,
)

from .pixels_reference import (
    PIXEL_REFERENCE,
    J2KR_08_08_3_0_1F_YBR_RCT,
    JPGB_08_08_3_0_1F_RGB,  # has RGB component IDs
    JPGB_08_08_3_0_1F_YBR_FULL,  # has JFIF APP marker
    J2KR_16_10_1_0_1F_M1,
    JPGB_08_08_3_0_1F_RGB_APP14,  # Adobe APP14 in RGB
    J2KR_16_13_1_1_1F_M2_MISMATCH,  # Pixel Representation mismatch to J2K codestream
    J2KR_1_1_3F,
    J2KR_1_1_3F_NONALIGNED,
)


HAVE_PILLOW = bool(importlib.util.find_spec("PIL"))
HAVE_LJ = features.check_codec("jpg") if HAVE_PILLOW else False
HAVE_OJ = features.check_codec("jpg_2000") if HAVE_PILLOW else False

SKIP_LJ = not (HAVE_NP and HAVE_LJ)
SKIP_OJ = not (HAVE_NP and HAVE_OJ)


def name(ref):
    return f"{ref.name}"


def test_is_available_unknown_uid():
    """Test is_available() for an unknown UID"""
    assert is_available("1.2.3.4") is False


@pytest.mark.skipif(SKIP_LJ, reason="Test is missing dependencies")
class TestLibJpegDecoder:
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGBaseline8Bit], ids=name)
    def test_jpg_baseline(self, reference):
        """Test the decoder with JPEGBaseline8Bit."""
        decoder = get_decoder(JPEGBaseline8Bit)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="pillow")
        reference.test(arr, plugin="pillow")
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGExtended12Bit], ids=name)
    def test_jpg_extended(self, reference):
        """Test the decoder with JPEGExtended12Bit."""
        decoder = get_decoder(JPEGExtended12Bit)
        if reference.ds.BitsStored == 12:
            msg = (
                "Unable to decode as exceptions were raised by all available "
                "plugins:\n  pillow: Pillow does not support 'JPEG Extended' "
                "for samples with 12-bit precision"
            )
            with pytest.raises(RuntimeError, match=msg):
                decoder.as_array(reference.ds, decoding_plugin="pillow")
        else:
            arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="pillow")
            reference.test(arr)
            assert arr.shape == reference.shape
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

    def test_rgb_component_ids(self):
        """Test decoding an incorrect photometric interpretation using CIDs."""
        decoder = get_decoder(JPEGBaseline8Bit)
        reference = JPGB_08_08_3_0_1F_RGB
        msg = (
            r"The \(0028,0004\) 'Photometric Interpretation' value is "
            "'YBR_FULL_422' however the encoded image codestream for frame 0 uses "
            "component IDs that indicate it may be 'RGB'"
        )
        ds = dcmread(reference.path)
        ds.PhotometricInterpretation = "YBR_FULL_422"
        with pytest.warns(UserWarning, match=msg):
            arr, meta = decoder.as_array(ds, raw=True, decoding_plugin="pillow")

        reference.test(arr, plugin="pylibjpeg")
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable
        assert meta["photometric_interpretation"] == "RGB"

    def test_jfif(self):
        """Test decoding an incorrect photometric interpretation using JFIF."""
        decoder = get_decoder(JPEGBaseline8Bit)
        reference = JPGB_08_08_3_0_1F_YBR_FULL
        msg = (
            r"The \(0028,0004\) 'Photometric Interpretation' value is "
            "'RGB' however the encoded image codestream for frame 0 contains a JFIF "
            "APP marker which indicates it may be 'YBR_FULL_422'"
        )
        ds = dcmread(reference.path)
        ds.PhotometricInterpretation = "RGB"
        with pytest.warns(UserWarning, match=msg):
            arr, meta = decoder.as_array(ds, raw=True, decoding_plugin="pillow")

        reference.test(arr, plugin="pillow")
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable
        assert meta["photometric_interpretation"] == "YBR_FULL_422"

    def test_adobe_color_space(self):
        """Test color space conversions if Adobe APP14 is present."""
        reference = JPGB_08_08_3_0_1F_RGB_APP14
        ds = dcmread(reference.path)
        decoder = get_decoder(JPEGBaseline8Bit)

        # Color space is in RGB so no transform needed
        assert ds.PhotometricInterpretation == "RGB"
        arr, meta = decoder.as_array(ds, raw=True, decoding_plugin="pillow")
        reference.test(arr, plugin="pillow")
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable
        assert meta["photometric_interpretation"] == "RGB"

        # Again, no conversion should be applied as already RGB
        arr, meta = decoder.as_array(ds, raw=False, decoding_plugin="pillow")
        reference.test(arr, plugin="pillow")
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable
        assert meta["photometric_interpretation"] == "RGB"

        ds.PhotometricInterpretation = "YBR_FULL"
        msg = "contains an Adobe APP14 marker which indicates it may be 'RGB'"
        with pytest.warns(UserWarning, match=msg):
            arr, meta = decoder.as_array(ds, raw=True, decoding_plugin="pillow")

        # Change apparent color space to YCbCr
        codestream = bytearray(get_frame(ds.PixelData, 0, number_of_frames=1))
        codestream[17] = 1
        ds.PixelData = encapsulate([codestream])
        ds.PhotometricInterpretation = "RGB"

        msg = "contains an Adobe APP14 marker which indicates it may be 'YBR_FULL_422'"
        with pytest.warns(UserWarning, match=msg):
            arr, meta = decoder.as_array(ds, raw=True, decoding_plugin="pillow")

        # No conversion should be used with raw=True so should match reference
        assert meta["photometric_interpretation"] == "YBR_FULL_422"
        reference.test(arr, plugin="pillow")
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        # With raw=False Pillow should apply a YCbCr -> RGB conversion
        ref = convert_color_space(arr, "YBR_FULL", "RGB")
        with pytest.warns(UserWarning, match=msg):
            arr, meta = decoder.as_array(ds, raw=False, decoding_plugin="pillow")

        assert meta["photometric_interpretation"] == "RGB"
        assert np.allclose(arr, ref, atol=1)

    def test_no_adobe_app_marker(self):
        """Test color space conversions without an Adobe APP14 marker."""
        reference = JPGB_08_08_3_0_1F_RGB_APP14
        ds = dcmread(reference.path)
        ref = ds.pixel_array
        codestream = b"\xff\xd8" + get_frame(ds.PixelData, 0, number_of_frames=1)[18:]
        meta = _get_jpg_parameters(codestream)
        assert "app" not in meta
        ds.PixelData = encapsulate([codestream])

        # Original is in RGB, but we want it to do a conversion
        ds.PhotometricInterpretation = "YBR_FULL"
        decoder = get_decoder(JPEGBaseline8Bit)
        arr, meta = decoder.as_array(ds, decoding_plugin="pillow")
        assert meta["photometric_interpretation"] == "RGB"
        assert np.allclose(arr, convert_color_space(ref, "YBR_FULL", "RGB"), atol=1)

        # If raw=True do no conversion
        arr, meta = decoder.as_array(ds, raw=True, decoding_plugin="pillow")
        assert meta["photometric_interpretation"] == "YBR_FULL"
        assert np.array_equal(arr, ref)

    def test_no_markers_but_pi_rgb_defaults_to_ybr_full_422(self):
        """If no APP markers and dataset PI is RGB, default to YBR_FULL_422.

        This simulates a common real-world case where the DICOM's
        PhotometricInterpretation is incorrectly set to RGB while the
        JPEG Baseline codestream is actually YCbCr with no APP hints.
        Raw decode should report YBR_FULL_422 PI, and non-raw should
        convert to RGB by default (as_rgb=True).
        """
        reference = JPGB_08_08_3_0_1F_RGB_APP14
        ds = dcmread(reference.path)

        # Strip APP markers by skipping initial segments up to the SOF
        codestream = b"\xff\xd8" + get_frame(ds.PixelData, 0, number_of_frames=1)[18:]
        meta = _get_jpg_parameters(codestream)
        assert "app" not in meta
        ds.PixelData = encapsulate([codestream])

        # Incorrectly mark dataset as RGB (common issue in the wild)
        ds.PhotometricInterpretation = "RGB"

        decoder = get_decoder(JPEGBaseline8Bit)

        # Raw decode should not convert; PI should default to YBR_FULL_422 now
        arr_raw, meta_raw = decoder.as_array(ds, raw=True, decoding_plugin="pillow")
        assert meta_raw["photometric_interpretation"] == "YBR_FULL_422"

        # Non-raw decode (default as_rgb=True) should convert to RGB
        arr_rgb, meta_rgb = decoder.as_array(ds, decoding_plugin="pillow")
        assert meta_rgb["photometric_interpretation"] == "RGB"
        # Validate conversion numerically against converting raw ourselves
        ref_rgb = convert_color_space(arr_raw, "YBR_FULL", "RGB")
        assert np.allclose(arr_rgb, ref_rgb, atol=1)


@pytest.mark.skipif(SKIP_OJ, reason="Test is missing dependencies")
class TestOpenJpegDecoder:
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEG2000Lossless], ids=name)
    def test_j2k_lossless(self, reference):
        """Test the decoder with JPEG2000Lossless."""
        decoder = get_decoder(JPEG2000Lossless)
        if reference == J2KR_08_08_3_0_1F_YBR_RCT:
            msg = (
                "Unable to decode as exceptions were raised by all available "
                "plugins:\n  pillow: broken data stream when reading image file"
            )
            with pytest.raises(RuntimeError, match=msg):
                decoder.as_array(reference.ds, raw=True, decoding_plugin="pillow")
        else:
            arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="pillow")
            reference.test(arr)
            assert arr.shape == reference.shape
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEG2000], ids=name)
    def test_j2k(self, reference):
        """Test the decoder with JPEG2000."""
        decoder = get_decoder(JPEG2000)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="pillow")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    def test_u4_raises(self):
        """Test decoding greyscale with bits stored > 16 raises exception."""
        decoder = get_decoder(JPEG2000Lossless)
        ds = dcmread(J2KR_08_08_3_0_1F_YBR_RCT.path)
        # Manually edit the precision in the J2K codestream
        data = bytearray(ds.PixelData)
        data[1716:1717] = b"\x10"
        ds.PixelData = bytes(data)

        msg = (
            "Unable to decode as exceptions were raised by all available plugins:\n"
            r"  pillow: only \(0028,0101\) 'Bits Stored' values of up "
            "to 16 are supported"
        )
        with pytest.raises(RuntimeError, match=msg):
            decoder.as_array(ds, decoding_plugin="pillow")

    def test_multisample_16bit_raises(self):
        """Test that > 8-bit RGB datasets raise exception"""
        decoder = get_decoder(JPEG2000Lossless)
        ds = J2KR_16_10_1_0_1F_M1.ds

        msg = (
            "Unable to decode as exceptions were raised by all available plugins:\n"
            r"  pillow: Pillow cannot decode 10-bit multi-sample data correctly"
        )
        with pytest.raises(RuntimeError, match=msg):
            decoder.as_array(
                ds,
                decoding_plugin="pillow",
                samples_per_pixel=3,
                planar_configuration=0,
            )

    def test_j2k_sign_correction_indexed(self):
        """Test that sign correction works as expected with `index`"""
        reference = J2KR_16_13_1_1_1F_M2_MISMATCH
        decoder = get_decoder(JPEG2000Lossless)
        arr, meta = decoder.as_array(reference.ds, index=0, decoding_plugin="pillow")
        reference.test(arr)
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    def test_j2k_sign_correction_iter(self):
        """Test that sign correction works as expected with iter_array()"""
        reference = J2KR_16_13_1_1_1F_M2_MISMATCH
        decoder = get_decoder(JPEG2000Lossless)
        for arr, _ in decoder.iter_array(reference.ds, decoding_plugin="pillow"):
            reference.test(arr)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

    @pytest.mark.parametrize("path", [J2KR_1_1_3F.path, J2KR_1_1_3F_NONALIGNED.path])
    def test_j2k_singlebit_as_buffer(self, path):
        """Test retrieving buffers from single bit J2K."""
        ds = dcmread(path)
        arr = ds.pixel_array
        n_pixels_per_frame = ds.Rows * ds.Columns
        n_pixels = n_pixels_per_frame * ds.NumberOfFrames

        decoder = get_decoder(JPEG2000Lossless)
        buffer, meta = decoder.as_buffer(ds, decoding_plugin="pillow")
        unpacked_buffer = unpack_bits(buffer)[:n_pixels]
        assert np.array_equal(unpacked_buffer, arr.flatten())

        for index in range(ds.NumberOfFrames):
            buffer, meta = decoder.as_buffer(ds, decoding_plugin="pillow", index=index)
            unpacked_buffer = unpack_bits(buffer)[:n_pixels_per_frame]
            assert np.array_equal(unpacked_buffer, arr[index].flatten())
