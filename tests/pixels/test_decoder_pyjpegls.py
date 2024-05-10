"""Test the pyjpegls decoder."""

import importlib

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom.pixels import get_decoder
from pydicom.uid import JPEGLSLossless, JPEGLSNearLossless

from .pixels_reference import PIXEL_REFERENCE, JLSN_08_01_1_0_1F


HAVE_PYJPEGLS = bool(importlib.util.find_spec("jpeg_ls"))
SKIP_TEST = not HAVE_NP or not HAVE_PYJPEGLS


def name(ref):
    return f"{ref.name}"


@pytest.mark.skipif(SKIP_TEST, reason="Test is missing dependencies")
class TestPyJpegLSDecoder:
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLSLossless], ids=name)
    def test_jls_lossless(self, reference):
        """Test the decoder with JPEGLSLossless."""
        decoder = get_decoder(JPEGLSLossless)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="pyjpegls")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLSNearLossless], ids=name)
    def test_jls_lossy(self, reference):
        """Test the decoder with JPEGLSNearLossless."""
        decoder = get_decoder(JPEGLSNearLossless)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="pyjpegls")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    def test_bits_allocated_mismatch_as_array(self):
        """Test the result when bits stored <= 8 and bits allocated 16"""
        # The JPEG-LS codestream uses a precision of 8, so it will return
        #   8-bit values, however the decoding process nominally expects 16-bit
        decoder = get_decoder(JPEGLSNearLossless)
        arr, meta = decoder.as_array(
            JLSN_08_01_1_0_1F.ds,
            raw=True,
            decoding_plugin="pyjpegls",
            bits_allocated=16,
        )
        JLSN_08_01_1_0_1F.test(arr)
        assert arr.shape == JLSN_08_01_1_0_1F.shape
        assert arr.dtype != JLSN_08_01_1_0_1F.dtype
        assert arr.dtype == np.uint16
        assert arr.flags.writeable
        assert meta["bits_allocated"] == 16
        assert meta["bits_stored"] == 8

    def test_bits_allocated_mismatch_as_buffer(self):
        """Test the result when bits stored <= 8 and bits allocated 16"""
        decoder = get_decoder(JPEGLSNearLossless)
        ds = JLSN_08_01_1_0_1F.ds
        buffer, meta = decoder.as_buffer(
            ds,
            raw=True,
            decoding_plugin="pyjpegls",
            bits_allocated=16,
        )
        assert ds.BitsStored == 8
        assert len(buffer) == ds.Rows * ds.Columns * ds.SamplesPerPixel
        arr = np.frombuffer(buffer, dtype="u1")
        arr = arr.reshape((ds.Rows, ds.Columns))
        JLSN_08_01_1_0_1F.test(arr)
        assert arr.shape == JLSN_08_01_1_0_1F.shape
        # as_buffer() returns container sized to codestream precision
        assert meta["bits_allocated"] == 8
        assert meta["bits_stored"] == 8
