"""Tests for encoding pixel data with pylibjpeg."""

import importlib

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom import dcmread
from pydicom.data import get_testdata_file
from pydicom.pixel_data_handlers.util import get_expected_length
from pydicom.uid import RLELossless


HAVE_PYLJ = bool(importlib.util.find_spec("pylibjpeg"))
HAVE_LJ = bool(importlib.util.find_spec("libjpeg"))
HAVE_OJ = bool(importlib.util.find_spec("openjpeg"))
HAVE_RLE = bool(importlib.util.find_spec("rle"))

SKIP_RLE = not (HAVE_NP and HAVE_PYLJ and HAVE_RLE)
SKIP_J2K = not (HAVE_NP and HAVE_PYLJ and HAVE_OJ)

IMPL = get_testdata_file("MR_small_implicit.dcm")
EXPL = get_testdata_file("OBXXXX1A.dcm")


@pytest.mark.skipif(SKIP_RLE, reason="no -rle plugin")
class TestRLEEncoding:
    def test_encode(self):
        """Test encoding"""
        ds = dcmread(EXPL)
        assert "PlanarConfiguration" not in ds
        expected = get_expected_length(ds, "bytes")
        assert expected == len(ds.PixelData)
        ref = ds.pixel_array
        del ds.PixelData
        del ds._pixel_array
        ds.compress(RLELossless, ref, encoding_plugin="pylibjpeg")
        assert expected > len(ds.PixelData)
        assert np.array_equal(ref, ds.pixel_array)
        assert ref is not ds.pixel_array

    def test_encode_big(self):
        """Test encoding big-endian src"""
        ds = dcmread(IMPL)
        ref = ds.pixel_array
        del ds._pixel_array
        ds.compress(
            RLELossless, ds.PixelData, byteorder=">", encoding_plugin="pylibjpeg"
        )
        assert np.array_equal(ref.newbyteorder(">"), ds.pixel_array)
        assert ref is not ds.pixel_array
