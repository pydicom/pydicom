"""Test the pylibjpeg decoder."""

import importlib

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom.encaps import get_frame
from pydicom.pixels import get_decoder
from pydicom.pixels.decoders.pylibjpeg import is_available
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
    JLSN_08_01_1_0_1F,
    JPGB_08_08_3_0_1F_RGB,  # has RGB component IDs
    JPGB_08_08_3_0_1F_YBR_FULL,  # has JFIF APP marker
)


HAVE_PYLJ = bool(importlib.util.find_spec("pylibjpeg"))
HAVE_LJ = bool(importlib.util.find_spec("libjpeg"))
HAVE_OJ = bool(importlib.util.find_spec("openjpeg"))
HAVE_RLE = bool(importlib.util.find_spec("rle"))

SKIP_LJ = not (HAVE_NP and HAVE_PYLJ and HAVE_LJ)
SKIP_OJ = not (HAVE_NP and HAVE_PYLJ and HAVE_OJ)
SKIP_RLE = not (HAVE_NP and HAVE_PYLJ and HAVE_RLE)


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

        if reference in (JPGB_08_08_3_0_1F_RGB, JPGB_08_08_3_0_1F_YBR_FULL):
            with pytest.warns(UserWarning):
                arr = decoder.as_array(
                    reference.ds, raw=True, decoding_plugin="pylibjpeg"
                )
        else:
            arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")

        reference.test(arr, plugin="pylibjpeg")
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGExtended12Bit], ids=name)
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

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLossless], ids=name)
    def test_jpg_lossless(self, reference):
        """Test the decoder with JPEGLossless."""
        decoder = get_decoder(JPEGLossless)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLosslessSV1], ids=name)
    def test_jpg_lossless_sv1(self, reference):
        """Test the decoder with JPEGLosslessSV1."""
        decoder = get_decoder(JPEGLosslessSV1)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLSLossless], ids=name)
    def test_jls_lossless(self, reference):
        """Test the decoder with JPEGLSLossless."""
        decoder = get_decoder(JPEGLSLossless)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLSNearLossless], ids=name)
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

    def test_bits_allocated_mismatch(self):
        """Test the result when bits stored <= 8 and bits allocated 16"""
        # The JPEG-LS codestream uses a precision of 8, so it will return
        #   8-bit values, however the decoding process nominally expects 16-bit
        decoder = get_decoder(JPEGLSNearLossless)
        arr = decoder.as_array(
            JLSN_08_01_1_0_1F.ds,
            raw=True,
            decoding_plugin="pylibjpeg",
            bits_allocated=16,
        )
        JLSN_08_01_1_0_1F.test(arr)
        assert arr.shape == JLSN_08_01_1_0_1F.shape
        assert arr.dtype != JLSN_08_01_1_0_1F.dtype
        assert arr.dtype == np.uint16
        assert arr.flags.writeable

    def test_bits_allocated_mismatch_as_buffer(self):
        """Test the result when bits stored <= 8 and bits allocated 16"""
        decoder = get_decoder(JPEGLSNearLossless)
        ds = JLSN_08_01_1_0_1F.ds
        buffer = decoder.as_buffer(
            ds,
            raw=True,
            decoding_plugin="pylibjpeg",
            bits_allocated=16,
        )
        assert ds.BitsStored == 8
        assert len(buffer) == ds.Rows * ds.Columns * ds.SamplesPerPixel
        arr = np.frombuffer(buffer, dtype="u1")
        arr = arr.reshape((ds.Rows, ds.Columns))
        JLSN_08_01_1_0_1F.test(arr)
        assert arr.shape == JLSN_08_01_1_0_1F.shape

    def test_rgb_component_ids(self):
        """Test decoding an incorrect photometric interpretation using cIDs."""
        decoder = get_decoder(JPEGBaseline8Bit)
        reference = JPGB_08_08_3_0_1F_RGB
        msg = (
            r"The \(0028,0004\) 'Photometric Interpretation' value is "
            "'YBR_FULL_422' however the encoded image's codestream uses "
            "component IDs that indicate it should be 'RGB'"
        )
        ds = reference.ds
        ds.PhotometricInterpretation = "YBR_FULL_422"
        with pytest.warns(UserWarning, match=msg):
            arr = decoder.as_array(ds, raw=True, decoding_plugin="pylibjpeg")

        reference.test(arr, plugin="pylibjpeg")
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    def test_jfif(self):
        """Test decoding an incorrect photometric interpretation using JFIF."""
        decoder = get_decoder(JPEGBaseline8Bit)
        reference = JPGB_08_08_3_0_1F_YBR_FULL
        msg = (
            r"The \(0028,0004\) 'Photometric Interpretation' value is "
            "'RGB' however the encoded image's codestream contains a JFIF APP "
            "marker which indicates it should be 'YBR_FULL_422'"
        )
        ds = reference.ds
        ds.PhotometricInterpretation = "RGB"
        with pytest.warns(UserWarning, match=msg):
            arr = decoder.as_array(ds, raw=True, decoding_plugin="pylibjpeg")

        reference.test(arr, plugin="pylibjpeg")
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable


@pytest.mark.skipif(SKIP_OJ, reason="Test is missing dependencies")
class TestOpenJpegDecoder:
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEG2000Lossless], ids=name)
    def test_j2k_lossless(self, reference):
        """Test the decoder with JPEG2000Lossless."""
        decoder = get_decoder(JPEG2000Lossless)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEG2000], ids=name)
    def test_j2k(self, reference):
        """Test the decoder with JPEG2000."""
        decoder = get_decoder(JPEG2000)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[HTJ2KLossless], ids=name)
    def test_htj2k_lossless(self, reference):
        """Test the decoder with HTJ2KLossless."""
        decoder = get_decoder(HTJ2KLossless)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[HTJ2KLosslessRPCL], ids=name)
    def test_htj2k_lossless_rpcl(self, reference):
        """Test the decoder with HTJ2KLosslessRPCL."""
        decoder = get_decoder(HTJ2KLosslessRPCL)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[HTJ2K], ids=name)
    def test_htj2k(self, reference):
        """Test the decoder with HTJ2K."""
        decoder = get_decoder(HTJ2K)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    def test_iter_array(self):
        """Test J2k corrections are applied when using iter_array()"""
        reference = J2KR_16_13_1_1_1F_M2_MISMATCH
        decoder = get_decoder(JPEG2000Lossless)
        # Using all frames
        frame_gen = decoder.iter_array(
            reference.ds, raw=True, decoding_plugin="pylibjpeg"
        )
        for arr in frame_gen:
            reference.test(arr)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

        # Using indices
        frame_gen = decoder.iter_array(
            reference.ds, raw=True, decoding_plugin="pylibjpeg", indices=[0]
        )
        for arr in frame_gen:
            reference.test(arr)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]


@pytest.mark.skipif(SKIP_RLE, reason="Test is missing dependencies")
class TestRleDecoder:
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[RLELossless], ids=name)
    def test_rle(self, reference):
        """Test the decoder with RLELossless."""
        decoder = get_decoder(RLELossless)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable
