# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Tests for the pixel_data_handlers.util module.

Numpy required
--------------
* reshape_pixel_array
* convert_YBR_to_RGB
* pixel_dtype

Numpy not required
------------------
* dtype_corrected_for_endianess
"""

from sys import byteorder

import pytest

try:
    import numpy as np
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom.dataset import Dataset
from pydicom.pixel_data_handlers.util import (
    dtype_corrected_for_endianess,
    reshape_pixel_array,
    convert_YBR_to_RGB,
    pixel_dtype
)
from pydicom.uid import (ExplicitVRLittleEndian,
                         UncompressedPixelTransferSyntaxes)


# Tests with Numpy unavailable
@pytest.mark.skipif(HAVE_NP, reason='Numpy is available')
class TestNoNumpy(object):
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
    """Tests for numpy_handler.pixel_dtype."""
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
        with pytest.raises(NotImplementedError,
                           match="value of '-1' for '\(0028,0103"):
            pixel_dtype(self.ds)

        self.ds.PixelRepresentation = 2
        with pytest.raises(NotImplementedError,
                           match="value of '2' for '\(0028,0103"):
            pixel_dtype(self.ds)

    def test_unknown_bits_allocated_raises(self):
        """Test an unknown BitsAllocated value raises exception."""
        self.ds.BitsAllocated = 0
        self.ds.PixelRepresentation = 0
        # The bracket needs to be escaped
        with pytest.raises(NotImplementedError,
                           match="value of '0' for '\(0028,0100"):
            pixel_dtype(self.ds)

        self.ds.BitsAllocated = 2
        with pytest.raises(NotImplementedError,
                           match="value of '2' for '\(0028,0100"):
            pixel_dtype(self.ds)

        self.ds.BitsAllocated = 15
        with pytest.raises(NotImplementedError,
                           match="value of '15' for '\(0028,0100"):
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
    """Tests for numpy_handler.pixel_dtype."""
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
                [[ 9, 10, 11, 12, 13],
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
        with pytest.raises(NotImplementedError,
                           match="value of 0 for \(0028,0008\)"):
            reshape_pixel_array(self.ds, RESHAPE_ARRAYS['1frame_1sample'])

    def test_invalid_samples_raises(self):
        """Test an invalid Samples per Pixel value raises exception."""
        self.ds.SamplesPerPixel = 0
        # Need to escape brackets
        with pytest.raises(NotImplementedError,
                           match="value of 0 for \(0028,0002\)"):
            reshape_pixel_array(self.ds, RESHAPE_ARRAYS['1frame_1sample'])

    def test_invalid_planar_conf_raises(self):
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 2
        # Need to escape brackets
        with pytest.raises(NotImplementedError,
                           match="value of 2 for \(0028,0006\)"):
            reshape_pixel_array(self.ds,
                                RESHAPE_ARRAYS['1frame_3sample_0config'])
