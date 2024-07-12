"""Tests for pydicom.pixels.decoder.base."""

from io import BytesIO
import logging
from struct import pack, unpack
from sys import byteorder

import pytest

from pydicom import config, dcmread
from pydicom.dataset import Dataset
from pydicom.encaps import get_frame, generate_frames, encapsulate
from pydicom.pixels import get_decoder
from pydicom.pixels.common import PhotometricInterpretation as PI
from pydicom.pixels.decoders import ExplicitVRLittleEndianDecoder
from pydicom.pixels.decoders.base import DecodeRunner, Decoder
from pydicom.pixels.processing import convert_color_space

from pydicom.uid import (
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian,
    ExplicitVRBigEndian,
    JPEGBaseline8Bit,
    RLELossless,
    SMPTEST211030PCMDigitalAudio,
)

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from .pixels_reference import (
    PIXEL_REFERENCE,
    RLE_16_1_1F,
    RLE_16_1_10F,
    EXPL_16_1_10F,
    EXPL_8_3_1F_YBR,
    EXPL_8_3_1F_YBR422,
    EXPL_1_1_1F,
    EXPB_8_1_1F,
)


RLE_REFERENCE = PIXEL_REFERENCE[RLELossless]


class TestDecodeRunner:
    """Tests for DecodeRunner."""

    def test_init(self):
        """Test initial creation."""
        # Encapsulated transfer syntax - pixel_keyword set, view_only not set
        runner = DecodeRunner(RLELossless)
        assert runner.transfer_syntax == RLELossless
        assert runner.get_option("pixel_keyword") == "PixelData"
        assert runner.get_option("as_rgb")
        assert runner.get_option("view_only") is None

        # Native transfer syntax - pixel_keyword not set, view_only set
        runner = DecodeRunner(ExplicitVRLittleEndian)
        assert runner.transfer_syntax == ExplicitVRLittleEndian
        assert runner.get_option("pixel_keyword") is None
        assert runner.get_option("as_rgb")
        assert not runner.get_option("view_only")

    def test_del_option(self):
        """Test for del_option()"""
        runner = DecodeRunner(RLELossless)
        for name in ("transfer_syntax_uid", "pixel_keyword"):
            msg = f"Deleting '{name}' is not allowed"
            with pytest.raises(ValueError, match=msg):
                runner.del_option(name)

    def test_set_source_dataset(self):
        """Test setting runner source and options via dataset."""
        runner = DecodeRunner(RLELossless)
        runner.set_source(RLE_16_1_1F.ds)
        assert runner.bits_allocated == 16
        assert runner.bits_stored == 16
        assert runner.columns == 64
        assert runner.extended_offsets is None
        assert runner.number_of_frames == 1
        assert runner.photometric_interpretation == PI.MONOCHROME2
        assert runner.pixel_keyword == "PixelData"
        assert runner.pixel_representation == 1
        assert runner.rows == 64
        assert runner.samples_per_pixel == 1
        assert runner.get_option("planar_configuration") is None

        ds = Dataset()
        ds.BitsAllocated = 32
        ds.BitsStored = 24
        ds.Columns = 10
        ds.Rows = 8
        ds.SamplesPerPixel = 3
        ds.NumberOfFrames = "5"
        ds.FloatPixelData = None
        ds.PlanarConfiguration = 1
        ds.ExtendedOffsetTable = b"\x00\x01"
        ds.ExtendedOffsetTableLengths = b"\x00\x02"
        ds.PhotometricInterpretation = "PALETTE COLOR"
        runner = DecodeRunner(RLELossless)
        runner.set_source(ds)
        assert runner.is_dataset

        assert runner.bits_allocated == 32
        assert runner.bits_stored == 24
        assert runner.columns == 10
        assert runner.extended_offsets == (b"\x00\x01", b"\x00\x02")
        assert runner.number_of_frames == 5
        assert runner.photometric_interpretation == PI.PALETTE_COLOR
        assert runner.pixel_keyword == "FloatPixelData"
        assert runner.get_option("pixel_representation") is None
        assert runner.rows == 8
        assert runner.samples_per_pixel == 3
        assert runner.planar_configuration == 1

        del ds.ExtendedOffsetTable
        ds.SamplesPerPixel = 1
        del ds.PlanarConfiguration
        del ds.FloatPixelData
        ds.DoubleFloatPixelData = None
        runner = DecodeRunner(RLELossless)
        runner.set_source(ds)
        assert runner.extended_offsets is None
        assert runner.pixel_keyword == "DoubleFloatPixelData"
        assert runner.get_option("planar_configuration") is None

        ds.PixelData = None
        msg = (
            "One and only one of 'Pixel Data', 'Float Pixel Data' or "
            "'Double Float Pixel Data' may be present in the dataset"
        )
        with pytest.raises(AttributeError, match=msg):
            runner.set_source(ds)

        del ds.PixelData
        del ds.DoubleFloatPixelData
        msg = (
            "The dataset has no 'Pixel Data', 'Float Pixel Data' or 'Double "
            "Float Pixel Data' element, no pixel data to decode"
        )
        with pytest.raises(AttributeError, match=msg):
            runner.set_source(ds)

        ds.file_meta = Dataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

        msg = (
            "The dataset's transfer syntax 'Explicit VR Little Endian' doesn't "
            "match the pixel data decoder"
        )
        with pytest.raises(ValueError, match=msg):
            runner.set_source(ds)

    def test_str(self):
        """Test str(DecodeRunner)"""
        runner = DecodeRunner(RLELossless)
        runner.set_decoders({"foo": None})
        assert str(runner) == (
            "DecodeRunner for 'RLE Lossless'\n"
            "Options\n"
            "  transfer_syntax_uid: 1.2.840.10008.1.2.5\n"
            "  as_rgb: True\n"
            "  allow_excess_frames: True\n"
            "  pixel_keyword: PixelData\n"
            "  correct_unused_bits: True\n"
            "Decoders\n"
            "  foo"
        )

    def test_test_for_be_swap(self):
        """Test test_for('be_swap_ow')"""
        runner = DecodeRunner(ExplicitVRBigEndian)
        with pytest.raises(ValueError, match=r"Unknown test 'foo'"):
            runner._test_for("foo")

        runner.set_option("bits_allocated", 8)
        runner.set_option("pixel_keyword", "PixelData")

        assert runner._test_for("be_swap_ow") is False
        runner.set_option("be_swap_ow", True)
        assert runner._test_for("be_swap_ow") is True
        runner.set_option("be_swap_ow", False)
        assert runner._test_for("be_swap_ow") is False
        runner.set_option("pixel_vr", "OW")
        assert runner._test_for("be_swap_ow") is True

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
    def test_pixel_dtype_unsupported_raises(self):
        """Test unsupported dtypes raise exception."""
        runner = DecodeRunner(RLELossless)
        runner.set_option("bits_allocated", 24)
        runner.set_option("pixel_representation", 0)

        msg = "The data type 'u3' needed to contain the pixel data"
        with pytest.raises(NotImplementedError, match=msg):
            runner.pixel_dtype

    @pytest.mark.skipif(HAVE_NP, reason="Numpy is available")
    def test_pixel_dtype_no_numpy_raises(self):
        """Tests exception raised if numpy not available."""
        runner = DecodeRunner(RLELossless)
        msg = "NumPy is required for 'DecodeRunner.pixel_dtype'"
        with pytest.raises(ImportError, match=msg):
            runner.pixel_dtype

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
    def test_pixel_dtype(self):
        """Test supported dtypes."""
        reference = [
            (1, 0, "u1"),
            (1, 1, "u1"),
            (8, 0, "u1"),
            (8, 1, "i1"),
            (16, 0, "u2"),
            (16, 1, "i2"),
            (32, 0, "u4"),
            (32, 1, "i4"),
        ]

        runner = DecodeRunner(RLELossless)
        for bits, pixel_repr, dtype in reference:
            runner.set_option("bits_allocated", bits)
            runner.set_option("pixel_representation", pixel_repr)

            # Correct for endianness of system
            ref_dtype = np.dtype(dtype)
            if not (byteorder == "little"):
                ref_dtype = ref_dtype.newbyteorder("S")

            assert ref_dtype == runner.pixel_dtype

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
    def test_pixel_dtype_float(self):
        runner = DecodeRunner(ExplicitVRLittleEndian)
        runner.set_option("pixel_keyword", "FloatPixelData")
        assert runner.pixel_dtype == np.float32
        runner.set_option("pixel_keyword", "DoubleFloatPixelData")
        assert runner.pixel_dtype == np.float64

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
    def test_pixel_dtype_byte_swapping(self):
        """Test that the endianness of the system is taken into account."""
        # The main problem is that our testing environments are probably
        #   all little endian, but we'll try our best
        runner = DecodeRunner(RLELossless)
        runner.set_option("bits_allocated", 16)
        runner.set_option("pixel_representation", 0)

        # < is little, = is native, > is big
        if byteorder == "little":
            assert runner.pixel_dtype.byteorder in ["<", "="]
            runner._opts["transfer_syntax_uid"] = ExplicitVRBigEndian
            assert runner.pixel_dtype.byteorder == ">"
        elif byteorder == "big":
            assert runner.pixel_dtype.byteorder == "<"
            runner._opts["transfer_syntax_uid"] = ExplicitVRBigEndian
            assert runner.pixel_dtype.byteorder in [">", "="]

    def test_validate_buffer(self):
        """Tests for validate_buffer()"""
        runner = DecodeRunner(RLELossless)
        # Padded
        runner.set_source(b"\x01\x02\x03\x00")
        runner.set_option("bits_allocated", 8)
        runner.set_option("rows", 1)
        runner.set_option("columns", 1)
        runner.set_option("samples_per_pixel", 3)
        runner.set_option("photometric_interpretation", "RGB")
        runner.set_option("number_of_frames", 1)

        msg = (
            "The number of bytes of compressed pixel data matches the "
            "expected number for uncompressed data - check that the "
            "transfer syntax has been set correctly"
        )
        with pytest.warns(UserWarning, match=msg):
            runner._validate_buffer()

        # Unpadded
        runner.set_source(b"\x01\x02\x03")
        with pytest.warns(UserWarning, match=msg):
            runner._validate_buffer()

        runner = DecodeRunner(ExplicitVRLittleEndian)
        runner.set_source(b"\x00\x00")
        runner.set_option("bits_allocated", 8)
        runner.set_option("rows", 1)
        runner.set_option("columns", 1)
        runner.set_option("samples_per_pixel", 3)
        runner.set_option("photometric_interpretation", "RGB")
        runner.set_option("number_of_frames", 1)

        # Actual length 2 is less than expected 3
        msg = (
            "The number of bytes of pixel data is less than expected "
            r"\(2 vs 4 bytes\) - the dataset may be corrupted, have an invalid "
            "group 0028 element value, or the transfer syntax may be incorrect"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_buffer()

        # Actual length 5 is greater than expected 3  (padding 2)
        runner.set_source(b"\x00" * 5)
        msg = (
            "The pixel data is 5 bytes long, which indicates it "
            "contains 2 bytes of excess padding to be removed"
        )
        with pytest.warns(UserWarning, match=msg):
            runner._validate_buffer()

        # YBR_FULL_422 but has unsubsampled length
        # expected 18 // 3 * 2 = 12, actual 18
        runner.set_option("photometric_interpretation", "YBR_FULL_422")
        runner.set_option("rows", 2)
        runner.set_option("columns", 3)
        runner.set_source(b"\x00" * 18)

        msg = (
            "The number of bytes of pixel data is a third larger than expected "
            r"\(18 vs 12 bytes\) which indicates the set \(0028,0004\) "
            r"'Photometric Interpretation' value of 'YBR_FULL_422' is "
            "incorrect and may need to be changed to either 'RGB' or 'YBR_FULL'"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_buffer()

    def test_validate_options(self):
        """Tests for validate_options()"""
        # DecodeRunner-specific option validation
        runner = DecodeRunner(ExplicitVRLittleEndian)
        runner.set_option("bits_allocated", 8)
        runner.set_option("bits_stored", 8)
        runner.set_option("columns", 8)
        runner.set_option("photometric_interpretation", PI.RGB)
        runner.set_option("pixel_keyword", "PixelData")
        runner.set_option("pixel_representation", 0)
        runner.set_option("rows", 10)
        runner.set_option("samples_per_pixel", 3)
        runner.set_option("planar_configuration", 1)
        runner.set_option("number_of_frames", 8)
        runner.set_option("extended_offsets", ([1, 2], [1]))
        msg = (
            r"The number of items in \(7FE0,0001\) 'Extended Offset Table' and "
            r"\(7FE0,0002\) 'Extended Offset Table Lengths' don't match - the "
            "extended offset table will be ignored"
        )
        with pytest.warns(UserWarning, match=msg):
            runner._validate_options()

        runner.set_option("extended_offsets", ([0], [10]))
        runner._validate_options()

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
    def test_decode(self):
        """Test decode()"""
        runner = DecodeRunner(RLELossless)
        runner.set_source(RLE_16_1_10F.ds)

        msg = "Unable to decode as exceptions were raised by all available plugins"
        with pytest.raises(RuntimeError, match=msg):
            runner.decode(0)

        decoder = get_decoder(RLELossless)
        runner.set_decoders(decoder._validate_plugins("pydicom"))
        buffer = runner.decode(0)

        assert runner._previous[1] == runner._decoders["pydicom"]

        arr = np.frombuffer(buffer, dtype=runner.pixel_dtype)
        arr = runner.reshape(arr, as_frame=True)
        RLE_16_1_10F.test(arr, index=0)

        buffer = runner.decode(9)
        arr = np.frombuffer(buffer, dtype=runner.pixel_dtype)
        arr = runner.reshape(arr, as_frame=True)
        RLE_16_1_10F.test(arr, index=9)

        def decode1(src, opts):
            raise ValueError("Bad decoding, many errors")

        def decode2(src, opts):
            raise AttributeError("Also bad, not helpful")

        # Check that exception messages on decoder failure
        # Need to update the attr to avoid resetting _previous
        runner._decoders = {"foo": decode1, "bar": decode2}
        assert hasattr(runner, "_previous")
        msg = (
            r"Unable to decode as exceptions were raised by all available plugins:"
            r"\n  foo: Bad decoding, many errors\n  bar: Also bad, not helpful"
        )
        with pytest.raises(RuntimeError, match=msg):
            runner.decode(0)

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
    def test_iter_decode(self, caplog):
        """Test iter_decode()"""
        runner = DecodeRunner(RLELossless)
        runner.set_source(RLE_16_1_10F.ds)

        msg = "Unable to decode as exceptions were raised by all available plugins"
        with pytest.raises(RuntimeError, match=msg):
            runner.decode(0)

        decoder = get_decoder(RLELossless)
        plugins = decoder._validate_plugins("pydicom")
        runner.set_decoders(plugins)
        data = runner.iter_decode()
        buffer = next(data)

        assert runner._previous[1] == runner._decoders["pydicom"]

        arr = np.frombuffer(buffer, dtype=runner.pixel_dtype)
        arr = runner.reshape(arr, as_frame=True)
        RLE_16_1_10F.test(arr, index=0)

        for ii in range(9):
            buffer = next(data)

        arr = np.frombuffer(buffer, dtype=runner.pixel_dtype)
        arr = runner.reshape(arr, as_frame=True)
        RLE_16_1_10F.test(arr, index=9)

        pytest.raises(StopIteration, next, data)

        raise_exc = [False]

        def foo(src, opts):
            if raise_exc[0]:
                raise ValueError("Oops")

            return b"\x00\x00"

        runner.set_decoders({"foo": foo})
        assert not hasattr(runner, "_previous")
        data = runner.iter_decode()
        assert b"\x00\x00" == next(data)
        assert runner._previous[1] == foo
        raise_exc[0] = True
        pytest.raises(RuntimeError, next, data)

        # Test decode failure during
        raise_exc = [False]

        def decode_partial(src, opts):
            if raise_exc[0]:
                raise ValueError("Whoops")

            return b"\x00\x00\x00\x00"

        def decode_all(src, opts):
            return b"\x03\x02\x01\x00"

        runner._src = encapsulate([b"\x00\x01\x02\x03"] * 10)
        runner.set_decoders({"foo": decode_partial})
        runner.set_decoders({"foo": decode_partial, "bar": decode_all})
        frame_generator = runner.iter_decode()
        assert next(frame_generator) == b"\x00\x00\x00\x00"
        raise_exc = [True]
        msg = (
            "The decoding plugin has changed from 'foo' to 'bar' during the "
            "decoding process - you may get inconsistent inter-frame results, "
            "consider passing 'decoding_plugin=\"bar\"' instead"
        )
        with caplog.at_level(logging.WARNING, logger="pydicom"):
            with pytest.warns(UserWarning, match=msg):
                assert next(frame_generator) == b"\x03\x02\x01\x00"

            assert (
                "The decoding plugin 'foo' failed to decode the frame at index 1"
            ) in caplog.text

    def test_get_data(self):
        """Test get_data()"""
        src = b"\x00\x01\x02\x03\x04\x05"
        runner = DecodeRunner(RLELossless)
        runner.set_source(src)
        assert runner.is_buffer
        assert runner.get_data(src, 0, 4) == b"\x00\x01\x02\x03"
        assert runner.get_data(src, 3, 4) == b"\x03\x04\x05"

        src = BytesIO(src)
        runner.set_source(src)
        assert not runner.is_buffer
        assert runner.get_data(src, 0, 4) == b"\x00\x01\x02\x03"
        assert src.tell() == 0
        assert runner.get_data(src, 3, 4) == b"\x03\x04\x05"
        assert src.seek(2)
        assert runner.get_data(src, 3, 4) == b"\x03\x04\x05"
        assert src.tell() == 2

    def test_pixel_properties(self):
        """Test pixel_properties()"""
        runner = DecodeRunner(RLELossless)
        opts = {
            "columns": 9,
            "rows": 10,
            "samples_per_pixel": 1,
            "number_of_frames": 3,
            "pixel_keyword": "PixelData",
            "photometric_interpretation": PI.RGB,
            "pixel_representation": 0,
            "bits_allocated": 16,
            "bits_stored": 8,
        }
        runner.set_options(**opts)
        d = runner.pixel_properties()
        assert d["columns"] == 9
        assert d["rows"] == 10
        assert d["samples_per_pixel"] == 1
        assert d["number_of_frames"] == 3
        assert d["photometric_interpretation"] == PI.RGB
        assert d["pixel_representation"] == 0
        assert d["bits_allocated"] == 16
        assert d["bits_stored"] == 8
        assert d["number_of_frames"] == 3
        assert "planar_configuration" not in d

        runner.set_option("pixel_keyword", "FloatPixelData")
        assert "pixel_representation" not in runner.pixel_properties()

        runner.set_option("samples_per_pixel", 3)
        runner.set_option("planar_configuration", 1)
        assert runner.pixel_properties()["planar_configuration"] == 1


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestDecodeRunner_Reshape:
    def setup_method(self):
        """Setup the test dataset."""
        self.runner = DecodeRunner(ExplicitVRLittleEndian)
        self.runner.set_option("rows", 4)
        self.runner.set_option("columns", 5)
        self.runner.set_option("number_of_frames", 1)

        self.reference = np.asarray(
            [
                [  # Frame 1
                    [[1, 9, 17], [2, 10, 18], [3, 11, 19], [4, 12, 20], [5, 13, 21]],
                    [[2, 10, 18], [3, 11, 19], [4, 12, 20], [5, 13, 21], [6, 14, 22]],
                    [[3, 11, 19], [4, 12, 20], [5, 13, 21], [6, 14, 22], [7, 15, 23]],
                    [[4, 12, 20], [5, 13, 21], [6, 14, 22], [7, 15, 23], [8, 16, 24]],
                ],
                [  # Frame 2
                    [
                        [25, 33, 41],
                        [26, 34, 42],
                        [27, 35, 43],
                        [28, 36, 44],
                        [29, 37, 45],
                    ],
                    [
                        [26, 34, 42],
                        [27, 35, 43],
                        [28, 36, 44],
                        [29, 37, 45],
                        [30, 38, 46],
                    ],
                    [
                        [27, 35, 43],
                        [28, 36, 44],
                        [29, 37, 45],
                        [30, 38, 46],
                        [31, 39, 47],
                    ],
                    [
                        [28, 36, 44],
                        [29, 37, 45],
                        [30, 38, 46],
                        [31, 39, 47],
                        [32, 40, 48],
                    ],
                ],
            ]
        )
        self.ref_1_1 = self.reference[0, :, :, 0]
        self.ref_1_3 = self.reference[0]
        self.ref_2_1 = self.reference[:, :, :, 0]
        self.ref_2_3 = self.reference

    @pytest.fixture
    def _1frame_1sample(self):
        return np.asarray([1, 2, 3, 4, 5, 2, 3, 4, 5, 6, 3, 4, 5, 6, 7, 4, 5, 6, 7, 8])

    @pytest.fixture
    def _2frame_1sample(self):
        return np.asarray(
            [
                [1, 2, 3, 4, 5, 2, 3, 4, 5, 6],
                [3, 4, 5, 6, 7, 4, 5, 6, 7, 8],
                [25, 26, 27, 28, 29, 26, 27, 28, 29, 30],
                [27, 28, 29, 30, 31, 28, 29, 30, 31, 32],
            ]
        ).ravel()

    @pytest.fixture
    def _1frame_3sample_0config(self):
        return np.asarray(
            [
                [1, 9, 17, 2, 10, 18, 3, 11, 19, 4],
                [12, 20, 5, 13, 21, 2, 10, 18, 3, 11],
                [19, 4, 12, 20, 5, 13, 21, 6, 14, 22],
                [3, 11, 19, 4, 12, 20, 5, 13, 21, 6],
                [14, 22, 7, 15, 23, 4, 12, 20, 5, 13],
                [21, 6, 14, 22, 7, 15, 23, 8, 16, 24],
            ]
        ).ravel()

    @pytest.fixture
    def _1frame_3sample_1config(self):
        return np.asarray(
            [
                [1, 2, 3, 4, 5, 2, 3, 4, 5, 6],  # Red
                [3, 4, 5, 6, 7, 4, 5, 6, 7, 8],
                [9, 10, 11, 12, 13, 10, 11, 12, 13, 14],  # Green
                [11, 12, 13, 14, 15, 12, 13, 14, 15, 16],
                [17, 18, 19, 20, 21, 18, 19, 20, 21, 22],  # Blue
                [19, 20, 21, 22, 23, 20, 21, 22, 23, 24],
            ]
        ).ravel()

    @pytest.fixture
    def _2frame_3sample_0config(self):
        return np.asarray(
            [
                [1, 9, 17, 2, 10, 18, 3, 11, 19, 4, 12, 20],  # Frame 1
                [5, 13, 21, 2, 10, 18, 3, 11, 19, 4, 12, 20],
                [5, 13, 21, 6, 14, 22, 3, 11, 19, 4, 12, 20],
                [5, 13, 21, 6, 14, 22, 7, 15, 23, 4, 12, 20],
                [5, 13, 21, 6, 14, 22, 7, 15, 23, 8, 16, 24],
                [25, 33, 41, 26, 34, 42, 27, 35, 43, 28, 36, 44],  # Frame 2
                [29, 37, 45, 26, 34, 42, 27, 35, 43, 28, 36, 44],
                [29, 37, 45, 30, 38, 46, 27, 35, 43, 28, 36, 44],
                [29, 37, 45, 30, 38, 46, 31, 39, 47, 28, 36, 44],
                [29, 37, 45, 30, 38, 46, 31, 39, 47, 32, 40, 48],
            ]
        ).ravel()

    @pytest.fixture
    def _2frame_3sample_1config(self):
        return np.asarray(
            [
                [1, 2, 3, 4, 5, 2, 3, 4, 5, 6],  # Frame 1, red
                [3, 4, 5, 6, 7, 4, 5, 6, 7, 8],
                [9, 10, 11, 12, 13, 10, 11, 12, 13, 14],  # Frame 1, green
                [11, 12, 13, 14, 15, 12, 13, 14, 15, 16],
                [17, 18, 19, 20, 21, 18, 19, 20, 21, 22],  # Frame 1, blue
                [19, 20, 21, 22, 23, 20, 21, 22, 23, 24],
                [25, 26, 27, 28, 29, 26, 27, 28, 29, 30],  # Frame 2, red
                [27, 28, 29, 30, 31, 28, 29, 30, 31, 32],
                [33, 34, 35, 36, 37, 34, 35, 36, 37, 38],  # Frame 2, green
                [35, 36, 37, 38, 39, 36, 37, 38, 39, 40],
                [41, 42, 43, 44, 45, 42, 43, 44, 45, 46],  # Frame 2, blue
                [43, 44, 45, 46, 47, 44, 45, 46, 47, 48],
            ]
        ).ravel()

    def test_reference_1frame_1sample(self):
        """Test the 1 frame 1 sample/pixel reference array is as expected."""
        # (rows, columns)
        assert (4, 5) == self.ref_1_1.shape
        assert np.array_equal(
            self.ref_1_1,
            np.asarray(
                [[1, 2, 3, 4, 5], [2, 3, 4, 5, 6], [3, 4, 5, 6, 7], [4, 5, 6, 7, 8]]
            ),
        )

    def test_reference_1frame_3sample(self):
        """Test the 1 frame 3 sample/pixel reference array is as expected."""
        # (rows, columns, planes)
        assert (4, 5, 3) == self.ref_1_3.shape

        # Red channel
        assert np.array_equal(
            self.ref_1_3[:, :, 0],
            np.asarray(
                [[1, 2, 3, 4, 5], [2, 3, 4, 5, 6], [3, 4, 5, 6, 7], [4, 5, 6, 7, 8]]
            ),
        )
        # Green channel
        assert np.array_equal(
            self.ref_1_3[:, :, 1],
            np.asarray(
                [
                    [9, 10, 11, 12, 13],
                    [10, 11, 12, 13, 14],
                    [11, 12, 13, 14, 15],
                    [12, 13, 14, 15, 16],
                ]
            ),
        )
        # Blue channel
        assert np.array_equal(
            self.ref_1_3[:, :, 2],
            np.asarray(
                [
                    [17, 18, 19, 20, 21],
                    [18, 19, 20, 21, 22],
                    [19, 20, 21, 22, 23],
                    [20, 21, 22, 23, 24],
                ]
            ),
        )

    def test_reference_2frame_1sample(self):
        """Test the 2 frame 1 sample/pixel reference array is as expected."""
        # (nr frames, rows, columns)
        assert (2, 4, 5) == self.ref_2_1.shape

        # Frame 1
        assert np.array_equal(
            self.ref_2_1[0, :, :],
            np.asarray(
                [[1, 2, 3, 4, 5], [2, 3, 4, 5, 6], [3, 4, 5, 6, 7], [4, 5, 6, 7, 8]]
            ),
        )
        # Frame 2
        assert np.array_equal(
            self.ref_2_1[1, :, :],
            np.asarray(
                [
                    [25, 26, 27, 28, 29],
                    [26, 27, 28, 29, 30],
                    [27, 28, 29, 30, 31],
                    [28, 29, 30, 31, 32],
                ]
            ),
        )

    def test_reference_2frame_3sample(self):
        """Test the 2 frame 3 sample/pixel reference array is as expected."""
        # (nr frames, row, columns, planes)
        assert (2, 4, 5, 3) == self.ref_2_3.shape

        # Red channel, frame 1
        assert np.array_equal(
            self.ref_2_3[0, :, :, 0],
            np.asarray(
                [[1, 2, 3, 4, 5], [2, 3, 4, 5, 6], [3, 4, 5, 6, 7], [4, 5, 6, 7, 8]]
            ),
        )
        # Green channel, frame 2
        assert np.array_equal(
            self.ref_2_3[1, :, :, 1],
            np.asarray(
                [
                    [33, 34, 35, 36, 37],
                    [34, 35, 36, 37, 38],
                    [35, 36, 37, 38, 39],
                    [36, 37, 38, 39, 40],
                ]
            ),
        )

    def test_1frame_1sample(self, _1frame_1sample):
        """Test reshaping 1 frame, 1 sample/pixel."""
        self.runner.set_option("samples_per_pixel", 1)
        arr = self.runner.reshape(_1frame_1sample)
        assert (4, 5) == arr.shape
        assert np.array_equal(arr, self.ref_1_1)

        # Test reshape to (rows, cols) is view-only
        buffer = arr.tobytes()
        out = np.frombuffer(buffer, arr.dtype)
        assert not out.flags.writeable
        out = self.runner.reshape(out)
        assert not out.flags.writeable

    def test_1frame_3sample_0conf(self, _1frame_3sample_0config):
        """Test reshaping 1 frame, 3 sample/pixel for 0 planar config."""
        self.runner.set_option("number_of_frames", 1)
        self.runner.set_option("samples_per_pixel", 3)
        self.runner.set_option("planar_configuration", 0)
        arr = self.runner.reshape(_1frame_3sample_0config)
        assert (4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_1_3)

        # Test reshape to (rows, cols, planes) is view-only
        buffer = arr.tobytes()
        out = np.frombuffer(buffer, arr.dtype)
        assert not out.flags.writeable
        out = self.runner.reshape(out)
        assert not out.flags.writeable

    def test_1frame_3sample_1conf(self, _1frame_3sample_1config):
        """Test reshaping 1 frame, 3 sample/pixel for 1 planar config."""
        self.runner.set_option("number_of_frames", 1)
        self.runner.set_option("samples_per_pixel", 3)
        self.runner.set_option("planar_configuration", 1)
        arr = self.runner.reshape(_1frame_3sample_1config)
        assert (4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_1_3)

        # Test reshape to (rows, cols, planes) is view-only
        buffer = arr.tobytes()
        out = np.frombuffer(buffer, arr.dtype)
        assert not out.flags.writeable
        out = self.runner.reshape(out)
        assert not out.flags.writeable

    def test_2frame_1sample(self, _1frame_1sample, _2frame_1sample):
        """Test reshaping 2 frame, 1 sample/pixel."""
        self.runner.set_option("number_of_frames", 2)
        self.runner.set_option("samples_per_pixel", 1)
        arr = self.runner.reshape(_2frame_1sample)
        assert (2, 4, 5) == arr.shape
        assert np.array_equal(arr, self.ref_2_1)

        # Test reshape to (frames, rows, cols) is view-only
        buffer = arr.tobytes()
        out = np.frombuffer(buffer, arr.dtype)
        assert not out.flags.writeable
        out = self.runner.reshape(out)
        assert not out.flags.writeable

        arr = self.runner.reshape(_1frame_1sample, as_frame=True)
        assert (4, 5) == arr.shape
        assert np.array_equal(arr, self.ref_1_1)

    def test_2frame_3sample_0conf(
        self, _1frame_3sample_0config, _2frame_3sample_0config
    ):
        """Test reshaping 2 frame, 3 sample/pixel for 0 planar config."""
        self.runner.set_option("number_of_frames", 2)
        self.runner.set_option("samples_per_pixel", 3)
        self.runner.set_option("planar_configuration", 0)
        arr = self.runner.reshape(_2frame_3sample_0config)
        assert (2, 4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_2_3)

        # Test reshape to (frames, rows, cols, planes) is view-only
        buffer = arr.tobytes()
        out = np.frombuffer(buffer, arr.dtype)
        assert not out.flags.writeable
        out = self.runner.reshape(out)
        assert not out.flags.writeable

        arr = self.runner.reshape(_1frame_3sample_0config, as_frame=True)
        assert (4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_1_3)

    def test_2frame_3sample_1conf(
        self, _1frame_3sample_1config, _2frame_3sample_1config
    ):
        """Test reshaping 2 frame, 3 sample/pixel for 1 planar config."""
        self.runner.set_option("number_of_frames", 2)
        self.runner.set_option("samples_per_pixel", 3)
        self.runner.set_option("planar_configuration", 1)
        arr = self.runner.reshape(_2frame_3sample_1config)
        assert (2, 4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_2_3)

        # Test reshape to (frames, rows, cols, planes) is view-only
        buffer = arr.tobytes()
        out = np.frombuffer(buffer, arr.dtype)
        assert not out.flags.writeable
        out = self.runner.reshape(out)
        assert not out.flags.writeable

        arr = self.runner.reshape(_1frame_3sample_1config, as_frame=True)
        assert (4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_1_3)


class TestDecoder:
    """Tests for Decoder"""

    def test_init(self):
        """Test creating a new Decoder"""
        dec = Decoder(ExplicitVRLittleEndian)
        assert {} == dec._available
        assert {} == dec._unavailable
        assert dec.missing_dependencies == []
        assert dec._validate_plugins() == {}
        assert dec._decoder is True

    def test_properties(self):
        """Test Decoder properties"""
        dec = Decoder(RLELossless)
        assert RLELossless == dec.UID
        assert not dec.is_available
        assert dec.is_encapsulated
        assert not dec.is_native

    @pytest.mark.skipif(HAVE_NP, reason="Numpy is available")
    def test_missing_numpy_raises(self):
        """Test as_array() raises if no numpy"""
        dec = Decoder(RLELossless)

        msg = "NumPy is required when converting pixel data to an ndarray"
        with pytest.raises(ImportError, match=msg):
            dec.as_array(None)

        with pytest.raises(ImportError, match=msg):
            next(dec.iter_array(None))

    def test_buffer(self):
        """Test as_buffer() and iter_buffer()"""
        # Functionality test that numpy isn't required
        decoder = get_decoder(RLELossless)
        reference = RLE_16_1_10F
        buffer, meta = decoder.as_buffer(reference.ds)
        assert isinstance(buffer, bytes | bytearray)
        assert isinstance(meta, dict)
        for buffer, meta in decoder.iter_buffer(reference.ds):
            assert isinstance(buffer, bytes | bytearray)
            assert isinstance(meta, dict)

    def test_validate_plugins(self):
        """Test _validate_plugins() with plugins available"""
        decoder = get_decoder(RLELossless)
        msg = (
            "No plugin named 'foo' has been added to 'RLELosslessDecoder', "
            "available plugins are"
        )
        with pytest.raises(ValueError, match=msg):
            decoder._validate_plugins("foo")


@pytest.fixture()
def enable_logging():
    original = config.debugging
    config.debugging = True
    yield
    config.debugging = original


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
class TestDecoder_Array:
    """Tests for Decoder.as_array() and Decoder.iter_array()."""

    def test_logging(self, enable_logging, caplog):
        """Test that the logging works during decode"""
        decoder = get_decoder(ExplicitVRLittleEndian)

        with caplog.at_level(logging.DEBUG, logger="pydicom"):
            decoder.as_array(EXPL_1_1_1F.ds)
            assert "DecodeRunner for 'Explicit VR Little Endian'" in caplog.text
            assert "  as_rgb: True" in caplog.text

        with caplog.at_level(logging.DEBUG, logger="pydicom"):
            next(decoder.iter_array(EXPL_1_1_1F.ds, as_rgb=False))
            assert "DecodeRunner for 'Explicit VR Little Endian'" in caplog.text
            assert "  as_rgb: False" in caplog.text

    def test_bad_index_raises(self):
        """Test invalid 'index'"""
        decoder = get_decoder(ExplicitVRLittleEndian)

        msg = "'index' must be greater than or equal to 0"
        with pytest.raises(ValueError, match=msg):
            decoder.as_array(None, index=-1)

        msg = "There is insufficient pixel data to contain 11 frames"
        with pytest.raises(ValueError, match=msg):
            decoder.as_array(EXPL_16_1_10F.ds, index=10)

        msg = "There is insufficient pixel data to contain 2 frames"
        with pytest.raises(ValueError, match=msg):
            decoder.as_array(EXPL_8_3_1F_YBR.ds, index=1)

    def test_native_bitpacked_view_warns(self, caplog):
        """Test warning for bit packed data with `view_only`"""
        decoder = get_decoder(ExplicitVRLittleEndian)
        with caplog.at_level(logging.WARNING, logger="pydicom"):
            decoder.as_array(EXPL_1_1_1F.ds)
            assert not caplog.text

        with caplog.at_level(logging.WARNING, logger="pydicom"):
            decoder.as_array(EXPL_1_1_1F.ds, view_only=True)

            assert (
                "Unable to return an ndarray that's a view on the original "
                "buffer for bit-packed pixel data"
            ) in caplog.text

    def test_native_ybr422_view_warns(self, caplog):
        """Test warning for YBR_FULL_422 data with `view_only`"""
        decoder = get_decoder(ExplicitVRLittleEndian)
        with caplog.at_level(logging.WARNING, logger="pydicom"):
            decoder.as_array(EXPL_8_3_1F_YBR422.ds)
            assert not caplog.text

        with caplog.at_level(logging.WARNING, logger="pydicom"):
            decoder.as_array(EXPL_8_3_1F_YBR422.ds, view_only=True, raw=True)

            assert (
                "Unable to return an ndarray that's a view on the original "
                "buffer for uncompressed pixel data with a photometric "
                "interpretation of 'YBR_FULL_422'"
            ) in caplog.text

    def test_colorspace_change_view_warns(self, caplog):
        """Test warning for color space change with `view_only`"""
        decoder = get_decoder(ExplicitVRLittleEndian)
        with caplog.at_level(logging.WARNING, logger="pydicom"):
            decoder.as_array(EXPL_8_3_1F_YBR.ds, view_only=True)

            assert (
                "Unable to return an ndarray that's a view on the original "
                "buffer if applying a color space conversion"
            ) in caplog.text

    def test_native_index(self):
        """Test as_array(index=X)"""
        decoder = get_decoder(ExplicitVRLittleEndian)
        reference = EXPL_16_1_10F
        for index in [0, 4, 9]:
            arr, meta = decoder.as_array(reference.ds, index=index)
            reference.test(arr, index=index)
            assert arr.shape == reference.shape[1:]
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable
            assert meta["bits_stored"] == 12

    def test_native_view_only(self):
        """Test as_array(view_only=True)"""
        decoder = get_decoder(ExplicitVRLittleEndian)

        # Also tests Dataset `src`
        reference = EXPL_8_3_1F_YBR
        arr, meta = decoder.as_array(reference.ds, view_only=True, raw=True)
        assert isinstance(reference.ds.PixelData, bytes)  # immutable
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert not arr.flags.writeable  # read-only
        assert meta["photometric_interpretation"] == PI.YBR_FULL

        # Also tests buffer-like `src`
        ds = reference.ds
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": ds.PixelRepresentation,
            "bits_allocated": ds.BitsAllocated,
            "bits_stored": ds.BitsStored,
            "number_of_frames": ds.get("NumberOfFrames", 1),
            "planar_configuration": ds.get("PlanarConfiguration", 0),
            "pixel_keyword": "PixelData",
        }

        arr, _ = decoder.as_array(
            bytearray(ds.PixelData),  # mutable
            raw=True,
            view_only=True,
            **opts,
        )
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable  # not read-only

        arr, _ = decoder.as_array(
            memoryview(ds.PixelData),  # view of an immutable
            raw=True,
            view_only=True,
            **opts,
        )
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert not arr.flags.writeable  # read-only

        arr, _ = decoder.as_array(
            memoryview(bytearray(ds.PixelData)),  # view of a mutable
            raw=True,
            view_only=True,
            **opts,
        )
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable  # not read-only

        # BinaryIO
        with open(reference.path, "rb") as f:
            f.seek(ds["PixelData"].file_tell)
            arr, _ = decoder.as_array(
                f,
                raw=True,
                view_only=True,
                **opts,
            )

        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert not arr.flags.writeable  # read-only

    def test_native_excess_frames(self):
        """Test returning excess frame data"""
        decoder = get_decoder(ExplicitVRLittleEndian)
        ds = dcmread(EXPL_16_1_10F.path)
        ds.NumberOfFrames = 9

        msg = (
            "The number of bytes of pixel data is sufficient to contain 10 frames "
            r"which is larger than the given \(0028,0008\) 'Number of Frames' "
            "value of 9. The returned data will include these extra frames and if "
            "it's correct then you should update 'Number of Frames' accordingly, "
            "otherwise pass 'allow_excess_frames=False' to return only the first "
            "9 frames."
        )
        with pytest.warns(UserWarning, match=msg):
            arr, meta = decoder.as_array(ds)

        assert arr.shape == (10, 64, 64)
        assert meta["number_of_frames"] == 10

        msg = "contains 8192 bytes of excess padding"
        with pytest.warns(UserWarning, match=msg):
            arr, meta = decoder.as_array(ds, allow_excess_frames=False)

        assert arr.shape == (9, 64, 64)
        assert meta["number_of_frames"] == 9

    def test_native_from_buffer(self):
        """Test decoding a dataset which uses buffered Pixel Data."""
        decoder = get_decoder(ExplicitVRLittleEndian)
        ds = dcmread(EXPL_16_1_10F.path)
        ds.PixelData = BytesIO(ds.PixelData)
        for index in [0, 4, 9]:
            arr, meta = decoder.as_array(ds, index=index)
            EXPL_16_1_10F.test(arr, index=index)
            assert arr.shape == EXPL_16_1_10F.shape[1:]
            assert arr.dtype == EXPL_16_1_10F.dtype
            assert arr.flags.writeable
            assert meta["bits_stored"] == 12

    def test_encapsulated_index(self):
        """Test `index` with an encapsulated pixel data."""
        decoder = get_decoder(RLELossless)

        reference = RLE_16_1_10F
        for index in [0, 4, 9]:
            arr, meta = decoder.as_array(
                reference.ds, index=index, decoding_plugin="pydicom"
            )
            reference.test(arr, index=index)
            assert arr.shape == reference.shape[1:]
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable
            assert meta["bits_stored"] == 12

    def test_encapsulated_plugin(self):
        """Test `decoding_plugin` with an encapsulated pixel data."""
        decoder = get_decoder(RLELossless)

        reference = RLE_16_1_10F
        arr, meta = decoder.as_array(reference.ds, decoding_plugin="pydicom")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable
        assert meta["bits_stored"] == 12

    def test_encapsulated_excess_frames(self):
        """Test returning excess frame data"""
        decoder = get_decoder(RLELossless)
        reference = RLE_16_1_10F
        frames = [x for x in generate_frames(reference.ds.PixelData)]
        frames.append(frames[-1])
        src = encapsulate(frames)

        runner = DecodeRunner(RLELossless)
        runner.set_source(reference.ds)

        msg = (
            "11 frames have been found in the encapsulated pixel data, which is "
            r"larger than the given \(0028,0008\) 'Number of Frames' value of 10. "
            "The returned data will include these extra frames and if it's correct "
            "then you should update 'Number of Frames' accordingly, otherwise pass "
            "'allow_excess_frames=False' to return only the first 10 frames."
        )
        with pytest.warns(UserWarning, match=msg):
            arr, meta = decoder.as_array(src, **runner.options)

        assert arr.shape == (11, 64, 64)
        assert meta["number_of_frames"] == 11

        runner.set_option("allow_excess_frames", False)
        arr, meta = decoder.as_array(src, **runner.options)
        assert arr.shape == (10, 64, 64)
        assert meta["number_of_frames"] == 10

    def test_encapsulated_from_buffer(self):
        """Test decoding a dataset which uses buffered Pixel Data."""
        decoder = get_decoder(RLELossless)
        reference = RLE_16_1_10F
        ds = dcmread(reference.path)
        ds.PixelData = BytesIO(ds.PixelData)
        for index in [0, 4, 9]:
            arr, meta = decoder.as_array(ds, index=index)
            reference.test(arr, index=index)
            assert arr.shape == reference.shape[1:]
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable
            assert meta["bits_stored"] == 12

    def test_processing_colorspace(self):
        """Test the processing colorspace options."""
        decoder = get_decoder(ExplicitVRLittleEndian)

        reference = EXPL_8_3_1F_YBR
        assert reference.ds.PhotometricInterpretation == PI.YBR_FULL

        msg = "'force_ybr' and 'force_rgb' cannot both be True"
        with pytest.raises(ValueError, match=msg):
            decoder.as_array(reference.ds, force_rgb=True, force_ybr=True)

        # as_rgb (default)
        arr, meta = decoder.as_array(reference.ds)
        reference.test(arr, as_rgb=True)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable
        assert meta["photometric_interpretation"] == PI.RGB

        # force_rgb
        rgb, meta = decoder.as_array(
            reference.ds,
            photometric_interpretation="RGB",
            force_rgb=True,
        )
        reference.test(rgb, as_rgb=True)
        assert meta["photometric_interpretation"] == PI.RGB

        # force_ybr
        # Test ignores as_rgb
        ybr, meta = decoder.as_array(reference.ds, as_rgb=False, force_ybr=True)
        assert meta["photometric_interpretation"] == PI.YBR_FULL
        ybr2, meta = decoder.as_array(reference.ds, as_rgb=True, force_ybr=True)
        assert meta["photometric_interpretation"] == PI.YBR_FULL
        assert np.array_equal(ybr, ybr2)

        # Test is actually ybr + ybr = ybr`
        raw, meta = decoder.as_array(reference.ds, raw=True)
        assert meta["photometric_interpretation"] == PI.YBR_FULL
        out = convert_color_space(ybr, PI.YBR_FULL, PI.RGB)
        # Lossy conversion, equal to within 1 intensity unit
        assert np.allclose(out, raw, atol=1)

    def test_expb_ow_view_only_warns(self, caplog):
        """Test view_only with BE swapped OW warns"""
        decoder = get_decoder(ExplicitVRBigEndian)
        reference = EXPB_8_1_1F
        msg = (
            "Unable to return an ndarray that's a view on the original buffer "
            "for 8-bit pixel data encoded as OW with 'Explicit VR Big Endian'"
        )
        with caplog.at_level(logging.WARNING, logger="pydicom"):
            decoder.as_array(reference.ds, view_only=True)
            assert msg in caplog.text

    def test_expb_ow_index_invalid_raises(self):
        """Test invalid index with BE swapped OW raises"""
        decoder = get_decoder(ExplicitVRBigEndian)
        reference = EXPB_8_1_1F
        msg = "There is insufficient pixel data to contain 2 frames"
        with pytest.raises(ValueError, match=msg):
            decoder.as_array(reference.ds, index=1)

    def test_expb_ow(self):
        """Test BE swapped OW"""
        decoder = get_decoder(ExplicitVRBigEndian)
        opts = {
            "rows": 3,
            "columns": 3,
            "samples_per_pixel": 1,
            "photometric_interpretation": "MONOCHROME1",
            "pixel_representation": 0,
            "bits_allocated": 8,
            "bits_stored": 8,
            "number_of_frames": 3,
            "pixel_keyword": "PixelData",
            "pixel_vr": "OW",
        }

        src = (  #                            | 2_1 | 1_9
            b"\x01\x00\x03\x02\x05\x04\x07\x06\x09\x08"
            # 2_2 | 2_3
            b"\x0B\x0A\x0D\x0C\x0F\x0E\x11\x10"
            # 3_1                             | pad | 3_9
            b"\x13\x12\x15\x14\x17\x16\x19\x18\x00\x1A"
        )
        # Test by frame - odd-length
        arr, _ = decoder.as_array(src, **opts, index=0)
        assert arr.ravel().tolist() == [0, 1, 2, 3, 4, 5, 6, 7, 8]
        arr, _ = decoder.as_array(src, **opts, index=1)
        assert arr.ravel().tolist() == [9, 10, 11, 12, 13, 14, 15, 16, 17]
        arr, _ = decoder.as_array(src, **opts, index=2)
        assert arr.ravel().tolist() == [18, 19, 20, 21, 22, 23, 24, 25, 26]

        # Test all - odd-length
        opts["number_of_frames"] = 1
        arr, _ = decoder.as_array(b"\x01\x00\x03\x02\x05\x04\x07\x06\x00\x08", **opts)
        assert arr.ravel().tolist() == [0, 1, 2, 3, 4, 5, 6, 7, 8]

        # Test all - even-length
        opts["rows"] = 5
        opts["columns"] = 2
        arr, _ = decoder.as_array(b"\x01\x00\x03\x02\x05\x04\x07\x06\x09\x08", **opts)
        assert arr.ravel().tolist() == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

        # Test by frame - even length
        opts["number_of_frames"] = 3
        arr, _ = decoder.as_array(src + b"\x1D\x1C", **opts, index=0)
        assert arr.ravel().tolist() == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        arr, _ = decoder.as_array(src + b"\x1D\x1C", **opts, index=1)
        assert arr.ravel().tolist() == [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
        arr, _ = decoder.as_array(src + b"\x1D\x1C", **opts, index=2)
        assert arr.ravel().tolist() == [20, 21, 22, 23, 24, 25, 26, 0, 28, 29]

    def test_iter_native_indices(self):
        """Test the `indices` argument with native data."""
        decoder = get_decoder(ExplicitVRLittleEndian)
        reference = EXPL_16_1_10F

        indices = [0, 4, 9]
        func = decoder.iter_array(reference.ds, raw=True, indices=indices)
        for idx, (arr, meta) in enumerate(func):
            reference.test(arr, index=indices[idx])
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable
            assert arr.shape == reference.shape[1:]
            assert meta["bits_stored"] == 12
            assert meta["number_of_frames"] == 1

        assert idx == 2

    def test_iter_native_view_only(self, caplog):
        """Test as_array(view_only=True)"""
        decoder = get_decoder(ExplicitVRLittleEndian)
        reference = EXPL_16_1_10F
        ds = reference.ds
        assert ds.BitsAllocated == 16
        assert ds.BitsStored == 12

        assert isinstance(ds.PixelData, bytes)  # immutable
        func = decoder.iter_array(ds, view_only=True, raw=True)
        msg = (
            "Unable to return an ndarray that's a view on the original buffer when "
            "(0028,0101) 'Bits Stored' doesn't equal (0028,0100) 'Bits Allocated' "
            "and 'correct_unused_bits=True'. In most cases you can pass "
            "'correct_unused_bits=False' instead to get a view if the uncorrected "
            "array is equivalent to the corrected one."
        )
        with caplog.at_level(logging.WARNING, logger="pydicom"):
            arr, _ = next(func)
            reference.test(arr, index=0)
            assert arr.shape == reference.shape[1:]
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable  # not a view due to bit-shift
            assert msg in caplog.text

        for index, (arr, _) in enumerate(func):
            reference.test(arr, index=index + 1)
            assert arr.shape == reference.shape[1:]
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable  # not a view due to bit-shift

        func = decoder.iter_array(
            ds, view_only=True, raw=True, correct_unused_bits=False
        )
        for index, (arr, _) in enumerate(func):
            reference.test(arr, index=index)
            assert arr.shape == reference.shape[1:]
            assert arr.dtype == reference.dtype
            assert not arr.flags.writeable  # read-only

        func = decoder.iter_array(
            bytearray(ds.PixelData),  # mutable
            raw=True,
            view_only=True,
            rows=ds.Rows,
            columns=ds.Columns,
            samples_per_pixel=ds.SamplesPerPixel,
            photometric_interpretation=ds.PhotometricInterpretation,
            pixel_representation=ds.PixelRepresentation,
            bits_allocated=ds.BitsAllocated,
            bits_stored=ds.BitsStored,
            number_of_frames=ds.get("NumberOfFrames", 1),
            planar_configuration=ds.get("PlanarConfiguration", 0),
            pixel_keyword="PixelData",
        )
        for index, (arr, _) in enumerate(func):
            reference.test(arr, index=index)
            assert arr.shape == reference.shape[1:]
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable  # not read-only

        func = decoder.iter_array(
            memoryview(ds.PixelData),  # view of an immutable
            raw=True,
            view_only=True,
            rows=ds.Rows,
            columns=ds.Columns,
            samples_per_pixel=ds.SamplesPerPixel,
            photometric_interpretation=ds.PhotometricInterpretation,
            pixel_representation=ds.PixelRepresentation,
            bits_allocated=ds.BitsAllocated,
            bits_stored=ds.BitsStored,
            number_of_frames=ds.get("NumberOfFrames", 1),
            planar_configuration=ds.get("PlanarConfiguration", 0),
            pixel_keyword="PixelData",
            correct_unused_bits=False,
        )
        for index, (arr, _) in enumerate(func):
            reference.test(arr, index=index)
            assert arr.shape == reference.shape[1:]
            assert arr.dtype == reference.dtype
            assert not arr.flags.writeable  # read-only

        func = decoder.iter_array(
            memoryview(bytearray(ds.PixelData)),  # view of a mutable
            raw=True,
            view_only=True,
            rows=ds.Rows,
            columns=ds.Columns,
            samples_per_pixel=ds.SamplesPerPixel,
            photometric_interpretation=ds.PhotometricInterpretation,
            pixel_representation=ds.PixelRepresentation,
            bits_allocated=ds.BitsAllocated,
            bits_stored=ds.BitsStored,
            number_of_frames=ds.get("NumberOfFrames", 1),
            planar_configuration=ds.get("PlanarConfiguration", 0),
            pixel_keyword="PixelData",
        )
        for index, (arr, _) in enumerate(func):
            reference.test(arr, index=index)
            assert arr.shape == reference.shape[1:]
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable  # not read-only

    def test_iter_encapsulated_indices(self):
        """Test the `indices` argument with encapsulated data."""
        decoder = get_decoder(RLELossless)
        reference = RLE_16_1_10F

        indices = [0, 4, 9]
        func = decoder.iter_array(
            reference.ds, raw=True, indices=indices, decoding_plugin="pydicom"
        )
        for idx, (arr, meta) in enumerate(func):
            reference.test(arr, index=indices[idx])
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable
            assert arr.shape == reference.shape[1:]
            assert meta["bits_stored"] == 12
            assert meta["number_of_frames"] == 1

        assert idx == 2

    def test_iter_encapsulated_plugin(self):
        """Test `decoding_plugin` with an encapsulated pixel data."""
        decoder = get_decoder(RLELossless)

        reference = RLE_16_1_10F
        func = decoder.iter_array(reference.ds, decoding_plugin="pydicom")
        for index, (arr, _) in enumerate(func):
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable
            assert arr.shape == reference.shape[1:]

    def test_iter_processing(self):
        """Test the processing options."""
        decoder = get_decoder(ExplicitVRLittleEndian)

        reference = EXPL_8_3_1F_YBR
        assert reference.ds.PhotometricInterpretation == PI.YBR_FULL

        msg = "'force_ybr' and 'force_rgb' cannot both be True"
        with pytest.raises(ValueError, match=msg):
            next(decoder.iter_array(reference.ds, force_rgb=True, force_ybr=True))

        # as_rgb
        func = decoder.iter_array(reference.ds)
        arr, meta = next(func)
        reference.test(arr, as_rgb=True)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable
        assert meta["photometric_interpretation"] == PI.RGB

        # force_rgb
        func = decoder.iter_array(
            reference.ds,
            photometric_interpretation="RGB",
            force_rgb=True,
        )
        rgb, meta = next(func)
        reference.test(rgb, as_rgb=True)
        assert meta["photometric_interpretation"] == PI.RGB

        # force_ybr
        # Test ignores as_rgb
        ybr, meta = next(decoder.iter_array(reference.ds, as_rgb=False, force_ybr=True))
        assert meta["photometric_interpretation"] == PI.YBR_FULL
        ybr2, meta = next(decoder.iter_array(reference.ds, as_rgb=True, force_ybr=True))
        assert meta["photometric_interpretation"] == PI.YBR_FULL
        assert np.array_equal(ybr, ybr2)

        # Test is actually ybr + ybr = ybr`
        raw, meta = next(decoder.iter_array(reference.ds, raw=True))
        assert meta["photometric_interpretation"] == PI.YBR_FULL
        out = convert_color_space(ybr, PI.YBR_FULL, PI.RGB)
        # Lossy conversion, equal to within 1 intensity unit
        assert np.allclose(out, raw, atol=1)

    def test_iter_ybr_to_rgb(self):
        """Test conversion from YBR to RGB for multi-framed data."""
        decoder = get_decoder(ExplicitVRLittleEndian)

        ds = dcmread(EXPL_8_3_1F_YBR.path)
        ds.PixelData = ds.PixelData * 2
        ds.NumberOfFrames = 2
        assert ds.PhotometricInterpretation == PI.YBR_FULL

        for arr, meta in decoder.iter_array(ds):
            assert meta["photometric_interpretation"] == PI.RGB
            EXPL_8_3_1F_YBR.test(arr, as_rgb=True)

    def test_iter_planar_configuration(self):
        """Test iter_pixels() with planar configuration."""
        decoder = get_decoder(ExplicitVRLittleEndian)

        ds = dcmread(EXPL_8_3_1F_YBR.path)
        ds.PixelData = ds.PixelData * 2
        ds.NumberOfFrames = 2
        ds.PlanarConfiguration = 1

        # Always 0 when converting to an ndarray
        for _, meta in decoder.iter_array(ds):
            assert meta["planar_configuration"] == 0


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
class TestDecoder_Buffer:
    """Tests for Decoder.as_buffer() and Decoder.iter_buffer()."""

    def test_native_index(self):
        """Test `index`"""
        decoder = get_decoder(ExplicitVRLittleEndian)

        assert decoder.is_available

        reference = EXPL_16_1_10F
        for index in [0, 4, 9]:
            arr, meta_a = decoder.as_array(reference.ds, index=index)
            buffer, meta_b = decoder.as_buffer(reference.ds, index=index)
            assert arr.tobytes() == buffer
            assert meta_a == meta_b
            assert meta_a["number_of_frames"] == 1

        msg = "There is insufficient pixel data to contain 11 frames"
        with pytest.raises(ValueError, match=msg):
            decoder.as_buffer(reference.ds, index=10)

    def test_native_view_only(self):
        """Test `view_only`"""
        decoder = get_decoder(ExplicitVRLittleEndian)

        # immutable source buffer
        # Also tests Dataset `src`
        reference = EXPL_8_3_1F_YBR
        arr, meta_a = decoder.as_array(reference.ds, view_only=True, raw=True)
        buffer, meta_b = decoder.as_buffer(reference.ds, view_only=True, raw=True)
        assert isinstance(buffer, memoryview)
        assert arr.tobytes() == buffer
        assert buffer.obj is reference.ds.PixelData
        assert meta_a == meta_b

        # mutable source buffer
        # Also tests buffer-like `src`
        src = bytearray()
        src += b"\x00\x01\x02\x03\x04\x05\x06\x07\x08"
        opts = {
            "raw": True,
            "view_only": True,
            "rows": 3,
            "columns": 3,
            "samples_per_pixel": 1,
            "photometric_interpretation": PI.MONOCHROME1,
            "pixel_representation": 0,
            "bits_allocated": 8,
            "bits_stored": 8,
            "number_of_frames": 1,
            "pixel_keyword": "PixelData",
        }
        arr, _ = decoder.as_array(src, **opts)
        buffer, _ = decoder.as_buffer(src, **opts)
        assert isinstance(buffer, memoryview)
        assert arr.tobytes() == buffer
        assert buffer.obj is src

        # view of a mutable
        mview = memoryview(src)
        arr, _ = decoder.as_array(mview, **opts)
        buffer, _ = decoder.as_buffer(mview, **opts)
        assert isinstance(buffer, memoryview)
        assert arr.tobytes() == buffer
        assert buffer.obj is src

        # view of an immutable
        src = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08"
        mview = memoryview(src)
        arr, _ = decoder.as_array(mview, **opts)
        buffer, _ = decoder.as_buffer(mview, **opts)
        assert isinstance(buffer, memoryview)
        assert arr.tobytes() == buffer
        assert buffer.obj is src

    def test_encapsulated_index(self):
        """Test `index` with an encapsulated pixel data."""
        decoder = get_decoder(RLELossless)

        reference = RLE_16_1_10F
        for index in [0, 4, 9]:
            arr, _ = decoder.as_array(reference.ds, index=index)
            buffer, meta = decoder.as_buffer(reference.ds, index=index)
            assert isinstance(buffer, bytes | bytearray)
            assert arr.tobytes() == buffer
            assert meta["bits_stored"] == 12
            assert meta["number_of_frames"] == 1

    def test_encapsulated_plugin(self):
        """Test `decoding_plugin` with an encapsulated pixel data."""
        decoder = get_decoder(RLELossless)
        reference = RLE_16_1_10F
        arr, _ = decoder.as_array(reference.ds, decoding_plugin="pydicom")
        buffer, _ = decoder.as_buffer(reference.ds, decoding_plugin="pydicom")
        assert isinstance(buffer, bytes | bytearray)
        assert arr.tobytes() == buffer

    def test_encapsulated_invalid_decode_raises(self):
        """Test invalid decode raises"""
        decoder = Decoder(RLELossless)
        reference = RLE_16_1_10F

        def foo(src, opts):
            return b"\x00\x01"

        msg = (
            "Unexpected number of bytes in the decoded frame with index 0 "
            r"\(2 bytes actual vs 8192 expected\)"
        )
        decoder._available = {"foo": foo}
        with pytest.raises(ValueError, match=msg):
            decoder.as_buffer(reference.ds)

        msg = (
            "Unexpected number of bytes in the decoded frame with index 9 "
            r"\(2 bytes actual vs 8192 expected\)"
        )
        with pytest.raises(ValueError, match=msg):
            decoder.as_buffer(reference.ds, index=9)

    def test_encapsulated_excess_frames(self):
        """Test returning excess frame data"""
        decoder = get_decoder(RLELossless)
        reference = RLE_16_1_10F
        frames = [x for x in generate_frames(reference.ds.PixelData)]
        frames.append(frames[-1])
        src = encapsulate(frames)

        runner = DecodeRunner(RLELossless)
        runner.set_source(reference.ds)

        msg = (
            "11 frames have been found in the encapsulated pixel data, which is "
            r"larger than the given \(0028,0008\) 'Number of Frames' value of 10. "
            "The returned data will include these extra frames and if it's correct "
            "then you should update 'Number of Frames' accordingly, otherwise pass "
            "'allow_excess_frames=False' to return only the first 10 frames."
        )
        with pytest.warns(UserWarning, match=msg):
            buffer, meta = decoder.as_buffer(src, **runner.options)

        assert len(buffer) == 11 * 64 * 64 * 2
        assert meta["number_of_frames"] == 11

        runner.set_option("allow_excess_frames", False)
        buffer, meta = decoder.as_buffer(src, **runner.options)
        assert len(buffer) == 10 * 64 * 64 * 2
        assert meta["number_of_frames"] == 10

    def test_expb_ow_index_invalid_raises(self):
        """Test invalid index with BE swapped OW raises"""
        decoder = get_decoder(ExplicitVRBigEndian)
        reference = EXPB_8_1_1F
        msg = "There is insufficient pixel data to contain 2 frames"
        with pytest.raises(ValueError, match=msg):
            decoder.as_buffer(reference.ds, index=1)

    def test_expb_ow_index_odd_length(self):
        """Test index with odd length BE swapped OW"""
        decoder = get_decoder(ExplicitVRBigEndian)
        opts = {
            "rows": 3,
            "columns": 3,
            "samples_per_pixel": 1,
            "photometric_interpretation": "MONOCHROME1",
            "pixel_representation": 0,
            "bits_allocated": 8,
            "bits_stored": 8,
            "number_of_frames": 3,
            "pixel_keyword": "PixelData",
            "pixel_vr": "OW",
        }

        src = (  #                            | 2_1 | 1_9
            b"\x01\x00\x03\x02\x05\x04\x07\x06\x09\x08"
            # 2_2 | 2_3
            b"\x0B\x0A\x0D\x0C\x0F\x0E\x11\x10"
            # 3_1                             | pad | 3_9
            b"\x13\x12\x15\x14\x17\x16\x19\x18\x00\x1A"
        )
        # Includes +1 at end
        buffer, _ = decoder.as_buffer(src, **opts, index=0)
        assert buffer == b"\x01\x00\x03\x02\x05\x04\x07\x06\x09\x08"
        # Includes -1 at start
        buffer, _ = decoder.as_buffer(src, **opts, index=1)
        assert buffer == b"\x09\x08\x0B\x0A\x0D\x0C\x0F\x0E\x11\x10"
        # Includes +1 at end
        buffer, _ = decoder.as_buffer(src, **opts, index=2)
        assert buffer == b"\x13\x12\x15\x14\x17\x16\x19\x18\x00\x1A"

    def test_iter_native_indices(self):
        """Test `index`"""
        decoder = get_decoder(ExplicitVRLittleEndian)
        reference = EXPL_16_1_10F

        indices = [0, 4, 9]
        arr_func = decoder.iter_array(reference.ds, indices=indices)
        buf_func = decoder.iter_buffer(reference.ds, indices=indices)
        for idx, ((arr, _), (buffer, _)) in enumerate(zip(arr_func, buf_func)):
            assert isinstance(buffer, bytes | bytearray)
            assert arr.tobytes() == buffer

        assert idx == 2

    def test_iter_native_view_only(self):
        """Test `view_only`"""
        decoder = get_decoder(ExplicitVRLittleEndian)

        # immutable source buffer
        # Also tests Dataset `src`
        reference = EXPL_8_3_1F_YBR
        arr, _ = next(decoder.iter_array(reference.ds, view_only=True, raw=True))
        buffer, _ = next(decoder.iter_buffer(reference.ds, view_only=True, raw=True))
        assert isinstance(buffer, memoryview)
        assert arr.tobytes() == buffer
        assert buffer.obj is reference.ds.PixelData

        # mutable source buffer
        # Also tests buffer-like `src`
        src = bytearray()
        src += b"\x00\x01\x02\x03\x04\x05\x06\x07\x08"
        opts = {
            "raw": True,
            "view_only": True,
            "rows": 3,
            "columns": 3,
            "samples_per_pixel": 1,
            "photometric_interpretation": PI.MONOCHROME1,
            "pixel_representation": 0,
            "bits_allocated": 8,
            "bits_stored": 8,
            "number_of_frames": 1,
            "pixel_keyword": "PixelData",
        }
        arr, _ = next(decoder.iter_array(src, **opts))
        buffer, _ = next(decoder.iter_buffer(src, **opts))
        assert isinstance(buffer, memoryview)
        assert arr.tobytes() == buffer
        assert buffer.obj is src

        # view of a mutable
        mview = memoryview(src)
        arr, _ = next(decoder.iter_array(mview, **opts))
        buffer, _ = next(decoder.iter_buffer(mview, **opts))
        assert isinstance(buffer, memoryview)
        assert arr.tobytes() == buffer
        assert buffer.obj is src

        # view of an immutable
        src = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08"
        mview = memoryview(src)
        arr, _ = next(decoder.iter_array(mview, **opts))
        buffer, _ = next(decoder.iter_buffer(mview, **opts))
        assert isinstance(buffer, memoryview)
        assert arr.tobytes() == buffer
        assert buffer.obj is src

    def test_iter_encapsulated_indices(self):
        """Test `indices` with an encapsulated pixel data."""
        decoder = get_decoder(RLELossless)
        reference = RLE_16_1_10F
        indices = [0, 4, 9]
        arr_func = decoder.iter_array(reference.ds, indices=indices)
        buf_func = decoder.iter_buffer(reference.ds, indices=indices)
        for idx, ((arr, _), (buffer, _)) in enumerate(zip(arr_func, buf_func)):
            assert isinstance(buffer, bytes | bytearray)
            assert arr.tobytes() == buffer

    def test_iter_encapsulated_plugin(self):
        """Test `decoding_plugin` with an encapsulated pixel data."""
        decoder = get_decoder(RLELossless)
        reference = RLE_16_1_10F
        arr, _ = next(decoder.iter_array(reference.ds, decoding_plugin="pydicom"))
        buffer, _ = next(decoder.iter_buffer(reference.ds, decoding_plugin="pydicom"))
        assert isinstance(buffer, bytes | bytearray)
        assert arr.tobytes() == buffer


def test_get_decoder():
    """Test get_decoder()"""
    uids = [
        ExplicitVRLittleEndian,
        ImplicitVRLittleEndian,
        DeflatedExplicitVRLittleEndian,
        ExplicitVRBigEndian,
        RLELossless,
    ]
    for uid in uids:
        decoder = get_decoder(uid)
        assert isinstance(decoder, Decoder)
        assert decoder.UID == uid

    msg = (
        "No pixel data decoders have been implemented for 'SMPTE ST 2110-30 "
        "PCM Digital Audio'"
    )
    with pytest.raises(NotImplementedError, match=msg):
        get_decoder(SMPTEST211030PCMDigitalAudio)
