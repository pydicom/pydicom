"""Test the pylibjpeg decoder."""

# TODO: Add test datasets for HTJ2K

import importlib

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom.encaps import get_frame
from pydicom.pixels import get_decoder
from pydicom.uid import (
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEGLossless,
    JPEGLosslessSV1,
    JPEGLSLossless,
    JPEGLSNearLossless,
    JPEG2000Lossless,
    JPEG2000,
    HTJ2KLossless,
    HTJ2KLosslessRPCL,
    HTJ2K,
    RLELossless,
)
from pydicom.pixel_data_handlers.util import get_j2k_parameters

from .pixels_reference import (
    PIXEL_REFERENCE,
    JPGE_BAD,
    J2KR_16_13_1_1_1F_M2_MISMATCH,
)


HAVE_PYLJ = bool(importlib.util.find_spec("pylibjpeg"))
HAVE_LJ = bool(importlib.util.find_spec("libjpeg"))
HAVE_OJ = bool(importlib.util.find_spec("openjpeg"))
HAVE_RLE = bool(importlib.util.find_spec("rle"))

SKIP_LJ = not (HAVE_NP and HAVE_PYLJ and HAVE_LJ)
SKIP_OJ = not (HAVE_NP and HAVE_PYLJ and HAVE_OJ)
SKIP_RLE = not (HAVE_NP and HAVE_PYLJ and HAVE_RLE)


@pytest.mark.skipif(SKIP_LJ, reason="Test is missing dependencies")
class TestLibJpegDecoder:
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGBaseline8Bit])
    def test_jpg_baseline(self, reference):
        """Test the decoder with JPEGBaseline8Bit."""
        decoder = get_decoder(JPEGBaseline8Bit)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGExtended12Bit])
    def test_jpg_extended(self, reference):
        """Test the decoder with JPEGExtended12Bit."""
        # Invalid spectrum end value, decode fails
        if reference.name == "JPEG-lossy.dcm":
            return

        decoder = get_decoder(JPEGExtended12Bit)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLossless])
    def test_jpg_lossless(self, reference):
        """Test the decoder with JPEGLossless."""
        decoder = get_decoder(JPEGLossless)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLosslessSV1])
    def test_jpg_lossless_sv1(self, reference):
        """Test the decoder with JPEGLosslessSV1."""
        decoder = get_decoder(JPEGLosslessSV1)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLSLossless])
    def test_jls_lossless(self, reference):
        """Test the decoder with JPEGLSLossless."""
        decoder = get_decoder(JPEGLSLossless)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLSNearLossless])
    def test_jls_lossy(self, reference):
        """Test the decoder with JPEGLSNearLossless."""
        decoder = get_decoder(JPEGLSNearLossless)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    def test_jpg_extended_invalid_se_raises(self):
        """Test invalid scan stop raises an exception."""
        decoder = get_decoder(JPEGExtended12Bit)
        msg = (
            "Unable to decode as exceptions were raised by all available "
            "plugins:\n  pylibjpeg: libjpeg error code '-1038' returned "
            r"from Decode\(\): A misplaced marker segment was found - scan "
            "start must be zero and scan stop must be 63 for the sequential "
            "operating modes"
        )
        with pytest.raises(RuntimeError, match=msg):
            decoder.as_array(JPGE_BAD.ds, decoding_plugin="pylibjpeg")


@pytest.mark.skipif(SKIP_OJ, reason="Test is missing dependencies")
class TestOpenJpegDecoder:
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEG2000Lossless])
    def test_j2k_lossless(self, reference):
        """Test the decoder with JPEG2000Lossless."""
        decoder = get_decoder(JPEG2000Lossless)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEG2000])
    def test_j2k(self, reference):
        """Test the decoder with JPEG2000."""
        decoder = get_decoder(JPEG2000)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[HTJ2KLossless])
    def test_htj2k_lossless(self, reference):
        """Test the decoder with HTJ2KLossless."""
        decoder = get_decoder(HTJ2KLossless)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[HTJ2KLosslessRPCL])
    def test_htj2k_lossless_rpcl(self, reference):
        """Test the decoder with HTJ2KLosslessRPCL."""
        decoder = get_decoder(HTJ2KLosslessRPCL)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[HTJ2K])
    def test_htj2k(self, reference):
        """Test the decoder with HTJ2K."""
        decoder = get_decoder(HTJ2K)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable


@pytest.mark.skipif(SKIP_RLE, reason="Test is missing dependencies")
class TestRleDecoder:
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[RLELossless])
    def test_rle(self, reference):
        """Test the decoder with RLELossless."""
        decoder = get_decoder(RLELossless)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable
