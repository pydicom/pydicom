"""Test the pyjpegls decoder."""

# TODO: add near lossless dataset

import importlib

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom.pixels import get_decoder
from pydicom.uid import JPEGLSLossless, JPEGLSNearLossless

from .pixels_reference import PIXEL_REFERENCE


HAVE_PYJPEGLS = bool(importlib.util.find_spec("jpeg_ls"))
SKIP_TEST = not HAVE_NP or not HAVE_PYJPEGLS


@pytest.mark.skipif(SKIP_TEST, reason="Test is missing dependencies")
class TestPyJpegLSDecoder:
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLSLossless])
    def test_jls_lossless(self, reference):
        """Test the decoder with JPEGLSLossless."""
        decoder = get_decoder(JPEGLSLossless)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pyjpegls")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLSNearLossless])
    def test_jls_lossy(self, reference):
        """Test the decoder with JPEGLSNearLossless."""
        decoder = get_decoder(JPEGLSNearLossless)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pyjpegls")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable
