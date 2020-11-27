# Copyright 2020 pydicom authors. See LICENSE file for details.
"""Tests for the reading large values through memmap."""

import pytest

from pydicom import config, dcmread
from pydicom.data import get_testdata_file

try:
    import numpy as np
    from pydicom.pixel_data_handlers import numpy_handler as NP_HANDLER
    HAVE_NP = True
except ImportError:
    NP_HANDLER = None
    HAVE_NP = False


@pytest.fixture(scope="function")
def memmap_setter(request):
    orig_memmap_size = config._memmap_size
    orig_memmap_read_only = config._memmap_read_only
    config.memmap_size("20KB")
    config.memmap_read_only(True)
    yield
    config.memmap_size(orig_memmap_size)
    config.memmap_read_only(orig_memmap_read_only)


@pytest.mark.skipif(not HAVE_NP, reason='numpy not available')
class TestMemmap:
    """Tests for handling memmap'd data element values"""
    def test_no_memmap(self):
        fn = get_testdata_file("CT_small.dcm")
        ds = dcmread(fn)
        pix_data = ds.PixelData
        assert isinstance(pix_data, bytes)
        assert 175 == pix_data[0]
        assert 3 == pix_data[-1]


    def test_read_memmapd_pixels(self, memmap_setter):
        """Check that a memmap is returned and gives correct values"""
        fn = get_testdata_file("CT_small.dcm")
        ds = dcmread(fn)
        pix_data = ds.PixelData
        assert isinstance(pix_data, np.memmap)
        assert 32768 == len(pix_data)
        assert 175 == pix_data[0]
        assert 0 == pix_data[1]
        assert 3 == pix_data[-1]

        # Check converting to pixel_array still works
        #  last value different than because 2-byte values
        pix_arr = ds.pixel_array
        assert 175 == pix_arr[0][0]
        assert 909 == pix_arr[-1][-1]