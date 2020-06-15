# Copyright 2020 pydicom authors. See LICENSE file for details.
"""Tests for the pixel_data_handlers.pylibjpeg_handler module."""

import pytest

import pydicom
from pydicom.data import get_testdata_file
from pydicom.encaps import defragment_data
from pydicom.filereader import dcmread
from pydicom.pixel_data_handlers.util import convert_color_space
from pydicom.tests._handler_common import ALL_TRANSFER_SYNTAXES
from pydicom.uid import (
    ImplicitVRLittleEndian,
    JPEGBaseline,
    JPEGExtended,
    JPEGLosslessP14,
    JPEGLossless,
    JPEGLSLossless,
    JPEGLSLossy,
    JPEG2000Lossless,
    JPEG2000
)

try:
    import numpy as np
    from pydicom.pixel_data_handlers import numpy_handler as NP_HANDLER
    HAVE_NP = True
except ImportError:
    NP_HANDLER = None
    HAVE_NP = False

try:
    from pydicom.pixel_data_handlers import pylibjpeg_handler as LJ_HANDLER
    from pydicom.pixel_data_handlers.pylibjpeg_handler import (
        get_pixeldata, as_array, generate_frames
    )
    HAVE_PYLIBJPEG = LJ_HANDLER.HAVE_PYLIBJPEG
    HAVE_LJ = LJ_HANDLER.HAVE_LIBJPEG
    HAVE_OJ = LJ_HANDLER.HAVE_OPENJPEG
except ImportError:
    LJ_HANDLER = None
    HAVE_PYLIBJPEG = False
    HAVE_LJ = False
    HAVE_OJ = False


TEST_HANDLER = HAVE_NP and HAVE_PYLIBJPEG  # Run handler tests
TEST_JPEG = TEST_HANDLER and HAVE_LJ  # Run 10918 JPEG tests
TEST_JPEGLS = TEST_HANDLER and HAVE_LJ  # Run 14495 JPEG-LS tests
TEST_JPEG2K = TEST_HANDLER and HAVE_OJ  # Run 15444 JPEG 2000 tests


SUPPORTED_SYNTAXES = [
    JPEGBaseline,
    JPEGExtended,
    JPEGLosslessP14,
    JPEGLossless,
    JPEGLSLossless,
    JPEGLSLossy,
    JPEG2000Lossless,
    JPEG2000
]
UNSUPPORTED_SYNTAXES = list(
    set(ALL_TRANSFER_SYNTAXES) ^ set(SUPPORTED_SYNTAXES)
)

# Transfer syntaxes supported by other handlers
IMPL = get_testdata_file("MR_small_implicit.dcm")
EXPL = get_testdata_file("OBXXXX1A.dcm")
EXPB = get_testdata_file("OBXXXX1A_expb.dcm")
DEFL = get_testdata_file("image_dfl.dcm")
RLE = get_testdata_file("MR_small_RLE.dcm")

REFERENCE_DATA_UNSUPPORTED = [
    (IMPL, ('1.2.840.10008.1.2', 'CompressedSamples^MR1')),
    (EXPL, ('1.2.840.10008.1.2.1', 'OB^^^^')),
    (EXPB, ('1.2.840.10008.1.2.2', 'OB^^^^')),
    (DEFL, ('1.2.840.10008.1.2.1.99', '^^^^')),
    (RLE, ('1.2.840.10008.1.2.5', 'CompressedSamples^MR1')),
]


def test_unsupported_syntaxes():
    """Test that UNSUPPORTED_SYNTAXES is as expected."""
    for syntax in SUPPORTED_SYNTAXES:
        assert syntax not in UNSUPPORTED_SYNTAXES


@pytest.mark.skipif(not HAVE_PYLIBJPEG, reason='pylibjpeg not available')
class TestHandler:
    """Tests for handling Pixel Data with the handler."""
    def setup(self):
        """Setup the test datasets and the environment."""
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [NP_HANDLER, LJ_HANDLER]

    def teardown(self):
        """Restore the environment."""
        pydicom.config.pixel_data_handlers = self.original_handlers

    def test_environment(self):
        """Check that the testing environment is as expected."""
        assert HAVE_NP
        assert HAVE_PYLIBJPEG
        assert LJ_HANDLER is not None

    def test_unsupported_syntax_raises(self):
        """Test pixel_array raises exception for unsupported syntaxes."""
        pydicom.config.pixel_data_handlers = [LJ_HANDLER]

        ds = dcmread(EXPL)
        for uid in UNSUPPORTED_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            with pytest.raises((NotImplementedError, RuntimeError)):
                ds.pixel_array


@pytest.mark.skipif(not TEST_JPEG, reason="no -libjpeg plugin")
class TestJPEG:
    def setup(self):
        """Setup the test datasets and the environment."""
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [NP_HANDLER, LJ_HANDLER]

    def teardown(self):
        """Restore the environment."""
        pydicom.config.pixel_data_handlers = self.original_handlers


@pytest.mark.skipif(not TEST_JPEGLS, reason="no -libjpeg plugin")
class TestJPEGLS:
    def setup(self):
        """Setup the test datasets and the environment."""
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [NP_HANDLER, LJ_HANDLER]

    def teardown(self):
        """Restore the environment."""
        pydicom.config.pixel_data_handlers = self.original_handlers


# JPEG 2000 - ISO/IEC 15444 Standard
J2KR = JPEG2000Lossless
J2KI = JPEG2000
# J2KR: 1.2.840.100008.1.2.4.90 - JPEG 2000 Lossless
J2KR_08_08_3_0_1F_YBR_ICT = get_testdata_file("US1_J2KR.dcm")
J2KR_16_10_1_0_1F_M1 = get_testdata_file("RG3_J2KR.dcm")
J2KR_16_12_1_0_1F_M2 = get_testdata_file("MR2_J2KR.dcm")
J2KR_16_15_1_0_1F_M1 = get_testdata_file("RG1_J2KR.dcm")
J2KR_16_16_1_0_10F_M2 = get_testdata_file("emri_small_jpeg_2k_lossless.dcm")
J2KR_16_14_1_1_1F_M2 = get_testdata_file("693_J2KR.dcm")
J2KR_16_16_1_1_1F_M2 = get_testdata_file("MR_small_jp2klossless.dcm")
# Non-conformant pixel data -> JP2 header present
J2KR_08_08_3_0_1F_YBR_RCT = get_testdata_file("GDCMJ2K_TextGBR.dcm")
# J2KI: 1.2.840.10008.1.2.4.91 - JPEG 2000
J2KI_08_08_3_0_1F_RGB = get_testdata_file("SC_rgb_gdcm_KY.dcm")
J2KI_08_08_3_0_1F_YBR_ICT = get_testdata_file("US1_J2KI.dcm")
J2KI_16_10_1_0_1F_M1 = get_testdata_file("RG3_J2KI.dcm")
J2KI_16_12_1_0_1F_M2 = get_testdata_file("MR2_J2KI.dcm")
J2KI_16_15_1_0_1F_M1 = get_testdata_file("RG1_J2KI.dcm")
J2KI_16_14_1_1_1F_M2 = get_testdata_file("693_J2KI.dcm")
J2KI_16_16_1_1_1F_M2 = get_testdata_file("JPEG2000.dcm")

J2K_REFERENCE_DATA = [
    # fpath, (syntax, bits, nr samples, pixel repr, nr frames, shape, dtype)
    (J2KR_08_08_3_0_1F_YBR_ICT, (J2KR, 8, 3, 0, 1, (480, 640, 3), 'uint8')),
    (J2KR_16_10_1_0_1F_M1, (J2KR, 16, 1, 0, 1, (1760, 1760), 'uint16')),
    (J2KR_16_12_1_0_1F_M2, (J2KR, 16, 1, 0, 1, (1024, 1024), 'uint16')),
    (J2KR_16_15_1_0_1F_M1, (J2KR, 16, 1, 0, 1, (1955, 1841), 'uint16')),
    # should be Bits Stored = 12
    (J2KR_16_16_1_0_10F_M2, (J2KR, 16, 1, 0, 10, (10, 64, 64), 'uint16')),
    # should be Bits Stored = 16
    (J2KR_16_14_1_1_1F_M2, (J2KR, 16, 1, 1, 1, (512, 512), 'int16')),
    (J2KR_16_16_1_1_1F_M2, (J2KR, 16, 1, 1, 1, (64, 64), 'int16')),
    (J2KI_08_08_3_0_1F_RGB, (J2KI, 8, 3, 0, 1, (100, 100, 3), 'uint8')),
    (J2KI_08_08_3_0_1F_YBR_ICT, (J2KI, 8, 3, 0, 1, (480, 640, 3), 'uint8')),
    (J2KI_16_10_1_0_1F_M1, (J2KI, 16, 1, 0, 1, (1760, 1760), 'uint16')),
    (J2KI_16_12_1_0_1F_M2, (J2KI, 16, 1, 0, 1, (1024, 1024), 'uint16')),
    (J2KI_16_15_1_0_1F_M1, (J2KI, 16, 1, 0, 1, (1955, 1841), 'uint16')),
    # should be Bits Stored = 16
    (J2KI_16_14_1_1_1F_M2, (J2KI, 16, 1, 1, 1, (512, 512), 'int16')),
    (J2KI_16_16_1_1_1F_M2, (J2KI, 16, 1, 1, 1, (1024, 256), 'int16')),
]
J2K_MATCHING_DATASETS = [
    # (compressed, reference, fixes)
    pytest.param(
        J2KR_08_08_3_0_1F_YBR_ICT,
        get_testdata_file("US1_UNCR.dcm"),
        {},
    ),
    pytest.param(
        J2KR_16_10_1_0_1F_M1,
        get_testdata_file("RG3_UNCR.dcm"),
        {},
    ),
    pytest.param(
        J2KR_16_12_1_0_1F_M2,
        get_testdata_file("MR2_UNCR.dcm"),
        {},
    ),
    pytest.param(
        J2KR_16_15_1_0_1F_M1,
        get_testdata_file("RG1_UNCR.dcm"),
        {},
    ),
    pytest.param(
        J2KR_16_16_1_0_10F_M2,
        get_testdata_file("emri_small.dcm"),
        {'BitsStored': 16},
    ),
    pytest.param(
        J2KR_16_14_1_1_1F_M2,
        get_testdata_file("693_UNCR.dcm"),
        {'BitsStored': 14},
    ),
    pytest.param(
        J2KR_16_16_1_1_1F_M2,
        get_testdata_file("MR_small.dcm"),
        {},
    ),
    pytest.param(
        J2KI_08_08_3_0_1F_RGB,
        get_testdata_file("SC_rgb_gdcm2k_uncompressed.dcm"),
        {},
    ),
    pytest.param(
        J2KI_08_08_3_0_1F_YBR_ICT,
        get_testdata_file("US1_UNCI.dcm"),
        {},
        marks=pytest.mark.xfail(
            reason="Needs YBR_ICT to RGB conversion"
        )
    ),
    pytest.param(
        J2KI_16_10_1_0_1F_M1,
        get_testdata_file("RG3_UNCI.dcm"),
        {},
    ),
    pytest.param(
        J2KI_16_12_1_0_1F_M2,
        get_testdata_file("MR2_UNCI.dcm"),
        {},
    ),
    pytest.param(
        J2KI_16_15_1_0_1F_M1,
        get_testdata_file("RG1_UNCI.dcm"),
        {},
    ),
    pytest.param(
        J2KI_16_14_1_1_1F_M2,
        get_testdata_file("693_UNCI.dcm"),
        {'BitsStored': 16},
    ),
    pytest.param(
        J2KI_16_16_1_1_1F_M2,
        get_testdata_file("JPEG2000_UNC.dcm"),
        {},
    ),
]


@pytest.mark.skipif(not TEST_JPEG2K, reason="no -openjpeg plugin")
class TestJPEG2K:
    def setup(self):
        """Setup the test datasets and the environment."""
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [NP_HANDLER, LJ_HANDLER]

    def teardown(self):
        """Restore the environment."""
        pydicom.config.pixel_data_handlers = self.original_handlers

    @pytest.mark.parametrize('fpath, data', J2K_REFERENCE_DATA)
    def test_properties(self, fpath, data):
        """Test dataset and pixel array properties are as expected."""
        ds = dcmread(fpath)
        assert ds.file_meta.TransferSyntaxUID == data[0]
        assert ds.BitsAllocated == data[1]
        assert ds.SamplesPerPixel == data[2]
        assert ds.PixelRepresentation == data[3]
        assert getattr(ds, 'NumberOfFrames', 1) == data[4]

        arr = ds.pixel_array

        assert arr.flags.writeable
        assert data[5] == arr.shape
        assert arr.dtype == data[6]

    @pytest.mark.parametrize('fpath, rpath, fixes', J2K_MATCHING_DATASETS)
    def test_array(self, fpath, rpath, fixes):
        """Test pixel_array returns correct values."""
        ds = dcmread(fpath)
        arr = ds.pixel_array

        ref = dcmread(rpath).pixel_array
        assert np.array_equal(arr, ref)

    def test_warnings(self):
        """Test the plugin warnings work."""
        # Bits Stored
        ds = dcmread(J2KR_16_14_1_1_1F_M2)
        msg = (
            r"The \(0028,0101\) Bits Stored value '16' in the dataset does "
            r"not match the component precision value '14' found in the JPEG "
            r"2000 data. It's recommended that you change the Bits Stored "
            r"value to produce the correct output"
        )
        with pytest.warns(UserWarning, match=msg):
            ds.pixel_array

        # Pixel Representation
        ds.BitsStored = 14
        ds.PixelRepresentation = 0
        msg = (
            r"The \(0028,0103\) Pixel Representation value '0' \(unsigned\) "
            r"in the dataset does not match the format of the values found in "
            r"the JPEG 2000 data 'signed'. It's recommended that you change "
            r"the  Pixel Representation value to produce the correct output"
        )
        with pytest.warns(UserWarning, match=msg):
            ds.pixel_array

        # Samples per Pixel
        ds.PixelRepresentation = 0
        ds.SamplesPerPixel = 3
        msg = (
            r"The \(0028,0002\) Samples per Pixel value '3' in the dataset "
            r"does not match the number of components '1' found in the JPEG "
            r"2000 data. It's recommended that you change the  Samples per "
            r"Pixel value to produce the correct output"
        )
        with pytest.warns(UserWarning, match=msg):
            with pytest.raises(ValueError):
                ds.pixel_array

        # JP2 header
        ds = dcmread(J2KR_08_08_3_0_1F_YBR_RCT)
        msg = (
            r"The \(7FE0,0010\) Pixel Data contains a JPEG 2000 codestream "
            r"with the optional JP2 file format header, which is "
            r"non-conformant to the DICOM Standard \(Part 5, Annex A.4.4\)"
        )
        with pytest.warns(UserWarning, match=msg):
            ds.pixel_array

    def test_decompress_using_pylibjpeg(self):
        """Test decompressing JPEG2K with pylibjpeg handler succeeds."""
        ds = dcmread(J2KR_16_12_1_0_1F_M2)
        ds.decompress(handler_name='pylibjpeg')
        arr = ds.pixel_array

        ds = dcmread(get_testdata_file("MR2_J2KR.dcm"))
        ref = ds.pixel_array
        assert np.array_equal(arr, ref)
