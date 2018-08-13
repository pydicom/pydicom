# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Tests for the pixel_data_handlers.numpy_handler module.

There are the following possibilities:

* numpy is not available and the numpy handler is not available
* numpy is available and

  * The numpy handler is not available
  * The numpy handler is available

**Supported transfer syntaxes**

* 1.2.840.10008.1.2 : Implicit VR Little Endian
* 1.2.840.10008.1.2.1 : Explicit VR Little Endian
* 1.2.840.10008.1.2.1.99 : Deflated Explicit VR Little Endian
* 1.2.840.10008.1.2.2 : Explicit VR Big Endian

**Elements affecting the handler**

* BitsAllocated
* SamplesPerPixel
* NumberOfFrames
"""

import os
import sys
import unittest

try:
    import numpy as np
    from pydicom.pixel_data_handlers import numpy_handler as NP_HANDLER
    HAVE_NP = True
except ImportError:
    HAVE_NP = False
    NP_HANDLER = None

import pytest

import pydicom
from pydicom.data import get_testdata_files
from pydicom.filereader import dcmread
from pydicom.uid import (
    ImplicitVRLittleEndian,
    ExplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian,
    ExplicitVRBigEndian
)


# Paths to the test datasets
# IMPL: Implicit VR Little Endian
# EXPB: Explicit VR Big Endian
# 1/1, 1 sample/pixel, 1 frame
IMPL_1_1_1F = get_testdata_files("liver_1frame.dcm")[0]
EXPB_1_1_1F = get_testdata_files("liver_expb_1frame.dcm")[0]
# 1/1, 3 sample/pixel, 1 frame
IMPL_1_3_1F = None
EXPB_1_3_1F = None
# 1/1, 1 sample/pixel, 3 frame
IMPL_1_1_3F = get_testdata_files("liver.dcm")[0]
EXPB_1_1_3F = get_testdata_files("liver_expb.dcm")[0]
# 1/1, 3 sample/pixel, 2 frame
IMPL_1_3_2F = None
EXPB_1_3_2F = None
# 8/8, 1 sample/pixel, 1 frame
IMPL_8_1_1F = get_testdata_files("OBXXXX1A.dcm")[0]
EXPB_8_1_1F = get_testdata_files("OBXXXX1A_expb.dcm")[0]
# 8/8, 3 sample/pixel, 1 frame
IMPL_8_3_1F = get_testdata_files("SC_rgb.dcm")[0]
EXPB_8_3_1F = get_testdata_files("SC_rgb_expb.dcm")[0]
# 8/8, 1 sample/pixel, 2 frame
IMPL_8_1_2F = get_testdata_files("OBXXXX1A_2frame.dcm")[0]
EXPB_8_1_2F = get_testdata_files("OBXXXX1A_expb_2frame.dcm")[0]
# 8/8, 3 sample/pixel, 2 frame
IMPL_8_3_2F = get_testdata_files("SC_rgb_2frame.dcm")[0]
EXPB_8_3_2F = get_testdata_files("SC_rgb_expb_2frame.dcm")[0]
# 16/16, 1 sample/pixel, 1 frame
IMPL_16_1_1F = get_testdata_files("MR_small.dcm")[0]
EXPB_16_1_1F = get_testdata_files("MR_small_expb.dcm")[0]
# 16/16, 3 sample/pixel, 1 frame
IMPL_16_3_1F = get_testdata_files("SC_rgb_16bit.dcm")[0]
EXPB_16_3_1F = get_testdata_files("SC_rgb_expb_16bit.dcm")[0]
# 16/12, 1 sample/pixel, 10 frame
IMPL_16_1_10F = get_testdata_files("emri_small.dcm")[0]
EXPB_16_1_10F = get_testdata_files("emri_small_big_endian.dcm")[0]
# 16/16, 3 sample/pixel, 2 frame
IMPL_16_3_2F = get_testdata_files("SC_rgb_16bit_2frame.dcm")[0]
EXPB_16_3_2F = get_testdata_files("SC_rgb_expb_16bit_2frame.dcm")[0]
# 32/32, 1 sample/pixel, 1 frame
IMPL_32_1_1F = get_testdata_files("rtdose_1frame.dcm")[0]
EXPB_32_1_1F = get_testdata_files("rtdose_expb_1frame.dcm")[0]
# 32/32, 3 sample/pixel, 1 frame
IMPL_32_3_1F = None
EXPB_32_3_1F = None
# 32/32, 1 sample/pixel, 10 frame
IMPL_32_1_10F = get_testdata_files("rtdose.dcm")[0]
EXPB_32_1_10F = get_testdata_files("rtdose_expb.dcm")[0]
# 32/32, 3 sample/pixel, 2 frame
IMPL_32_3_2F = None
EXPB_32_3_2F = None

# Transfer Syntaxes (non-retired + Explicit VR Big Endian)
SUPPORTED_SYNTAXES = [
    ImplicitVRLittleEndian,
    ExplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian,
    ExplicitVRBigEndian
]
UNSUPPORTED_SYNTAXES = [
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
    '1.2.840.10008.1.2.5',  # RLE Lossless
]
ALL_SYNTAXES = SUPPORTED_SYNTAXES + UNSUPPORTED_SYNTAXES


# Numpy and the numpy handler are unavailable
@pytest.mark.skipif(HAVE_NP, reason='Numpy is available')
class TestNoNumpy_NoNumpyHandler(object):
    """Tests for handling Pixel Data without numpy and the handler."""
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
        assert NP_HANLDER is None
        assert NP_HANDLER not in pydicom.config.image_handlers

    def test_can_access_dataset(self):
        """Test that we can read and access elements in dataset."""
        ds = dcmread(IMPL_16_1_1F)
        assert 'CompressedSamples^MR1' == ds.PatientName
        assert 6128 == len(ds.PixelData)

    def test_pixel_array_raises(self):
        """Test pixel_array raises exception for all syntaxes."""
        ds = dcmread(IMPL_16_1_1F)
        for uid in ALL_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            exc_msg = (
                'No available image handler could decode this transfer syntax'
            )
            with pytest.raises(NotImplementedError, match=exc_msg):
                ds.pixel_array


# Numpy is available, the numpy handler is unavailable
@pytest.mark.skipif(HAVE_NP, reason='Numpy is available')
class TestNumpy_NoNumpyHandler(object):
    """Tests for handling Pixel Data without the handler."""
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
        # We numpy handler should still be available
        assert NP_HANLDER is not None
        # But we don't want to use it
        assert NP_HANDLER not in pydicom.config.image_handlers

    def test_can_access_dataset(self):
        """Test that we can read and access elements in an RLE dataset."""
        ds = dcmread(IMPL_16_1_1F)
        assert 'CompressedSamples^MR1' == ds.PatientName
        assert 6128 == len(ds.PixelData)

    def test_pixel_array_raises(self):
        """Test pixel_array raises exception for all syntaxes."""
        ds = dcmread(IMPL_16_1_1F)
        for uid in ALL_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            exc_msg = (
                'No available image handler could decode this transfer syntax'
            )
            with pytest.raises(NotImplementedError, match=exc_msg):
                ds.pixel_array


# Numpy and the numpy handler are available
MATCHING_DATASETS = [
    (IMPL_1_1_1F, EXPB_1_1_1F),
    (IMPL_1_3_1F, EXPB_1_3_1F),
    (IMPL_1_1_3F, EXPB_1_1_3F),
    (IMPL_1_3_3F, EXPB_1_3_3F),
    (IMPL_8_1_1F, EXPB_8_1_1F),
    (IMPL_8_3_1F, EXPB_8_3_1F),
    (IMPL_8_1_2F, EXPB_8_1_2F),
    (IMPL_8_3_2F, EXPB_8_3_2F),
    (IMPL_16_1_1F, EXPB_16_1_1F),
    (IMPL_16_3_1F, EXPB_16_3_1F),
    (IMPL_16_1_10F, EXPB_16_1_10F),
    (IMPL_16_3_2F, EXPB_16_3_2F),
    (IMPL_32_1_1F, EXPB_32_1_1F),
    (IMPL_32_3_1F, EXPB_32_3_1F),
    (IMPL_32_1_10F, EXPB_32_1_10F),
    (IMPL_32_3_2F, EXPB_32_3_2F)
]

@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class TestNumpy_NumpyHandler(object):
    """Tests for handling Pixel Data with the handler.

    The tests spot check values for little endian pixel data and then uses the
    little endian pixel aray as the reference for the other transfer syntaxes.
    """
    def setup(self):
        """Setup the test datasets and the environment."""
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [NP_HANDLER]

    def teardown(self):
        """Restore the environment."""
        pydicom.config.image_handlers = self.original_handlers

    def test_environment(self):
        """Check that the testing environment is as expected."""
        assert HAVE_NP
        assert NP_HANLDER is not None
        assert NP_HANDLER in pydicom.config.image_handlers

    def test_unsupported_syntax_raises(self):
        """Test pixel_array raises exception for unsupported syntaxes."""
        ds = dcmread(IMPL_16_1_1F)
        for uid in UNSUPPORTED_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            with pytest.raises(NotImplementedError,
                               match='image handler could decode'):
                ds.pixel_array

    def test_can_access_dataset(self):
        """Test that we can read and access elements in unsupported datasest."""
        pass

    # Little endian datasets
    def test_little_1bit_1sample_1frame(self):
        """Test pixel_array for little 1-bit, 1 sample/pixel, 1 frame."""
        ds = dcmread(IMPL_1_1_1F)
        assert ds.BitsAllocated == 1
        assert ds.SamplesPerPixel == 1
        assert 'NumberOfFrames' not in ds

        # Check all little endian syntaxes
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    def test_little_1bit_1sample_10frame(self):
        """Test pixel_array for little 1-bit, 1 sample/pixel, 10 frame."""
        ds = dcmread(IMPL_1_1_10F)
        assert ds.BitsAllocated == 1
        assert ds.SamplesPerPixel == 1
        assert ds.NumberOfFrames == 10

        # Check all little endian syntaxes
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    def test_little_1bit_3sample_1frame(self):
        """Test pixel_array for little 1-bit, 3 sample/pixel, 1 frame."""
        ds = dcmread(IMPL_1_3_1F)
        assert ds.BitsAllocated == 1
        assert ds.SamplesPerPixel == 3
        assert 'NumberOfFrames' not in ds or ds.NumberOfFrames == 1

        # Check all little endian syntaxes
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    def test_little_1bit_3sample_10frame(self):
        """Test pixel_array for little 1-bit, 3 sample/pixel, 10 frame."""
        ds = dcmread(IMPL_1_3_10F)
        assert ds.BitsAllocated == 1
        assert ds.SamplesPerPixel == 3
        assert ds.NumberOfFrames == 10

        # Check all little endian syntaxes
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    def test_little_8bit_1sample_1frame(self):
        """Test pixel_array for little 8-bit, 1 sample/pixel, 1 frame."""
        ds = dcmread(IMPL_8_1_1F)
        assert ds.BitsAllocated == 8
        assert ds.SamplesPerPixel == 1
        assert 'NumberOfFrames' not in ds or ds.NumberOfFrames == 1

        # Check all little endian syntaxes
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    def test_little_8bit_1sample_10frame(self):
        """Test pixel_array for little 8-bit, 1 sample/pixel, 10 frame."""
        ds = dcmread(IMPL_8_1_10F)
        assert ds.BitsAllocated == 8
        assert ds.SamplesPerPixel == 1
        assert ds.NumberOfFrames == 10

        # Check all little endian syntaxes
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    def test_little_8bit_3sample_1frame(self):
        """Test pixel_array for little 8-bit, 3 sample/pixel, 1 frame."""
        ds = dcmread(IMPL_8_3_1F)
        assert ds.BitsAllocated == 8
        assert ds.SamplesPerPixel == 3
        assert 'NumberOfFrames' not in ds or ds.NumberOfFrames == 1

        # Check all little endian syntaxes
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    def test_little_8bit_3sample_10frame(self):
        """Test pixel_array for little 8-bit, 3 sample/pixel, 10 frame."""
        ds = dcmread(IMPL_8_3_10F)
        assert ds.BitsAllocated == 8
        assert ds.SamplesPerPixel == 3
        assert ds.NumberOfFrames == 10

        # Check all little endian syntaxes
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    def test_little_16bit_1sample_1frame(self):
        """Test pixel_array for little 16-bit, 1 sample/pixel, 1 frame."""
        ds = dcmread(IMPL_16_1_1F)
        assert ds.BitsAllocated == 16
        assert ds.SamplesPerPixel == 1
        assert 'NumberOfFrames' not in ds or ds.NumberOfFrames == 1

        # Check all little endian syntaxes
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    def test_little_16bit_1sample_10frame(self):
        """Test pixel_array for little 16-bit, 1 sample/pixel, 10 frame."""
        ds = dcmread(IMPL_16_1_10F)
        assert ds.BitsAllocated == 16
        assert ds.SamplesPerPixel == 1
        assert ds.NumberOfFrames == 10

        # Check all little endian syntaxes
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    def test_little_16bit_3sample_1frame(self):
        """Test pixel_array for little 16-bit, 3 sample/pixel, 1 frame."""
        ds = dcmread(IMPL_16_3_1F)
        assert ds.BitsAllocated == 16
        assert ds.SamplesPerPixel == 3
        assert 'NumberOfFrames' not in ds or ds.NumberOfFrames == 1

        # Check all little endian syntaxes
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    def test_little_16bit_3sample_10frame(self):
        """Test pixel_array for little 16-bit, 3 sample/pixel, 10 frame."""
        ds = dcmread(IMPL_16_3_10F)
        assert ds.BitsAllocated == 16
        assert ds.SamplesPerPixel == 3
        assert ds.NumberOfFrames == 10

        # Check all little endian syntaxes
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    def test_little_32bit_1sample_1frame(self):
        """Test pixel_array for little 32-bit, 1 sample/pixel, 1 frame."""
        ds = dcmread(IMPL_32_1_1F)
        assert ds.BitsAllocated == 32
        assert ds.SamplesPerPixel == 1
        assert 'NumberOfFrames' not in ds or ds.NumberOfFrames == 1

        # Check all little endian syntaxes
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    def test_little_32bit_1sample_10frame(self):
        """Test pixel_array for little 32-bit, 1 sample/pixel, 10 frame."""
        ds = dcmread(IMPL_32_1_10F)
        assert ds.BitsAllocated == 32
        assert ds.SamplesPerPixel == 1
        assert ds.NumberOfFrames == 10

        # Check all little endian syntaxes
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    def test_little_32bit_3sample_1frame(self):
        """Test pixel_array for little 32-bit, 3 sample/pixel, 1 frame."""
        ds = dcmread(IMPL_32_3_1F)
        assert ds.BitsAllocated == 32
        assert ds.SamplesPerPixel == 3
        assert 'NumberOfFrames' not in ds or ds.NumberOfFrames == 1

        # Check all little endian syntaxes
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    def test_little_32bit_3sample_10frame(self):
        """Test pixel_array for little 32-bit, 3 sample/pixel, 10 frame."""
        ds = dcmread(IMPL_32_3_10F)
        assert ds.BitsAllocated == 32
        assert ds.SamplesPerPixel == 3
        assert ds.NumberOfFrames == 10

        # Check all little endian syntaxes
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    # Big endian datasets
    @pytest.mark.parametrize('little,big', MATCHING_DATASETS)
    def test_big_datasets(self):
        """Test pixel_array for big endian matches little."""
        ds = dcmread(big)
        ref = dcmread(little)
        assert np.array_equal(ds.pixel_array, ref.pixel_array)


# Tests for numpy_handler module with Numpy available
@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class TestNumpy_GetPixelData(object):
    """Tests for numpy_handler.get_pixeldata with numpy."""
    def test_no_pixel_data_raises(self):
        """Test get_pixeldata raises if dataset has no PixelData."""
        ds = dcmread(MR_RLE_1F)
        del ds.PixelData
        assert 'PixelData' not in ds
        # Should probably be AttributeError instead
        with pytest.raises(TypeError, match='No pixel data found'):
            get_pixeldata(ds)

    def test_unknown_pixel_representation_raises(self):
        """Test get_pixeldata raises if unsupported PixelRepresentation."""
        ds = dcmread(MR_RLE_1F)
        ds.PixelRepresentation = 2
        # Should probably be NotImplementedError instead
        with pytest.raises(TypeError, match="format='bad_pixel_repr"):
            get_pixeldata(ds)

    def test_unsupported_syntaxes_raises(self):
        """Test get_pixeldata raises if unsupported Transfer Syntax."""
        ds = dcmread(MR_EXPL_LITTLE_1F)
        # Typo in exception message
        with pytest.raises(NotImplementedError, match='RLE decompressordoes'):
            get_pixeldata(ds)

    def test_change_photometric_interpretation(self):
        """Test get_pixeldata changes PhotometricInterpretation if required."""
        def to_rgb(ds):
            """Override the original function that returned False"""
            return True

        orig_fn = RLE_HANDLER.should_change_PhotometricInterpretation_to_RGB
        RLE_HANDLER.should_change_PhotometricInterpretation_to_RGB = to_rgb

        ds = dcmread(MR_RLE_1F)
        assert ds.PhotometricInterpretation == 'MONOCHROME2'

        get_pixeldata(ds)
        assert ds.PhotometricInterpretation == 'RGB'

        RLE_HANDLER.should_change_PhotometricInterpretation_to_RGB = orig_fn


## Old tests
@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class numpy_BigEndian_Tests_with_numpy(unittest.TestCase):
    def setUp(self):
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [NP_HANDLER]
        self.emri_big_endian = dcmread(EXPB_16_1_10F)
        self.emri_small = dcmread(emri_name)

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_big_endian_PixelArray(self):
        a = self.emri_big_endian.pixel_array
        b = self.emri_small.pixel_array
        self.assertEqual(
            a.mean(),
            b.mean(),
            "Decoded big endian pixel data is not "
            "all {0} (mean == {1})".format(b.mean(), a.mean()))


@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class OneBitAllocatedTests(unittest.TestCase):
    def setUp(self):
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [NP_HANDLER]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_unpack_pixel_data(self):
        dataset = dcmread(one_bit_allocated_name)
        packed_data = dataset.PixelData
        assert len(packed_data) == 3 * 512 * 512 / 8
        unpacked_data = dataset.pixel_array
        assert len(unpacked_data) == 3
        assert len(unpacked_data[0]) == 512
        assert len(unpacked_data[2]) == 512
        assert len(unpacked_data[0][0]) == 512
        assert len(unpacked_data[2][511]) == 512
        assert unpacked_data[0][0][0] == 0
        assert unpacked_data[2][511][511] == 0
        assert unpacked_data[1][256][256] == 1


@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class numpy_LittleEndian_Tests(unittest.TestCase):
    def setUp(self):
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [NP_HANDLER]
        self.odd_size_image = dcmread(
            get_testdata_files('SC_rgb_small_odd.dcm')[0])
        self.emri_small = dcmread(emri_name)

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_little_endian_PixelArray_odd_data_size(self):
        pixel_data = self.odd_size_image.pixel_array
        assert pixel_data.nbytes == 27
        assert pixel_data.shape == (3, 3, 3)

    def test_little_endian_PixelArray(self):
        pixel_data = self.emri_small.pixel_array
        assert pixel_data.nbytes == 81920
        assert pixel_data.shape == (10, 64, 64)
