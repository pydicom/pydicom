"""Unit tests for the pydicom.encoders module."""

import pytest

try:
    import numpy as np
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom.dataset import Dataset
from pydicom.encoders import EncoderFactory
from pydicom.uid import RLELossless


@pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
class TestEncoderFactory:
    """Tests for encoders.EncoderFactory."""
    def setup(self):
        self.e = EncoderFactory(RLELossless)
        self.ds = ds = Dataset()
        ds.Rows = 1
        ds.Columns = 3
        ds.SamplesPerPixel = 1
        ds.PixelRepresentation = 0
        ds.BitsAllocated = 8
        ds.BitsStored = 8
        ds.NumberOfFrames = 1

        self.arr_3s = np.asarray(
            [
                [[ 1,  2,  3], [ 4,  5,  6]],
                [[ 7,  8,  9], [10, 11, 12]],
                [[13, 14, 15], [16, 17, 18]],
                [[19, 20, 21], [22, 23, 24]],
            ],
            '|u1'
        )
        assert (4, 2, 3) == self.arr_3s.shape

    # Tests for EncoderFactory._process_array()
    def test_bad_arr_shape_raises(self):
        """Test that an array size and dataset mismatch raise exceptions"""
        # 1D arrays
        arr = np.asarray((1, 2, 3, 4))
        msg = r"The shape of the array doesn't match the dataset"

        assert (4, ) == arr.shape
        with pytest.raises(ValueError, match=msg):
            self.e._process_frame(arr, self.ds)

        # 2D arrays
        arr = np.asarray([[1, 2, 3, 4]])
        assert (1, 4) == arr.shape
        with pytest.raises(ValueError, match=msg):
            self.e._process_frame(arr, self.ds)

        self.ds.Rows = 2
        self.ds.Columns = 2
        self.ds.SamplesPerPixel = 3
        arr = np.asarray([[1, 2], [3, 4]])
        assert (2, 2) == arr.shape
        with pytest.raises(ValueError, match=msg):
            self.e._process_frame(arr, self.ds)

        # 3D arrays
        self.ds.Rows = 3
        arr = np.asarray([[[1, 2, 1], [3, 4, 1]]])
        assert (1, 2, 3) == arr.shape
        with pytest.raises(ValueError, match=msg):
            self.e._process_frame(arr, self.ds)

        # 4D arrays
        arr = np.asarray([[[[1, 2, 1], [3, 4, 1]]]])
        assert (1, 1, 2, 3) == arr.shape
        msg = r"The maximum supported array dimensions is 4"
        with pytest.raises(ValueError, match=msg):
            self.e._process_frame(arr, self.ds)

    def test_invalid_bits_allocated_raises(self):
        """Test exception raised for invalid Bits Allocated"""
        self.ds.BitsAllocated = 9
        self.ds.BitsStored = 8
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        arr = np.asarray([1, 2, 3], dtype='|u1')
        msg = r"Unsupported 'Bits Allocated' must be 8, 16, 32 or 64"
        with pytest.raises(ValueError, match=msg):
            self.e._process_frame(arr, self.ds)

    def test_invalid_pixel_representation_raises(self):
        """Test exception raised if pixel representation/dtype mismatch"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        arr = np.asarray([1, 2, 3], dtype='|i1')
        msg = r"Incompatible array dtype and dataset 'Pixel Representation'"
        with pytest.raises(ValueError, match=msg):
            self.e._process_frame(arr, self.ds)

        self.ds.PixelRepresentation = 1
        arr = np.asarray([1, 2, 3], dtype='|u1')
        with pytest.raises(ValueError, match=msg):
            self.e._process_frame(arr, self.ds)

    def test_u8_1s_as_u8(self):
        """Test processing u8/1s"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        arr = np.asarray([1, 2, 3], dtype='|u1')
        out = self.e._process_frame(arr, self.ds)
        assert 3 == len(out)
        assert b"\x01\x02\x03" == out

    def test_u8_1s_as_u16(self):
        """Test processing u8/1s w/ upscale to u16/1s"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        arr = np.asarray([1, 2, 3], dtype='|u1')
        out = self.e._process_frame(arr, self.ds)
        assert 6 == len(out)
        assert b"\x01\x00\x02\x00\x03\x00" == out

    def test_u8_1s_as_u32(self):
        """Test processing u8/1s w/ upscale to u32/1s"""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        arr = np.asarray([1, 2, 3], dtype='|u1')
        out = self.e._process_frame(arr, self.ds)
        assert 12 == len(out)
        assert b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00" == out

    def test_u8_3s_as_u8(self):
        """Test processing u8/3s"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 4
        self.ds.Columns = 2
        self.ds.SamplesPerPixel = 3
        out = self.e._process_frame(self.arr_3s, self.ds)
        assert 24 == len(out)
        assert bytes(range(1, 25)) == out

    def test_u8_3s_as_u16(self):
        """Test processing u8/3s w/ upscale to u16/3s"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 4
        self.ds.Columns = 2
        self.ds.SamplesPerPixel = 3
        ref = b''.join([bytes([b]) + b'\x00' for b in bytes(range(1, 25))])

        out = self.e._process_frame(self.arr_3s, self.ds)
        assert 48 == len(out)
        assert ref == out

    def test_u8_3s_as_u32(self):
        """Test processing u8/3s w/ upscale to u32/3s"""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 4
        self.ds.Columns = 2
        self.ds.SamplesPerPixel = 3
        ref = b''.join([bytes([b]) + b'\x00' * 3 for b in bytes(range(1, 25))])

        out = self.e._process_frame(self.arr_3s, self.ds)
        assert 96 == len(out)
        assert ref == out

    def test_u16_1s_as_u16(self):
        """Test processing u16/3s"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3
        self.ds.SamplesPerPixel = 1

        # Test big-endian
        arr = np.asarray([1, 2, 3], dtype='>u2')
        out = self.e._process_frame(arr, self.ds)
        assert 6 == len(out)
        assert b"\x01\x00\x02\x00\x03\x00" == out

        # Test little-endian
        arr = np.asarray([1, 2, 3], dtype='<u2')
        out = self.e._process_frame(arr, self.ds)
        assert 6 == len(out)
        assert b"\x01\x00\x02\x00\x03\x00" == out

        # Test native
        arr = np.asarray([1, 2, 3], dtype='=u2')
        out = self.e._process_frame(arr, self.ds)
        assert 6 == len(out)
        assert b"\x01\x00\x02\x00\x03\x00" == out

    def test_u16_1s_as_u32(self):
        """Test processing u16/3s"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3
        self.ds.SamplesPerPixel = 1

        # Test big-endian
        arr = np.asarray([1, 2, 3], dtype='>u2')
        out = self.e._process_frame(arr, self.ds)
        assert 6 == len(out)
        assert b"\x01\x00\x02\x00\x03\x00" == out

        # Test little-endian
        arr = np.asarray([1, 2, 3], dtype='<u2')
        out = self.e._process_frame(arr, self.ds)
        assert 6 == len(out)
        assert b"\x01\x00\x02\x00\x03\x00" == out

    def test_u16_3s_as_u16(self):
        """Test processing u16/3s"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.SamplesPerPixel = 3
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 4
        self.ds.Columns = 2
        ref = b''.join([bytes([b]) + b'\x00' for b in bytes(range(1, 25))])

        # Test big-endian
        out = self.e._process_frame(self.arr_3s.astype('>u2'), self.ds)
        assert 48 == len(out)
        assert ref == out

        # Test little-endian
        out = self.e._process_frame(self.arr_3s.astype('<u2'), self.ds)
        assert 48 == len(out)
        assert ref == out

    def test_u16_3s_as_u32(self):
        """Test processing u16/3s"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.SamplesPerPixel = 3
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 4
        self.ds.Columns = 2
        ref = b''.join([bytes([b]) + b'\x00' for b in bytes(range(1, 25))])

        # Test big-endian
        out = self.e._process_frame(self.arr_3s.astype('>u2'), self.ds)
        assert 48 == len(out)
        assert ref == out

        # Test little-endian
        out = self.e._process_frame(self.arr_3s.astype('<u2'), self.ds)
        assert 48 == len(out)
        assert ref == out

    def test_u32_1s_as_u32(self):
        """Test processing u32/1s"""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3
        ref = b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00"

        # Test big-endian
        arr = np.asarray([1, 2, 3], dtype='>u4')
        out = self.e._process_frame(arr, self.ds)
        assert 12 == len(out)
        assert ref == out

        # Test little-endian
        arr = np.asarray([1, 2, 3], dtype='<u4')
        out = self.e._process_frame(arr, self.ds)
        assert 12 == len(out)
        assert ref == out

        # Test native
        arr = np.asarray([1, 2, 3], dtype='=u4')
        out = self.e._process_frame(arr, self.ds)
        assert 12 == len(out)
        assert ref == out

    def test_u32_3s_as_u32(self):
        """Test processing u32/3s"""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.SamplesPerPixel = 3
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 4
        self.ds.Columns = 2

        ref = b''.join([bytes([b]) + b'\x00' * 3 for b in bytes(range(1, 25))])

        out = self.e._process_frame(self.arr_3s.astype('>u4'), self.ds)
        assert 96 == len(out)
        assert ref == out
        out = self.e._process_frame(self.arr_3s.astype('<u4'), self.ds)
        assert 96 == len(out)
        assert ref == out
