# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Tests for the pixel_data_handlers.util module."""

import os
from struct import unpack
from sys import byteorder

import pytest

try:
    import numpy as np
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom import dcmread
from pydicom.data import get_testdata_files, get_palette_files
from pydicom.dataset import Dataset
from pydicom.pixel_data_handlers.util import (
    dtype_corrected_for_endianness,
    reshape_pixel_array,
    convert_color_space,
    pixel_dtype,
    get_expected_length,
    apply_color_lut,
    _expand_segmented_lut,
    apply_modality_lut,
)
from pydicom.uid import (ExplicitVRLittleEndian, ImplicitVRLittleEndian,
                         UncompressedPixelTransferSyntaxes)


# PAL: PALETTE COLOR Photometric Interpretation
# SEG: Segmented LUT data
# SUP: uses Supplemental Palette Color
# LE, BE: little endian, big endian encoding
# 8/8, 1 sample/pixel, 1 frame
PAL_08_256_0_16_1F = get_testdata_files("OBXXXX1A.dcm")[0]
PAL_08_200_0_16_1F = get_testdata_files("OT-PAL-8-face.dcm")[0]
# PALETTE COLOR with 16-bit LUTs (no indirect segments)
PAL_SEG_LE_16_1F = get_testdata_files("gdcm-US-ALOKA-16.dcm")[0]
PAL_SEG_BE_16_1F = get_testdata_files("gdcm-US-ALOKA-16_big.dcm")[0]
# Supplemental palette colour
SUP_16_16_2F = get_testdata_files("eCT_Supplemental.dcm")[0]
# 8 bit, 3 samples/pixel, 1 and 2 frame datasets
# RGB colorspace, uncompressed
RGB_8_3_1F = get_testdata_files("SC_rgb.dcm")[0]
RGB_8_3_2F = get_testdata_files("SC_rgb_2frame.dcm")[0]


# Tests with Numpy unavailable
@pytest.mark.skipif(HAVE_NP, reason='Numpy is available')
class TestNoNumpy(object):
    """Tests for the util functions without numpy."""
    def test_pixel_dtype_raises(self):
        """Test that pixel_dtype raises exception without numpy."""
        with pytest.raises(ImportError,
                           match="Numpy is required to determine the dtype"):
            pixel_dtype(None)

    def test_reshape_pixel_array_raises(self):
        """Test that reshape_pixel_array raises exception without numpy."""
        with pytest.raises(ImportError,
                           match="Numpy is required to reshape"):
            reshape_pixel_array(None, None)


# Tests with Numpy available
REFERENCE_DTYPE = [
    # BitsAllocated, PixelRepresentation, numpy dtype string
    (1, 0, 'uint8'), (1, 1, 'uint8'),
    (8, 0, 'uint8'), (8, 1, 'int8'),
    (16, 0, 'uint16'), (16, 1, 'int16'),
    (32, 0, 'uint32'), (32, 1, 'int32'),
]


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestNumpy_PixelDtype(object):
    """Tests for util.pixel_dtype."""
    def setup(self):
        """Setup the test dataset."""
        self.ds = Dataset()
        self.ds.file_meta = Dataset()
        self.ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    def test_unknown_pixel_representation_raises(self):
        """Test an unknown PixelRepresentation value raises exception."""
        self.ds.BitsAllocated = 16
        self.ds.PixelRepresentation = -1
        # The bracket needs to be escaped
        with pytest.raises(ValueError,
                           match=r"value of '-1' for '\(0028,0103"):
            pixel_dtype(self.ds)

        self.ds.PixelRepresentation = 2
        with pytest.raises(ValueError,
                           match=r"value of '2' for '\(0028,0103"):
            pixel_dtype(self.ds)

    def test_unknown_bits_allocated_raises(self):
        """Test an unknown BitsAllocated value raises exception."""
        self.ds.BitsAllocated = 0
        self.ds.PixelRepresentation = 0
        # The bracket needs to be escaped
        with pytest.raises(ValueError,
                           match=r"value of '0' for '\(0028,0100"):
            pixel_dtype(self.ds)

        self.ds.BitsAllocated = 2
        with pytest.raises(ValueError,
                           match=r"value of '2' for '\(0028,0100"):
            pixel_dtype(self.ds)

        self.ds.BitsAllocated = 15
        with pytest.raises(ValueError,
                           match=r"value of '15' for '\(0028,0100"):
            pixel_dtype(self.ds)

    def test_unsupported_dtypes(self):
        """Test unsupported dtypes raise exception."""
        self.ds.BitsAllocated = 24
        self.ds.PixelRepresentation = 0

        with pytest.raises(NotImplementedError,
                           match="data type 'uint24' needed to contain"):
            pixel_dtype(self.ds)

    @pytest.mark.parametrize('bits, pixel_repr, dtype', REFERENCE_DTYPE)
    def test_supported_dtypes(self, bits, pixel_repr, dtype):
        """Test supported dtypes."""
        self.ds.BitsAllocated = bits
        self.ds.PixelRepresentation = pixel_repr
        # Correct for endianness of system
        ref_dtype = np.dtype(dtype)
        endianness = self.ds.file_meta.TransferSyntaxUID.is_little_endian
        if endianness != (byteorder == 'little'):
            ref_dtype = ref_dtype.newbyteorder('S')

        assert ref_dtype == pixel_dtype(self.ds)

    def test_byte_swapping(self):
        """Test that the endianess of the system is taken into account."""
        # The main problem is that our testing environments are probably
        #   all little endian, but we'll try our best
        self.ds.BitsAllocated = 16
        self.ds.PixelRepresentation = 0

        # < is little, = is native, > is big
        if byteorder == 'little':
            self.ds.is_little_endian = True
            assert pixel_dtype(self.ds).byteorder in ['<', '=']
            self.ds.is_little_endian = False
            assert pixel_dtype(self.ds).byteorder == '>'
        elif byteorder == 'big':
            self.ds.is_little_endian = True
            assert pixel_dtype(self.ds).byteorder == '<'
            self.ds.is_little_endian = False
            assert pixel_dtype(self.ds).byteorder in ['>', '=']


if HAVE_NP:
    RESHAPE_ARRAYS = {
        'reference': np.asarray([
            [  # Frame 1
                [[1,  9, 17],
                 [2, 10, 18],
                 [3, 11, 19],
                 [4, 12, 20],
                 [5, 13, 21]],
                [[2, 10, 18],
                 [3, 11, 19],
                 [4, 12, 20],
                 [5, 13, 21],
                 [6, 14, 22]],
                [[3, 11, 19],
                 [4, 12, 20],
                 [5, 13, 21],
                 [6, 14, 22],
                 [7, 15, 23]],
                [[4, 12, 20],
                 [5, 13, 21],
                 [6, 14, 22],
                 [7, 15, 23],
                 [8, 16, 24]],
            ],
            [  # Frame 2
                [[25, 33, 41],
                 [26, 34, 42],
                 [27, 35, 43],
                 [28, 36, 44],
                 [29, 37, 45]],
                [[26, 34, 42],
                 [27, 35, 43],
                 [28, 36, 44],
                 [29, 37, 45],
                 [30, 38, 46]],
                [[27, 35, 43],
                 [28, 36, 44],
                 [29, 37, 45],
                 [30, 38, 46],
                 [31, 39, 47]],
                [[28, 36, 44],
                 [29, 37, 45],
                 [30, 38, 46],
                 [31, 39, 47],
                 [32, 40, 48]],
            ]
        ]),
        '1frame_1sample': np.asarray(
            [1, 2, 3, 4, 5, 2, 3, 4, 5, 6, 3, 4, 5, 6, 7, 4, 5, 6, 7, 8]
        ),
        '2frame_1sample': np.asarray(
            [1,   2,  3,  4,  5,  2,  3,  4,  5,  6,  # Frame 1
             3,   4,  5,  6,  7,  4,  5,  6,  7,  8,
             25, 26, 27, 28, 29, 26, 27, 28, 29, 30,  # Frame 2
             27, 28, 29, 30, 31, 28, 29, 30, 31, 32]
        ),
        '1frame_3sample_0config': np.asarray(
            [1,  9, 17,  2, 10, 18,  3, 11, 19,  4, 12, 20,
             5, 13, 21,  2, 10, 18,  3, 11, 19,  4, 12, 20,
             5, 13, 21,  6, 14, 22,  3, 11, 19,  4, 12, 20,
             5, 13, 21,  6, 14, 22,  7, 15, 23,  4, 12, 20,
             5, 13, 21,  6, 14, 22,  7, 15, 23,  8, 16, 24]
        ),
        '1frame_3sample_1config': np.asarray(
            [1,   2,  3,  4,  5,  2,  3,  4,  5,  6,  # Red
             3,   4,  5,  6,  7,  4,  5,  6,  7,  8,
             9,  10, 11, 12, 13, 10, 11, 12, 13, 14,  # Green
             11, 12, 13, 14, 15, 12, 13, 14, 15, 16,
             17, 18, 19, 20, 21, 18, 19, 20, 21, 22,  # Blue
             19, 20, 21, 22, 23, 20, 21, 22, 23, 24]
        ),
        '2frame_3sample_0config': np.asarray(
            [1,   9, 17,  2, 10, 18,  3, 11, 19,  4, 12, 20,  # Frame 1
             5,  13, 21,  2, 10, 18,  3, 11, 19,  4, 12, 20,
             5,  13, 21,  6, 14, 22,  3, 11, 19,  4, 12, 20,
             5,  13, 21,  6, 14, 22,  7, 15, 23,  4, 12, 20,
             5,  13, 21,  6, 14, 22,  7, 15, 23,  8, 16, 24,
             25, 33, 41, 26, 34, 42, 27, 35, 43, 28, 36, 44,  # Frame 2
             29, 37, 45, 26, 34, 42, 27, 35, 43, 28, 36, 44,
             29, 37, 45, 30, 38, 46, 27, 35, 43, 28, 36, 44,
             29, 37, 45, 30, 38, 46, 31, 39, 47, 28, 36, 44,
             29, 37, 45, 30, 38, 46, 31, 39, 47, 32, 40, 48]
        ),
        '2frame_3sample_1config': np.asarray(
            [1,   2,  3,  4,  5,  2,  3,  4,  5,  6,  # Frame 1, red
             3,   4,  5,  6,  7,  4,  5,  6,  7,  8,
             9,  10, 11, 12, 13, 10, 11, 12, 13, 14,  # Frame 1, green
             11, 12, 13, 14, 15, 12, 13, 14, 15, 16,
             17, 18, 19, 20, 21, 18, 19, 20, 21, 22,  # Frame 1, blue
             19, 20, 21, 22, 23, 20, 21, 22, 23, 24,
             25, 26, 27, 28, 29, 26, 27, 28, 29, 30,  # Frame 2, red
             27, 28, 29, 30, 31, 28, 29, 30, 31, 32,
             33, 34, 35, 36, 37, 34, 35, 36, 37, 38,  # Frame 2, green
             35, 36, 37, 38, 39, 36, 37, 38, 39, 40,
             41, 42, 43, 44, 45, 42, 43, 44, 45, 46,  # Frame 2, blue
             43, 44, 45, 46, 47, 44, 45, 46, 47, 48]
        )
    }


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestNumpy_ReshapePixelArray(object):
    """Tests for util.reshape_pixel_array."""
    def setup(self):
        """Setup the test dataset."""
        self.ds = Dataset()
        self.ds.file_meta = Dataset()
        self.ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        self.ds.Rows = 4
        self.ds.Columns = 5

        # Expected output ref_#frames_#samples
        self.ref_1_1 = RESHAPE_ARRAYS['reference'][0, :, :, 0]
        self.ref_1_3 = RESHAPE_ARRAYS['reference'][0]
        self.ref_2_1 = RESHAPE_ARRAYS['reference'][:, :, :, 0]
        self.ref_2_3 = RESHAPE_ARRAYS['reference']

    def test_reference_1frame_1sample(self):
        """Test the 1 frame 1 sample/pixel reference array is as expected."""
        # (rows, columns)
        assert (4, 5) == self.ref_1_1.shape
        assert np.array_equal(
            self.ref_1_1,
            np.asarray(
                [[1, 2, 3, 4, 5],
                 [2, 3, 4, 5, 6],
                 [3, 4, 5, 6, 7],
                 [4, 5, 6, 7, 8]]
            )
        )

    def test_reference_1frame_3sample(self):
        """Test the 1 frame 3 sample/pixel reference array is as expected."""
        # (rows, columns, planes)
        assert (4, 5, 3) == self.ref_1_3.shape

        # Red channel
        assert np.array_equal(
            self.ref_1_3[:, :, 0],
            np.asarray(
                [[1, 2, 3, 4, 5],
                 [2, 3, 4, 5, 6],
                 [3, 4, 5, 6, 7],
                 [4, 5, 6, 7, 8]]
            )
        )
        # Green channel
        assert np.array_equal(
            self.ref_1_3[:, :, 1],
            np.asarray(
                [[9,  10, 11, 12, 13],
                 [10, 11, 12, 13, 14],
                 [11, 12, 13, 14, 15],
                 [12, 13, 14, 15, 16]]
            )
        )
        # Blue channel
        assert np.array_equal(
            self.ref_1_3[:, :, 2],
            np.asarray(
                [[17, 18, 19, 20, 21],
                 [18, 19, 20, 21, 22],
                 [19, 20, 21, 22, 23],
                 [20, 21, 22, 23, 24]]
            )
        )

    def test_reference_2frame_1sample(self):
        """Test the 2 frame 1 sample/pixel reference array is as expected."""
        # (nr frames, rows, columns)
        assert (2, 4, 5) == self.ref_2_1.shape

        # Frame 1
        assert np.array_equal(
            self.ref_2_1[0, :, :],
            np.asarray(
                [[1, 2, 3, 4, 5],
                 [2, 3, 4, 5, 6],
                 [3, 4, 5, 6, 7],
                 [4, 5, 6, 7, 8]]
            )
        )
        # Frame 2
        assert np.array_equal(
            self.ref_2_1[1, :, :],
            np.asarray(
                [[25, 26, 27, 28, 29],
                 [26, 27, 28, 29, 30],
                 [27, 28, 29, 30, 31],
                 [28, 29, 30, 31, 32]]
            )
        )

    def test_reference_2frame_3sample(self):
        """Test the 2 frame 3 sample/pixel reference array is as expected."""
        # (nr frames, row, columns, planes)
        assert (2, 4, 5, 3) == self.ref_2_3.shape

        # Red channel, frame 1
        assert np.array_equal(
            self.ref_2_3[0, :, :, 0],
            np.asarray(
                [[1, 2, 3, 4, 5],
                 [2, 3, 4, 5, 6],
                 [3, 4, 5, 6, 7],
                 [4, 5, 6, 7, 8]]
            )
        )
        # Green channel, frame 2
        assert np.array_equal(
            self.ref_2_3[1, :, :, 1],
            np.asarray(
                [[33, 34, 35, 36, 37],
                 [34, 35, 36, 37, 38],
                 [35, 36, 37, 38, 39],
                 [36, 37, 38, 39, 40]]
            )
        )

    def test_1frame_1sample(self):
        """Test reshaping 1 frame, 1 sample/pixel."""
        self.ds.SamplesPerPixel = 1
        arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS['1frame_1sample'])
        assert (4, 5) == arr.shape
        assert np.array_equal(arr, self.ref_1_1)

    def test_1frame_3sample_0conf(self):
        """Test reshaping 1 frame, 3 sample/pixel for 0 planar config."""
        self.ds.NumberOfFrames = 1
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 0
        arr = reshape_pixel_array(self.ds,
                                  RESHAPE_ARRAYS['1frame_3sample_0config'])
        assert (4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_1_3)

    def test_1frame_3sample_1conf(self):
        """Test reshaping 1 frame, 3 sample/pixel for 1 planar config."""
        self.ds.NumberOfFrames = 1
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 1
        arr = reshape_pixel_array(self.ds,
                                  RESHAPE_ARRAYS['1frame_3sample_1config'])
        assert (4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_1_3)

    def test_2frame_1sample(self):
        """Test reshaping 2 frame, 1 sample/pixel."""
        self.ds.NumberOfFrames = 2
        self.ds.SamplesPerPixel = 1
        arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS['2frame_1sample'])
        assert (2, 4, 5) == arr.shape
        assert np.array_equal(arr, self.ref_2_1)

    def test_2frame_3sample_0conf(self):
        """Test reshaping 2 frame, 3 sample/pixel for 0 planar config."""
        self.ds.NumberOfFrames = 2
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 0
        arr = reshape_pixel_array(self.ds,
                                  RESHAPE_ARRAYS['2frame_3sample_0config'])
        assert (2, 4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_2_3)

    def test_2frame_3sample_1conf(self):
        """Test reshaping 2 frame, 3 sample/pixel for 1 planar config."""
        self.ds.NumberOfFrames = 2
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 1
        arr = reshape_pixel_array(self.ds,
                                  RESHAPE_ARRAYS['2frame_3sample_1config'])
        assert (2, 4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_2_3)

    def test_compressed_syntaxes_0conf(self):
        """Test the compressed syntaxes that are always 0 planar conf."""
        for uid in ['1.2.840.10008.1.2.4.50',
                    '1.2.840.10008.1.2.4.57',
                    '1.2.840.10008.1.2.4.70',
                    '1.2.840.10008.1.2.4.90',
                    '1.2.840.10008.1.2.4.91']:
            self.ds.file_meta.TransferSyntaxUID = uid
            self.ds.PlanarConfiguration = 1
            self.ds.NumberOfFrames = 1
            self.ds.SamplesPerPixel = 3

            arr = reshape_pixel_array(self.ds,
                                      RESHAPE_ARRAYS['1frame_3sample_0config'])
            assert (4, 5, 3) == arr.shape
            assert np.array_equal(arr, self.ref_1_3)

    def test_compressed_syntaxes_1conf(self):
        """Test the compressed syntaxes that are always 1 planar conf."""
        for uid in ['1.2.840.10008.1.2.4.80',
                    '1.2.840.10008.1.2.4.81',
                    '1.2.840.10008.1.2.5']:
            self.ds.file_meta.TransferSyntaxUID = uid
            self.ds.PlanarConfiguration = 0
            self.ds.NumberOfFrames = 1
            self.ds.SamplesPerPixel = 3

            arr = reshape_pixel_array(self.ds,
                                      RESHAPE_ARRAYS['1frame_3sample_1config'])
            assert (4, 5, 3) == arr.shape
            assert np.array_equal(arr, self.ref_1_3)

    def test_uncompressed_syntaxes(self):
        """Test that uncompressed syntaxes use the dataset planar conf."""
        for uid in UncompressedPixelTransferSyntaxes:
            self.ds.file_meta.TransferSyntaxUID = uid
            self.ds.PlanarConfiguration = 0
            self.ds.NumberOfFrames = 1
            self.ds.SamplesPerPixel = 3

            arr = reshape_pixel_array(self.ds,
                                      RESHAPE_ARRAYS['1frame_3sample_0config'])
            assert (4, 5, 3) == arr.shape
            assert np.array_equal(arr, self.ref_1_3)

            self.ds.PlanarConfiguration = 1
            arr = reshape_pixel_array(self.ds,
                                      RESHAPE_ARRAYS['1frame_3sample_1config'])
            assert (4, 5, 3) == arr.shape
            assert np.array_equal(arr, self.ref_1_3)

    def test_invalid_nr_frames_raises(self):
        """Test an invalid Number of Frames value raises exception."""
        self.ds.SamplesPerPixel = 1
        self.ds.NumberOfFrames = 0
        # Need to escape brackets
        with pytest.raises(ValueError,
                           match=r"value of 0 for \(0028,0008\)"):
            reshape_pixel_array(self.ds, RESHAPE_ARRAYS['1frame_1sample'])

    def test_invalid_samples_raises(self):
        """Test an invalid Samples per Pixel value raises exception."""
        self.ds.SamplesPerPixel = 0
        # Need to escape brackets
        with pytest.raises(ValueError,
                           match=r"value of 0 for \(0028,0002\)"):
            reshape_pixel_array(self.ds, RESHAPE_ARRAYS['1frame_1sample'])

    def test_invalid_planar_conf_raises(self):
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 2
        # Need to escape brackets
        with pytest.raises(ValueError,
                           match=r"value of 2 for \(0028,0006\)"):
            reshape_pixel_array(self.ds,
                                RESHAPE_ARRAYS['1frame_3sample_0config'])


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestNumpy_ConvertColourSpace(object):
    """Tests for util.convert_color_space."""
    def test_unknown_current_raises(self):
        """Test an unknown current color space raises exception."""
        with pytest.raises(NotImplementedError,
                           match="Conversion from TEST to RGB is not suppo"):
            convert_color_space(None, 'TEST', 'RGB')

    def test_unknown_desired_raises(self):
        """Test an unknown desdired color space raises exception."""
        with pytest.raises(NotImplementedError,
                           match="Conversion from RGB to TEST is not suppo"):
            convert_color_space(None, 'RGB', 'TEST')

    @pytest.mark.parametrize(
        'current, desired',
        [('RGB', 'RGB'),
         ('YBR_FULL', 'YBR_FULL'), ('YBR_FULL', 'YBR_FULL_422'),
         ('YBR_FULL_422', 'YBR_FULL_422'), ('YBR_FULL_422', 'YBR_FULL')]
    )
    def test_current_is_desired(self, current, desired):
        """Test that the array is unchanged when current matches desired."""
        arr = np.ones((2, 3))
        assert np.array_equal(arr, convert_color_space(arr, current, desired))

    def test_rgb_ybr_rgb_single_frame(self):
        """Test round trip conversion of single framed pixel data."""
        ds = dcmread(RGB_8_3_1F)

        arr = ds.pixel_array
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

        ybr = convert_color_space(arr, 'RGB', 'YBR_FULL')
        assert (76, 85, 255) == tuple(ybr[5, 50, :])
        assert (166, 107, 192) == tuple(ybr[15, 50, :])
        assert (150, 44, 21) == tuple(ybr[25, 50, :])
        assert (203, 86, 75) == tuple(ybr[35, 50, :])
        assert (29, 255, 107) == tuple(ybr[45, 50, :])
        assert (142, 192, 118) == tuple(ybr[55, 50, :])
        assert (0, 128, 128) == tuple(ybr[65, 50, :])
        assert (64, 128, 128) == tuple(ybr[75, 50, :])
        assert (192, 128, 128) == tuple(ybr[85, 50, :])
        assert (255, 128, 128) == tuple(ybr[95, 50, :])

        # Round trip -> rounding errors get compounded
        rgb = convert_color_space(ybr, 'YBR_FULL', 'RGB')
        # All pixels within +/- 1 units
        assert np.allclose(rgb, arr, atol=1)
        assert rgb.shape == arr.shape

    def test_rgb_ybr_rgb_multi_frame(self):
        """Test round trip conversion of multi-framed pixel data."""
        ds = dcmread(RGB_8_3_2F)

        arr = ds.pixel_array
        assert (255, 0, 0) == tuple(arr[0, 5, 50, :])
        assert (255, 128, 128) == tuple(arr[0, 15, 50, :])
        assert (0, 255, 0) == tuple(arr[0, 25, 50, :])
        assert (128, 255, 128) == tuple(arr[0, 35, 50, :])
        assert (0, 0, 255) == tuple(arr[0, 45, 50, :])
        assert (128, 128, 255) == tuple(arr[0, 55, 50, :])
        assert (0, 0, 0) == tuple(arr[0, 65, 50, :])
        assert (64, 64, 64) == tuple(arr[0, 75, 50, :])
        assert (192, 192, 192) == tuple(arr[0, 85, 50, :])
        assert (255, 255, 255) == tuple(arr[0, 95, 50, :])
        # Frame 2 is frame 1 inverted
        assert np.array_equal((2**ds.BitsAllocated - 1) - arr[1], arr[0])

        ybr = convert_color_space(arr, 'RGB', 'YBR_FULL')
        assert (76, 85, 255) == tuple(ybr[0, 5, 50, :])
        assert (166, 107, 192) == tuple(ybr[0, 15, 50, :])
        assert (150, 44, 21) == tuple(ybr[0, 25, 50, :])
        assert (203, 86, 75) == tuple(ybr[0, 35, 50, :])
        assert (29, 255, 107) == tuple(ybr[0, 45, 50, :])
        assert (142, 192, 118) == tuple(ybr[0, 55, 50, :])
        assert (0, 128, 128) == tuple(ybr[0, 65, 50, :])
        assert (64, 128, 128) == tuple(ybr[0, 75, 50, :])
        assert (192, 128, 128) == tuple(ybr[0, 85, 50, :])
        assert (255, 128, 128) == tuple(ybr[0, 95, 50, :])
        # Frame 2
        assert (179, 171, 1) == tuple(ybr[1, 5, 50, :])
        assert (89, 149, 65) == tuple(ybr[1, 15, 50, :])
        assert (105, 212, 235) == tuple(ybr[1, 25, 50, :])
        assert (52, 170, 181) == tuple(ybr[1, 35, 50, :])
        assert (226, 1, 149) == tuple(ybr[1, 45, 50, :])
        assert (113, 65, 138) == tuple(ybr[1, 55, 50, :])
        assert (255, 128, 128) == tuple(ybr[1, 65, 50, :])
        assert (191, 128, 128) == tuple(ybr[1, 75, 50, :])
        assert (63, 128, 128) == tuple(ybr[1, 85, 50, :])
        assert (0, 128, 128) == tuple(ybr[1, 95, 50, :])

        # Round trip -> rounding errors get compounded
        rgb = convert_color_space(ybr, 'YBR_FULL', 'RGB')
        # All pixels within +/- 1 units
        assert np.allclose(rgb, arr, atol=1)
        assert rgb.shape == arr.shape


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestNumpy_DtypeCorrectedForEndianness(object):
    """Tests for util.dtype_corrected_for_endianness."""
    def test_byte_swapping(self):
        """Test that the endianess of the system is taken into account."""
        # The main problem is that our testing environments are probably
        #   all little endian, but we'll try our best
        dtype = np.dtype('uint16')

        # < is little, = is native, > is big
        if byteorder == 'little':
            out = dtype_corrected_for_endianness(True, dtype)
            assert out.byteorder in ['<', '=']
            out = dtype_corrected_for_endianness(False, dtype)
            assert out.byteorder == '>'
        elif byteorder == 'big':
            out = dtype_corrected_for_endianness(True, dtype)
            assert out.byteorder == '<'
            out = dtype_corrected_for_endianness(False, dtype)
            assert out.byteorder in ['>', '=']

    def test_no_endian_raises(self):
        """Test that an unset endianness raises exception."""
        with pytest.raises(ValueError,
                           match="attribute 'is_little_endian' has"):
            dtype_corrected_for_endianness(None, None)


REFERENCE_LENGTH = [
    # (frames, rows, cols, samples), bit depth, result in (bytes, pixels)
    # No 'NumberOfFrames' in dataset
    ((0, 0, 0, 0), 1, (0, 0)),
    ((0, 1, 1, 1), 1, (1, 1)),  # 1 bit -> 1 byte
    ((0, 1, 1, 3), 1, (1, 3)),  # 3 bits -> 1 byte
    ((0, 1, 3, 3), 1, (2, 9)),  # 9 bits -> 2 bytes
    ((0, 2, 2, 1), 1, (1, 4)),  # 4 bits -> 1 byte
    ((0, 2, 4, 1), 1, (1, 8)),  # 8 bits -> 1 byte
    ((0, 3, 3, 1), 1, (2, 9)),  # 9 bits -> 2 bytes
    ((0, 512, 512, 1), 1, (32768, 262144)),  # Typical length
    ((0, 512, 512, 3), 1, (98304, 786432)),
    ((0, 0, 0, 0), 8, (0, 0)),
    ((0, 1, 1, 1), 8, (1, 1)),  # Odd length
    ((0, 9, 1, 1), 8, (9, 9)),  # Odd length
    ((0, 1, 2, 1), 8, (2, 2)),  # Even length
    ((0, 512, 512, 1), 8, (262144, 262144)),
    ((0, 512, 512, 3), 8, (786432, 786432)),
    ((0, 0, 0, 0), 16, (0, 0)),
    ((0, 1, 1, 1), 16, (2, 1)),  # 16 bit data can't be odd length
    ((0, 1, 2, 1), 16, (4, 2)),
    ((0, 512, 512, 1), 16, (524288, 262144)),
    ((0, 512, 512, 3), 16, (1572864, 786432)),
    ((0, 0, 0, 0), 32, (0, 0)),
    ((0, 1, 1, 1), 32, (4, 1)),  # 32 bit data can't be odd length
    ((0, 1, 2, 1), 32, (8, 2)),
    ((0, 512, 512, 1), 32, (1048576, 262144)),
    ((0, 512, 512, 3), 32, (3145728, 786432)),
    # NumberOfFrames odd
    ((3, 0, 0, 0), 1, (0, 0)),
    ((3, 1, 1, 1), 1, (1, 3)),
    ((3, 1, 1, 3), 1, (2, 9)),
    ((3, 1, 3, 3), 1, (4, 27)),
    ((3, 2, 4, 1), 1, (3, 24)),
    ((3, 2, 2, 1), 1, (2, 12)),
    ((3, 3, 3, 1), 1, (4, 27)),
    ((3, 512, 512, 1), 1, (98304, 786432)),
    ((3, 512, 512, 3), 1, (294912, 2359296)),
    ((3, 0, 0, 0), 8, (0, 0)),
    ((3, 1, 1, 1), 8, (3, 3)),
    ((3, 9, 1, 1), 8, (27, 27)),
    ((3, 1, 2, 1), 8, (6, 6)),
    ((3, 512, 512, 1), 8, (786432, 786432)),
    ((3, 512, 512, 3), 8, (2359296, 2359296)),
    ((3, 0, 0, 0), 16, (0, 0)),
    ((3, 512, 512, 1), 16, (1572864, 786432)),
    ((3, 512, 512, 3), 16, (4718592, 2359296)),
    ((3, 0, 0, 0), 32, (0, 0)),
    ((3, 512, 512, 1), 32, (3145728, 786432)),
    ((3, 512, 512, 3), 32, (9437184, 2359296)),
    # NumberOfFrames even
    ((4, 0, 0, 0), 1, (0, 0)),
    ((4, 1, 1, 1), 1, (1, 4)),
    ((4, 1, 1, 3), 1, (2, 12)),
    ((4, 1, 3, 3), 1, (5, 36)),
    ((4, 2, 4, 1), 1, (4, 32)),
    ((4, 2, 2, 1), 1, (2, 16)),
    ((4, 3, 3, 1), 1, (5, 36)),
    ((4, 512, 512, 1), 1, (131072, 1048576)),
    ((4, 512, 512, 3), 1, (393216, 3145728)),
    ((4, 0, 0, 0), 8, (0, 0)),
    ((4, 512, 512, 1), 8, (1048576, 1048576)),
    ((4, 512, 512, 3), 8, (3145728, 3145728)),
    ((4, 0, 0, 0), 16, (0, 0)),
    ((4, 512, 512, 1), 16, (2097152, 1048576)),
    ((4, 512, 512, 3), 16, (6291456, 3145728)),
    ((4, 0, 0, 0), 32, (0, 0)),
    ((4, 512, 512, 1), 32, (4194304, 1048576)),
    ((4, 512, 512, 3), 32, (12582912, 3145728)),
]


class TestGetExpectedLength(object):
    """Tests for util.get_expected_length."""
    @pytest.mark.parametrize('shape, bits, length', REFERENCE_LENGTH)
    def test_length_in_bytes(self, shape, bits, length):
        """Test get_expected_length(ds, unit='bytes')."""
        ds = Dataset()
        ds.Rows = shape[1]
        ds.Columns = shape[2]
        ds.BitsAllocated = bits
        if shape[0] != 0:
            ds.NumberOfFrames = shape[0]
        ds.SamplesPerPixel = shape[3]

        assert length[0] == get_expected_length(ds, unit='bytes')

    @pytest.mark.parametrize('shape, bits, length', REFERENCE_LENGTH)
    def test_length_in_pixels(self, shape, bits, length):
        """Test get_expected_length(ds, unit='pixels')."""
        ds = Dataset()
        ds.Rows = shape[1]
        ds.Columns = shape[2]
        ds.BitsAllocated = bits
        if shape[0] != 0:
            ds.NumberOfFrames = shape[0]
        ds.SamplesPerPixel = shape[3]

        assert length[1] == get_expected_length(ds, unit='pixels')


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestNumpy_ModalityLUT(object):
    """Tests for util.apply_modality_lut()."""
    def setup(self):
        pass


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestNumpy_PaletteColor(object):
    """Tests for util.apply_color_lut()."""
    def setup(self):
        """Setup the tests"""
        self.o_palette = get_palette_files('pet.dcm')[0]
        self.n_palette = get_palette_files('pet.dcm')[0][:-3] + 'tmp'

    def teardown(self):
        """Teardown the tests"""
        if os.path.exists(self.n_palette):
            os.rename(self.n_palette, self.o_palette)

    def test_neither_ds_nor_palette_raises(self):
        """Test missing `ds` and `palette` raise an exception."""
        ds = dcmread(PAL_08_256_0_16_1F)
        msg = r"Either 'ds' or 'palette' is required"
        with pytest.raises(ValueError, match=msg):
            apply_color_lut(ds.pixel_array)

    def test_palette_unknown_raises(self):
        """Test using an unknown `palette` raise an exception."""
        ds = dcmread(PAL_08_256_0_16_1F)
        # Palette name
        msg = r"Unknown palette 'TEST'"
        with pytest.raises(ValueError, match=msg):
            apply_color_lut(ds.pixel_array, palette='TEST')

        # SOP Instance UID
        msg = r"Unknown palette '1.2.840.10008.1.1'"
        with pytest.raises(ValueError, match=msg):
            apply_color_lut(ds.pixel_array, palette='1.2.840.10008.1.1')

    def test_palette_unavailable_raises(self):
        """Test using a missing `palette` raise an exception."""
        os.rename(self.o_palette, self.n_palette)
        ds = dcmread(PAL_08_256_0_16_1F)
        msg = r"list index out of range"
        with pytest.raises(IndexError, match=msg):
            apply_color_lut(ds.pixel_array, palette='PET')

    def test_supplemental_raises(self):
        """Test that supplemental palette color LUT raises exception."""
        ds = dcmread(SUP_16_16_2F)
        msg = (
            r"Use of this function with the Supplemental Palette Color Lookup "
            r"Table Module is not currently supported"
        )
        with pytest.raises(ValueError, match=msg):
            apply_color_lut(ds.pixel_array, ds)

    def test_invalid_bit_depth_raises(self):
        """Test that an invalid bit depth raises an exception."""
        ds = dcmread(PAL_08_256_0_16_1F)
        ds.RedPaletteColorLookupTableDescriptor[2] = 15
        msg = (
            r'data type "uint15" not understood'
        )
        with pytest.raises(TypeError, match=msg):
            apply_color_lut(ds.pixel_array, ds)

    def test_invalid_lut_bit_depth_raises(self):
        """Test that an invalid LUT bit depth raises an exception."""
        ds = dcmread(PAL_08_256_0_16_1F)
        ds.RedPaletteColorLookupTableData = (
            ds.RedPaletteColorLookupTableData[:-2]
        )
        ds.GreenPaletteColorLookupTableData = (
            ds.GreenPaletteColorLookupTableData[:-2]
        )
        ds.BluePaletteColorLookupTableData = (
            ds.BluePaletteColorLookupTableData[:-2]
        )
        msg = (
            r"The bit depth of the LUT data '15.9' is invalid \(only 8 or 16 "
            r"bits per entry allowed\)"
        )
        with pytest.raises(ValueError, match=msg):
            apply_color_lut(ds.pixel_array, ds)

    def test_unequal_lut_length_raises(self):
        """Test that an unequal LUT lengths raise an exception."""
        ds = dcmread(PAL_08_256_0_16_1F)
        ds.BluePaletteColorLookupTableData = (
            ds.BluePaletteColorLookupTableData[:-2]
        )
        msg = r"LUT data must be the same length"
        with pytest.raises(ValueError, match=msg):
            apply_color_lut(ds.pixel_array, ds)

    def test_uint08_16(self):
        """Test uint8 Pixel Data with 16-bit LUT entries."""
        ds = dcmread(PAL_08_200_0_16_1F, force=True)
        ds.file_meta = Dataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        arr = ds.pixel_array
        orig = arr.copy()
        rgb = apply_color_lut(arr, ds)
        assert (480, 640, 3) == rgb.shape
        assert [0, 0, 0] == list(rgb[0, 0, :])
        assert [9216, 9216, 9216] == list(rgb[0, 4, :])
        assert [18688, 18688, 18688] == list(rgb[0, 9, :])
        assert [27904, 33536, 0] == list(rgb[0, 638, :])
        assert [18688, 24320, 0] == list(rgb[479, 639, :])

        assert (orig == arr).all()

    def test_uint16_16_segmented(self):
        """Test uint16 Pixel Data with 16-bit LUT entries."""
        ds = dcmread(PAL_SEG_LE_16_1F)
        arr = ds.pixel_array
        orig = arr.copy()
        rgb = apply_color_lut(arr, ds)
        assert (480, 640, 3) == rgb.shape
        assert [10280, 11565, 16705] == list(rgb[0, 0, :])
        assert [10280, 11565, 16705] == list(rgb[0, 320, :])
        assert [10280, 11565, 16705] == list(rgb[0, 639, :])
        assert [0, 0, 0] == list(rgb[240, 0, :])
        assert [257, 257, 257] == list(rgb[240, 320, :])
        assert [2313, 2313, 2313] == list(rgb[240, 639, :])
        assert [10280, 11565, 16705] == list(rgb[479, 0, :])
        assert [10280, 11565, 16705] == list(rgb[479, 320, :])
        assert [10280, 11565, 16705] == list(rgb[479, 639, :])

        assert (orig == arr).all()

    def test_alpha(self):
        """Test applying a color palette with an alpha channel."""
        ds = dcmread(PAL_08_256_0_16_1F)
        ds.AlphaPaletteColorLookupTableData = b'\x00\x80' * 256
        arr = ds.pixel_array
        rgba = apply_color_lut(arr, ds)
        assert (600, 800, 4) == rgba.shape
        assert 32768 == rgba[:, :, 3][0, 0]
        assert (32768 == rgba[:, :, 3]).any()

    def test_well_known_palette(self):
        """Test using a well-known palette."""
        ds = dcmread(PAL_08_256_0_16_1F)
        # Drop it to 8-bit
        arr = ds.pixel_array
        rgb = apply_color_lut(arr, palette='PET')
        line = rgb[68:88, 364, :]
        ref = [
            [249, 122, 12],
            [255, 130, 4],
            [255, 136, 16],
            [255, 134, 12],
            [253, 126, 4],
            [239, 112, 32],
            [211, 84, 88],
            [197, 70, 116],
            [177, 50, 156],
            [168, 40, 176],
            [173, 46, 164],
            [185, 58, 140],
            [207, 80, 96],
            [209, 82, 92],
            [189, 62, 132],
            [173, 46, 164],
            [168, 40, 176],
            [162, 34, 188],
            [162, 34, 188],
            [154, 26, 204],
        ]
        assert np.array_equal(np.asarray(ref), line)
        uid = apply_color_lut(arr, palette='1.2.840.10008.1.5.2')
        assert np.array_equal(uid, rgb)

    def test_first_map_positive(self):
        """Test a positive first mapping value."""
        ds = dcmread(PAL_08_200_0_16_1F, force=True)
        ds.file_meta = Dataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        ds.RedPaletteColorLookupTableDescriptor[1] = 10
        arr = ds.pixel_array
        rgb = apply_color_lut(arr, ds)
        # All IVs < 10 should be set to LUT[0]
        # All IVs >= 10 should be shifted down 10 entries
        # Original IV range is 56 to 149 -> 46 to 139
        # LUT[88] -> LUT[78] = [33280, 56320, 65280]
        # LUT[149] -> LUT[139] = [50944, 16384, 27904]
        assert [33280, 56320, 65280] == list(rgb[arr == 88][0])
        assert ([33280, 56320, 65280] == rgb[arr == 88]).all()
        assert [50944, 16384, 27904] == list(rgb[arr == 149][0])
        assert ([50944, 16384, 27904] == rgb[arr == 149]).all()

    def test_first_map_negative(self):
        """Test a positive first mapping value."""
        ds = dcmread(PAL_08_200_0_16_1F, force=True)
        ds.file_meta = Dataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        ds.RedPaletteColorLookupTableDescriptor[1] = -10
        arr = ds.pixel_array
        rgb = apply_color_lut(arr, ds)
        # All IVs < -10 should be set to LUT[0]
        # All IVs >= -10 should be shifted up 10 entries
        # Original IV range is 56 to 149 -> 66 to 159
        # LUT[60] -> LUT[70] = [33280 61952 65280]
        # LUT[130] -> LUT[140] = [60160, 25600, 37376]
        assert [33280, 61952, 65280] == list(rgb[arr == 60][0])
        assert ([33280, 61952, 65280] == rgb[arr == 60]).all()
        assert [60160, 25600, 37376] == list(rgb[arr == 130][0])
        assert ([60160, 25600, 37376] == rgb[arr == 130]).all()


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestNumpy_ExpandSegmentedLUT(object):
    """Tests for util._expand_segmented_lut()."""
    def test_discrete(self):
        """Test expanding a discrete segment."""
        data = (0, 1, 0)
        assert [0] == _expand_segmented_lut(data, 'H')

        data = (0, 2, 0, 112)
        assert [0, 112] == _expand_segmented_lut(data, 'H')

        data = (0, 2, 0, -112)
        assert [0, -112] == _expand_segmented_lut(data, 'H')

        data = (0, 2, 0, 112, 0, 0)
        assert [0, 112] == _expand_segmented_lut(data, 'H')

        data = (0, 2, 0, -112, 0, 0)
        assert [0, -112] == _expand_segmented_lut(data, 'H')

    def test_linear(self):
        """Test expanding a linear segment."""
        # Linear can never be the first segment
        # Positive slope
        data = (0, 2, 0, 28672, 1, 5, 49152)
        out = _expand_segmented_lut(data, 'H')
        assert [0, 28672, 32768, 36864, 40960, 45056, 49152] == out

        data = (0, 1, -400, 1, 5, 0)
        out = _expand_segmented_lut(data, 'H')
        assert [-400, -320, -240, -160, -80, 0] == out

        # No slope
        data = (0, 2, 0, 28672, 1, 5, 28672)
        out = _expand_segmented_lut(data, 'H')
        assert [0, 28672, 28672, 28672, 28672, 28672, 28672] == out

        data = (0, 1, -100, 1, 5, -100)
        out = _expand_segmented_lut(data, 'H')
        assert [-100, -100, -100, -100, -100, -100] == out

        # Negative slope
        data = (0, 2, 0, 49152, 1, 5, 28672)
        out = _expand_segmented_lut(data, 'H')
        assert [0, 49152, 45056, 40960, 36864, 32768, 28672] == out

        data = (0, 1, 0, 1, 5, -400)
        out = _expand_segmented_lut(data, 'H')
        assert [0, -80, -160, -240, -320, -400] == out

    def test_indirect_08(self):
        """Test expanding an indirect segment encoded as 8-bit."""
        # No real world test data available for this
        # LSB, MSB
        ref_a = [0, 112, 128, 144, 160, 176, 192, 192, 192, 192, 192, 192]

        # Little endian
        data = (0, 2, 0, 112, 1, 5, 192, 2, 1, 4, 0, 0, 0)
        out = _expand_segmented_lut(data, '<B')
        assert ref_a == out

        data = (0, 2, 0, 112, 2, 1, 0, 0, 0, 0)
        out = _expand_segmented_lut(data, '<B')
        assert [0, 112, 0, 112] == out

        # 0x0100 0x0302 is 66051 in LE 16-bit MSB, LSB
        data = [0, 1, 0] * 22017 + [0, 2, 1, 2] + [2, 1, 3, 2, 1, 0]
        out = _expand_segmented_lut(data, '<B')
        assert [0] * 22017 + [1, 2, 1, 2] == out

        # Big endian
        data = (0, 2, 0, 112, 1, 5, 192, 2, 1, 0, 4, 0, 0)
        out = _expand_segmented_lut(data, '>B')
        assert ref_a == out

        data = (0, 2, 0, 112, 2, 1, 0, 0, 0, 0)
        out = _expand_segmented_lut(data, '>B')
        assert [0, 112, 0, 112] == out

        # 0x0001 0x0203 is 66051 in BE 16-bit MSB, LSB
        data = [0, 1, 0] * 22017 + [0, 2, 1, 2] + [2, 1, 2, 3, 0, 1]
        out = _expand_segmented_lut(data, '>B')
        assert [0] * 22017 + [1, 2, 1, 2] == out

    def test_indirect_16(self):
        """Test expanding an indirect segment encoded as 16-bit."""
        # Start from a discrete segment
        data = (0, 2, 0, 112, 1, 5, 192, 2, 2, 0, 0)
        out = _expand_segmented_lut(data, 'H')
        assert [0, 112, 128, 144, 160, 176, 192] * 2 == out

        # Start from a linear segment
        data = (0, 2, 0, 112, 1, 5, 192, 2, 1, 4, 0)
        out = _expand_segmented_lut(data, 'H')
        assert [
            0, 112, 128, 144, 160, 176, 192, 192, 192, 192, 192, 192
        ] == out

    def test_palettes_spring(self):
        """Test expanding the SPRING palette."""
        ds = dcmread(get_palette_files('spring.dcm')[0])

        bs = ds.SegmentedRedPaletteColorLookupTableData
        fmt = '<{}B'.format(len(bs))
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert [255] * 256 == out

        bs = ds.SegmentedGreenPaletteColorLookupTableData
        fmt = '<{}B'.format(len(bs))
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert list(range(0, 256)) == out

        bs = ds.SegmentedBluePaletteColorLookupTableData
        fmt = '<{}B'.format(len(bs))
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert list(range(255, -1, -1)) == out

    def test_palettes_summer(self):
        """Test expanding the SUMMER palette."""
        ds = dcmread(get_palette_files('summer.dcm')[0])

        bs = ds.SegmentedRedPaletteColorLookupTableData
        fmt = '<{}B'.format(len(bs))
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert [0] * 256 == out

        bs = ds.SegmentedGreenPaletteColorLookupTableData
        fmt = '<{}B'.format(len(bs))
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert [255, 255, 254, 254, 253] == out[:5]
        assert [130, 129, 129, 128, 128] == out[-5:]

        bs = ds.SegmentedBluePaletteColorLookupTableData
        fmt = '<{}B'.format(len(bs))
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert [0] * 128 == out[:128]
        assert [246, 248, 250, 252, 254] == out[-5:]

    def test_palettes_fall(self):
        """Test expanding the FALL palette."""
        ds = dcmread(get_palette_files('fall.dcm')[0])

        bs = ds.SegmentedRedPaletteColorLookupTableData
        fmt = '<{}B'.format(len(bs))
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert [255] * 256 == out

        bs = ds.SegmentedGreenPaletteColorLookupTableData
        fmt = '<{}B'.format(len(bs))
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert list(range(255, -1, -1)) == out

        bs = ds.SegmentedBluePaletteColorLookupTableData
        fmt = '<{}B'.format(len(bs))
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert [0] * 256 == out

    def test_palettes_winter(self):
        """Test expanding the WINTER palette."""
        ds = dcmread(get_palette_files('winter.dcm')[0])

        bs = ds.SegmentedRedPaletteColorLookupTableData
        fmt = '<{}B'.format(len(bs))
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert [0] * 128 == out[:128]
        assert [123, 124, 125, 126, 127] == out[-5:]

        bs = ds.SegmentedGreenPaletteColorLookupTableData
        fmt = '<{}B'.format(len(bs))
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert list(range(0, 256)) == out

        bs = ds.SegmentedBluePaletteColorLookupTableData
        fmt = '<{}B'.format(len(bs))
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert [255, 255, 254, 254, 253] == out[:5]
        assert [130, 129, 129, 128, 128] == out[-5:]

    def test_first_linear_raises(self):
        """Test having a linear segment first raises exception."""
        data = (1, 5, 49152)
        msg = (
            r"Error expanding a segmented palette color lookup table: "
            r"the first segment cannot be a linear segment"
        )
        with pytest.raises(ValueError, match=msg):
            _expand_segmented_lut(data, 'H')

    def test_unknown_opcode_raises(self):
        """Test having an unknown opcode raises exception."""
        data = (3, 5, 49152)
        msg = (
            r"Error expanding a segmented palette lookup table: "
            r"unknown segment type '3'"
        )
        with pytest.raises(ValueError, match=msg):
            _expand_segmented_lut(data, 'H')
