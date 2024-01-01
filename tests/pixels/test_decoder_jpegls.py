# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Unit tests for the JPEG-LS Pixel Data handler."""

import os
import sys

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

import pytest

import pydicom
from pydicom.data import get_testdata_file
from pydicom.encaps import encapsulate, generate_frames
from pydicom.filereader import dcmread
from pydicom.pixel_data_handlers import numpy_handler
from pydicom.pixel_data_handlers import jpeg_ls_handler

jpeg_ls_missing_message = "jpeg_ls is not available in this test environment"
jpeg_ls_present_message = "jpeg_ls is being tested"

have_numpy_handler = numpy_handler.is_available()
have_jpeg_ls_handler = jpeg_ls_handler.is_available()
test_jpeg_ls_decoder = have_numpy_handler and have_jpeg_ls_handler

empty_number_tags_name = get_testdata_file("reportsi_with_empty_number_tags.dcm")
rtplan_name = get_testdata_file("rtplan.dcm")
rtdose_name = get_testdata_file("rtdose.dcm")
ct_name = get_testdata_file("CT_small.dcm")
mr_name = get_testdata_file("MR_small.dcm")
truncated_mr_name = get_testdata_file("MR_truncated.dcm")
jpeg2000_name = get_testdata_file("JPEG2000.dcm")
jpeg2000_lossless_name = get_testdata_file("MR_small_jp2klossless.dcm")
jpeg_ls_lossless_name = get_testdata_file("MR_small_jpeg_ls_lossless.dcm")
jpeg_lossy_name = get_testdata_file("JPEG-lossy.dcm")
jpeg_lossless_name = get_testdata_file("JPEG-LL.dcm")
deflate_name = get_testdata_file("image_dfl.dcm")
rtstruct_name = get_testdata_file("rtstruct.dcm")
priv_SQ_name = get_testdata_file("priv_SQ.dcm")
nested_priv_SQ_name = get_testdata_file("nested_priv_SQ.dcm")
meta_missing_tsyntax_name = get_testdata_file("meta_missing_tsyntax.dcm")
no_meta_group_length = get_testdata_file("no_meta_group_length.dcm")
gzip_name = get_testdata_file("zipMR.gz")
color_px_name = get_testdata_file("color-px.dcm")
color_pl_name = get_testdata_file("color-pl.dcm")
explicit_vr_le_no_meta = get_testdata_file("ExplVR_LitEndNoMeta.dcm")
explicit_vr_be_no_meta = get_testdata_file("ExplVR_BigEndNoMeta.dcm")
emri_name = get_testdata_file("emri_small.dcm")
emri_big_endian_name = get_testdata_file("emri_small_big_endian.dcm")
emri_jpeg_ls_lossless = get_testdata_file("emri_small_jpeg_ls_lossless.dcm")
emri_jpeg_2k_lossless = get_testdata_file("emri_small_jpeg_2k_lossless.dcm")
color_3d_jpeg_baseline = get_testdata_file("color3d_jpeg_baseline.dcm")
dir_name = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()

SUPPORTED_HANDLER_NAMES = (
    "jpegls",
    "jpeg_ls",
    "JPEG_LS",
    "jpegls_handler",
    "JPEG_LS_Handler",
)


class TestJPEGLS_no_jpeg_ls:
    def setup_method(self):
        self.jpeg_ls_lossless = dcmread(jpeg_ls_lossless_name)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_ls_lossless = dcmread(emri_jpeg_ls_lossless)
        self.emri_small = dcmread(emri_name)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [numpy_handler]

    def teardown_method(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def test_JPEG_LS_PixelArray(self):
        with pytest.raises((RuntimeError, NotImplementedError)):
            self.jpeg_ls_lossless.pixel_array


class TestJPEGLS_JPEG2000_no_jpeg_ls:
    def setup_method(self):
        self.jpeg_2k = dcmread(jpeg2000_name)
        self.jpeg_2k_lossless = dcmread(jpeg2000_lossless_name)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_2k_lossless = dcmread(emri_jpeg_2k_lossless)
        self.emri_small = dcmread(emri_name)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [numpy_handler]

    def teardown_method(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def test_JPEG2000PixelArray(self):
        """JPEG2000: Now works"""
        with pytest.raises(NotImplementedError):
            self.jpeg_2k.pixel_array

    def test_emri_JPEG2000PixelArray(self):
        """JPEG2000: Now works"""
        with pytest.raises(NotImplementedError):
            self.emri_jpeg_2k_lossless.pixel_array


class TestJPEGLS_JPEGlossy_no_jpeg_ls:
    def setup_method(self):
        self.jpeg_lossy = dcmread(jpeg_lossy_name)
        self.color_3d_jpeg = dcmread(color_3d_jpeg_baseline)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [numpy_handler]

    def teardown_method(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def testJPEGlossy(self):
        """JPEG-lossy: Returns correct values for sample data elements"""
        got = self.jpeg_lossy.DerivationCodeSequence[0].CodeMeaning
        assert "Lossy Compression" == got

    def testJPEGlossyPixelArray(self):
        """JPEG-lossy: Fails gracefully when uncompressed data is asked for"""
        with pytest.raises(NotImplementedError):
            self.jpeg_lossy.pixel_array

    def testJPEGBaselineColor3DPixelArray(self):
        with pytest.raises(NotImplementedError):
            self.color_3d_jpeg.pixel_array


class TestJPEGLS_JPEGlossless_no_jpeg_ls:
    def setup_method(self):
        self.jpeg_lossless = dcmread(jpeg_lossless_name)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [numpy_handler]

    def teardown_method(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def testJPEGlossless(self):
        """JPEGlossless: Returns correct values for sample data elements"""
        got = (
            self.jpeg_lossless.SourceImageSequence[0]
            .PurposeOfReferenceCodeSequence[0]
            .CodeMeaning
        )
        assert "Uncompressed predecessor" == got

    def testJPEGlosslessPixelArray(self):
        """JPEGlossless: Fails gracefully when uncompressed data asked for"""
        with pytest.raises(NotImplementedError):
            self.jpeg_lossless.pixel_array


@pytest.mark.skipif(not test_jpeg_ls_decoder, reason=jpeg_ls_missing_message)
class TestJPEGLS_JPEG_LS_with_jpeg_ls:
    def setup_method(self):
        self.jpeg_ls_lossless = dcmread(jpeg_ls_lossless_name)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_ls_lossless = dcmread(emri_jpeg_ls_lossless)
        self.emri_small = dcmread(emri_name)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [jpeg_ls_handler, numpy_handler]

    def teardown_method(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def test_JPEG_LS_PixelArray(self):
        a = self.jpeg_ls_lossless.pixel_array
        b = self.mr_small.pixel_array
        assert b.mean() == a.mean()
        assert a.flags.writeable

    def test_emri_JPEG_LS_PixelArray(self):
        a = self.emri_jpeg_ls_lossless.pixel_array
        b = self.emri_small.pixel_array
        assert b.mean() == a.mean()
        assert a.flags.writeable

    @pytest.mark.parametrize("handler_name", SUPPORTED_HANDLER_NAMES)
    def test_decompress_using_handler(self, handler_name):
        self.emri_jpeg_ls_lossless.decompress(handler_name=handler_name)
        a = self.emri_jpeg_ls_lossless.pixel_array
        b = self.emri_small.pixel_array
        assert b.mean() == a.mean()

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_frame_multiple_fragments(self):
        """Test a frame split across multiple fragments."""
        ds = dcmread(jpeg_ls_lossless_name)
        ref = ds.pixel_array
        frame = next(generate_frames(ds.PixelData, number_of_frames=1))
        ds.PixelData = encapsulate([frame, frame], fragments_per_frame=4)
        ds.NumberOfFrames = 2
        assert np.array_equal(ds.pixel_array[0], ref)


@pytest.mark.skipif(not test_jpeg_ls_decoder, reason=jpeg_ls_missing_message)
class TestJPEGLS_JPEG2000_with_jpeg_ls:
    def setup_method(self):
        self.jpeg_2k = dcmread(jpeg2000_name)
        self.jpeg_2k_lossless = dcmread(jpeg2000_lossless_name)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_2k_lossless = dcmread(emri_jpeg_2k_lossless)
        self.emri_small = dcmread(emri_name)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [jpeg_ls_handler, numpy_handler]

    def teardown_method(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def test_JPEG2000PixelArray(self):
        with pytest.raises(NotImplementedError):
            self.jpeg_2k.pixel_array

    def test_emri_JPEG2000PixelArray(self):
        with pytest.raises(NotImplementedError):
            self.emri_jpeg_2k_lossless.pixel_array


@pytest.mark.skipif(not test_jpeg_ls_decoder, reason=jpeg_ls_missing_message)
class TestJPEGLS_JPEGlossy_with_jpeg_ls:
    def setup_method(self):
        self.jpeg_lossy = dcmread(jpeg_lossy_name)
        self.color_3d_jpeg = dcmread(color_3d_jpeg_baseline)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [jpeg_ls_handler, numpy_handler]

    def teardown_method(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def testJPEGlossy(self):
        """JPEG-lossy: Returns correct values for sample data elements"""
        got = self.jpeg_lossy.DerivationCodeSequence[0].CodeMeaning
        assert "Lossy Compression" == got

    def testJPEGlossyPixelArray(self):
        with pytest.raises(NotImplementedError):
            self.jpeg_lossy.pixel_array

    def testJPEGBaselineColor3DPixelArray(self):
        with pytest.raises(NotImplementedError):
            self.color_3d_jpeg.pixel_array


@pytest.mark.skipif(not test_jpeg_ls_decoder, reason=jpeg_ls_missing_message)
class TestJPEGLS_JPEGlossless_with_jpeg_ls:
    def setup_method(self):
        self.jpeg_lossless = dcmread(jpeg_lossless_name)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [jpeg_ls_handler, numpy_handler]

    def teardown_method(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def testJPEGlossless(self):
        """JPEGlossless: Returns correct values for sample data elements"""
        got = (
            self.jpeg_lossless.SourceImageSequence[0]
            .PurposeOfReferenceCodeSequence[0]
            .CodeMeaning
        )
        assert "Uncompressed predecessor" == got

    def testJPEGlosslessPixelArray(self):
        """JPEGlossless: Fails gracefully when uncompressed data asked for"""
        with pytest.raises(NotImplementedError):
            self.jpeg_lossless.pixel_array


# Copyright 2008-2018 pydicom authors. See LICENSE file for details.

import os
import sys
import pytest
import pydicom
from pydicom.filereader import dcmread
from pydicom.data import get_testdata_file

pillow_missing_message = "pillow is not available " "in this test environment"
pillow_present_message = "pillow is being tested"
gdcm_missing_message = "GDCM is not available in this test environment"
numpy_missing_message = "numpy is not available " "in this test environment"
jpeg_ls_missing_message = "jpeg_ls is not available " "in this test environment"


try:
    from pydicom.pixel_data_handlers import numpy_handler

    HAVE_NP = numpy_handler.HAVE_NP
except ImportError:
    HAVE_NP = False
    numpy_handler = None

try:
    from pydicom.pixel_data_handlers import pillow_handler

    HAVE_PIL = pillow_handler.HAVE_PIL
    HAVE_JPEG = pillow_handler.HAVE_JPEG
    HAVE_JPEG2K = pillow_handler.HAVE_JPEG2K
except ImportError:
    HAVE_PIL = False
    pillow_handler = None
    HAVE_JPEG = False
    HAVE_JPEG2K = False

try:
    from pydicom.pixel_data_handlers import jpeg_ls_handler

    HAVE_JPEGLS = jpeg_ls_handler.HAVE_JPEGLS
except ImportError:
    jpeg_ls_handler = None
    HAVE_JPEGLS = False

try:
    from pydicom.pixel_data_handlers import gdcm_handler

    HAVE_GDCM = gdcm_handler.HAVE_GDCM
except ImportError:
    gdcm_handler = None
    HAVE_GDCM = False

mr_name = get_testdata_file("MR_small.dcm")
jpeg_ls_lossless_name = get_testdata_file("MR_small_jpeg_ls_lossless.dcm")
emri_name = get_testdata_file("emri_small.dcm")
emri_jpeg_ls_lossless = get_testdata_file("emri_small_jpeg_ls_lossless.dcm")
dir_name = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()


class Test_JPEG_LS_Lossless_transfer_syntax:
    def setup_method(self, method):
        self.jpeg_ls_lossless = dcmread(jpeg_ls_lossless_name)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_ls_lossless = dcmread(emri_jpeg_ls_lossless)
        self.emri_small = dcmread(emri_name)
        self.original_handlers = pydicom.config.pixel_data_handlers

    def teardown_method(self, method):
        pydicom.config.pixel_data_handlers = self.original_handlers

    @pytest.mark.skipif(not HAVE_NP, reason=numpy_missing_message)
    def test_read_mr_with_numpy(self):
        pydicom.config.pixel_data_handlers = [numpy_handler]
        msg = (
            r"Unable to decode pixel data with a transfer syntax UID of "
            r"'1.2.840.10008.1.2.4.80' \(JPEG-LS Lossless Image Compression\) "
            r"as there are no pixel data handlers available."
        )
        with pytest.raises(NotImplementedError, match=msg):
            self.jpeg_ls_lossless.pixel_array

    @pytest.mark.skipif(not HAVE_NP, reason=numpy_missing_message)
    def test_read_emri_with_numpy(self):
        pydicom.config.pixel_data_handlers = [numpy_handler]
        msg = (
            r"Unable to decode pixel data with a transfer syntax UID of "
            r"'1.2.840.10008.1.2.4.80' \(JPEG-LS Lossless Image Compression\) "
            r"as there are no pixel data handlers available."
        )
        with pytest.raises(NotImplementedError, match=msg):
            self.emri_jpeg_ls_lossless.pixel_array

    @pytest.mark.skipif(not HAVE_PIL, reason=pillow_missing_message)
    def test_read_mr_with_pillow(self):
        pydicom.config.pixel_data_handlers = [pillow_handler]
        msg = (
            r"Unable to decode pixel data with a transfer syntax UID of "
            r"'1.2.840.10008.1.2.4.80' \(JPEG-LS Lossless Image Compression\) "
            r"as there are no pixel data handlers available."
        )
        with pytest.raises(NotImplementedError, match=msg):
            self.jpeg_ls_lossless.pixel_array

    @pytest.mark.skipif(not HAVE_PIL, reason=pillow_missing_message)
    def test_read_emri_with_pillow(self):
        pydicom.config.pixel_data_handlers = [pillow_handler]
        msg = (
            r"Unable to decode pixel data with a transfer syntax UID of "
            r"'1.2.840.10008.1.2.4.80' \(JPEG-LS Lossless Image Compression\) "
            r"as there are no pixel data handlers available."
        )
        with pytest.raises(NotImplementedError, match=msg):
            self.emri_jpeg_ls_lossless.pixel_array

    @pytest.mark.skipif(not HAVE_GDCM, reason=gdcm_missing_message)
    def test_read_mr_with_gdcm(self):
        pydicom.config.pixel_data_handlers = [numpy_handler, gdcm_handler]
        a = self.jpeg_ls_lossless.pixel_array
        b = self.mr_small.pixel_array
        a_mean = a.mean()
        b_mean = b.mean()
        msg = f"using GDCM Decoded pixel data is not all {b_mean} (mean == {a_mean})"
        assert a_mean == b_mean, msg

    @pytest.mark.skipif(not HAVE_GDCM, reason=gdcm_missing_message)
    def test_read_emri_with_gdcm(self):
        pydicom.config.pixel_data_handlers = [numpy_handler, gdcm_handler]
        a = self.emri_jpeg_ls_lossless.pixel_array
        b = self.emri_small.pixel_array
        a_mean = a.mean()
        b_mean = b.mean()
        msg = f"using GDCM Decoded pixel data is not all {b_mean} (mean == {a_mean})"
        assert a_mean == b_mean, msg

    @pytest.mark.skipif(not HAVE_JPEGLS, reason=jpeg_ls_missing_message)
    def test_read_mr_with_jpeg_ls(self):
        pydicom.config.pixel_data_handlers = [numpy_handler, jpeg_ls_handler]
        a = self.jpeg_ls_lossless.pixel_array
        b = self.mr_small.pixel_array
        a_mean = a.mean()
        b_mean = b.mean()
        msg = f"using jpeg_ls decoded pixel data is not all {b_mean} (mean == {a_mean})"
        assert a_mean == b_mean, msg

    @pytest.mark.skipif(not HAVE_JPEGLS, reason=jpeg_ls_missing_message)
    def test_read_emri_with_jpeg_ls(self):
        pydicom.config.pixel_data_handlers = [numpy_handler, jpeg_ls_handler]
        a = self.emri_jpeg_ls_lossless.pixel_array
        b = self.emri_small.pixel_array
        a_mean = a.mean()
        b_mean = b.mean()
        msg = f"using jpeg_ls decoded pixel data is not all {b_mean} (mean == {a_mean})"
        assert a_mean == b_mean, msg

    def test_read_mr_without_any_handler(self):
        pydicom.config.pixel_data_handlers = []
        msg = (
            r"Unable to decode pixel data with a transfer syntax UID of "
            r"'1.2.840.10008.1.2.4.80' \(JPEG-LS Lossless Image Compression\) "
            r"as there are no pixel data handlers available."
        )
        with pytest.raises(NotImplementedError, match=msg):
            self.jpeg_ls_lossless.pixel_array

    def test_read_emri_without_any_handler(self):
        pydicom.config.pixel_data_handlers = []
        msg = (
            r"Unable to decode pixel data with a transfer syntax UID of "
            r"'1.2.840.10008.1.2.4.80' \(JPEG-LS Lossless Image Compression\) "
            r"as there are no pixel data handlers available."
        )
        with pytest.raises(NotImplementedError, match=msg):
            self.emri_jpeg_ls_lossless.pixel_array
