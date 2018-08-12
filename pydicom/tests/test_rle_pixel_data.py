# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Tests for the pixel_data_handlers.rle_handler module.

There are the following possibilities:

* numpy is not available and the RLE handler is not available
* numpy is available and

  * The RLE handler is not available
  * The RLE handler is available

**Supported transfer syntaxes**

* 1.2.840.10008.1.2.5 : RLE Lossless

**Elements affecting the handler**

* BitsAllocated (1, 8, 16, 32, ...)
* SamplesPerPixel (1, 2, 3, ...)
* NumberOfFrames (1, 2, ...)
"""

import os
import sys

import pytest

from pydicom import dcmread
import pydicom.config
from pydicom.data import get_testdata_files
from pydicom.uid import RLELossless

try:
    import numpy as np
    from pydicom.pixel_data_handlers import numpy_handler as NP_HANDLER
    HAVE_NP = True
except ImportError:
    NP_HANDLER = None
    HAVE_NP = False

try:
    from pydicom.pixel_data_handlers import rle_handler as RLE_HANDLER
    HAVE_RLE = True
except ImportError:
    RLE_HANDLER = None
    HAVE_RLE = False


# Paths to the test datasets
# 8/8-bit, 1 sample/pixel, 1 frame
OB_EXPL_LITTLE_1F = get_testdata_files("OBXXXX1A.dcm")[0]
OB_RLE_1F = get_testdata_files("OBXXXX1A_rle.dcm")[0]
# 8/8-bit, 1 sample/pixel, 2 frame
OB_EXPL_LITTLE_2F = get_testdata_files("OBXXXX1A_2frame.dcm")[0]
OB_RLE_2F = get_testdata_files("OBXXXX1A_rle_2frame.dcm")[0]
# 8/8-bit, 3 sample/pixel, 1 frame
SC_EXPL_LITTLE_1F = get_testdata_files("SC_rgb.dcm")[0]
SC_RLE_1F = get_testdata_files("SC_rgb_rle.dcm")[0]
# 8/8-bit, 3 sample/pixel, 2 frame
SC_EXPL_LITTLE_2F = get_testdata_files("SC_rgb_2frame.dcm")[0]
SC_RLE_2F = get_testdata_files("SC_rgb_rle_2frame.dcm")[0]
# 16/16-bit, 1 sample/pixel, 1 frame
MR_EXPL_LITTLE_1F = get_testdata_files("MR_small.dcm")[0]
MR_RLE_1F = get_testdata_files("MR_small_RLE.dcm")[0]
# 16/16-bit, 3 sample/pixel, 1 frame
SC_EXPL_LITTLE_16_1F = get_testdata_files("SC_rgb_16bit.dcm")[0]
SC_RLE_16_1F = get_testdata_files("SC_rgb_rle_16bit.dcm")[0]
# 16/16-bit, 3 sample/pixel, 2 frame
SC_EXPL_LITTLE_16_2F = get_testdata_files("SC_rgb_16bit_2frame.dcm")[0]
SC_RLE_16_2F = get_testdata_files("SC_rgb_rle_16bit_2frame.dcm")[0]
# 16/12-bit, 1 sample/pixel, 10 frame
EMRI_EXPL_LITTLE_10F = get_testdata_files("emri_small.dcm")[0]
EMRI_RLE_10F = get_testdata_files("emri_small_RLE.dcm")[0]
# 32/32-bit, 1 sample/pixel, 1 frame
RTDOSE_EXPL_LITTLE_1F = get_testdata_files("rtdose_1frame.dcm")[0]
RTDOSE_RLE_1F = get_testdata_files("rtdose_rle_1frame.dcm")[0]
# 32/32-bit, 1 sample/pixel, 15 frame
RTDOSE_EXPL_LITTLE_15F = get_testdata_files("rtdose.dcm")[0]
RTDOSE_RLE_15F = get_testdata_files("rtdose_rle.dcm")[0]

# Transfer Syntaxes (non-retired + Explicit VR Big Endian)
SUPPORTED_SYNTAXES = [RLELossless]
UNSUPPORTED_SYNTAXES = [
    '1.2.840.10008.1.2',  # Implicit VR Little Endian
    '1.2.840.10008.1.2.1',  # Explicit VR Little Endian
    '1.2.840.10008.1.2.1.99',  # Deflated Explicit VR Little Endian
    '1.2.840.10008.1.2.2',  # Explicit VR Big Endian
    '1.2.840.10008.1.2.4.50',  # JPEG Baseline (Process 1)
    '1.2.840.10008.1.2.4.51',  # JPEG Extended (Process 2 and 4)
    '1.2.840.10008.1.2.4.57',  # JPEG Lossless (Process 14)
    '1.2.840.10008.1.2.4.70',  # JPEG Lossless (Process 14, Selection Value 1)
    '1.2.840.10008.1.2.4.80',  # JPEG-LS Lossless
    '1.2.840.10008.1.2.4.81',  # JPEG-LS Lossy (Near-Lossless)
    '1.2.840.10008.1.2.4.90',  # JPEG 2000 Image Compression (Lossless Only)
    '1.2.840.10008.1.2.4.91',  # JPEG 2000 Image Compression
    '1.2.840.10008.1.2.4.92',  # JPEG 2000 Part 2 Multi-component
    '1.2.840.10008.1.2.4.93',  # JPEG 2000 Part 2 Multi-component
    '1.2.840.10008.1.2.4.94',  # JPIP Referenced
    '1.2.840.10008.1.2.4.95',  # JPIP Referenced Deflate
    '1.2.840.10008.1.2.4.100',  # MPEG2 Main Profile / Main Level
    '1.2.840.10008.1.2.4.101',  # MPEG2 Main Profile / High Level
    '1.2.840.10008.1.2.4.102',  # MPEG-4 AVC/H.264 High Profile / Level 4.1
    '1.2.840.10008.1.2.4.103',  # MPEG-4 AVC/H.264 BD-compatible High Profile
    '1.2.840.10008.1.2.4.104',  # MPEG-4 AVC/H.264 High Profile For 2D Video
    '1.2.840.10008.1.2.4.105',  # MPEG-4 AVC/H.264 High Profile For 3D Video
    '1.2.840.10008.1.2.4.106',  # MPEG-4 AVC/H.264 Stereo High Profile
    '1.2.840.10008.1.2.4.107',  # HEVC/H.265 Main Profile / Level 5.1
    '1.2.840.10008.1.2.4.108',  # HEVC/H.265 Main 10 Profile / Level 5.1
]
ALL_SYNTAXES = SUPPORTED_SYNTAXES + UNSUPPORTED_SYNTAXES


def _get_pixel_array(fpath):
    """Return the pixel data as a numpy ndarray.

    Only suitable for transfer syntaxes supported by the numpy pixel data
    handler.

    Parameters
    ----------
    fpath : str
        Path to the dataset containing the Pixel Data.

    Returns
    -------
    numpy.ndarray
    """
    if NP_HANDLER is None:
        raise RuntimeError('Function only usable with numpy handler')

    original_handlers = pydicom.config.image_handlers
    pydicom.config.image_handlers = [NP_HANDLER]

    ds = dcmread(fpath)
    arr = ds.pixel_array

    pydicom.config.image_handlers = original_handlers

    return arr


# Numpy and the RLE handler are not available
@pytest.mark.skipif(HAVE_NP, reason='Numpy is available')
class TestNoNumpy_NoRLE(object):
    def setup(self):
        """Setup the test datasets and the environment."""
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = []

    def teardown(self):
        """Restore the environment."""
        pydicom.config.image_handlers = self.original_handlers

    def test_environment(self):
        """Check that the testing environment is as expected."""
        assert not HAVE_NP
        assert not HAVE_RLE
        assert RLE_HANDLER not in pydicom.config.image_handlers

    def test_can_access_dataset(self):
        """Test that we can read and access elements in an RLE dataset."""
        ds = dcmread(MR_RLE_1F)
        assert 'CompressedSamples^MR1' == ds.PatientName
        assert 6128 == len(ds.PixelData)

    def test_pixel_array_raises(self):
        """Test pixel_array raises exception for all syntaxes."""
        ds = dcmread(MR_EXPL_LITTLE_1F)
        for uid in ALL_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            with pytest.raises(NotImplementedError):
                ds.pixel_array


# Numpy is available, the RLE handler is not available
@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class TestNumpy_NoRLE(object):
    def setup(self):
        """Setup the test datasets and the environment."""
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = []

    def teardown(self):
        """Restore the environment."""
        pydicom.config.image_handlers = self.original_handlers

    def test_environment(self):
        """Check that the testing environment is as expected."""
        assert HAVE_NP
        # The RLE handler should still be available
        assert HAVE_RLE
        # But we don't want to use it
        assert RLE_HANDLER not in pydicom.config.image_handlers

    def test_can_access_dataset(self):
        """Test that we can read and access elements in an RLE dataset."""
        ds = dcmread(MR_RLE_1F)
        assert 'CompressedSamples^MR1' == ds.PatientName
        assert 6128 == len(ds.PixelData)

    def test_pixel_array_raises(self):
        """Test pixel_array raises exception for all syntaxes."""
        ds = dcmread(MR_EXPL_LITTLE_1F)
        for uid in ALL_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            with pytest.raises(NotImplementedError):
                ds.pixel_array


# Numpy and the RLE handler are available
@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class TestNumpy_RLE(object):
    def setup(self):
        """Setup the test datasets and the environment."""
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [RLE_HANDLER]

    def teardown(self):
        """Restore the environment."""
        pydicom.config.image_handlers = self.original_handlers

    def test_environment(self):
        """Check that the testing environment is as expected."""
        assert HAVE_NP
        assert HAVE_RLE
        assert RLE_HANDLER in pydicom.config.image_handlers

    def test_unsupported_syntax_raises(self):
        """Test pixel_array raises exception for unsupported syntaxes."""
        ds = dcmread(MR_EXPL_LITTLE_1F)
        for uid in UNSUPPORTED_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            with pytest.raises(NotImplementedError):
                ds.pixel_array

    def test_pixel_array_1_1_1_frame(self):
        """Test pixel_array for 1-bit, 1 sample/pixel, 1 frame."""
        ds = dcmread(SC_RLE_1F)
        ds.BitsAllocated = 1
        # This should raise NotImplementedError instead
        with pytest.raises(TypeError):
            ds.pixel_array

    def test_pixel_array_1_1_2_frame(self):
        """Test pixel_array for 1-bit, 1 sample/pixel, 2 frame."""
        ds = dcmread(SC_RLE_2F)
        ds.BitsAllocated = 1
        # This should raise NotImplementedError instead
        with pytest.raises(TypeError):
            ds.pixel_array

    def test_pixel_array_8_1_1_frame(self):
        """Test pixel_array for 8-bit, 1 sample/pixel, 1 frame."""
        ds = dcmread(OB_RLE_1F)
        ref = _get_pixel_array(OB_EXPL_LITTLE_1F)
        arr = ds.pixel_array

        assert np.array_equal(arr, ref)
        assert (600, 800) == arr.shape
        assert 244 == arr[0].min() == arr[0].max()
        assert (1, 246, 1) == tuple(arr[300, 491:494])
        assert 0 == arr[-1].min() == arr[-1].max()

    def test_pixel_array_8_1_2_frame(self):
        """Test pixel_array for 8-bit, 1 sample/pixel, 2 frame."""
        ds = dcmread(OB_RLE_2F)
        ref = _get_pixel_array(OB_EXPL_LITTLE_2F)
        arr = ds.pixel_array

        assert np.array_equal(arr, ref)
        assert (2, 600, 800) == arr.shape
        assert 244 == arr[0, 0].min() == arr[0, 0].max()
        assert (1, 246, 1) == tuple(arr[0, 300, 491:494])
        assert 0 == arr[0, -1].min() == arr[0, -1].max()

        # Frame 2 is frame 1 inverted
        assert 11 == arr[1, 0].min() == arr[1, 0].max()
        assert (254, 9, 254) == tuple(arr[1, 300, 491:494])
        assert 255 == arr[1, -1].min() == arr[1, -1].max()

    def test_pixel_array_8_3_1_frame(self):
        """Test pixel_array for 8-bit, 3 sample/pixel, 1 frame."""
        ds = dcmread(SC_RLE_1F)
        ref = _get_pixel_array(SC_EXPL_LITTLE_1F)
        arr = ds.pixel_array

        assert np.array_equal(arr, ref)

        assert (255, 0, 0) == tuple(arr[5, 50, :])
        assert (255, 128, 128) == tuple(arr[15, 50, :])
        assert (0, 255, 0) == tuple(arr[25, 50, :])
        assert (128, 255, 128) == tuple(arr[35, 50, :])
        assert (0, 0, 255) == tuple(arr[45, 50, :])
        assert (128, 128, 255) == tuple(arr[55, 50, :])
        assert (0, 0, 0) == tuple(arr[65, 50, :])
        assert (64, 64, 64) == tuple(arr[75, 50, :])
        assert (192, 192, 192) == tuple(arr[85, 50, :])
        assert (255, 255, 255) == tuple(arr[95, 50, :])

    def test_pixel_array_8_3_2_frame(self):
        """Test pixel_array for 8-bit, 3 sample/pixel, 2 frame."""
        ds = dcmread(SC_RLE_2F)
        ref = _get_pixel_array(SC_EXPL_LITTLE_2F)
        arr = ds.pixel_array

        assert np.array_equal(ds.pixel_array, ref)

        # Frame 1
        frame = arr[0]
        assert (255, 0, 0) == tuple(frame[5, 50, :])
        assert (255, 128, 128) == tuple(frame[15, 50, :])
        assert (0, 255, 0) == tuple(frame[25, 50, :])
        assert (128, 255, 128) == tuple(frame[35, 50, :])
        assert (0, 0, 255) == tuple(frame[45, 50, :])
        assert (128, 128, 255) == tuple(frame[55, 50, :])
        assert (0, 0, 0) == tuple(frame[65, 50, :])
        assert (64, 64, 64) == tuple(frame[75, 50, :])
        assert (192, 192, 192) == tuple(frame[85, 50, :])
        assert (255, 255, 255) == tuple(frame[95, 50, :])

        # Frame 2 is frame 1 inverted
        frame = arr[1]
        assert (0, 255, 255) == tuple(frame[5, 50, :])
        assert (0, 127, 127) == tuple(frame[15, 50, :])
        assert (255, 0, 255) == tuple(frame[25, 50, :])
        assert (127, 0, 127) == tuple(frame[35, 50, :])
        assert (255, 255, 0) == tuple(frame[45, 50, :])
        assert (127, 127, 0) == tuple(frame[55, 50, :])
        assert (255, 255, 255) == tuple(frame[65, 50, :])
        assert (191, 191, 191) == tuple(frame[75, 50, :])
        assert (63, 63, 63) == tuple(frame[85, 50, :])
        assert (0, 0, 0) == tuple(frame[95, 50, :])

    def test_pixel_array_16_1_1_frame(self):
        """Test pixel_array for 16-bit, 1 sample/pixel, 1 frame."""
        ds = dcmread(MR_RLE_1F)
        ref = _get_pixel_array(MR_EXPL_LITTLE_1F)
        arr = ds.pixel_array

        assert np.array_equal(arr, ref)
        assert (64, 64) == arr.shape

        assert (422, 319, 361) == tuple(arr[0, 31:34])
        assert (366, 363, 322) == tuple(arr[31, :3])
        assert (1369, 1129, 862) == tuple(arr[-1, -3:])

    def test_pixel_array_16_1_10_frame(self):
        """Test pixel_array for 16-bit, 1, sample/pixel, 10 frame."""
        ds = dcmread(EMRI_RLE_10F)
        ref = _get_pixel_array(EMRI_EXPL_LITTLE_10F)
        arr = ds.pixel_array

        assert np.array_equal(arr, ref)
        assert (10, 64, 64) == arr.shape

        # Frame 1
        assert (206, 197, 159) == tuple(arr[0, 0, 31:34])
        assert (49, 78, 128) == tuple(arr[0, 31, :3])
        assert (362, 219, 135) == tuple(arr[0, -1, -3:])

        # Frame 5
        assert (67, 82, 44) == tuple(arr[4, 0, 31:34])
        assert (37, 41, 17) == tuple(arr[4, 31, :3])
        assert (225, 380, 355) == tuple(arr[4, -1, -3:])

        # Frame 10
        assert (72, 86, 69) == tuple(arr[-1, 0, 31:34])
        assert (25, 4, 9) == tuple(arr[-1, 31, :3])
        assert (227, 300, 147) == tuple(arr[-1, -1, -3:])

    @pytest.mark.skip(reason='Samples/pixel>1, BitsAllocated>8 not supported')
    def test_pixel_array_16_3_1_frame(self):
        """Test pixel_array for 16-bit, 3 sample/pixel, 1 frame."""
        ds = dcmread(SC_RLE_16_1F)
        arr = ds.pixel_array
        ref = _get_pixel_array(SC_EXPL_LITTLE_16_1F)

        assert np.array_equal(ds.pixel_array, ref)

        assert (65535, 0, 0) == tuple(arr[5, 50, :])
        assert (65535, 32896, 32896) == tuple(arr[15, 50, :])
        assert (0, 65535, 0) == tuple(arr[25, 50, :])
        assert (32896, 65535, 32896) == tuple(arr[35, 50, :])
        assert (0, 0, 65535) == tuple(arr[45, 50, :])
        assert (32896, 32896, 65535) == tuple(arr[55, 50, :])
        assert (0, 0, 0) == tuple(arr[65, 50, :])
        assert (16448, 16448, 16448) == tuple(arr[75, 50, :])
        assert (49344, 49344, 49344) == tuple(arr[85, 50, :])
        assert (65535, 65535, 65535) == tuple(arr[95, 50, :])

    @pytest.mark.skip(reason='Samples/pixel>1, BitsAllocated>8 not supported')
    def test_pixel_array_16_3_2_frame(self):
        """Test pixel_array for 16-bit, 3, sample/pixel, 10 frame."""
        ds = dcmread(SC_RLE_16_2F)
        arr = ds.pixel_array
        ref = _get_pixel_array(SC_EXPL_LITTLE_16_2F)

        assert np.array_equal(ds.pixel_array, ref)

        # Frame 1
        frame = arr[0]
        assert (65535, 0, 0) == tuple(frame[5, 50, :])
        assert (65535, 32896, 32896) == tuple(frame[15, 50, :])
        assert (0, 65535, 0) == tuple(frame[25, 50, :])
        assert (32896, 65535, 32896) == tuple(frame[35, 50, :])
        assert (0, 0, 65535) == tuple(frame[45, 50, :])
        assert (32896, 32896, 65535) == tuple(frame[55, 50, :])
        assert (0, 0, 0) == tuple(frame[65, 50, :])
        assert (16448, 16448, 16448) == tuple(frame[75, 50, :])
        assert (49344, 49344, 49344) == tuple(frame[85, 50, :])
        assert (65535, 65535, 65535) == tuple(frame[95, 50, :])

        # Frame 2 is frame 1 inverted
        frame = arr[1]
        assert (0, 65535, 65535) == tuple(frame[5, 50, :])
        assert (0, 32639, 32639) == tuple(frame[15, 50, :])
        assert (65535, 0, 65535) == tuple(frame[25, 50, :])
        assert (32639, 0, 32639) == tuple(frame[35, 50, :])
        assert (65535, 65535, 0) == tuple(frame[45, 50, :])
        assert (32639, 32639, 0) == tuple(frame[55, 50, :])
        assert (65535, 65535, 65535) == tuple(frame[65, 50, :])
        assert (49087, 49087, 49087) == tuple(frame[75, 50, :])
        assert (16191, 16191, 16191) == tuple(frame[85, 50, :])
        assert (0, 0, 0) == tuple(frame[95, 50, :])

    def test_pixel_array_32_1_1_frame(self):
        """Test pixel_array for 32-bit, 1 sample/pixel, 1 frame."""
        ds = dcmread(RTDOSE_RLE_1F)
        ref = _get_pixel_array(RTDOSE_EXPL_LITTLE_1F)
        arr = ds.pixel_array

        assert np.array_equal(arr, ref)
        assert (10, 10) == arr.shape
        assert (1249000, 1249000, 1250000) == tuple(ref[0, :3])
        assert (1031000, 1029000, 1027000) == tuple(ref[4, 3:6])
        assert (803000, 801000, 798000) == tuple(ref[-1, -3:])

    def test_pixel_array_32_1_15_frame(self):
        """Test pixel_array for 32-bit, 1, sample/pixel, 15 frame."""
        ds = dcmread(RTDOSE_RLE_15F)
        ref = _get_pixel_array(RTDOSE_EXPL_LITTLE_15F)
        arr = ds.pixel_array

        assert np.array_equal(arr, ref)
        assert (15, 10, 10) == arr.shape

        # Frame 1
        assert (1249000, 1249000, 1250000) == tuple(arr[0, 0, :3])
        assert (1031000, 1029000, 1027000) == tuple(arr[0, 4, 3:6])
        assert (803000, 801000, 798000) == tuple(arr[0, -1, -3:])

        # Frame 8
        assert (1253000, 1253000, 1249000) == tuple(arr[7, 0, :3])
        assert (1026000, 1023000, 1022000) == tuple(arr[7, 4, 3:6])
        assert (803000, 803000, 803000) == tuple(arr[7, -1, -3:])

        # Frame 15
        assert (1249000, 1250000, 1251000) == tuple(ref[-1, 0, :3])
        assert (1031000, 1031000, 1031000) == tuple(ref[-1, 4, 3:6])
        assert (801000, 800000, 799000) == tuple(ref[-1, -1, -3:])

    @pytest.mark.skip(reason='Missing a suitable RLE encoded dataset')
    def test_pixel_array_32_3_1_frame(self):
        """Test pixel_array for 32-bit, 3 sample/pixel, 1 frame."""
        # Can't generate RLE encoded data for 32-bit 3 samples/pixel
        #   placeholder for future test
        pass

    @pytest.mark.skip(reason='Missing a suitable RLE encoded dataset')
    def test_pixel_array_32_3_2_frame(self):
        """Test pixel_array for 32-bit, 3, sample/pixel, 2 frame."""
        # Can't generate RLE encoded data for 32-bit 3 samples/pixel
        #   placeholder for future test
        pass
