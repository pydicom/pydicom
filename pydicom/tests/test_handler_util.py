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
    from pydicom.pixel_data_handlers import numpy_handler as NP_HANDLER
    from pydicom.pixel_data_handlers.util import (
        dtype_corrected_for_endianess,
        reshape_pixel_array,
        convert_YBR_to_RGB,
        pixel_dtype
    )
    HAVE_NP = True
except ImportError:
    HAVE_NP = False
    NP_HANDLER = None

from pydicom.dataset import Dataset
from pydicom.uid import ExplicitVRLittleEndian


# Tests with Numpy unavailable
@pytest.mark.skipif(HAVE_NP, reason='Numpy is available')
class TestNoNumpy_PixelDtype(object):
    pass


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


RESHAPE_ARRAYS = {
    'reference' : np.asarray([
        [  # Frame 1
            [[ 1,  9, 17],
             [ 2, 10, 18],
             [ 3, 11, 19],
             [ 4, 12, 20],
             [ 5, 13, 21]],
            [[ 2, 10, 18],
             [ 3, 11, 19],
             [ 4, 12, 20],
             [ 5, 13, 21],
             [ 6, 14, 22]],
            [[ 3, 11, 19],
             [ 4, 12, 20],
             [ 5, 13, 21],
             [ 6, 14, 22],
             [ 7, 15, 23]],
            [[ 4, 12, 20],
             [ 5, 13, 21],
             [ 6, 14, 22],
             [ 7, 15, 23],
             [ 8, 16, 24]],
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
    '1frame_1sample' : np.asarray([]),
    '2frame_1sample' : np.asarray([]),
    '1frame_3sample_0config' : np.asarray([]),
    '1frame_3sample_1config' : np.asarray([]),
    '2frame_3sample_0config' : np.asarray(
        [ 1,  9, 17,  2, 10, 18,  3, 11, 19,  4, 12, 20,  # Frame 1
          5, 13, 21,  2, 10, 18,  3, 11, 19,  4, 12, 20,
          5, 13, 21,  6, 14, 22,  3, 11, 19,  4, 12, 20,
          5, 13, 21,  6, 14, 22,  7, 15, 23,  4, 12, 20,
          5, 13, 21,  6, 14, 22,  7, 15, 23,  8, 16, 24,
         25, 33, 41, 26, 34, 42, 27, 35, 43, 28, 36, 44,  # Frame 2
         29, 37, 45, 26, 34, 42, 27, 35, 43, 28, 36, 44,
         29, 37, 45, 30, 38, 46, 27, 35, 43, 28, 36, 44,
         29, 37, 45, 30, 38, 46, 31, 39, 47, 28, 36, 44,
         29, 37, 45, 30, 38, 46, 31, 39, 47, 32, 40, 48]
    ),
    '2frame_3sample_1config' : np.asarray(
        [ 1,  2,  3,  4,  5,  2,  3,  4,  5,  6,  # Frame 1, red
          3,  4,  5,  6,  7,  4,  5,  6,  7,  8,
          9, 10, 11, 12, 13, 10, 11, 12, 13, 14,  # Frame 1, green
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

    def test_reference(self):
        """Test that the reference array is as expected."""
        arr = RESHAPE_ARRAYS['reference']
        # (nr frames, row, columns, samples/pixel)
        assert (2, 4, 5, 3) == arr.shape

        # Red channel, frame 1
        assert np.array_equal(
            arr[0, :, :, 0],
            np.asarray(
                [[1, 2, 3, 4, 5],
                 [2, 3, 4, 5, 6],
                 [3, 4, 5, 6, 7],
                 [4, 5, 6, 7, 8]]
            )
        )
        # Green channel, frame 2
        assert np.array_equal(
            arr[1, :, :, 1],
            np.asarray(
                [[33, 34, 35, 36, 37],
                 [34, 35, 36, 37, 38],
                 [35, 36, 37, 38, 39],
                 [36, 37, 38, 39, 40]]
            )
        )
        #import matplotlib.pyplot as plt
        #plt.imshow(arr[0, :, :])
        #plt.show()

    def test_1frame_1sample(self):
        arr = RESHAPE_ARRAYS[]

    def test_1frame_3sample_no_conf(self):
        pass

    def test_1frame_3sample_0conf(self):
        pass

    def test_1frame_3sample_1conf(self):
        pass

    def test_2frame_1sample(self):
        pass

    def test_2frame_3sample_no_conf(self):
        pass

    def test_2frame_3sample_0conf(self):
        pass

    def test_2frame_3sample_1conf(self):
        pass

    def test_3sample_0conf_compressed_syntax(self):
        pass

    def test_3sample_1conf_compressed_syntax(self):
        pass
