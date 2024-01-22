"""Tests for pydicom.pixels.decoder.base."""

from io import BytesIO
import logging
from struct import pack, unpack
from sys import byteorder

import pytest

from pydicom import config
from pydicom.dataset import Dataset
from pydicom.encaps import get_frame, generate_frames, encapsulate
from pydicom.pixels import get_decoder, ExplicitVRLittleEndianDecoder
from pydicom.pixels.decoders.base import DecodeRunner, Decoder
from pydicom.pixels.enums import PhotometricInterpretation as PI
from pydicom.pixel_data_handlers.util import convert_color_space

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
REFERENCE_FRAME_LENGTHS = [
    # (rows, cols, samples), bit depth, result in (bytes, pixels, ybr_bytes)
    # YBR can only be 3 samples/px and > 1 bit depth
    ((0, 0, 0), 1, (0, 0, None)),
    ((1, 1, 1), 1, (1, 1, None)),  # 1 bit -> 1 byte
    ((1, 1, 3), 1, (1, 3, None)),  # 3 bits -> 1 byte
    ((1, 3, 3), 1, (2, 9, None)),  # 9 bits -> 2 bytes
    ((2, 2, 1), 1, (1, 4, None)),  # 4 bits -> 1 byte
    ((2, 4, 1), 1, (1, 8, None)),  # 8 bits -> 1 byte
    ((3, 3, 1), 1, (2, 9, None)),  # 9 bits -> 2 bytes
    ((512, 512, 1), 1, (32768, 262144, None)),  # Typical length
    ((512, 512, 3), 1, (98304, 786432, None)),
    ((0, 0, 0), 8, (0, 0, None)),
    ((1, 1, 1), 8, (1, 1, None)),  # Odd length
    ((9, 1, 1), 8, (9, 9, None)),  # Odd length
    ((1, 2, 1), 8, (2, 2, None)),  # Even length
    ((512, 512, 1), 8, (262144, 262144, None)),
    ((512, 512, 3), 8, (786432, 786432, 524288)),
    ((0, 0, 0), 16, (0, 0, None)),
    ((1, 1, 1), 16, (2, 1, None)),  # 16 bit data can't be odd length
    ((1, 2, 1), 16, (4, 2, None)),
    ((512, 512, 1), 16, (524288, 262144, None)),
    ((512, 512, 3), 16, (1572864, 786432, 1048576)),
    ((0, 0, 0), 32, (0, 0, None)),
    ((1, 1, 1), 32, (4, 1, None)),  # 32 bit data can't be odd length
    ((1, 2, 1), 32, (8, 2, None)),
    ((512, 512, 1), 32, (1048576, 262144, None)),
    ((512, 512, 3), 32, (3145728, 786432, 2097152)),
]


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

        # No exception if deleting non-existent option
        assert runner.get_option("foo") is None
        runner.del_option("foo")

        assert runner.get_option("as_rgb") is not None
        runner.del_option("as_rgb")
        assert runner.get_option("as_rgb") is None

    @pytest.mark.parametrize("shape, bits, length", REFERENCE_FRAME_LENGTHS)
    def test_frame_length(self, shape, bits, length):
        """Test frame_length(unit='bytes')."""
        opts = {
            "photometric_interpretation": PI.MONOCHROME1,
            "rows": shape[0],
            "columns": shape[1],
            "bits_allocated": bits,
            "samples_per_pixel": shape[2],
        }

        native_runner = DecodeRunner(ExplicitVRLittleEndian)
        native_runner.set_options(**opts)
        encaps_runner = DecodeRunner(RLELossless)
        encaps_runner.set_options(**opts)

        assert length[0] == native_runner.frame_length(unit="bytes")
        assert length[1] == native_runner.frame_length(unit="pixels")
        assert length[0] == encaps_runner.frame_length(unit="bytes")
        assert length[1] == encaps_runner.frame_length(unit="pixels")

        if shape[2] == 3 and bits != 1:
            native_runner.set_option("photometric_interpretation", PI.YBR_FULL_422)
            encaps_runner.set_option("photometric_interpretation", PI.YBR_FULL_422)
            assert length[2] == native_runner.frame_length(unit="bytes")
            assert length[0] == encaps_runner.frame_length(unit="bytes")

    def test_option_properties(self):
        """Tests for properties derived from options."""
        runner = DecodeRunner(ExplicitVRLittleEndian)
        attrs = [
            "bits_allocated",
            "bits_stored",
            "columns",
            "photometric_interpretation",
            "pixel_representation",
            "rows",
            "samples_per_pixel",
        ]
        for attr in attrs:
            msg = f"No value for '{attr}' has been set"
            with pytest.raises(AttributeError, match=msg):
                getattr(runner, attr)

            runner.set_option(attr, 0)
            assert getattr(runner, attr) == 0
            assert runner.get_option(attr) == 0

            runner.del_option(attr)
            with pytest.raises(AttributeError, match=msg):
                getattr(runner, attr)

        # pixel_keyword not deletable
        msg = "No value for 'pixel_keyword' has been set"
        with pytest.raises(AttributeError, match=msg):
            runner.pixel_keyword

        runner.set_option("pixel_keyword", 0)
        assert runner.pixel_keyword == 0

        # number_of_frames defaults to 1 if 0 or None
        msg = "No value for 'number_of_frames' has been set"
        with pytest.raises(AttributeError, match=msg):
            runner.number_of_frames

        runner.set_option("number_of_frames", 0)
        assert runner.number_of_frames == 1
        runner.set_option("number_of_frames", None)
        assert runner.number_of_frames == 1
        assert runner.get_option("number_of_frames") == 1

        runner.del_option("number_of_frames")
        with pytest.raises(AttributeError, match=msg):
            runner.number_of_frames

        # extended_offsets defaults to None if not set
        assert runner.extended_offsets is None
        runner.set_option("extended_offsets", 0)
        assert runner.extended_offsets == 0

    def test_planar_configuration(self):
        """Tests for 'planar_configuration' option."""
        # planar_configuration required for native
        msg = "No value for 'planar_configuration' has been set"
        runner = DecodeRunner(ExplicitVRLittleEndian)
        with pytest.raises(AttributeError, match=msg):
            runner.planar_configuration

        runner.set_option("planar_configuration", 0)
        assert runner.planar_configuration == 0
        runner.set_option("planar_configuration", 1)
        assert runner.planar_configuration == 1
        runner.del_option("planar_configuration")
        with pytest.raises(AttributeError, match=msg):
            runner.planar_configuration

        # planar_configuration for encapsulated is 0 by default, otherwise set value
        runner = DecodeRunner(JPEGBaseline8Bit)
        assert runner.planar_configuration == 0
        runner.set_option("planar_configuration", 1)
        assert runner.planar_configuration == 1
        runner.set_option("planar_configuration", 0)
        assert runner.planar_configuration == 0
        runner.set_option("planar_configuration", 1)
        runner.del_option("planar_configuration")
        assert runner.planar_configuration == 0

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
        runner.set_source(ds)

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
        del ds.FloatPixelData
        ds.DoubleFloatPixelData = None
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

    def test_set_number_of_frames(self):
        """Test setting 'number_of_frames'"""
        runner = DecodeRunner(RLELossless)
        runner.set_option("number_of_frames", None)
        assert runner.number_of_frames == 1
        runner.set_option("number_of_frames", 0)
        assert runner.number_of_frames == 1
        runner.set_option("number_of_frames", 10)
        assert runner.number_of_frames == 10
        runner.set_option("number_of_frames", "0")
        assert runner.number_of_frames == 1
        runner.set_option("number_of_frames", "10")
        assert runner.number_of_frames == 10

    def test_set_photometric_interpretation(self):
        """Test setting 'photometric_interpretation'"""
        runner = DecodeRunner(RLELossless)
        # Known photometric interpretations converted to enum instance
        runner.set_option("photometric_interpretation", "RGB")
        assert runner.photometric_interpretation == "RGB"
        assert isinstance(runner.photometric_interpretation, PI)
        runner.set_option("photometric_interpretation", "PALETTE COLOR")
        assert runner.photometric_interpretation == "PALETTE COLOR"
        assert isinstance(runner.photometric_interpretation, PI)
        # Unknown kept as str
        runner.set_option("photometric_interpretation", "FOO")
        assert runner.photometric_interpretation == "FOO"
        assert not isinstance(runner.photometric_interpretation, PI)

    def test_options(self):
        """Test the options property returns a copy of the options."""
        runner = DecodeRunner(RLELossless)
        assert runner.options is runner._opts

    def test_str(self):
        """Test str(DecodeRunner)"""
        runner = DecodeRunner(RLELossless)
        runner.set_decoders({"foo": None})
        assert str(runner) == (
            "DecodeRunner for 'RLE Lossless'\n"
            "Options\n"
            "  transfer_syntax_uid: 1.2.840.10008.1.2.5\n"
            "  as_rgb: True\n"
            "  pixel_keyword: PixelData\n"
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
            "expected number for uncompressed data - check you have "
            "set the correct transfer syntax"
        )
        with pytest.warns(UserWarning, match=msg):
            runner.validate_buffer()

        # Unpadded
        runner.set_source(b"\x01\x02\x03")
        with pytest.warns(UserWarning, match=msg):
            runner.validate_buffer()

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
            runner.validate_buffer()

        # Actual length 5 is greater than expected 3  (padding 2)
        runner.set_source(b"\x00" * 5)
        msg = (
            "The pixel data is 5 bytes long, which indicates it "
            "contains 2 bytes of excess padding to be removed"
        )
        with pytest.warns(UserWarning, match=msg):
            runner.validate_buffer()

        # YBR_FULL_422 but has unsubsampled length
        # expected 18 // 3 * 2 = 12, actual 18
        runner.set_option("photometric_interpretation", "YBR_FULL_422")
        runner.set_option("rows", 2)
        runner.set_option("columns", 3)
        runner.set_source(b"\x00" * 18)

        msg = (
            "The number of bytes of pixel data is a third larger "
            r"than expected \(18 vs 12 bytes\) which indicates "
            "the set photometric interpretation 'YBR_FULL_422' is "
            "incorrect"
        )
        with pytest.raises(ValueError, match=msg):
            runner.validate_buffer()

    def test_validate_options(self):
        """Tests for validate_options()"""
        runner = DecodeRunner(ExplicitVRLittleEndian)

        msg = (
            "Missing expected options: bits_allocated, bits_stored, columns, "
            "number_of_frames, photometric_interpretation, pixel_keyword, rows, "
            "samples_per_pixel"
        )
        with pytest.raises(AttributeError, match=msg):
            runner.validate_options()

        runner.set_option("bits_allocated", -1)
        runner.set_option("bits_stored", -1)
        runner.set_option("columns", -1)
        runner.set_option("number_of_frames", -1)
        runner.set_option("photometric_interpretation", -1)
        runner.set_option("rows", -1)
        runner.set_option("pixel_keyword", -1)
        runner.set_option("samples_per_pixel", -1)
        runner.set_option("extended_offsets", ([1, 2], [1]))

        msg = (
            "A bits allocated value of '-1' is invalid, it must be in the "
            r"range \(1, 64\)"
        )
        with pytest.raises(ValueError, match=msg):
            runner.validate_options()

        runner.set_option("bits_allocated", 4)
        msg = (
            "A bits allocated value of '4' is invalid, it must be 1 or a multiple of 8"
        )
        with pytest.raises(ValueError, match=msg):
            runner.validate_options()

        runner.set_option("bits_allocated", 8)
        msg = (
            "A bits stored value of '-1' is invalid, it must be in the range "
            r"\(1, 64\) and no greater than the bits allocated value of 8"
        )
        with pytest.raises(ValueError, match=msg):
            runner.validate_options()

        runner.set_option("bits_stored", 10)
        msg = (
            "A bits stored value of '10' is invalid, it must be in the range "
            r"\(1, 64\) and no greater than the bits allocated value of 8"
        )
        with pytest.raises(ValueError, match=msg):
            runner.validate_options()

        runner.set_option("bits_stored", 8)
        msg = (
            r"A columns value of '-1' is invalid, it must be in the range \(1, 65535\)"
        )
        with pytest.raises(ValueError, match=msg):
            runner.validate_options()

        runner.set_option("columns", 8)
        msg = (
            "A number of frames value of '-1' is invalid, it must be greater "
            "than or equal to 1"
        )
        with pytest.raises(ValueError, match=msg):
            runner.validate_options()

        runner.set_option("number_of_frames", 8)
        msg = r"Unknown photometric interpretation '-1'"
        with pytest.raises(ValueError, match=msg):
            runner.validate_options()

        runner.set_option("photometric_interpretation", PI.RGB)
        msg = r"Unknown pixel data keyword '-1'"
        with pytest.raises(ValueError, match=msg):
            runner.validate_options()

        runner.set_option("pixel_keyword", "PixelData")
        msg = r"Missing expected option: pixel_representation"
        with pytest.raises(AttributeError, match=msg):
            runner.validate_options()

        runner.set_option("pixel_representation", -1)
        msg = "A pixel representation value of '-1' is invalid, it must be 0 or 1"
        with pytest.raises(ValueError, match=msg):
            runner.validate_options()

        runner.set_option("pixel_representation", 0)
        msg = r"A rows value of '-1' is invalid, it must be in the range \(1, 65535\)"
        with pytest.raises(ValueError, match=msg):
            runner.validate_options()

        runner.set_option("rows", 10)
        msg = "A samples per pixel value of '-1' is invalid, it must be 1 or 3"
        with pytest.raises(ValueError, match=msg):
            runner.validate_options()

        runner.set_option("samples_per_pixel", 3)
        msg = r"Missing expected option: planar_configuration"
        with pytest.raises(AttributeError, match=msg):
            runner.validate_options()

        runner.set_option("planar_configuration", -1)
        msg = "A planar configuration value of '-1' is invalid, it must be 0 or 1"
        with pytest.raises(ValueError, match=msg):
            runner.validate_options()

        runner.set_option("planar_configuration", 1)
        msg = r"There must be an equal number of extended offsets and offset lengths"
        with pytest.raises(ValueError, match=msg):
            runner.validate_options()

        runner.set_option("extended_offsets", ([0], [10]))

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
    def test_decode(self):
        """Test decode()"""
        runner = DecodeRunner(RLELossless)
        runner.set_source(RLE_16_1_10F.ds)

        msg = "Unable to decode as exceptions were raised by all available plugins"
        with pytest.raises(RuntimeError, match=msg):
            runner.decode(0)

        decoder = get_decoder(RLELossless)
        runner.set_decoders(decoder._validate_decoders("pydicom"))
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
        plugins = decoder._validate_decoders("pydicom")
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
        assert dec._validate_decoders() == {}

    def test_properties(self):
        """Test Decoder properties"""
        dec = Decoder(RLELossless)
        assert "RLELosslessDecoder" == dec.name
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

    def test_add_plugin(self):
        """Test add_plugin()"""
        dec = Decoder(RLELossless)
        dec.add_plugin("foo", ("pydicom.pixels.decoders.rle", "_decode_frame"))
        assert dec.is_available

        msg = "'RLELosslessDecoder' already has a plugin named 'foo'"
        with pytest.raises(ValueError, match=msg):
            dec.add_plugin("foo", ("pydicom.pixels.decoders.rle", "_decode_frame"))

    @pytest.mark.skipif(HAVE_NP, reason="Numpy is available")
    def test_add_plugin_unavailable(self):
        """Test adding an unavailable plugin."""
        dec = Decoder(ExplicitVRLittleEndian)
        dec.add_plugin("foo", ("pydicom.pixels.decoders.rle", "_decode_frame"))
        assert "foo" in dec._unavailable
        assert dec._unavailable["foo"] == (
            "Plugin 'foo' does not support 'Explicit VR Little Endian'"
        )
        dec.remove_plugin("foo")
        assert {} == dec._unavailable

    def test_add_plugin_module_import_failure(self):
        """Test a module import failure when adding a plugin."""
        dec = Decoder(RLELossless)

        msg = r"No module named 'badpath'"
        with pytest.raises(ModuleNotFoundError, match=msg):
            dec.add_plugin("foo", ("badpath", "_encode_frame"))
        assert {} == dec._available
        assert {} == dec._unavailable

    def test_add_plugin_function_missing(self):
        """Test decoding function missing when adding a plugin."""
        dec = Decoder(RLELossless)

        msg = (
            r"module 'pydicom.pixels.decoders.rle' has no attribute 'bad_function_name'"
        )
        with pytest.raises(AttributeError, match=msg):
            dec.add_plugin("foo", ("pydicom.pixels.decoders.rle", "bad_function_name"))
        assert {} == dec._available
        assert {} == dec._unavailable

    def test_remove_plugin(self):
        """Test removing a plugin."""
        dec = Decoder(RLELossless)
        dec.add_plugin("foo", ("pydicom.pixels.decoders.rle", "_decode_frame"))
        dec.add_plugin("bar", ("pydicom.pixels.decoders.rle", "_decode_frame"))
        assert "foo" in dec._available
        assert "bar" in dec._available
        assert {} == dec._unavailable
        assert dec.is_available

        dec.remove_plugin("foo")
        assert "bar" in dec._available
        assert dec.is_available

        dec.remove_plugin("bar")
        assert {} == dec._available
        assert not dec.is_available

        msg = r"Unable to remove 'foo', no such plugin"
        with pytest.raises(ValueError, match=msg):
            dec.remove_plugin("foo")

    def test_missing_dependencies(self):
        """Test the required decoder being unavailable."""
        dec = Decoder(RLELossless)

        dec._unavailable["foo"] = ()
        s = dec.missing_dependencies
        assert "foo - plugin indicating it is unavailable" == s[0]

        dec._unavailable["foo"] = ("bar",)
        s = dec.missing_dependencies
        assert "foo - requires bar" == s[0]

        dec._unavailable["foo"] = ("numpy", "pylibjpeg")
        s = dec.missing_dependencies
        assert "foo - requires numpy and pylibjpeg" == s[0]

    def test_validate_decoders(self):
        """Tests for _validate_decoders()"""
        dec = Decoder(ExplicitVRLittleEndian)
        assert dec._validate_decoders() == {}

        dec = Decoder(RLELossless)

        msg = (
            "Unable to decode because the decoding plugins are all missing "
            "dependencies:"
        )
        with pytest.raises(RuntimeError, match=msg):
            dec._validate_decoders()

        msg = (
            "No decoding plugin named 'foo' has been added to the 'RLELosslessDecoder'"
        )
        with pytest.raises(ValueError, match=msg):
            dec._validate_decoders("foo")

        dec._available["foo"] = 0
        assert dec._validate_decoders() == {"foo": 0}
        assert dec._validate_decoders("foo") == {"foo": 0}

        dec._available = {}
        dec._unavailable["foo"] = ("numpy", "pylibjpeg", "gdcm")
        msg = (
            "Unable to decode with the 'foo' decoding plugin because it's missing "
            "dependencies - requires numpy, pylibjpeg and gdcm"
        )
        with pytest.raises(RuntimeError, match=msg):
            dec._validate_decoders("foo")

    def test_buffer(self):
        """Test as_buffer() and iter_buffer()"""
        # Functionality test that numpy isn't required
        decoder = get_decoder(RLELossless)
        reference = RLE_16_1_10F
        buffer = decoder.as_buffer(reference.ds)
        assert isinstance(buffer, bytes | bytearray)
        for buffer in decoder.iter_buffer(reference.ds):
            assert isinstance(buffer, bytes | bytearray)


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
            arr = decoder.as_array(reference.ds, index=index)
            reference.test(arr, index=index)
            assert arr.shape == reference.shape[1:]
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

    def test_native_view_only(self):
        """Test as_array(view_only=True)"""
        decoder = get_decoder(ExplicitVRLittleEndian)

        # Also tests Dataset `src`
        reference = EXPL_8_3_1F_YBR
        arr = decoder.as_array(reference.ds, view_only=True, raw=True)
        assert isinstance(reference.ds.PixelData, bytes)  # immutable
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert not arr.flags.writeable  # read-only

        # Also tests buffer-like `src`
        ds = reference.ds
        arr = decoder.as_array(
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
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable  # not read-only

        arr = decoder.as_array(
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
        )
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert not arr.flags.writeable  # read-only

        arr = decoder.as_array(
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
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable  # not read-only

    def test_encapsulated_index(self):
        """Test `index` with an encapsulated pixel data."""
        decoder = get_decoder(RLELossless)

        reference = RLE_16_1_10F
        for index in [0, 4, 9]:
            arr = decoder.as_array(reference.ds, index=index, decoding_plugin="pydicom")
            reference.test(arr, index=index)
            assert arr.shape == reference.shape[1:]
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

    def test_encapsulated_plugin(self):
        """Test `decoding_plugin` with an encapsulated pixel data."""
        decoder = get_decoder(RLELossless)

        reference = RLE_16_1_10F
        arr = decoder.as_array(reference.ds, decoding_plugin="pydicom")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

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
            "More frames have been found in the encapsulated pixel data than "
            "expected from the supplied number of frames"
        )
        with pytest.warns(UserWarning, match=msg):
            arr = decoder.as_array(src, **runner.options)

        assert arr.shape == (11, 64, 64)

    def test_processing_colorspace(self):
        """Test the processing colorspace options."""
        decoder = get_decoder(ExplicitVRLittleEndian)

        reference = EXPL_8_3_1F_YBR

        msg = "'force_ybr' and 'force_rgb' cannot both be True"
        with pytest.raises(ValueError, match=msg):
            decoder.as_array(reference.ds, force_rgb=True, force_ybr=True)

        # as_rgb (default)
        arr = decoder.as_array(reference.ds)
        reference.test(arr, as_rgb=True)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        # force_rgb
        rgb = decoder.as_array(
            reference.ds,
            photometric_interpretation="RGB",
            force_rgb=True,
        )
        reference.test(rgb, as_rgb=True)

        # force_ybr
        # Test ignores as_rgb
        ybr = decoder.as_array(reference.ds, as_rgb=False, force_ybr=True)
        ybr2 = decoder.as_array(reference.ds, as_rgb=True, force_ybr=True)
        assert np.array_equal(ybr, ybr2)

        # Test is actually ybr + ybr = ybr`
        raw = decoder.as_array(reference.ds, raw=True)
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

    def test_expb_ow_index_invalid_raises(self, caplog):
        """Test invalid index with BE swapped OW raises"""
        decoder = get_decoder(ExplicitVRBigEndian)
        reference = EXPB_8_1_1F
        msg = "There is insufficient pixel data to contain 2 frames"
        with pytest.raises(ValueError, match=msg):
            decoder.as_array(reference.ds, index=1)

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
        arr = decoder.as_array(src, **opts, index=0)
        assert arr.ravel().tolist() == [0, 1, 2, 3, 4, 5, 6, 7, 8]
        arr = decoder.as_array(src, **opts, index=1)
        assert arr.ravel().tolist() == [9, 10, 11, 12, 13, 14, 15, 16, 17]
        arr = decoder.as_array(src, **opts, index=2)
        assert arr.ravel().tolist() == [18, 19, 20, 21, 22, 23, 24, 25, 26]

    def test_iter_native_indices(self):
        """Test the `indices` argument with native data."""
        decoder = get_decoder(ExplicitVRLittleEndian)
        reference = EXPL_16_1_10F

        indices = [0, 4, 9]
        func = decoder.iter_array(reference.ds, raw=True, indices=indices)
        for idx, arr in enumerate(func):
            reference.test(arr, index=indices[idx])
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable
            assert arr.shape == reference.shape[1:]

        assert idx == 2

    def test_iter_native_view_only(self):
        """Test as_array(view_only=True)"""
        decoder = get_decoder(ExplicitVRLittleEndian)
        reference = EXPL_16_1_10F
        ds = reference.ds

        assert isinstance(ds.PixelData, bytes)  # immutable
        func = decoder.iter_array(ds, view_only=True, raw=True)
        for index, arr in enumerate(func):
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
        for index, arr in enumerate(func):
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
        )
        for index, arr in enumerate(func):
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
        for index, arr in enumerate(func):
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
        for idx, arr in enumerate(func):
            reference.test(arr, index=indices[idx])
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable
            assert arr.shape == reference.shape[1:]

        assert idx == 2

    def test_iter_encapsulated_plugin(self):
        """Test `decoding_plugin` with an encapsulated pixel data."""
        decoder = get_decoder(RLELossless)

        reference = RLE_16_1_10F
        func = decoder.iter_array(reference.ds, decoding_plugin="pydicom")
        for index, arr in enumerate(func):
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable
            assert arr.shape == reference.shape[1:]

    def test_iter_processing(self):
        """Test the processing options."""
        decoder = get_decoder(ExplicitVRLittleEndian)

        reference = EXPL_8_3_1F_YBR

        msg = "'force_ybr' and 'force_rgb' cannot both be True"
        with pytest.raises(ValueError, match=msg):
            next(decoder.iter_array(reference.ds, force_rgb=True, force_ybr=True))

        # as_rgb
        func = decoder.iter_array(reference.ds)
        arr = next(func)
        reference.test(arr, as_rgb=True)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        # force_rgb
        func = decoder.iter_array(
            reference.ds,
            photometric_interpretation="RGB",
            force_rgb=True,
        )
        rgb = next(func)
        reference.test(rgb, as_rgb=True)

        # force_ybr
        # Test ignores as_rgb
        ybr = next(decoder.iter_array(reference.ds, as_rgb=False, force_ybr=True))
        ybr2 = next(decoder.iter_array(reference.ds, as_rgb=True, force_ybr=True))
        assert np.array_equal(ybr, ybr2)

        # Test is actually ybr + ybr = ybr`
        raw = next(decoder.iter_array(reference.ds, raw=True))
        out = convert_color_space(ybr, PI.YBR_FULL, PI.RGB)
        # Lossy conversion, equal to within 1 intensity unit
        assert np.allclose(out, raw, atol=1)


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
class TestDecoder_Buffer:
    """Tests for Decoder.as_buffer() and Decoder.iter_buffer()."""

    def test_native_index(self):
        """Test `index`"""
        decoder = get_decoder(ExplicitVRLittleEndian)

        assert decoder.is_available

        reference = EXPL_16_1_10F
        for index in [0, 4, 9]:
            arr = decoder.as_array(reference.ds, index=index)
            buffer = decoder.as_buffer(reference.ds, index=index)
            assert arr.tobytes() == buffer

        msg = "There is insufficient pixel data to contain 11 frames"
        with pytest.raises(ValueError, match=msg):
            decoder.as_buffer(reference.ds, index=10)

    def test_native_view_only(self):
        """Test `view_only`"""
        decoder = get_decoder(ExplicitVRLittleEndian)

        # immutable source buffer
        # Also tests Dataset `src`
        reference = EXPL_8_3_1F_YBR
        arr = decoder.as_array(reference.ds, view_only=True, raw=True)
        buffer = decoder.as_buffer(reference.ds, view_only=True, raw=True)
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
        arr = decoder.as_array(src, **opts)
        buffer = decoder.as_buffer(src, **opts)
        assert isinstance(buffer, memoryview)
        assert arr.tobytes() == buffer
        assert buffer.obj is src

        # view of a mutable
        mview = memoryview(src)
        arr = decoder.as_array(mview, **opts)
        buffer = decoder.as_buffer(mview, **opts)
        assert isinstance(buffer, memoryview)
        assert arr.tobytes() == buffer
        assert buffer.obj is src

        # view of an immutable
        src = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08"
        mview = memoryview(src)
        arr = decoder.as_array(mview, **opts)
        buffer = decoder.as_buffer(mview, **opts)
        assert isinstance(buffer, memoryview)
        assert arr.tobytes() == buffer
        assert buffer.obj is src

    def test_encapsulated_index(self):
        """Test `index` with an encapsulated pixel data."""
        decoder = get_decoder(RLELossless)

        reference = RLE_16_1_10F
        for index in [0, 4, 9]:
            arr = decoder.as_array(reference.ds, index=index)
            buffer = decoder.as_buffer(reference.ds, index=index)
            assert isinstance(buffer, bytes | bytearray)
            assert arr.tobytes() == buffer

    def test_encapsulated_plugin(self):
        """Test `decoding_plugin` with an encapsulated pixel data."""
        decoder = get_decoder(RLELossless)
        reference = RLE_16_1_10F
        arr = decoder.as_array(reference.ds, decoding_plugin="pydicom")
        buffer = decoder.as_buffer(reference.ds, decoding_plugin="pydicom")
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
            "More frames have been found in the encapsulated pixel data than "
            "expected from the supplied number of frames"
        )
        with pytest.warns(UserWarning, match=msg):
            buffer = decoder.as_buffer(src, **runner.options)

        assert len(buffer) == 11 * 64 * 64 * 2

    def test_expb_ow_index_invalid_raises(self, caplog):
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
        buffer = decoder.as_buffer(src, **opts, index=0)
        assert buffer == b"\x01\x00\x03\x02\x05\x04\x07\x06\x09\x08"
        # Includes -1 at start
        buffer = decoder.as_buffer(src, **opts, index=1)
        assert buffer == b"\x09\x08\x0B\x0A\x0D\x0C\x0F\x0E\x11\x10"
        # Includes +1 at end
        buffer = decoder.as_buffer(src, **opts, index=2)
        assert buffer == b"\x13\x12\x15\x14\x17\x16\x19\x18\x00\x1A"

    def test_iter_native_indices(self):
        """Test `index`"""
        decoder = get_decoder(ExplicitVRLittleEndian)
        reference = EXPL_16_1_10F

        indices = [0, 4, 9]
        arr_func = decoder.iter_array(reference.ds, indices=indices)
        buf_func = decoder.iter_buffer(reference.ds, indices=indices)
        for idx, (arr, buffer) in enumerate(zip(arr_func, buf_func)):
            assert isinstance(buffer, bytes | bytearray)
            assert arr.tobytes() == buffer

        assert idx == 2

    def test_iter_native_view_only(self):
        """Test `view_only`"""
        decoder = get_decoder(ExplicitVRLittleEndian)

        # immutable source buffer
        # Also tests Dataset `src`
        reference = EXPL_8_3_1F_YBR
        arr = next(decoder.iter_array(reference.ds, view_only=True, raw=True))
        buffer = next(decoder.iter_buffer(reference.ds, view_only=True, raw=True))
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
        arr = next(decoder.iter_array(src, **opts))
        buffer = next(decoder.iter_buffer(src, **opts))
        assert isinstance(buffer, memoryview)
        assert arr.tobytes() == buffer
        assert buffer.obj is src

        # view of a mutable
        mview = memoryview(src)
        arr = next(decoder.iter_array(mview, **opts))
        buffer = next(decoder.iter_buffer(mview, **opts))
        assert isinstance(buffer, memoryview)
        assert arr.tobytes() == buffer
        assert buffer.obj is src

        # view of an immutable
        src = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08"
        mview = memoryview(src)
        arr = next(decoder.iter_array(mview, **opts))
        buffer = next(decoder.iter_buffer(mview, **opts))
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
        for idx, (arr, buffer) in enumerate(zip(arr_func, buf_func)):
            assert isinstance(buffer, bytes | bytearray)
            assert arr.tobytes() == buffer

    def test_iter_encapsulated_plugin(self):
        """Test `decoding_plugin` with an encapsulated pixel data."""
        decoder = get_decoder(RLELossless)
        reference = RLE_16_1_10F
        arr = next(decoder.iter_array(reference.ds, decoding_plugin="pydicom"))
        buffer = next(decoder.iter_buffer(reference.ds, decoding_plugin="pydicom"))
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
