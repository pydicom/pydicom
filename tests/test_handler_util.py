# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Tests for the pixel_data_handlers.util module."""

from sys import byteorder

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom import config

with pytest.warns(DeprecationWarning):
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


def test_deprecation_warnings():
    msg = (
        "The 'pydicom.pixel_data_handlers' module will be removed in v4.0, "
        "please use 'from pydicom.pixels import convert_color_space' instead"
    )
    with pytest.warns(DeprecationWarning, match=msg):
        from pydicom.pixel_data_handlers import convert_color_space

    with pytest.warns(DeprecationWarning, match=msg):
        from pydicom.pixel_data_handlers.util import convert_color_space as x

    msg = (
        "The 'pydicom.pixel_data_handlers' module will be removed in v4.0, "
        "please use 'from pydicom.pixels.utils import expand_ybr422' instead"
    )
    with pytest.warns(DeprecationWarning, match=msg):
        from pydicom.pixel_data_handlers import expand_ybr422

    with pytest.warns(DeprecationWarning, match=msg):
        from pydicom.pixel_data_handlers.util import expand_ybr422 as y

    msg = "'dtype_corrected_for_endianness' is deprecated and will be removed in v4.0"
    with pytest.warns(DeprecationWarning, match=msg):
        from pydicom.pixel_data_handlers.util import dtype_corrected_for_endianness


@pytest.fixture
def use_future():
    original = config._use_future
    config._use_future = True
    yield
    config._use_future = original


class TestFuture:
    def test_imports_raise(self, use_future):
        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers import apply_color_lut as x

        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers.util import apply_color_lut

        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers.util import apply_modality_lut

        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers.util import apply_voi_lut

        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers.util import apply_voi

        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers.util import apply_windowing

        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers.util import convert_color_space

        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers import expand_ybr422 as y

        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers.util import expand_ybr422

        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers.util import get_expected_length

        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers.util import get_image_pixel_ids

        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers.util import get_j2k_parameters

        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers.util import get_nr_frames

        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers.util import pack_bits

        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers.util import pixel_dtype

        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers.util import reshape_pixel_array

        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers.util import unpack_bits

        with pytest.raises(ImportError):
            from pydicom.pixel_data_handlers.util import dtype_corrected_for_endianness
