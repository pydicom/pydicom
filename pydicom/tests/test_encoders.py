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
class TestEncoderFactory_ProcessFrame:
    """Tests for encoders.EncoderFactory._process_frame."""
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

    @pytest.mark.skip()
    def test_invalid_samples_per_pixel_raises(self):
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

    # Unsigned 8-bit processing
    def test_u08_1s_as_u08(self):
        """Test processing u8/1s"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        arr = np.asarray([1, 2, 3], dtype='|u1')
        assert 1 == arr.dtype.itemsize
        out = self.e._process_frame(arr, self.ds)
        assert 3 == len(out)
        assert b"\x01\x02\x03" == out

    def test_u08_1s_as_u16(self):
        """Test processing u8/1s w/ upsize to u16"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        arr = np.asarray([1, 2, 3], dtype='|u1')
        assert 1 == arr.dtype.itemsize
        out = self.e._process_frame(arr, self.ds)
        assert 6 == len(out)
        assert b"\x01\x00\x02\x00\x03\x00" == out

    def test_u08_1s_as_u32(self):
        """Test processing u8/1s w/ upsize to u32"""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        arr = np.asarray([1, 2, 3], dtype='|u1')
        assert 1 == arr.dtype.itemsize
        out = self.e._process_frame(arr, self.ds)
        assert 12 == len(out)
        assert b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00" == out

    def test_u08_3s_as_u08(self):
        """Test processing u8/3s"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 4
        self.ds.Columns = 2
        self.ds.SamplesPerPixel = 3

        arr = self.arr_3s.astype('|u1')
        assert 1 == arr.dtype.itemsize
        out = self.e._process_frame(arr, self.ds)
        assert 24 == len(out)
        assert bytes(range(1, 25)) == out

    # Signed 8-bit processing
    def test_i08_1s_as_i08(self):
        """Test processing i8/1s"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 1
        self.ds.Columns = 3

        arr = np.asarray([-128, 0, 127], dtype='|i1')
        assert 1 == arr.dtype.itemsize
        out = self.e._process_frame(arr, self.ds)
        assert 3 == len(out)
        assert b"\x80\x00\x7f" == out

    def test_i08_1s_as_i16(self):
        """Test processing i8/1s w/ upsize to i16"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 1
        self.ds.Columns = 3

        arr = np.asarray([-128, 0, 127], dtype='|i1')
        assert 1 == arr.dtype.itemsize
        out = self.e._process_frame(arr, self.ds)
        assert 6 == len(out)
        assert b"\x80\x00\x00\x00\x7f\x00" == out

    def test_i08_1s_as_i32(self):
        """Test processing i8/1s w/ upsize to i32"""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 1
        self.ds.Columns = 3

        arr = np.asarray([-128, 0, 127], dtype='|i1')
        assert 1 == arr.dtype.itemsize
        out = self.e._process_frame(arr, self.ds)
        assert 12 == len(out)
        assert b"\x80\x00\x00\x00\x00\x00\x00\x00\x7f\x00\x00\x00" == out

    # Unsigned 16-bit processing
    def test_u16_1s_as_u08(self):
        """Test processing u16/1s w/ downsize to u8"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3
        self.ds.SamplesPerPixel = 1

        for dtype in ('>u2', '<u2', '=u2'):
            arr = np.asarray([255, 127, 0], dtype=dtype)
            assert 2 == arr.dtype.itemsize
            out = self.e._process_frame(arr, self.ds)
            assert 3 == len(out)
            assert b"\xff\x7f\x00" == out

    def test_u16_1s_as_u08_overflow_raises(self):
        """Test processing u16/3s w/ downsize to u8 raises on overflow"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3
        self.ds.SamplesPerPixel = 1

        msg = (
            r"Cannot modify the array to match 'Bits Allocated' without "
            r"clipping the pixel values"
        )
        for dtype in ('>u2', '<u2', '=u2'):
            arr = np.asarray([256, 2, 3], dtype=dtype)
            assert 2 == arr.dtype.itemsize
            with pytest.raises(ValueError, match=msg):
                self.e._process_frame(arr, self.ds)

    def test_u16_1s_as_u16(self):
        """Test processing u16/1s"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3
        self.ds.SamplesPerPixel = 1

        for dtype in ('>u2', '<u2', '=u2'):
            arr = np.asarray([1, 2, 3], dtype=dtype)
            assert 2 == arr.dtype.itemsize
            out = self.e._process_frame(arr, self.ds)
            assert 6 == len(out)
            assert b"\x01\x00\x02\x00\x03\x00" == out

    def test_u16_1s_as_u32(self):
        """Test processing u16/1s w/ upsize to u32"""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3
        self.ds.SamplesPerPixel = 1

        for dtype in ('>u2', '<u2', '=u2'):
            arr = np.asarray([1, 2, 3], dtype=dtype)
            assert 2 == arr.dtype.itemsize
            out = self.e._process_frame(arr, self.ds)
            assert 12 == len(out)
            assert b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00" == out

    def test_u16_3s_as_u16(self):
        """Test processing u16/3s"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.SamplesPerPixel = 3
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 4
        self.ds.Columns = 2
        ref = b''.join([bytes([b]) + b'\x00' for b in bytes(range(1, 25))])

        for dtype in ('>u2', '<u2', '=u2'):
            arr = self.arr_3s.astype(dtype)
            assert 2 == arr.dtype.itemsize
            out = self.e._process_frame(arr, self.ds)
            assert 48 == len(out)
            assert ref == out

    # Signed 16-bit processing

    # Unsigned 32-bit processing
    def test_u32_1s_as_u08(self):
        """Test processing u32/1s w/ downsize to u8"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        for dtype in ('>u4', '<u4', '=u4'):
            arr = np.asarray([255, 127, 0], dtype=dtype)
            assert 4 == arr.dtype.itemsize
            out = self.e._process_frame(arr, self.ds)
            assert 3 == len(out)
            assert b"\xff\x7f\x00" == out

    def test_u32_1s_as_u08_overflow_raises(self):
        """Test processing u32/1s w/ downsize to u8 raises on overflow"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        msg = (
            r"Cannot modify the array to match 'Bits Allocated' without "
            r"clipping the pixel values"
        )
        for dtype in ('>u4', '<u4', '=u4'):
            arr = np.asarray([256, 2, 3], dtype=dtype)
            assert 4 == arr.dtype.itemsize
            with pytest.raises(ValueError, match=msg):
                self.e._process_frame(arr, self.ds)

    def test_u32_1s_as_u16(self):
        """Test processing u32/1s w/ downsize to u16"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        for dtype in ('>u4', '<u4', '=u4'):
            arr = np.asarray([1, 2, 3], dtype=dtype)
            assert 4 == arr.dtype.itemsize
            out = self.e._process_frame(arr, self.ds)
            assert 6 == len(out)
            assert b"\x01\x00\x02\x00\x03\x00" == out

    def test_u32_1s_as_u16_overflow_raises(self):
        """Test processing u32/1s w/ downsize to u16 raises on overflow"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        msg = (
            r"Cannot modify the array to match 'Bits Allocated' without "
            r"clipping the pixel values"
        )
        for dtype in ('>u4', '<u4', '=u4'):
            arr = np.asarray([65536, 2, 3], dtype=dtype)
            assert 4 == arr.dtype.itemsize
            with pytest.raises(ValueError, match=msg):
                self.e._process_frame(arr, self.ds)

    def test_u32_1s_as_u32(self):
        """Test processing u32/1s"""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3
        ref = b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00"

        for dtype in ('>u4', '<u4', '=u4'):
            arr = np.asarray([1, 2, 3], dtype=dtype)
            assert 4 == arr.dtype.itemsize
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

        for dtype in ('>u4', '<u4', '=u4'):
            arr = self.arr_3s.astype(dtype)
            assert 4 == arr.dtype.itemsize
            out = self.e._process_frame(arr, self.ds)
            assert 96 == len(out)
            assert ref == out

    # Signed 32-bit processing
