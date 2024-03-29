# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Tests for the pixel_data_handlers.util module."""

from sys import byteorder

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom.pixel_data_handlers.util import dtype_corrected_for_endianness


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestNumpy_DtypeCorrectedForEndianness:
    """Tests for util.dtype_corrected_for_endianness."""

    def test_byte_swapping(self):
        """Test that the endianness of the system is taken into account."""
        # The main problem is that our testing environments are probably
        #   all little endian, but we'll try our best
        dtype = np.dtype("uint16")

        # < is little, = is native, > is big
        if byteorder == "little":
            out = dtype_corrected_for_endianness(True, dtype)
            assert out.byteorder in ["<", "="]
            out = dtype_corrected_for_endianness(False, dtype)
            assert out.byteorder == ">"
        elif byteorder == "big":
            out = dtype_corrected_for_endianness(True, dtype)
            assert out.byteorder == "<"
            out = dtype_corrected_for_endianness(False, dtype)
            assert out.byteorder in [">", "="]

    def test_no_endian_raises(self):
        """Test that an unset endianness raises exception."""
        with pytest.raises(ValueError, match="attribute 'is_little_endian' has"):
            dtype_corrected_for_endianness(None, None)
