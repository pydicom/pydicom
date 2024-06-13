"""Tests for pydicom.pixels.common."""

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom import dcmread
from pydicom.pixels.common import CoderBase, RunnerBase, PhotometricInterpretation as PI
from pydicom.uid import (
    RLELossless,
    ExplicitVRLittleEndian,
    JPEGBaseline8Bit,
    JPEGLSLossless,
)

from .pixels_reference import RLE_16_1_10F, EXPL_8_3_1F_YBR


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


class TestRunnerBase:
    """Tests for RunnerBase"""

    def test_init(self):
        """Test initial creation."""
        runner = RunnerBase(RLELossless)
        assert runner.transfer_syntax == RLELossless
        assert runner.options == {"transfer_syntax_uid": RLELossless}
        assert runner._src_type == "UNDEFINED"

    def test_del_option(self):
        """Test for del_option()"""
        runner = RunnerBase(RLELossless)

        msg = "Deleting 'transfer_syntax_uid' is not allowed"
        with pytest.raises(ValueError, match=msg):
            runner.del_option("transfer_syntax_uid")

        # No exception if deleting non-existent option
        assert runner.get_option("foo") is None
        runner.del_option("foo")

        runner.set_option("as_rgb", True)
        assert runner.get_option("as_rgb") is not None
        runner.del_option("as_rgb")
        assert runner.get_option("as_rgb") is None

    def test_option_properties(self):
        """Tests for properties derived from options."""
        runner = RunnerBase(ExplicitVRLittleEndian)
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

        msg = r"A value of '0' for \(0028,0008\) 'Number of Frames' is invalid"
        with pytest.warns(UserWarning, match=msg):
            runner.set_option("number_of_frames", 0)

        assert runner.number_of_frames == 1

        msg = r"A value of 'None' for \(0028,0008\) 'Number of Frames' is invalid"
        with pytest.warns(UserWarning, match=msg):
            runner.set_option("number_of_frames", None)

        assert runner.number_of_frames == 1
        assert runner.get_option("number_of_frames") == 1

        runner.del_option("number_of_frames")
        msg = "No value for 'number_of_frames' has been set"
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
        runner = RunnerBase(ExplicitVRLittleEndian)
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
        runner = RunnerBase(JPEGBaseline8Bit)
        assert runner.planar_configuration == 0
        runner.set_option("planar_configuration", 1)
        assert runner.planar_configuration == 1
        runner.set_option("planar_configuration", 0)
        assert runner.planar_configuration == 0
        runner.set_option("planar_configuration", 1)
        runner.del_option("planar_configuration")
        assert runner.planar_configuration == 0

    def test_set_number_of_frames(self):
        """Test setting 'number_of_frames'"""
        runner = RunnerBase(RLELossless)
        msg = r"A value of 'None' for \(0028,0008\) 'Number of Frames' is invalid"
        with pytest.warns(UserWarning, match=msg):
            runner.set_option("number_of_frames", None)

        assert runner.number_of_frames == 1

        msg = r"A value of '0' for \(0028,0008\) 'Number of Frames' is invalid"
        with pytest.warns(UserWarning, match=msg):
            runner.set_option("number_of_frames", 0)

        assert runner.number_of_frames == 1
        runner.set_option("number_of_frames", 10)
        assert runner.number_of_frames == 10
        with pytest.warns(UserWarning, match=msg):
            runner.set_option("number_of_frames", "0")

        assert runner.number_of_frames == 1
        runner.set_option("number_of_frames", "10")
        assert runner.number_of_frames == 10

    def test_set_photometric_interpretation(self):
        """Test setting 'photometric_interpretation'"""
        runner = RunnerBase(RLELossless)
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
        runner = RunnerBase(RLELossless)
        assert runner.options is runner._opts

    def test_validate_options(self):
        """Tests for validate_options()"""
        # Generic option validation
        runner = RunnerBase(ExplicitVRLittleEndian)

        msg = r"Missing required element: \(0028,0100\) 'Bits Allocated'"
        with pytest.raises(AttributeError, match=msg):
            runner._validate_options()

        runner.set_option("bits_allocated", -1)
        msg = (
            r"A \(0028,0100\) 'Bits Allocated' value of '-1' is invalid, it "
            r"must be 1 or a multiple of 8 and in the range \(1, 64\)"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_options()

        runner.set_option("bits_allocated", 4)
        msg = (
            r"A \(0028,0100\) 'Bits Allocated' value of '4' is invalid, it "
            r"must be 1 or a multiple of 8 and in the range \(1, 64\)"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_options()

        runner.set_option("bits_allocated", 8)
        msg = r"Missing required element: \(0028,0101\) 'Bits Stored'"
        with pytest.raises(AttributeError, match=msg):
            runner._validate_options()

        runner.set_option("bits_stored", -1)
        msg = (
            r"A \(0028,0101\) 'Bits Stored' value of '-1' is invalid, it must "
            r"be in the range \(1, 64\) and no greater than the \(0028,0100\) "
            "'Bits Allocated' value of '8'"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_options()

        runner.set_option("bits_stored", 10)
        msg = (
            r"A \(0028,0101\) 'Bits Stored' value of '10' is invalid, it must "
            r"be in the range \(1, 64\) and no greater than the \(0028,0100\) "
            "'Bits Allocated' value of '8'"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_options()

        runner.set_option("bits_stored", 8)
        msg = r"Missing required element: \(0028,0011\) 'Columns'"
        with pytest.raises(AttributeError, match=msg):
            runner._validate_options()

        runner.set_option("columns", -1)
        msg = (
            r"A \(0028,0011\) 'Columns' value of '-1' is invalid, it must be "
            r"in the range \(1, 65535\)"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_options()

        runner.set_option("columns", 8)
        msg = r"Missing required element: \(0028,0004\) 'Photometric Interpretation'"
        with pytest.raises(AttributeError, match=msg):
            runner._validate_options()

        runner.set_option("photometric_interpretation", -1)
        msg = r"\(0028,0004\) 'Photometric Interpretation' value '-1'"
        with pytest.raises(ValueError, match=msg):
            runner._validate_options()

        runner.set_option("photometric_interpretation", PI.RGB)
        msg = "No value for 'pixel_keyword' has been set"
        with pytest.raises(AttributeError, match=msg):
            runner._validate_options()

        runner.set_option("pixel_keyword", -1)
        msg = "Unknown 'pixel_keyword' value '-1'"
        with pytest.raises(ValueError, match=msg):
            runner._validate_options()

        runner.set_option("pixel_keyword", "PixelData")
        msg = r"Missing required element: \(0028,0103\) 'Pixel Representation'"
        with pytest.raises(AttributeError, match=msg):
            runner._validate_options()

        runner.set_option("pixel_representation", -1)
        msg = (
            r"A \(0028,0103\) 'Pixel Representation' value of '-1' is invalid, "
            "it must be 0 or 1"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_options()

        runner.set_option("pixel_representation", 0)
        msg = r"Missing required element: \(0028,0010\) 'Rows'"
        with pytest.raises(AttributeError, match=msg):
            runner._validate_options()

        runner.set_option("rows", -1)
        msg = (
            r"A \(0028,0010\) 'Rows' value of '-1' is invalid, it must be "
            r"in the range \(1, 65535\)"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_options()

        runner.set_option("rows", 10)
        msg = r"Missing required element: \(0028,0002\) 'Samples per Pixel'"
        with pytest.raises(AttributeError, match=msg):
            runner._validate_options()

        runner.set_option("samples_per_pixel", -1)
        msg = (
            r"A \(0028,0002\) 'Samples per Pixel' value of '-1' is invalid, it "
            "must be 1 or 3"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_options()

        runner.set_option("samples_per_pixel", 3)
        msg = r"Missing required element: \(0028,0006\) 'Planar Configuration'"
        with pytest.raises(AttributeError, match=msg):
            runner._validate_options()

        runner.set_option("planar_configuration", -1)
        msg = (
            r"A \(0028,0006\) 'Planar Configuration' value of '-1' is invalid, "
            "it must be 0 or 1"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_options()

        runner.set_option("planar_configuration", 1)

        # Number of Frames may be conditionally absent
        runner.set_option("number_of_frames", -1)
        msg = (
            r"A \(0028,0008\) 'Number of Frames' value of '-1' is invalid, it "
            "must be greater than or equal to 1"
        )
        with pytest.raises(ValueError, match=msg):
            runner._validate_options()

    def test_validate_raises(self):
        """Test validate() raises exception."""
        runner = RunnerBase(RLELossless)
        msg = r"RunnerBase.validate\(\) has not been implemented"
        with pytest.raises(NotImplementedError, match=msg):
            runner.validate()

    def test_set_options_ds(self):
        """Test _set_options_ds()"""
        ds = RLE_16_1_10F.ds
        runner = RunnerBase(RLELossless)
        runner._set_options_ds(ds)
        assert runner.samples_per_pixel == ds.SamplesPerPixel
        assert runner.photometric_interpretation == ds.PhotometricInterpretation
        assert runner.number_of_frames == ds.NumberOfFrames
        assert runner.rows == ds.Rows
        assert runner.columns == ds.Columns
        assert runner.bits_allocated == ds.BitsAllocated
        assert runner.bits_stored == ds.BitsStored
        assert runner.pixel_representation == ds.PixelRepresentation

        ds = EXPL_8_3_1F_YBR.ds
        assert "NumberOfFrames" not in ds
        runner = RunnerBase(RLELossless)
        runner._set_options_ds(ds)
        assert runner.samples_per_pixel == ds.SamplesPerPixel
        assert runner.photometric_interpretation == ds.PhotometricInterpretation
        assert runner.number_of_frames == 1
        assert runner.rows == ds.Rows
        assert runner.columns == ds.Columns
        assert runner.bits_allocated == ds.BitsAllocated
        assert runner.bits_stored == ds.BitsStored
        assert runner.pixel_representation == ds.PixelRepresentation
        assert runner.planar_configuration == ds.PlanarConfiguration

        ds = dcmread(RLE_16_1_10F.path)
        ds.ExtendedOffsetTable = b"\x00\x01\x02\x03"
        ds.ExtendedOffsetTableLengths = b"\x00\x01\x02\x04"
        runner = RunnerBase(RLELossless)
        runner._set_options_ds(ds)
        assert runner.extended_offsets == (b"\x00\x01\x02\x03", b"\x00\x01\x02\x04")

    def test_src_type_properties(self):
        """Test is_array, is_binary, is_buffer and is_dataset"""
        runner = RunnerBase(RLELossless)
        runner._src_type = "BinaryIO"
        assert runner.is_binary
        assert not runner.is_buffer
        assert not runner.is_dataset
        assert not runner.is_array

        runner._src_type = "Buffer"
        assert not runner.is_binary
        assert runner.is_buffer
        assert not runner.is_dataset
        assert not runner.is_array

        runner._src_type = "Dataset"
        assert not runner.is_binary
        assert not runner.is_buffer
        assert runner.is_dataset
        assert not runner.is_array

        runner._src_type = "Array"
        assert not runner.is_binary
        assert not runner.is_buffer
        assert not runner.is_dataset
        assert runner.is_array

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

        native_runner = RunnerBase(ExplicitVRLittleEndian)
        native_runner.set_options(**opts)
        encaps_runner = RunnerBase(RLELossless)
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


class TestCoderBase:
    """Tests for CoderBase"""

    def test_init(self):
        """Test creating a new CoderBase"""
        coder = CoderBase(ExplicitVRLittleEndian, decoder=True)
        assert coder.UID == ExplicitVRLittleEndian
        assert not coder.is_encapsulated
        assert coder.is_native
        assert {} == coder._available
        assert {} == coder._unavailable
        assert coder.missing_dependencies == []
        assert coder._validate_plugins() == {}

    def test_add_plugin(self):
        """Test add_plugin()"""
        coder = CoderBase(RLELossless, decoder=True)
        coder.add_plugin("foo", ("pydicom.pixels.decoders.rle", "_decode_frame"))
        assert coder.is_available

        msg = "'CoderBase' already has a plugin named 'foo'"
        with pytest.raises(ValueError, match=msg):
            coder.add_plugin("foo", ("pydicom.pixels.decoders.rle", "_decode_frame"))

        coder = CoderBase(RLELossless, decoder=False)
        coder.add_plugin("foo", ("pydicom.pixels.decoders.rle", "_decode_frame"))
        assert coder.is_available

        msg = "'CoderBase' already has a plugin named 'foo'"
        with pytest.raises(ValueError, match=msg):
            coder.add_plugin("foo", ("pydicom.pixels.decoders.rle", "_decode_frame"))

    @pytest.mark.skipif(HAVE_NP, reason="Numpy is available")
    def test_add_plugin_unavailable(self):
        """Test adding an unavailable plugin."""
        coder = CoderBase(ExplicitVRLittleEndian, decoder=True)
        # UID isn't supported by decoder
        msg = "The 'foo' plugin doesn't support 'Explicit VR Little Endian'"
        with pytest.raises(ValueError, match=msg):
            coder.add_plugin("foo", ("pydicom.pixels.decoders.rle", "_decode_frame"))

        # UID is supported but dependencies not met
        coder = CoderBase(JPEGLSLossless, decoder=True)
        coder.add_plugin("foo", ("pydicom.pixels.decoders.pylibjpeg", "_decode_frame"))
        assert "foo" not in coder._available
        assert "foo" in coder._unavailable
        coder.remove_plugin("foo")
        assert {} == coder._unavailable

        # UID isn't supported by encoder
        coder = CoderBase(ExplicitVRLittleEndian, decoder=False)
        with pytest.raises(ValueError, match=msg):
            coder.add_plugin(
                "foo", ("pydicom.pixels.encoders.pyjpegls", "_encode_frame")
            )

        # UID is supported but dependencies not met
        coder = CoderBase(JPEGLSLossless, decoder=False)
        coder.add_plugin("foo", ("pydicom.pixels.encoders.pyjpegls", "_encode_frame"))
        assert "foo" not in coder._available
        assert "foo" in coder._unavailable
        coder.remove_plugin("foo")
        assert {} == coder._unavailable

    def test_add_plugin_module_import_failure(self):
        """Test a module import failure when adding a plugin."""
        coder = CoderBase(RLELossless, decoder=True)
        msg = r"No module named 'badpath'"
        with pytest.raises(ModuleNotFoundError, match=msg):
            coder.add_plugin("foo", ("badpath", "_encode_frame"))
        assert {} == coder._available
        assert {} == coder._unavailable

    def test_add_plugin_function_missing(self):
        """Test decoding function missing when adding a plugin."""
        coder = CoderBase(RLELossless, decoder=True)
        msg = (
            r"module 'pydicom.pixels.decoders.rle' has no attribute 'bad_function_name'"
        )
        with pytest.raises(AttributeError, match=msg):
            coder.add_plugin(
                "foo", ("pydicom.pixels.decoders.rle", "bad_function_name")
            )
        assert {} == coder._available
        assert {} == coder._unavailable

    def test_remove_plugin(self):
        """Test removing a plugin."""
        coder = CoderBase(RLELossless, decoder=True)
        coder.add_plugin("foo", ("pydicom.pixels.decoders.rle", "_decode_frame"))
        coder.add_plugin("bar", ("pydicom.pixels.decoders.rle", "_decode_frame"))
        assert "foo" in coder._available
        assert "bar" in coder._available
        assert {} == coder._unavailable
        assert coder.is_available

        coder.remove_plugin("foo")
        assert "bar" in coder._available
        assert coder.is_available

        coder.remove_plugin("bar")
        assert {} == coder._available
        assert not coder.is_available

        msg = r"Unable to remove 'foo', no such plugin"
        with pytest.raises(ValueError, match=msg):
            coder.remove_plugin("foo")

    def test_missing_dependencies(self):
        """Test the required decoder being unavailable."""
        coder = CoderBase(RLELossless, decoder=True)

        coder._unavailable["foo"] = ()
        s = coder.missing_dependencies
        assert "foo - plugin indicating it is unavailable" == s[0]

        coder._unavailable["foo"] = ("bar",)
        s = coder.missing_dependencies
        assert "foo - requires bar" == s[0]

        coder._unavailable["foo"] = ("numpy", "pylibjpeg")
        s = coder.missing_dependencies
        assert "foo - requires numpy and pylibjpeg" == s[0]

    def test_validate_plugins(self):
        """Tests for _validate_plugins()"""
        coder = CoderBase(ExplicitVRLittleEndian, decoder=True)
        assert coder._validate_plugins() == {}

        coder = CoderBase(RLELossless, decoder=True)
        msg = (
            "Unable to decompress 'RLE Lossless' pixel data because all plugins "
            "are missing dependencies:"
        )
        with pytest.raises(RuntimeError, match=msg):
            coder._validate_plugins()

        msg = "No plugin named 'foo' has been added to 'RLELosslessCoderBase'"
        with pytest.raises(ValueError, match=msg):
            coder._validate_plugins("foo")

        coder._available["foo"] = 0
        assert coder._validate_plugins() == {"foo": 0}
        assert coder._validate_plugins("foo") == {"foo": 0}

        coder._available = {}
        coder._unavailable["foo"] = ("numpy", "pylibjpeg", "gdcm")
        msg = (
            "Unable to decompress 'RLE Lossless' pixel data because the specified "
            "plugin is missing dependencies:\n\tfoo - requires numpy, pylibjpeg and gdcm"
        )
        with pytest.raises(RuntimeError, match=msg):
            coder._validate_plugins("foo")
