"""Tests for pydicom.pixels.encoders.base and Dataset.compress()."""

import importlib
import logging

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom import config, examples
from pydicom.data import get_testdata_file
from pydicom.dataset import Dataset
from pydicom.pixels.encoders import RLELosslessEncoder
from pydicom.pixels.common import PhotometricInterpretation as PI
from pydicom.pixels.encoders.base import Encoder, EncodeRunner
from pydicom.pixels.utils import get_expected_length
from pydicom.uid import (
    UID,
    RLELossless,
    JPEGLSLossless,
    JPEG2000MC,
    JPEG2000Lossless,
    JPEGLSNearLossless,
)

from .pixels_reference import (
    PIXEL_REFERENCE,
    RLE_16_1_1F,
    EXPL_16_16_1F,
)


HAVE_GDCM = bool(importlib.util.find_spec("gdcm"))
HAVE_PYLJ = bool(importlib.util.find_spec("pylibjpeg"))
HAVE_RLE = bool(importlib.util.find_spec("rle"))


class TestEncodeRunner:
    """Tests for EncodeRunner."""

    def test_init(self):
        """Test initial creation."""
        runner = EncodeRunner(RLELossless)
        assert runner.transfer_syntax == RLELossless
        assert runner.get_option("pixel_keyword") == "PixelData"
        assert runner.get_option("byteorder") == "<"

    def test_set_source_dataset(self):
        """Test setting runner source and options via dataset."""
        runner = EncodeRunner("1.2.3.4")
        runner.set_source(RLE_16_1_1F.ds)
        assert runner.bits_allocated == 16
        assert runner.bits_stored == 16
        assert runner.columns == 64
        assert runner.number_of_frames == 1
        assert runner.photometric_interpretation == PI.MONOCHROME2
        assert runner.pixel_keyword == "PixelData"
        assert runner.pixel_representation == 1
        assert runner.rows == 64
        assert runner.samples_per_pixel == 1
        assert runner.get_option("planar_configuration") is None
        assert runner.is_dataset
        assert runner.transfer_syntax == "1.2.3.4"
        assert runner.src is RLE_16_1_1F.ds.PixelData

        ds = Dataset()
        ds.BitsAllocated = 32
        ds.BitsStored = 24
        ds.Columns = 10
        ds.Rows = 8
        ds.SamplesPerPixel = 3
        ds.NumberOfFrames = "5"
        ds.PixelData = None
        ds.PlanarConfiguration = 1
        ds.PixelRepresentation = 0
        ds.PhotometricInterpretation = "PALETTE COLOR"
        runner.set_source(ds)

        assert runner.is_dataset
        assert runner.bits_allocated == 32
        assert runner.bits_stored == 24
        assert runner.columns == 10
        assert runner.number_of_frames == 5
        assert runner.photometric_interpretation == PI.PALETTE_COLOR
        assert runner.pixel_keyword == "PixelData"
        assert runner.pixel_representation == 0
        assert runner.rows == 8
        assert runner.samples_per_pixel == 3
        assert runner.planar_configuration == 1

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_set_source_ndarray(self):
        """Setting runner source using an ndarray."""
        runner = EncodeRunner(RLELossless)
        arr = np.ones((1, 2, 3), dtype="<u2")
        runner.set_source(arr)
        assert runner.is_array
        assert runner.src is arr

        # Test switching byte order to little endian
        arr = arr.astype(">u2")
        assert arr.dtype.byteorder == ">"
        runner.set_source(arr)
        assert runner.is_array
        assert runner.src is not arr
        assert runner.src.dtype.byteorder == "<"
        assert np.array_equal(runner.src, np.ones((1, 2, 3)))

    def test_set_source_buffer(self):
        """Setting runner source using a buffer-like."""
        runner = EncodeRunner(RLELossless)
        b = b"\x00\x01\x02\x03"
        runner.set_source(b)
        assert runner.is_buffer
        assert runner.src is b

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_set_source_raises(self):
        """Test runner.set_source() raises if unknown type."""
        runner = EncodeRunner(RLELossless)
        msg = (
            "'src' must be bytes, numpy.ndarray or pydicom.dataset.Dataset, "
            "not 'NoneType'"
        )
        with pytest.raises(TypeError, match=msg):
            runner.set_source(None)

    def test_str(self):
        """Test str(EncodeRunner)"""
        runner = EncodeRunner(RLELossless)
        runner.set_encoders({"foo": None})
        assert str(runner) == (
            "EncodeRunner for 'RLE Lossless'\n"
            "Options\n"
            "  transfer_syntax_uid: 1.2.840.10008.1.2.5\n"
            "  byteorder: <\n"
            "  pixel_keyword: PixelData\n"
            "Encoders\n"
            "  foo"
        )

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_validate_array_dimensions(self):
        """Test the ndarray dimensions validation."""
        runner = EncodeRunner(RLELossless)
        runner._src = np.ones((1,))
        msg = "Unable to encode 1D ndarrays"
        with pytest.raises(ValueError, match=msg):
            runner._validate_array()

        runner._src = np.ones((1, 2, 3, 4, 5))
        msg = "Unable to encode 5D ndarrays"
        with pytest.raises(ValueError, match=msg):
            runner._validate_array()

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_validate_array_shape(self):
        """Test the ndarray shape validation."""
        runner = EncodeRunner(RLELossless)
        opts = {"rows": 1, "columns": 2, "number_of_frames": 1, "samples_per_pixel": 1}
        runner._src = np.ones((1, 1))
        runner.set_options(**opts)
        msg = (
            r"Mismatch between the expected ndarray shape \(1, 2\) and the "
            r"actual shape \(1, 1\)"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_array()

        runner._src = np.ones((2, 2))
        runner.set_options(**opts)
        msg = (
            r"Mismatch between the expected ndarray shape \(1, 2\) and the "
            r"actual shape \(2, 2\)"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_array()

        runner.set_option("samples_per_pixel", 3)
        msg = (
            r"Mismatch between the expected ndarray shape \(1, 2, 3\) and the "
            r"actual shape \(2, 2\)"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_array()

        runner.set_option("number_of_frames", 4)
        msg = (
            r"Mismatch between the expected ndarray shape \(4, 1, 2, 3\) and the "
            r"actual shape \(2, 2\)"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_array()

        runner.set_option("samples_per_pixel", 1)
        msg = (
            r"Mismatch between the expected ndarray shape \(4, 1, 2\) and the "
            r"actual shape \(2, 2\)"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_array()

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_validate_array_dtype(self):
        """Test the ndarray dtype validation."""
        runner = EncodeRunner(RLELossless)
        opts = {
            "rows": 3,
            "columns": 4,
            "number_of_frames": 1,
            "samples_per_pixel": 1,
            "pixel_representation": 0,
        }
        runner._src = np.ones((3, 4), dtype="float32")
        runner.set_options(**opts)
        msg = (
            "The ndarray's dtype 'float32' is not supported, must be a signed "
            "or unsigned integer type"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_array()

        runner._src = np.ones((3, 4), dtype="i1")
        msg = (
            r"The ndarray's dtype 'int8' is not consistent with a \(0028,0103\) "
            r"'Pixel Representation' of '0' \(unsigned integers\)"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_array()

        runner.set_option("pixel_representation", 1)
        runner._src = np.ones((3, 4), dtype="u1")
        msg = (
            r"The ndarray's dtype 'uint8' is not consistent with a \(0028,0103\) "
            r"'Pixel Representation' of '1' \(signed integers\)"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_array()

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_validate_array_values(self):
        """Test the ndarray values validation."""
        runner = EncodeRunner(RLELossless)
        opts = {
            "rows": 3,
            "columns": 4,
            "number_of_frames": 1,
            "samples_per_pixel": 1,
            "pixel_representation": 0,
            "bits_allocated": 16,
        }
        runner._src = np.ones((3, 4), dtype="u1")
        runner.set_options(**opts)
        msg = (
            r"The ndarray's dtype 'uint8' is not consistent with a \(0028,0100\) "
            "'Bits Allocated' value of '16'"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_array()

        runner.set_option("bits_stored", 2)
        runner._src = np.ones((3, 4), dtype="u2") * 4
        msg = (
            "The ndarray contains values that are outside the allowable range "
            r"of \(0, 3\) for a \(0028,0101\) 'Bits Stored' value of '2'"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_array()

        runner.set_option("bits_stored", 3)
        runner.set_option("pixel_representation", 1)
        runner._src = np.ones((3, 4), dtype="i2") * 4
        msg = (
            "The ndarray contains values that are outside the allowable range "
            r"of \(-4, 3\) for a \(0028,0101\) 'Bits Stored' value of '3'"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_array()

        runner._src = np.ones((3, 4), dtype="i2") * -5
        with pytest.raises(ValueError, match=msg):
            runner._validate_array()

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_validate_array_jls_lossy(self):
        """Test pixel value range for lossy JPEG-LS encoding."""
        runner = EncodeRunner(JPEGLSNearLossless)
        opts = {
            "rows": 3,
            "columns": 4,
            "number_of_frames": 1,
            "samples_per_pixel": 1,
            "pixel_representation": 1,
            "bits_allocated": 16,
            "jls_error": 3,
        }

        # Use a minimum bits_stored of 4 so we have a usable range
        #   min/max = (-8, 7) -> limit (-5, 4)
        for bits_stored in range(4, 17):
            opts["bits_stored"] = bits_stored
            arr = np.ones((3, 4), dtype="i2")
            minimum = -(2 ** (bits_stored - 1))
            maximum = 2 ** (bits_stored - 1) - 1
            # Both OK
            arr[0, 0] = minimum + 3
            arr[0, 1] = maximum - 3
            runner._src = arr
            runner.set_options(**opts)
            runner._validate_array()

            arr = np.ones((3, 4), dtype="i2")
            minimum = -(2 ** (bits_stored - 1))
            maximum = 2 ** (bits_stored - 1) - 1
            # Minimum is outside range
            arr[0, 0] = minimum + 2
            arr[0, 1] = maximum - 3
            runner._src = arr
            runner.set_options(**opts)

            msg = (
                "The supported range of pixel values when performing lossy "
                r"JPEG-LS encoding of signed integers with a \(0028,0103\) "
                f"'Bits Stored' value of '{bits_stored}' and a 'jls_error' "
                rf"of '3' is \({minimum + 3}, {maximum - 3}\)"
            )
            with pytest.raises(ValueError, match=msg):
                runner._validate_array()

            arr = np.ones((3, 4), dtype="i2")
            minimum = -(2 ** (bits_stored - 1))
            maximum = 2 ** (bits_stored - 1) - 1
            # Maximum is outside range
            arr[0, 0] = minimum + 3
            arr[0, 1] = maximum - 2
            runner._src = arr
            runner.set_options(**opts)
            with pytest.raises(ValueError, match=msg):
                runner._validate_array()

    def test_validate_buffer(self):
        """Test the buffer validation."""
        runner = EncodeRunner(RLELossless)
        opts = {
            "rows": 3,
            "columns": 4,
            "number_of_frames": 1,
            "samples_per_pixel": 1,
            "bits_allocated": 16,
            "photometric_interpretation": PI.MONOCHROME2,
        }
        runner._src = b"\x00" * 23
        runner.set_options(**opts)
        msg = (
            "The length of the uncompressed pixel data doesn't match the "
            "expected length - 23 bytes actual vs. 24 expected"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_buffer()

        runner.set_option("number_of_frames", 3)
        runner._src = b"\x00" * 24
        msg = (
            "The length of the uncompressed pixel data doesn't match the "
            "expected length - 24 bytes actual vs. 72 expected"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_buffer()

    def test_validate_encoding_profile(self):
        """Test the encoding profile validation."""
        runner = EncodeRunner(RLELossless)
        opts = {
            "rows": 3,
            "columns": 4,
            "number_of_frames": 1,
            "samples_per_pixel": 3,
            "bits_allocated": 24,
            "bits_stored": 12,
            "pixel_representation": 0,
            "photometric_interpretation": PI.RGB,
            "planar_configuration": 0,
        }
        runner.set_options(**opts)
        msg = (
            "One or more of the following values is not valid for pixel data "
            "encoded with 'RLE Lossless':\n"
            r"  \(0028,0002\) Samples per Pixel: 3\n"
            r"  \(0028,0006\) Photometric Interpretation: RGB\n"
            r"  \(0028,0100\) Bits Allocated: 24\n"
            r"  \(0028,0101\) Bits Stored: 12\n"
            r"  \(0028,0103\) Pixel Representation: 0\n"
            "See Part 5, Section 8.2 of the DICOM Standard for more information"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_encoding_profile()

        # Test validation skipped if unknown transfer syntax
        runner = EncodeRunner("1.2.3.4")
        opts = {
            "rows": 3,
            "columns": 4,
            "number_of_frames": 1,
            "samples_per_pixel": 3,
            "bits_allocated": 24,
            "bits_stored": 12,
            "pixel_representation": 0,
            "photometric_interpretation": PI.RGB,
            "planar_configuration": 0,
        }
        runner.set_options(**opts)
        runner._validate_encoding_profile()


@pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
class TestEncodeRunner_GetFrame:
    """Tests for EncodeRunner.get_frame)."""

    def setup_method(self):
        self.runner = EncodeRunner(JPEG2000Lossless)
        self.ds = ds = Dataset()
        ds.Rows = 1
        ds.Columns = 3
        ds.SamplesPerPixel = 1
        ds.PixelRepresentation = 0
        ds.BitsAllocated = 8
        ds.BitsStored = 8
        ds.NumberOfFrames = 1
        ds.PhotometricInterpretation = "RGB"

        self.arr_3s = np.asarray(
            [
                [[1, 2, 3], [4, 5, 6]],
                [[7, 8, 9], [10, 11, 12]],
                [[13, 14, 15], [16, 17, 18]],
                [[19, 20, 21], [22, 23, 24]],
            ],
            "|u1",
        )
        assert self.arr_3s.shape == (4, 2, 3)

    def test_arr_u08_1s(self):
        """Test processing u8/1s"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        arr = np.asarray([1, 2, 3], dtype="|u1")
        assert arr.dtype.itemsize == 1
        self.runner._set_options_ds(self.ds)
        self.runner.set_source(arr)
        out = self.runner.get_frame(None)
        assert len(out) == 3
        assert b"\x01\x02\x03" == out

    def test_arr_u08_3s(self):
        """Test processing u8/3s"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 4
        self.ds.Columns = 2
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 0

        arr = self.arr_3s.astype("|u1")
        assert arr.dtype.itemsize == 1
        self.runner._set_options_ds(self.ds)
        self.runner.set_source(arr)
        out = self.runner.get_frame(None)
        assert len(out) == 24
        assert out == bytes(range(1, 25))

    def test_arr_i08_1s(self):
        """Test processing i8/1s"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 1
        self.ds.Columns = 3

        arr = np.asarray([-128, 0, 127], dtype="|i1")
        assert arr.dtype.itemsize == 1
        self.runner._set_options_ds(self.ds)
        self.runner.set_source(arr)
        out = self.runner.get_frame(None)
        assert len(out) == 3
        assert out == b"\x80\x00\x7f"

    def test_arr_i08_3s(self):
        """Test processing i8/3s"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 4
        self.ds.Columns = 2
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 0

        arr = self.arr_3s.astype("|i1")
        assert arr.dtype.itemsize == 1
        self.runner._set_options_ds(self.ds)
        self.runner.set_source(arr)
        out = self.runner.get_frame(None)
        assert len(out) == 24
        assert out == bytes(range(1, 25))

    def test_arr_u16_1s(self):
        """Test processing u16/1s"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3
        self.ds.SamplesPerPixel = 1

        for dtype in (">u2", "<u2", "=u2"):
            arr = np.asarray([1, 2, 3], dtype=dtype)
            assert arr.dtype.itemsize == 2
            self.runner._set_options_ds(self.ds)
            self.runner.set_source(arr)
            out = self.runner.get_frame(None)
            assert len(out) == 6
            assert out == b"\x01\x00\x02\x00\x03\x00"

    def test_arr_u16_3s(self):
        """Test processing u16/3s"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.SamplesPerPixel = 3
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 4
        self.ds.Columns = 2
        self.ds.PlanarConfiguration = 0
        ref = b"".join([bytes([b]) + b"\x00" for b in bytes(range(1, 25))])

        for dtype in (">u2", "<u2", "=u2"):
            arr = self.arr_3s.astype(dtype)
            assert arr.dtype.itemsize == 2
            self.runner._set_options_ds(self.ds)
            self.runner.set_source(arr)
            out = self.runner.get_frame(None)
            assert len(out) == 48
            assert out == ref

    def test_arr_i16_1s(self):
        """Test processing i16/1s"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 1
        self.ds.Columns = 3
        self.ds.SamplesPerPixel = 1

        for dtype in (">i2", "<i2", "=i2"):
            arr = np.asarray([-128, 0, 127], dtype=dtype)
            assert arr.dtype.itemsize == 2
            self.runner._set_options_ds(self.ds)
            self.runner.set_source(arr)
            out = self.runner.get_frame(None)
            assert len(out) == 6
            assert out == b"\x80\xff\x00\x00\x7f\x00"

    def test_arr_i16_3s(self):
        """Test processing i16/3s"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.SamplesPerPixel = 3
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 4
        self.ds.Columns = 2
        self.ds.PlanarConfiguration = 0
        ref = b"".join([bytes([b]) + b"\x00" for b in bytes(range(1, 25))])

        for dtype in (">i2", "<i2", "=i2"):
            arr = self.arr_3s.astype(dtype)
            assert arr.dtype.itemsize == 2
            self.runner._set_options_ds(self.ds)
            self.runner.set_source(arr)
            out = self.runner.get_frame(None)
            assert len(out) == 48
            assert out == ref

    def test_arr_u32_1s(self):
        """Test processing u32/1s"""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3
        ref = b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00"

        for dtype in (">u4", "<u4", "=u4"):
            arr = np.asarray([1, 2, 3], dtype=dtype)
            assert arr.dtype.itemsize == 4
            self.runner._set_options_ds(self.ds)
            self.runner.set_source(arr)
            out = self.runner.get_frame(None)
            assert len(out) == 12
            assert out == ref

    def test_arr_u32_3s(self):
        """Test processing u32/3s"""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.SamplesPerPixel = 3
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 4
        self.ds.Columns = 2
        self.ds.PlanarConfiguration = 0
        ref = b"".join([bytes([b]) + b"\x00" * 3 for b in bytes(range(1, 25))])

        for dtype in (">u4", "<u4", "=u4"):
            arr = self.arr_3s.astype(dtype)
            assert arr.dtype.itemsize == 4
            self.runner._set_options_ds(self.ds)
            self.runner.set_source(arr)
            out = self.runner.get_frame(None)
            assert len(out) == 96
            assert out == ref

    def test_arr_i32_1s(self):
        """Test processing i32/1s"""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 1
        self.ds.Columns = 3
        ref = b"\x80\xff\xff\xff\x00\x00\x00\x00\x7f\x00\x00\x00"

        for dtype in (">i4", "<i4", "=i4"):
            arr = np.asarray([-128, 0, 127], dtype=dtype)
            assert arr.dtype.itemsize == 4
            self.runner._set_options_ds(self.ds)
            self.runner.set_source(arr)
            out = self.runner.get_frame(None)
            assert len(out) == 12
            assert out == ref

    def test_arr_i32_3s(self):
        """Test processing i32/3s"""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.SamplesPerPixel = 3
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 4
        self.ds.Columns = 2
        self.ds.PlanarConfiguration = 0
        ref = b"".join([bytes([b]) + b"\x00" * 3 for b in bytes(range(1, 25))])

        for dtype in (">i4", "<i4", "=i4"):
            arr = self.arr_3s.astype(dtype)
            assert arr.dtype.itemsize == 4
            self.runner._set_options_ds(self.ds)
            self.runner.set_source(arr)
            out = self.runner.get_frame(None)
            assert len(out) == 96
            assert out == ref

    def test_arr_u08(self):
        """Test get_frame() using 8-bit samples with u1, u2, u4 and u8."""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        for itemsize in (1, 2, 4, 8):
            arr = np.asarray([1, 2, 3], dtype=f"|u{itemsize}")
            self.runner._set_options_ds(self.ds)
            self.runner.set_source(arr)
            out = self.runner.get_frame(None)
            assert len(out) == 3
            assert b"\x01\x02\x03" == out

    def test_arr_u16(self):
        """Test get_frame() using 16-bit samples with u2, u4 and u8."""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        for itemsize in (2, 4, 8):
            arr = np.asarray([1, 2, 3], dtype=f"<u{itemsize}")
            self.runner._set_options_ds(self.ds)
            self.runner.set_source(arr)
            out = self.runner.get_frame(None)
            assert len(out) == 6
            assert b"\x01\x00\x02\x00\x03\x00" == out

    def test_arr_u32(self):
        """Test get_frame() using 32-bit samples with u4 and u8."""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        for itemsize in (4, 8):
            arr = np.asarray([1, 2, 3], dtype=f"<u{itemsize}")
            self.runner._set_options_ds(self.ds)
            self.runner.set_source(arr)
            out = self.runner.get_frame(None)
            assert len(out) == 12
            assert b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00" == out

    def test_arr_u64(self):
        """Test get_frame() using 64-bit samples with u8."""
        self.ds.BitsAllocated = 64
        self.ds.BitsStored = 64
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        arr = np.asarray([1, 2, 3], dtype="<u8")
        self.runner._set_options_ds(self.ds)
        self.runner.set_source(arr)
        out = self.runner.get_frame(None)
        assert len(out) == 24
        assert (
            b"\x01\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00"
            b"\x03\x00\x00\x00\x00\x00\x00\x00"
        ) == out

    def test_arr_i08(self):
        """Test get_frame() using 8-bit samples with i1, i2, i4 and i8."""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 1
        self.ds.Columns = 3

        for itemsize in (1, 2, 4, 8):
            arr = np.asarray([-128, 0, 127], dtype=f"|i{itemsize}")
            self.runner._set_options_ds(self.ds)
            self.runner.set_source(arr)
            out = self.runner.get_frame(None)
            assert len(out) == 3
            assert out == b"\x80\x00\x7f"

    def test_arr_i16(self):
        """Test get_frame() using 16-bit samples with i2, i4 and i8."""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 1
        self.ds.Columns = 3

        for itemsize in (2, 4, 8):
            arr = np.asarray([-128, 0, 127], dtype=f"<i{itemsize}")
            self.runner._set_options_ds(self.ds)
            self.runner.set_source(arr)
            out = self.runner.get_frame(None)
            assert len(out) == 6
            assert out == b"\x80\xFF\x00\x00\x7f\x00"

    def test_arr_i32(self):
        """Test get_frame() using 32-bit samples with i4 and i8."""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 1
        self.ds.Columns = 3

        for itemsize in (4, 8):
            arr = np.asarray([-128, 0, 127], dtype=f"<i{itemsize}")
            self.runner._set_options_ds(self.ds)
            self.runner.set_source(arr)
            out = self.runner.get_frame(None)
            assert len(out) == 12
            assert out == b"\x80\xFF\xFF\xFF\x00\x00\x00\x00\x7f\x00\x00\x00"

    def test_arr_i64(self):
        """Test get_frame() using 64-bit samples with i8."""
        self.ds.BitsAllocated = 64
        self.ds.BitsStored = 64
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 1
        self.ds.Columns = 3

        arr = np.asarray([-128, 0, 127], dtype="<i8")
        self.runner._set_options_ds(self.ds)
        self.runner.set_source(arr)
        out = self.runner.get_frame(None)
        assert len(out) == 24
        assert out == (
            b"\x80\xFF\xFF\xFF\xFF\xFF\xFF\xFF\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x7f\x00\x00\x00\x00\x00\x00\x00"
        )

    def test_ndarray(self):
        """Test get_frame() with an ndarray."""
        # u1, monochrome, 1 frame, even length
        runner = EncodeRunner(RLELossless)
        opts = {
            "rows": 1,
            "columns": 2,
            "number_of_frames": 1,
            "samples_per_pixel": 1,
            "bits_allocated": 8,
            "bits_stored": 8,
            "pixel_representation": 0,
            "photometric_interpretation": PI.MONOCHROME1,
            "planar_configuration": 0,
        }
        runner.set_options(**opts)
        runner.set_source(np.ones((1, 2), dtype="u1"))
        assert runner.get_frame(None) == b"\x01\x01"

        # Odd length
        runner.set_option("columns", 3)
        runner.set_source(np.ones((1, 3), dtype="u1"))
        assert runner.get_frame(None) == b"\x01\x01\x01"

        # 3 frames, odd length
        runner.set_option("number_of_frames", 3)
        arr = np.asarray([0, 1, 2, 3, 4, 5, 6, 7, 8], dtype="u1")
        runner.set_source(arr.reshape(3, 1, 3))
        assert runner.get_frame(0) == b"\x00\x01\x02"
        assert runner.get_frame(1) == b"\x03\x04\x05"
        assert runner.get_frame(2) == b"\x06\x07\x08"

        # 3 frames, even length
        runner.set_option("number_of_frames", 3)
        runner.set_option("columns", 2)
        arr = np.asarray([0, 1, 2, 3, 4, 5], dtype="u1")
        runner.set_source(arr.reshape(3, 1, 2))
        assert runner.get_frame(0) == b"\x00\x01"
        assert runner.get_frame(1) == b"\x02\x03"
        assert runner.get_frame(2) == b"\x04\x05"

        # i2, RGB, 1 frame, even length, planar conf 0
        runner.set_option("number_of_frames", 1)
        runner.set_option("photometric_interpretation", PI.RGB)
        runner.set_option("samples_per_pixel", 3)
        runner.set_option("bits_allocated", 16)
        runner.set_option("bits_stored", 16)
        runner.set_option("pixel_representation", 1)
        arr = np.asarray([0, 1, 2, -3, -4, -5], dtype="i2")
        runner.set_source(arr.reshape(1, 2, 3))
        assert runner.get_frame(None) == (
            b"\x00\x00\x01\x00\x02\x00\xFD\xFF\xFC\xFF\xFB\xFF"
        )

        # i1, RGB, 3 frames, odd length, planar conf 1
        runner.set_option("number_of_frames", 3)
        runner.set_option("columns", 3)
        runner.set_option("bits_allocated", 8)
        runner.set_option("bits_stored", 8)
        runner.set_option("planar_configuration", 1)
        x = [0, 1, 2, -3, -4, -5, 6, 7, 8]
        x.extend([0, -1, -2, 3, 4, 5, -6, -7, -8])
        x.extend([0, 1, 2, 3, 4, 5, 6, 7, 8])
        arr = np.asarray(x, dtype="i1")
        runner.set_source(arr.reshape(3, 1, 3, 3))
        assert runner.get_frame(0) == b"\x00\x01\x02\xFD\xFC\xFB\x06\x07\x08"
        assert runner.get_frame(1) == b"\x00\xFF\xFE\x03\x04\x05\xFA\xF9\xF8"
        assert runner.get_frame(2) == b"\x00\x01\x02\x03\x04\x05\x06\x07\x08"

        # JPEL-LS, 1 frame, planar conf 1
        runner = EncodeRunner(JPEGLSLossless)
        opts = {
            "rows": 1,
            "columns": 2,
            "number_of_frames": 1,
            "samples_per_pixel": 3,
            "bits_allocated": 8,
            "bits_stored": 8,
            "pixel_representation": 0,
            "photometric_interpretation": PI.RGB,
            "planar_configuration": 1,
        }
        runner.set_options(**opts)
        arr = np.asarray([0, 1, 2, 3, 4, 5], dtype="u1")
        runner.set_source(arr.reshape(1, 2, 3))
        assert runner.get_frame(None) == b"\x00\x03\x01\x04\x02\x05"

        # 3 frames
        runner.set_option("number_of_frames", 3)
        arr = np.asarray(
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
            dtype="u1",
        )
        runner.set_source(arr.reshape(3, 1, 2, 3))
        assert runner.get_frame(0) == b"\x00\x03\x01\x04\x02\x05"
        assert runner.get_frame(1) == b"\x06\x09\x07\x0A\x08\x0B"
        assert runner.get_frame(2) == b"\x0C\x0F\x0D\x10\x0E\x11"

    def test_buffer_08(self):
        """Test get_frame() using [0, 8)-bit samples with N-bit containers."""
        # [0, 8)-bit samples should be in 8-bit containers
        runner = EncodeRunner(RLELossless)
        opts = {
            "rows": 1,
            "columns": 2,
            "number_of_frames": 1,
            "samples_per_pixel": 1,
            "pixel_representation": 0,
            "photometric_interpretation": PI.MONOCHROME1,
            "planar_configuration": 0,
        }

        for bits_allocated in (16, 24, 32, 40, 48, 56, 64):
            opts["bits_allocated"] = bits_allocated
            padding = bits_allocated // 8 - 1
            src_a = b"\x00" + b"\x00" * padding + b"\x01" + b"\x00" * padding
            src_b = src_a + b"\x02" + b"\x00" * padding
            src_c = (
                src_b
                + b"\x03"
                + b"\x00" * padding
                + b"\x04"
                + b"\x00" * padding
                + b"\x05"
                + b"\x00" * padding
                + b"\x06"
                + b"\x00" * padding
                + b"\x07"
                + b"\x00" * padding
                + b"\x08"
                + b"\x00" * padding
            )
            for bits_stored in range(9):
                opts["bits_stored"] = bits_stored
                runner.set_options(**opts)
                runner.set_source(src_a)
                assert runner.get_frame(None) == b"\x00\x01"

                runner.set_option("columns", 3)
                runner.set_source(src_b)
                assert runner.get_frame(None) == b"\x00\x01\x02"

                runner.set_option("number_of_frames", 3)
                runner.set_source(src_c)
                assert runner.get_frame(0) == b"\x00\x01\x02"
                assert runner.get_frame(1) == b"\x03\x04\x05"
                assert runner.get_frame(2) == b"\x06\x07\x08"

    def test_buffer_16(self):
        """Test get_frame() using [8, 16)-bit samples with N-bit containers."""
        # [8, 16)-bit samples should be in 16-bit containers
        runner = EncodeRunner(RLELossless)
        opts = {
            "rows": 1,
            "columns": 2,
            "number_of_frames": 1,
            "samples_per_pixel": 1,
            "pixel_representation": 0,
            "photometric_interpretation": PI.MONOCHROME1,
            "planar_configuration": 0,
        }

        for bits_allocated in (16, 24, 32, 40, 48, 56, 64):
            opts["bits_allocated"] = bits_allocated
            padding = bits_allocated // 8 - 1
            src_a = b"\x00" + b"\x00" * padding + b"\x01" + b"\x00" * padding
            src_b = src_a + b"\x02" + b"\x00" * padding
            src_c = (
                src_b
                + b"\x03"
                + b"\x00" * padding
                + b"\x04"
                + b"\x00" * padding
                + b"\x05"
                + b"\x00" * padding
                + b"\x06"
                + b"\x00" * padding
                + b"\x07"
                + b"\x00" * padding
                + b"\x08"
                + b"\x00" * padding
            )
            for bits_stored in range(9, 17):
                opts["bits_stored"] = bits_stored
                runner.set_options(**opts)
                runner.set_source(src_a)
                assert runner.get_frame(None) == b"\x00\x00\x01\x00"

                runner.set_option("columns", 3)
                runner.set_source(src_b)
                assert runner.get_frame(None) == b"\x00\x00\x01\x00\x02\x00"

                runner.set_option("number_of_frames", 3)
                runner.set_source(src_c)
                assert runner.get_frame(0) == b"\x00\x00\x01\x00\x02\x00"
                assert runner.get_frame(1) == b"\x03\x00\x04\x00\x05\x00"
                assert runner.get_frame(2) == b"\x06\x00\x07\x00\x08\x00"

    def test_buffer_24(self):
        """Test get_frame() using [16, 24)-bit samples with N-bit containers."""
        runner = EncodeRunner(RLELossless)
        # [16, 24)-bit samples should be in 32-bit containers
        opts = {
            "rows": 1,
            "columns": 2,
            "number_of_frames": 1,
            "samples_per_pixel": 1,
            "pixel_representation": 0,
            "photometric_interpretation": PI.MONOCHROME1,
            "planar_configuration": 0,
        }

        for bits_allocated in (24, 32, 40, 48, 56, 64):
            opts["bits_allocated"] = bits_allocated
            padding = bits_allocated // 8 - 1
            src_a = b"\x00" + b"\x00" * padding + b"\x01" + b"\x00" * padding
            src_b = src_a + b"\x02" + b"\x00" * padding
            src_c = (
                src_b
                + b"\x03"
                + b"\x00" * padding
                + b"\x04"
                + b"\x00" * padding
                + b"\x05"
                + b"\x00" * padding
                + b"\x06"
                + b"\x00" * padding
                + b"\x07"
                + b"\x00" * padding
                + b"\x08"
                + b"\x00" * padding
            )
            for bits_stored in range(17, 25):
                opts["bits_stored"] = bits_stored
                runner.set_options(**opts)
                runner.set_source(src_a)
                assert runner.get_frame(None) == b"\x00\x00\x00\x00\x01\x00\x00\x00"

                runner.set_option("columns", 3)
                runner.set_source(src_b)
                assert runner.get_frame(None) == (
                    b"\x00\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00"
                )

                runner.set_option("number_of_frames", 3)
                runner.set_source(src_c)
                assert runner.get_frame(0) == (
                    b"\x00\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00"
                )
                assert runner.get_frame(1) == (
                    b"\x03\x00\x00\x00\x04\x00\x00\x00\x05\x00\x00\x00"
                )
                assert runner.get_frame(2) == (
                    b"\x06\x00\x00\x00\x07\x00\x00\x00\x08\x00\x00\x00"
                )

    def test_buffer_32(self):
        """Test get_frame() using [25, 32)-bit samples with N-bit containers."""
        runner = EncodeRunner(RLELossless)
        # [25, 32)-bit samples should be in 32-bit containers
        opts = {
            "rows": 1,
            "columns": 2,
            "number_of_frames": 1,
            "samples_per_pixel": 1,
            "pixel_representation": 0,
            "photometric_interpretation": PI.MONOCHROME1,
            "planar_configuration": 0,
        }

        for bits_allocated in (32, 40, 48, 56, 64):
            opts["bits_allocated"] = bits_allocated
            padding = bits_allocated // 8 - 1
            src_a = b"\x00" + b"\x00" * padding + b"\x01" + b"\x00" * padding
            src_b = src_a + b"\x02" + b"\x00" * padding
            src_c = (
                src_b
                + b"\x03"
                + b"\x00" * padding
                + b"\x04"
                + b"\x00" * padding
                + b"\x05"
                + b"\x00" * padding
                + b"\x06"
                + b"\x00" * padding
                + b"\x07"
                + b"\x00" * padding
                + b"\x08"
                + b"\x00" * padding
            )
            for bits_stored in range(25, 33):
                opts["bits_stored"] = bits_stored
                runner.set_options(**opts)
                runner.set_source(src_a)
                assert runner.get_frame(None) == b"\x00\x00\x00\x00\x01\x00\x00\x00"

                runner.set_option("columns", 3)
                runner.set_source(src_b)
                assert runner.get_frame(None) == (
                    b"\x00\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00"
                )

                runner.set_option("number_of_frames", 3)
                runner.set_source(src_c)
                assert runner.get_frame(0) == (
                    b"\x00\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00"
                )
                assert runner.get_frame(1) == (
                    b"\x03\x00\x00\x00\x04\x00\x00\x00\x05\x00\x00\x00"
                )
                assert runner.get_frame(2) == (
                    b"\x06\x00\x00\x00\x07\x00\x00\x00\x08\x00\x00\x00"
                )

    def test_buffer_40(self):
        """Test get_frame() using [32, 40)-bit samples with N-bit containers."""
        runner = EncodeRunner(RLELossless)
        # [32, 40)-bit samples should be in 64-bit containers
        opts = {
            "rows": 1,
            "columns": 2,
            "number_of_frames": 1,
            "samples_per_pixel": 1,
            "pixel_representation": 0,
            "photometric_interpretation": PI.MONOCHROME1,
            "planar_configuration": 0,
        }

        for bits_allocated in (40, 48, 56, 64):
            opts["bits_allocated"] = bits_allocated
            padding = bits_allocated // 8 - 1
            src_a = b"\x00" + b"\x00" * padding + b"\x01" + b"\x00" * padding
            src_b = src_a + b"\x02" + b"\x00" * padding
            src_c = (
                src_b
                + b"\x03"
                + b"\x00" * padding
                + b"\x04"
                + b"\x00" * padding
                + b"\x05"
                + b"\x00" * padding
                + b"\x06"
                + b"\x00" * padding
                + b"\x07"
                + b"\x00" * padding
                + b"\x08"
                + b"\x00" * padding
            )
            for bits_stored in range(33, 41):
                opts["bits_stored"] = bits_stored
                runner.set_options(**opts)
                runner.set_source(src_a)
                assert runner.get_frame(None) == (
                    b"\x00\x00\x00\x00\x00\x00\x00\x00"
                    b"\x01\x00\x00\x00\x00\x00\x00\x00"
                )

                runner.set_option("columns", 3)
                runner.set_source(src_b)
                assert runner.get_frame(None) == (
                    b"\x00\x00\x00\x00\x00\x00\x00\x00"
                    b"\x01\x00\x00\x00\x00\x00\x00\x00"
                    b"\x02\x00\x00\x00\x00\x00\x00\x00"
                )

                runner.set_option("number_of_frames", 3)
                runner.set_source(src_c)
                assert runner.get_frame(0) == (
                    b"\x00\x00\x00\x00\x00\x00\x00\x00"
                    b"\x01\x00\x00\x00\x00\x00\x00\x00"
                    b"\x02\x00\x00\x00\x00\x00\x00\x00"
                )
                assert runner.get_frame(1) == (
                    b"\x03\x00\x00\x00\x00\x00\x00\x00"
                    b"\x04\x00\x00\x00\x00\x00\x00\x00"
                    b"\x05\x00\x00\x00\x00\x00\x00\x00"
                )
                assert runner.get_frame(2) == (
                    b"\x06\x00\x00\x00\x00\x00\x00\x00"
                    b"\x07\x00\x00\x00\x00\x00\x00\x00"
                    b"\x08\x00\x00\x00\x00\x00\x00\x00"
                )

    def test_buffer_48(self):
        """Test get_frame() using [40, 48)-bit samples with N-bit containers."""
        runner = EncodeRunner(RLELossless)
        # [40, 48)-bit samples should be in 64-bit containers
        opts = {
            "rows": 1,
            "columns": 2,
            "number_of_frames": 1,
            "samples_per_pixel": 1,
            "pixel_representation": 0,
            "photometric_interpretation": PI.MONOCHROME1,
            "planar_configuration": 0,
        }

        for bits_allocated in (48, 56, 64):
            opts["bits_allocated"] = bits_allocated
            padding = bits_allocated // 8 - 1
            src_a = b"\x00" + b"\x00" * padding + b"\x01" + b"\x00" * padding
            src_b = src_a + b"\x02" + b"\x00" * padding
            src_c = (
                src_b
                + b"\x03"
                + b"\x00" * padding
                + b"\x04"
                + b"\x00" * padding
                + b"\x05"
                + b"\x00" * padding
                + b"\x06"
                + b"\x00" * padding
                + b"\x07"
                + b"\x00" * padding
                + b"\x08"
                + b"\x00" * padding
            )
            for bits_stored in range(41, 49):
                opts["bits_stored"] = bits_stored
                runner.set_options(**opts)
                runner.set_source(src_a)
                assert runner.get_frame(None) == (
                    b"\x00\x00\x00\x00\x00\x00\x00\x00"
                    b"\x01\x00\x00\x00\x00\x00\x00\x00"
                )

                runner.set_option("columns", 3)
                runner.set_source(src_b)
                assert runner.get_frame(None) == (
                    b"\x00\x00\x00\x00\x00\x00\x00\x00"
                    b"\x01\x00\x00\x00\x00\x00\x00\x00"
                    b"\x02\x00\x00\x00\x00\x00\x00\x00"
                )

                runner.set_option("number_of_frames", 3)
                runner.set_source(src_c)
                assert runner.get_frame(0) == (
                    b"\x00\x00\x00\x00\x00\x00\x00\x00"
                    b"\x01\x00\x00\x00\x00\x00\x00\x00"
                    b"\x02\x00\x00\x00\x00\x00\x00\x00"
                )
                assert runner.get_frame(1) == (
                    b"\x03\x00\x00\x00\x00\x00\x00\x00"
                    b"\x04\x00\x00\x00\x00\x00\x00\x00"
                    b"\x05\x00\x00\x00\x00\x00\x00\x00"
                )
                assert runner.get_frame(2) == (
                    b"\x06\x00\x00\x00\x00\x00\x00\x00"
                    b"\x07\x00\x00\x00\x00\x00\x00\x00"
                    b"\x08\x00\x00\x00\x00\x00\x00\x00"
                )

    def test_buffer_56(self):
        """Test get_frame() using [48, 56)-bit samples with N-bit containers."""
        runner = EncodeRunner(RLELossless)
        # [48, 56)-bit samples should be in 64-bit containers
        opts = {
            "rows": 1,
            "columns": 2,
            "number_of_frames": 1,
            "samples_per_pixel": 1,
            "pixel_representation": 0,
            "photometric_interpretation": PI.MONOCHROME1,
            "planar_configuration": 0,
        }

        for bits_allocated in (56, 64):
            opts["bits_allocated"] = bits_allocated
            padding = bits_allocated // 8 - 1
            src_a = b"\x00" + b"\x00" * padding + b"\x01" + b"\x00" * padding
            src_b = src_a + b"\x02" + b"\x00" * padding
            src_c = (
                src_b
                + b"\x03"
                + b"\x00" * padding
                + b"\x04"
                + b"\x00" * padding
                + b"\x05"
                + b"\x00" * padding
                + b"\x06"
                + b"\x00" * padding
                + b"\x07"
                + b"\x00" * padding
                + b"\x08"
                + b"\x00" * padding
            )
            for bits_stored in range(49, 57):
                opts["bits_stored"] = bits_stored
                runner.set_options(**opts)
                runner.set_source(src_a)
                assert runner.get_frame(None) == (
                    b"\x00\x00\x00\x00\x00\x00\x00\x00"
                    b"\x01\x00\x00\x00\x00\x00\x00\x00"
                )

                runner.set_option("columns", 3)
                runner.set_source(src_b)
                assert runner.get_frame(None) == (
                    b"\x00\x00\x00\x00\x00\x00\x00\x00"
                    b"\x01\x00\x00\x00\x00\x00\x00\x00"
                    b"\x02\x00\x00\x00\x00\x00\x00\x00"
                )

                runner.set_option("number_of_frames", 3)
                runner.set_source(src_c)
                assert runner.get_frame(0) == (
                    b"\x00\x00\x00\x00\x00\x00\x00\x00"
                    b"\x01\x00\x00\x00\x00\x00\x00\x00"
                    b"\x02\x00\x00\x00\x00\x00\x00\x00"
                )
                assert runner.get_frame(1) == (
                    b"\x03\x00\x00\x00\x00\x00\x00\x00"
                    b"\x04\x00\x00\x00\x00\x00\x00\x00"
                    b"\x05\x00\x00\x00\x00\x00\x00\x00"
                )
                assert runner.get_frame(2) == (
                    b"\x06\x00\x00\x00\x00\x00\x00\x00"
                    b"\x07\x00\x00\x00\x00\x00\x00\x00"
                    b"\x08\x00\x00\x00\x00\x00\x00\x00"
                )

    def test_buffer_64(self):
        """Test get_frame() using [56, 64)-bit samples with N-bit containers."""
        runner = EncodeRunner(RLELossless)
        # [56, 64)-bit samples should be in 64-bit containers
        opts = {
            "rows": 1,
            "columns": 2,
            "number_of_frames": 1,
            "samples_per_pixel": 1,
            "pixel_representation": 0,
            "photometric_interpretation": PI.MONOCHROME1,
            "planar_configuration": 0,
        }

        bits_allocated = 64
        opts["bits_allocated"] = bits_allocated
        padding = bits_allocated // 8 - 1
        src_a = b"\x00" + b"\x00" * padding + b"\x01" + b"\x00" * padding
        src_b = src_a + b"\x02" + b"\x00" * padding
        src_c = (
            src_b
            + b"\x03"
            + b"\x00" * padding
            + b"\x04"
            + b"\x00" * padding
            + b"\x05"
            + b"\x00" * padding
            + b"\x06"
            + b"\x00" * padding
            + b"\x07"
            + b"\x00" * padding
            + b"\x08"
            + b"\x00" * padding
        )
        for bits_stored in range(57, 65):
            opts["bits_stored"] = bits_stored
            runner.set_options(**opts)
            runner.set_source(src_a)
            assert runner.get_frame(None) == (
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00"
            )

            runner.set_option("columns", 3)
            runner.set_source(src_b)
            assert runner.get_frame(None) == (
                b"\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x01\x00\x00\x00\x00\x00\x00\x00"
                b"\x02\x00\x00\x00\x00\x00\x00\x00"
            )

            runner.set_option("number_of_frames", 3)
            runner.set_source(src_c)
            assert runner.get_frame(0) == (
                b"\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x01\x00\x00\x00\x00\x00\x00\x00"
                b"\x02\x00\x00\x00\x00\x00\x00\x00"
            )
            assert runner.get_frame(1) == (
                b"\x03\x00\x00\x00\x00\x00\x00\x00"
                b"\x04\x00\x00\x00\x00\x00\x00\x00"
                b"\x05\x00\x00\x00\x00\x00\x00\x00"
            )
            assert runner.get_frame(2) == (
                b"\x06\x00\x00\x00\x00\x00\x00\x00"
                b"\x07\x00\x00\x00\x00\x00\x00\x00"
                b"\x08\x00\x00\x00\x00\x00\x00\x00"
            )


class TestEncodeRunner_Encode:
    """Tests for EncodeRunner.encode()"""

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy unavailable")
    def test_specify_plugin(self):
        """Test with specific plugin"""
        enc = RLELosslessEncoder
        enc.encode(EXPL_16_16_1F.ds, encoding_plugin="pydicom")

    def test_specify_invalid_plugin_raises(self):
        """Test an invalid plugin raises exception"""
        msg = r"No plugin named 'foo' has been added to 'RLELosslessEncoder'"
        with pytest.raises(ValueError, match=msg):
            RLELosslessEncoder.encode(EXPL_16_16_1F.ds, encoding_plugin="foo")

    @pytest.mark.skipif(
        not HAVE_NP or HAVE_PYLJ or HAVE_GDCM,
        reason="Numpy unavailable or other plugin available",
    )
    def test_specify_plugin_unavailable_raises(self):
        """Test with specific unavailable plugin"""
        enc = RLELosslessEncoder
        assert enc.is_available
        msg = (
            "Unable to compress the pixel data using 'RLE Lossless' because the "
            "specified plugin is missing dependencies:\n\tpylibjpeg - requires numpy, "
            "pylibjpeg>=2.0 and pylibjpeg-rle>=2.0"
        )
        with pytest.raises(RuntimeError, match=msg):
            enc.encode(EXPL_16_16_1F.ds, encoding_plugin="pylibjpeg")

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy unavailable")
    def test_specify_plugin_encoding_exception(self):
        """Test an encoding exception occurring with a specific plugin"""
        enc = RLELosslessEncoder
        msg = (
            "Unable to encode as exceptions were raised by all available "
            "plugins:\n  pydicom: Unsupported option \"byteorder = '>'\""
        )
        with pytest.raises(RuntimeError, match=msg):
            enc.encode(EXPL_16_16_1F.ds, encoding_plugin="pydicom", byteorder=">")

    @pytest.mark.skipif(not HAVE_NP or HAVE_RLE, reason="Numpy unavailable")
    def test_encoding_exceptions(self):
        """Test an encoding exception occurring in all plugins"""
        msg = "Unable to encode as exceptions were raised by all available plugins:\n"
        with pytest.raises(RuntimeError, match=msg):
            RLELosslessEncoder.encode(EXPL_16_16_1F.ds, byteorder=">")


@pytest.fixture()
def enable_logging():
    original = config.debugging
    config.debugging = True
    yield
    config.debugging = original


@pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
class TestEncoder:
    """Tests for Encoder and related methods."""

    def setup_method(self):
        self.enc = RLELosslessEncoder
        self.ds = get_testdata_file("CT_small.dcm", read=True)
        self.ds_enc = get_testdata_file("MR_small_RLE.dcm", read=True)
        self.ds_enc_mf = get_testdata_file("emri_small_RLE.dcm", read=True)
        self.bytes = self.ds.PixelData
        self.arr = self.ds.pixel_array
        self.kwargs = {
            "rows": self.ds.Rows,
            "columns": self.ds.Columns,
            "samples_per_pixel": self.ds.SamplesPerPixel,
            "photometric_interpretation": self.ds.PhotometricInterpretation,
            "pixel_representation": self.ds.PixelRepresentation,
            "bits_allocated": self.ds.BitsAllocated,
            "bits_stored": self.ds.BitsStored,
            "number_of_frames": 1,
        }

    def test_init(self):
        """Test creating a new Encoder"""
        uid = UID("1.2.3")
        enc = Encoder(uid)
        assert {} == enc._available
        assert {} == enc._unavailable
        assert enc._decoder is False

    def test_logging(self, enable_logging, caplog):
        """Test that the logging works during encode"""
        with caplog.at_level(logging.DEBUG, logger="pydicom"):
            self.enc.encode(self.bytes, **self.kwargs)
            assert "EncodeRunner for 'RLE Lossless'" in caplog.text
            assert "  byteorder: <" in caplog.text

        caplog.clear()

        with caplog.at_level(logging.DEBUG, logger="pydicom"):
            next(self.enc.iter_encode(self.bytes, **self.kwargs))
            assert "EncodeRunner for 'RLE Lossless'" in caplog.text
            assert "Encoders" in caplog.text

    def test_encode_invalid_type_raises(self):
        """Test exception raised if passing invalid type."""
        enc = RLELosslessEncoder
        msg = (
            r"'src' must be bytes, numpy.ndarray or pydicom.dataset.Dataset, "
            r"not 'str'"
        )
        with pytest.raises(TypeError, match=msg):
            enc.encode("abc")

    def test_iter_encode_invalid_type_raises(self):
        """Test exception raised if passing invalid type."""
        enc = RLELosslessEncoder
        msg = (
            r"'src' must be bytes, numpy.ndarray or pydicom.dataset.Dataset, "
            r"not 'str'"
        )
        with pytest.raises(TypeError, match=msg):
            next(enc.iter_encode("abc"))

    # Passing bytes
    def test_bytes(self):
        """Test encoding bytes"""
        assert len(self.bytes) == 32768
        out = self.enc.encode(self.bytes, **self.kwargs)
        assert len(self.bytes) > len(out)

    def test_bytes_specific(self):
        """Test encoding bytes with a specific encoder"""
        out = self.enc.encode(self.bytes, encoding_plugin="pydicom", **self.kwargs)
        assert len(out) == 21350

    def test_bytes_short_raises(self):
        """Test encoding bytes with short data raises exception"""
        msg = (
            "The length of the uncompressed pixel data doesn't match the "
            "expected length - 32767 bytes actual vs. 32768 expected"
        )
        with pytest.raises(ValueError, match=msg):
            self.enc.encode(self.bytes[:-1], **self.kwargs)

    def test_bytes_padded(self):
        """Test encoding bytes with padded data"""
        out = self.enc.encode(
            self.bytes + b"\x00\x00", encoding_plugin="pydicom", **self.kwargs
        )
        assert len(out) == 21350

    def test_bytes_multiframe(self):
        """Test encoding multiframe bytes with idx"""
        self.kwargs["number_of_frames"] = 2
        out = self.enc.encode(
            self.bytes * 2, index=0, encoding_plugin="pydicom", **self.kwargs
        )
        assert len(out) == 21350

    def test_bytes_multiframe_no_index_raises(self):
        """Test encoding multiframe bytes without index raises exception"""
        msg = (
            "The 'index' of the frame to be encoded is required for "
            "multi-frame pixel data"
        )
        self.kwargs["number_of_frames"] = 2
        with pytest.raises(ValueError, match=msg):
            self.enc.encode(self.bytes * 2, **self.kwargs)

        msg = "'index' must be greater than or equal to 0"
        with pytest.raises(ValueError, match=msg):
            self.enc.encode(
                self.bytes * 2, index=-1, encoding_plugin="pydicom", **self.kwargs
            )

    def test_bytes_iter_encode(self):
        """Test encoding multiframe bytes with iter_encode"""
        self.kwargs["number_of_frames"] = 2
        gen = self.enc.iter_encode(
            self.bytes * 2, encoding_plugin="pydicom", **self.kwargs
        )
        assert len(next(gen)) == 21350
        assert len(next(gen)) == 21350
        with pytest.raises(StopIteration):
            next(gen)

    # Passing ndarray
    def test_array(self):
        """Test encode with an array"""
        out = self.enc.encode(self.arr, **self.kwargs)
        assert len(self.arr.tobytes()) > len(out)

    def test_array_specific(self):
        """Test encoding with a specific plugin"""
        out = self.enc.encode(self.arr, encoding_plugin="pydicom", **self.kwargs)
        assert len(out) == 21350

    def test_array_multiframe(self):
        """Test encoding a multiframe array with idx"""
        arr = np.stack((self.arr, self.arr))
        assert arr.shape == (2, 128, 128)
        self.kwargs["number_of_frames"] = 2
        out = self.enc.encode(arr, index=0, encoding_plugin="pydicom", **self.kwargs)
        assert len(out) == 21350

    def test_array_invalid_dims_raises(self):
        """Test encoding an array with too many dimensions raises"""
        arr = np.zeros((1, 2, 3, 4, 5))
        assert arr.shape == (1, 2, 3, 4, 5)
        msg = r"Unable to encode 5D ndarrays"
        with pytest.raises(ValueError, match=msg):
            self.enc.encode(arr, **self.kwargs)

    def test_array_multiframe_no_index_raises(self):
        """Test encoding a multiframe array without index raises"""
        arr = np.stack((self.arr, self.arr))
        assert arr.shape == (2, 128, 128)
        self.kwargs["number_of_frames"] = 2
        msg = (
            "The 'index' of the frame to be encoded is required for "
            "multi-frame pixel data"
        )
        with pytest.raises(ValueError, match=msg):
            self.enc.encode(arr, **self.kwargs)

        msg = "'index' must be greater than or equal to 0"
        with pytest.raises(ValueError, match=msg):
            self.enc.encode(arr, index=-1, encoding_plugin="pydicom", **self.kwargs)

    def test_array_iter_encode(self):
        """Test encoding a multiframe array with iter_encode"""
        arr = np.stack((self.arr, self.arr))
        assert arr.shape == (2, 128, 128)
        self.kwargs["number_of_frames"] = 2
        gen = self.enc.iter_encode(arr, encoding_plugin="pydicom", **self.kwargs)
        assert len(next(gen)) == 21350
        assert len(next(gen)) == 21350
        with pytest.raises(StopIteration):
            next(gen)

    # Passing Dataset
    def test_unc_dataset(self):
        """Test encoding an uncompressed dataset"""
        assert not self.ds.file_meta.TransferSyntaxUID.is_compressed
        out = self.enc.encode(self.ds)
        assert len(self.ds.PixelData) > len(out)

    def test_unc_dataset_specific(self):
        """Test encoding an uncompressed dataset with specific plugin"""
        assert not self.ds.file_meta.TransferSyntaxUID.is_compressed
        out = self.enc.encode(self.ds, encoding_plugin="pydicom")
        assert len(out) == 21350

    def test_unc_dataset_multiframe(self):
        """Test encoding a multiframe uncompressed dataset"""
        assert not self.ds.file_meta.TransferSyntaxUID.is_compressed
        self.ds.NumberOfFrames = 2
        self.ds.PixelData = self.ds.PixelData * 2
        out = self.enc.encode(self.ds, index=0)
        assert len(self.ds.PixelData) > len(out)

    def test_unc_dataset_multiframe_no_index_raises(self):
        """Test encoding multiframe uncompressed dataset without index raises"""
        assert not self.ds.file_meta.TransferSyntaxUID.is_compressed
        self.ds.NumberOfFrames = 2
        self.ds.PixelData = self.ds.PixelData * 2
        msg = (
            "The 'index' of the frame to be encoded is required for "
            "multi-frame pixel data"
        )
        with pytest.raises(ValueError, match=msg):
            self.enc.encode(self.ds)

    def test_unc_iter_encode(self):
        """Test iter_encode with an uncompressed dataset"""
        self.ds.NumberOfFrames = 2
        self.ds.PixelData = self.ds.PixelData * 2
        gen = self.enc.iter_encode(self.ds, encoding_plugin="pydicom")
        out = next(gen)
        assert len(self.ds.PixelData) > len(out)
        out = next(gen)
        assert len(self.ds.PixelData) > len(out)
        with pytest.raises(StopIteration):
            next(gen)


class TestDatasetCompress:
    """Tests for Dataset.compress()."""

    def test_compress_inplace(self):
        """Test encode with a dataset."""
        ds = get_testdata_file("CT_small.dcm", read=True)
        assert ds["PixelData"].VR == "OW"
        ds.compress(RLELossless, encoding_plugin="pydicom")
        assert ds.SamplesPerPixel == 1
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert len(ds.PixelData) == 21370
        assert "PlanarConfiguration" not in ds
        assert ds["PixelData"].is_undefined_length
        assert ds["PixelData"].VR == "OB"

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_compress_arr(self):
        """Test encode with an arr."""
        ds = get_testdata_file("CT_small.dcm", read=True)
        assert hasattr(ds, "file_meta")
        arr = ds.pixel_array
        del ds.PixelData
        del ds.file_meta

        ds.compress(RLELossless, arr, encoding_plugin="pydicom")
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert len(ds.PixelData) == 21370

    @pytest.mark.skipif(HAVE_NP, reason="Numpy is available")
    def test_encoder_unavailable(self, monkeypatch):
        """Test the required encoder being unavailable."""
        ds = get_testdata_file("CT_small.dcm", read=True)
        monkeypatch.delitem(RLELosslessEncoder._available, "pydicom")
        msg = (
            r"The pixel data encoder for 'RLE Lossless' is unavailable because all "
            r"of its plugins are missing dependencies:\n"
            r"    gdcm - requires gdcm>=3.0.10\n"
            r"    pylibjpeg - requires numpy, pylibjpeg>=2.0 and pylibjpeg-rle>=2.0"
        )
        with pytest.raises(RuntimeError, match=msg):
            ds.compress(RLELossless)

    def test_uid_not_supported(self):
        """Test the UID not having any encoders."""
        ds = get_testdata_file("CT_small.dcm", read=True)

        msg = (
            r"No pixel data encoders have been implemented for "
            r"'JPEG 2000 Part 2 Multi-component Image Compression'"
        )
        with pytest.raises(NotImplementedError, match=msg):
            ds.compress(JPEG2000MC, encoding_plugin="pydicom")

    def test_encapsulate_extended(self):
        """Test forcing extended encapsulation."""
        ds = get_testdata_file("CT_small.dcm", read=True)
        assert "ExtendedOffsetTable" not in ds
        assert "ExtendedOffsetTableLengths" not in ds

        ds.compress(RLELossless, encapsulate_ext=True, encoding_plugin="pydicom")
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert len(ds.PixelData) == 21366
        assert ds.ExtendedOffsetTable == b"\x00" * 8
        assert ds.ExtendedOffsetTableLengths == b"\x66\x53" + b"\x00" * 6

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_round_trip(self):
        """Test an encoding round-trip"""
        ds = get_testdata_file("MR_small_RLE.dcm", read=True)
        arr = ds.pixel_array
        # Setting PixelData to None frees the memory which may
        #   sometimes be reused, causes the _pixel_id check to fail
        ds.PixelData = None
        ds._pixel_array = None
        ds.compress(RLELossless, arr, encoding_plugin="pydicom")
        assert ds.PixelData is not None
        assert np.array_equal(arr, ds.pixel_array)

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_overriding_kwargs_raises(self):
        """Test unable to override using kwargs."""
        ds = get_testdata_file("SC_rgb_small_odd.dcm", read=True)
        ds.SamplesPerPixel = 1
        msg = "One or more of the following values is not valid"
        with pytest.raises(ValueError, match=msg):
            ds.compress(
                RLELossless,
                encoding_plugin="pydicom",
                samples_per_pixel=3,
                planar_configuration=0,
            )

    def test_planar_configuration_rle(self):
        """Test that multi-sample data has correct planar configuration."""
        ds = examples.rgb_color
        assert ds.SamplesPerPixel == 3
        assert ds.PlanarConfiguration == 0

        ds.compress(RLELossless, encoding_plugin="pydicom")
        assert ds.PlanarConfiguration == 0
        assert ds.file_meta.TransferSyntaxUID == RLELossless


@pytest.fixture
def use_future():
    original = config._use_future
    config._use_future = True
    yield
    config._use_future = original


class TestFuture:
    def test_compress(self, use_future):
        ds = get_testdata_file("CT_small.dcm", read=True)
        ds.compress(RLELossless, encoding_plugin="pydicom")
        assert not hasattr(ds, "_is_little_endian")
        assert not hasattr(ds, "_is_implicit_VR")

    def test_imports_raise(self, use_future):
        with pytest.raises(ImportError):
            from pydicom.encoders import get_encoder

        with pytest.raises(ImportError):
            from pydicom.encoders import RLELosslessEncoder


def test_deprecation_warning():
    msg = (
        "The 'pydicom.encoders' module will be removed in v4.0, please use "
        "'from pydicom.pixels import get_encoder' instead"
    )
    with pytest.warns(DeprecationWarning, match=msg):
        from pydicom.encoders import get_encoder as get_foo
