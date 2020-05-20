# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Unit tests for the JPEG-LS Pixel Data handler."""

import os
import sys

import pytest

import pydicom
from pydicom.filereader import dcmread
from pydicom.data import get_testdata_files

jpeg_ls_missing_message = ("jpeg_ls is not available "
                           "in this test environment")
jpeg_ls_present_message = "jpeg_ls is being tested"

from pydicom.pixel_data_handlers import numpy_handler
have_numpy_handler = numpy_handler.is_available()

from pydicom.pixel_data_handlers import jpeg_ls_handler
have_jpeg_ls_handler = jpeg_ls_handler.is_available()

test_jpeg_ls_decoder = have_numpy_handler and have_jpeg_ls_handler

empty_number_tags_name = get_testdata_files(
    "reportsi_with_empty_number_tags.dcm")[0]
rtplan_name = get_testdata_files("rtplan.dcm")[0]
rtdose_name = get_testdata_files("rtdose.dcm")[0]
ct_name = get_testdata_files("CT_small.dcm")[0]
mr_name = get_testdata_files("MR_small.dcm")[0]
truncated_mr_name = get_testdata_files("MR_truncated.dcm")[0]
jpeg2000_name = get_testdata_files("JPEG2000.dcm")[0]
jpeg2000_lossless_name = get_testdata_files(
    "MR_small_jp2klossless.dcm")[0]
jpeg_ls_lossless_name = get_testdata_files(
    "MR_small_jpeg_ls_lossless.dcm")[0]
jpeg_lossy_name = get_testdata_files("JPEG-lossy.dcm")[0]
jpeg_lossless_name = get_testdata_files("JPEG-LL.dcm")[0]
deflate_name = get_testdata_files("image_dfl.dcm")[0]
rtstruct_name = get_testdata_files("rtstruct.dcm")[0]
priv_SQ_name = get_testdata_files("priv_SQ.dcm")[0]
nested_priv_SQ_name = get_testdata_files("nested_priv_SQ.dcm")[0]
meta_missing_tsyntax_name = get_testdata_files(
    "meta_missing_tsyntax.dcm")[0]
no_meta_group_length = get_testdata_files(
    "no_meta_group_length.dcm")[0]
gzip_name = get_testdata_files("zipMR.gz")[0]
color_px_name = get_testdata_files("color-px.dcm")[0]
color_pl_name = get_testdata_files("color-pl.dcm")[0]
explicit_vr_le_no_meta = get_testdata_files(
    "ExplVR_LitEndNoMeta.dcm")[0]
explicit_vr_be_no_meta = get_testdata_files(
    "ExplVR_BigEndNoMeta.dcm")[0]
emri_name = get_testdata_files("emri_small.dcm")[0]
emri_big_endian_name = get_testdata_files(
    "emri_small_big_endian.dcm")[0]
emri_jpeg_ls_lossless = get_testdata_files(
    "emri_small_jpeg_ls_lossless.dcm")[0]
emri_jpeg_2k_lossless = get_testdata_files(
    "emri_small_jpeg_2k_lossless.dcm")[0]
color_3d_jpeg_baseline = get_testdata_files(
    "color3d_jpeg_baseline.dcm")[0]
dir_name = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()

SUPPORTED_HANDLER_NAMES = (
    'jpegls', 'jpeg_ls', 'JPEG_LS', 'jpegls_handler', 'JPEG_LS_Handler'
)

class TestJPEGLS_no_jpeg_ls:
    def setup(self):
        self.jpeg_ls_lossless = dcmread(jpeg_ls_lossless_name)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_ls_lossless = dcmread(emri_jpeg_ls_lossless)
        self.emri_small = dcmread(emri_name)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [numpy_handler]

    def teardown(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def test_JPEG_LS_PixelArray(self):
        with pytest.raises((RuntimeError, NotImplementedError)):
            self.jpeg_ls_lossless.pixel_array


class TestJPEGLS_JPEG2000_no_jpeg_ls:
    def setup(self):
        self.jpeg_2k = dcmread(jpeg2000_name)
        self.jpeg_2k_lossless = dcmread(jpeg2000_lossless_name)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_2k_lossless = dcmread(emri_jpeg_2k_lossless)
        self.emri_small = dcmread(emri_name)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [numpy_handler]

    def teardown(self):
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
    def setup(self):
        self.jpeg_lossy = dcmread(jpeg_lossy_name)
        self.color_3d_jpeg = dcmread(color_3d_jpeg_baseline)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [numpy_handler]

    def teardown(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def testJPEGlossy(self):
        """JPEG-lossy: Returns correct values for sample data elements"""
        got = self.jpeg_lossy.DerivationCodeSequence[0].CodeMeaning
        assert 'Lossy Compression' == got

    def testJPEGlossyPixelArray(self):
        """JPEG-lossy: Fails gracefully when uncompressed data is asked for"""
        with pytest.raises(NotImplementedError):
            self.jpeg_lossy.pixel_array

    def testJPEGBaselineColor3DPixelArray(self):
        with pytest.raises(NotImplementedError):
            self.color_3d_jpeg.pixel_array


class TestJPEGLS_JPEGlossless_no_jpeg_ls:
    def setup(self):
        self.jpeg_lossless = dcmread(jpeg_lossless_name)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [numpy_handler]

    def teardown(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def testJPEGlossless(self):
        """JPEGlossless: Returns correct values for sample data elements"""
        got = self.\
            jpeg_lossless.\
            SourceImageSequence[0].\
            PurposeOfReferenceCodeSequence[0].CodeMeaning
        assert 'Uncompressed predecessor' == got

    def testJPEGlosslessPixelArray(self):
        """JPEGlossless: Fails gracefully when uncompressed data asked for"""
        with pytest.raises(NotImplementedError):
            self.jpeg_lossless.pixel_array


@pytest.mark.skipif(not test_jpeg_ls_decoder, reason=jpeg_ls_missing_message)
class TestJPEGLS_JPEG_LS_with_jpeg_ls:
    def setup(self):
        self.jpeg_ls_lossless = dcmread(jpeg_ls_lossless_name)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_ls_lossless = dcmread(emri_jpeg_ls_lossless)
        self.emri_small = dcmread(emri_name)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [jpeg_ls_handler, numpy_handler]

    def teardown(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def test_raises_if_endianess_not_set(self):
        self.jpeg_ls_lossless.is_little_endian = None
        with pytest.raises(ValueError):
            self.jpeg_ls_lossless.pixel_array

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


@pytest.mark.skipif(not test_jpeg_ls_decoder, reason=jpeg_ls_missing_message)
class TestJPEGLS_JPEG2000_with_jpeg_ls:
    def setup(self):
        self.jpeg_2k = dcmread(jpeg2000_name)
        self.jpeg_2k_lossless = dcmread(jpeg2000_lossless_name)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_2k_lossless = dcmread(emri_jpeg_2k_lossless)
        self.emri_small = dcmread(emri_name)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [jpeg_ls_handler, numpy_handler]

    def teardown(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def test_JPEG2000PixelArray(self):
        with pytest.raises(NotImplementedError):
            self.jpeg_2k.pixel_array

    def test_emri_JPEG2000PixelArray(self):
        with pytest.raises(NotImplementedError):
            self.emri_jpeg_2k_lossless.pixel_array


@pytest.mark.skipif(not test_jpeg_ls_decoder, reason=jpeg_ls_missing_message)
class TestJPEGLS_JPEGlossy_with_jpeg_ls:
    def setup(self):
        self.jpeg_lossy = dcmread(jpeg_lossy_name)
        self.color_3d_jpeg = dcmread(color_3d_jpeg_baseline)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [jpeg_ls_handler, numpy_handler]

    def teardown(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def testJPEGlossy(self):
        """JPEG-lossy: Returns correct values for sample data elements"""
        got = self.jpeg_lossy.DerivationCodeSequence[0].CodeMeaning
        assert 'Lossy Compression' == got

    def testJPEGlossyPixelArray(self):
        with pytest.raises(NotImplementedError):
            self.jpeg_lossy.pixel_array

    def testJPEGBaselineColor3DPixelArray(self):
        with pytest.raises(NotImplementedError):
            self.color_3d_jpeg.pixel_array


@pytest.mark.skipif(not test_jpeg_ls_decoder, reason=jpeg_ls_missing_message)
class TestJPEGLS_JPEGlossless_with_jpeg_ls:
    def setup(self):
        self.jpeg_lossless = dcmread(jpeg_lossless_name)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [jpeg_ls_handler, numpy_handler]

    def teardown(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def testJPEGlossless(self):
        """JPEGlossless: Returns correct values for sample data elements"""
        got = self.\
            jpeg_lossless.\
            SourceImageSequence[0].\
            PurposeOfReferenceCodeSequence[0].CodeMeaning
        assert 'Uncompressed predecessor' == got

    def testJPEGlosslessPixelArray(self):
        """JPEGlossless: Fails gracefully when uncompressed data asked for"""
        with pytest.raises(NotImplementedError):
            self.jpeg_lossless.pixel_array
