"""Test the GDCM decoder."""

import importlib
import logging

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom import dcmread
from pydicom.pixels import get_decoder
from pydicom.pixels.utils import _passes_version_check
from pydicom.uid import (
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEGLossless,
    JPEGLosslessSV1,
    JPEGLSLossless,
    JPEGLSNearLossless,
    JPEG2000Lossless,
    JPEG2000,
)

from .pixels_reference import (
    PIXEL_REFERENCE,
    JPGE_BAD,
    J2KR_16_13_1_1_1F_M2_MISMATCH,
    JLSN_08_01_1_0_1F,
    JLSL_08_07_1_0_1F,
    JPGB_08_08_3_0_1F_RGB,  # has RGB component IDs
    JPGB_08_08_3_0_1F_YBR_FULL,  # has JFIF APP marker
)


HAVE_GDCM = bool(importlib.util.find_spec("gdcm"))
SKIP_TEST = not HAVE_NP or not HAVE_GDCM


def name(ref):
    return f"{ref.name}"


@pytest.mark.skipif(SKIP_TEST, reason="Test is missing dependencies")
class TestDecoding:
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGBaseline8Bit], ids=name)
    def test_jpg_baseline(self, reference):
        """Test the decoder with JPEGBaseline8Bit."""
        decoder = get_decoder(JPEGBaseline8Bit)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="gdcm")
        reference.test(arr, plugin="gdcm")
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
                "plugins:\n  gdcm: GDCM does not support 'JPEG Extended' for samples "
                "with 12-bit precision"
            )
            with pytest.raises(RuntimeError, match=msg):
                decoder.as_array(reference.ds, decoding_plugin="gdcm")
        else:
            arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="gdcm")
            reference.test(arr)
            assert arr.shape == reference.shape
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLossless], ids=name)
    def test_jpg_lossless(self, reference):
        """Test the decoder with JPEGLossless."""
        decoder = get_decoder(JPEGLossless)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="gdcm")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLosslessSV1], ids=name)
    def test_jpg_lossless_sv1(self, reference):
        """Test the decoder with JPEGLosslessSV1."""
        decoder = get_decoder(JPEGLosslessSV1)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="gdcm")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLSLossless], ids=name)
    def test_jls_lossless(self, reference):
        """Test the decoder with JPEGLSLossless."""
        decoder = get_decoder(JPEGLSLossless)
        if reference == JLSL_08_07_1_0_1F:
            msg = (
                "Unable to decode as exceptions were raised by all available "
                "plugins:\n  gdcm: Unable to decode unsigned JPEG-LS pixel "
                "data with a sample precision of 6 or 7"
            )
            with pytest.raises(RuntimeError, match=msg):
                decoder.as_array(reference.ds, raw=True, decoding_plugin="gdcm")
        else:
            arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="gdcm")
            reference.test(arr)
            assert arr.shape == reference.shape
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLSNearLossless], ids=name)
    def test_jls_lossy(self, reference):
        """Test the decoder with JPEGLSNearLossless."""
        decoder = get_decoder(JPEGLSNearLossless)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="gdcm")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEG2000Lossless], ids=name)
    def test_j2k_lossless(self, reference):
        """Test the decoder with JPEG2000Lossless."""
        decoder = get_decoder(JPEG2000Lossless)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="gdcm")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEG2000], ids=name)
    def test_j2k(self, reference):
        """Test the decoder with JPEG2000."""
        decoder = get_decoder(JPEG2000)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="gdcm")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    def test_bits_allocated_mismatch(self):
        """Test the result when bits stored <= 8 and bits allocated 16"""
        # The JPEG-LS codestream uses a precision of 8, so it will return
        #   8-bit values, however the decoding process nominally expects 16-bit
        decoder = get_decoder(JPEGLSNearLossless)
        arr, _ = decoder.as_array(
            JLSN_08_01_1_0_1F.ds,
            raw=True,
            decoding_plugin="gdcm",
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
        buffer, meta = decoder.as_buffer(
            ds,
            raw=True,
            decoding_plugin="gdcm",
            bits_allocated=16,
        )
        assert ds.BitsStored == 8
        assert len(buffer) == ds.Rows * ds.Columns * ds.SamplesPerPixel
        arr = np.frombuffer(buffer, dtype="u1")
        arr = arr.reshape((ds.Rows, ds.Columns))
        JLSN_08_01_1_0_1F.test(arr)
        assert arr.shape == JLSN_08_01_1_0_1F.shape
        assert meta["bits_allocated"] == 8

    def test_jls_lossy_signed_raises(self):
        """Test decoding JPEG-LS signed with < 8-bits raises."""
        decoder = get_decoder(JPEGLSNearLossless)
        ds = JLSN_08_01_1_0_1F.ds

        msg = (
            "Unable to decode as exceptions were raised by all available plugins:\n  "
            "gdcm: Unable to decode signed lossy JPEG-LS pixel data with a sample "
            "precision less than 8 bits"
        )
        with pytest.raises(RuntimeError, match=msg):
            decoder.as_buffer(
                ds,
                raw=True,
                decoding_plugin="gdcm",
                bits_stored=7,
                pixel_representation=1,
            )

    def test_rgb_component_ids(self):
        """Test decoding an incorrect photometric interpretation using cIDs."""
        decoder = get_decoder(JPEGBaseline8Bit)
        reference = JPGB_08_08_3_0_1F_RGB
        msg = (
            r"The \(0028,0004\) 'Photometric Interpretation' value is "
            "'YBR_FULL_422' however the encoded image's codestream uses "
            "component IDs that indicate it should be 'RGB'"
        )
        ds = dcmread(reference.path)
        ds.PhotometricInterpretation = "YBR_FULL_422"
        with pytest.warns(UserWarning, match=msg):
            arr, meta = decoder.as_array(ds, raw=True, decoding_plugin="gdcm")

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
            "'RGB' however the encoded image's codestream contains a JFIF APP "
            "marker which indicates it should be 'YBR_FULL_422'"
        )
        ds = dcmread(reference.path)
        ds.PhotometricInterpretation = "RGB"
        with pytest.warns(UserWarning, match=msg):
            arr, meta = decoder.as_array(ds, raw=True, decoding_plugin="gdcm")

        reference.test(arr, plugin="pylibjpeg")
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable
        assert meta["photometric_interpretation"] == "YBR_FULL_422"


@pytest.mark.skipif(SKIP_TEST, reason="Test is missing dependencies")
def test_version_check(caplog):
    """Test _passes_version_check() when the package has no __version__"""
    # GDCM doesn't have a __version__ attribute
    with caplog.at_level(logging.ERROR, logger="pydicom"):
        assert _passes_version_check("gdcm", (3, 0)) is False
        assert "module 'gdcm' has no attribute '__version__'" in caplog.text
