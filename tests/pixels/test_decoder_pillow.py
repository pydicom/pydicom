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

from pydicom.encaps import get_frame
from pydicom.pixels import get_decoder
from pydicom.pixels.decoders.pillow import is_available
from pydicom.uid import (
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEG2000Lossless,
    JPEG2000,
)

from .pixels_reference import (
    PIXEL_REFERENCE,
    J2KR_08_08_3_0_1F_YBR_RCT,
    JPGB_08_08_3_0_1F_RGB,
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
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pillow")
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
            arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pillow")
            reference.test(arr)
            assert arr.shape == reference.shape
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable


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
            arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pillow")
            reference.test(arr)
            assert arr.shape == reference.shape
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEG2000], ids=name)
    def test_j2k(self, reference):
        """Test the decoder with JPEG2000."""
        decoder = get_decoder(JPEG2000)
        arr = decoder.as_array(reference.ds, raw=True, decoding_plugin="pillow")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable
