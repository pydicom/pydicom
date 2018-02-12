import unittest
import os
import sys
import pytest
import pydicom
import pydicom.config
from pydicom import dcmread
from pydicom.data import get_testdata_files

rle_missing_message = ("RLE decoder (numpy based) is not available "
                       "in this test environment")
rle_present_message = "RLE decoder (numpy based) is being tested"
rle_handler = None
have_rle_handler = True
numpy_handler = None
have_numpy_handler = True

try:
    import pydicom.pixel_data_handlers.numpy_handler as numpy_handler
except ImportError:
    have_numpy_handler = False

try:
    import pydicom.pixel_data_handlers.rle_handler as rle_handler
except ImportError:
    have_rle_handler = False

test_rle_decoder = have_numpy_handler and have_rle_handler

empty_number_tags_name = get_testdata_files(
    "reportsi_with_empty_number_tags.dcm")[0]
rtplan_name = get_testdata_files("rtplan.dcm")[0]
rtdose_name = get_testdata_files("rtdose.dcm")[0]
ct_name = get_testdata_files("CT_small.dcm")[0]
mr_name = get_testdata_files("MR_small.dcm")[0]
mr_rle = get_testdata_files("MR_small_RLE.dcm")[0]
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
emri_rle = get_testdata_files(
    "emri_small_RLE.dcm")[0]
color_3d_jpeg_baseline = get_testdata_files(
    "color3d_jpeg_baseline.dcm")[0]
dir_name = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()


class rle_RLE_Tests_no_rle(unittest.TestCase):
    def setUp(self):
        self.mr_small = dcmread(mr_name)
        self.mr_rle = dcmread(mr_rle)
        self.emri = dcmread(emri_name)
        self.emri_rle = dcmread(emri_rle)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [numpy_handler]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_RLE_PixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.emri_rle.pixel_array
            _ = self.mr_rle.pixel_array


@pytest.mark.skipif(
    not test_rle_decoder,
    reason=rle_missing_message)
class rle_RLE_Tests_with_rle(unittest.TestCase):
    def setUp(self):
        self.mr_small = dcmread(mr_name)
        self.mr_rle = dcmread(mr_rle)
        self.emri_small = dcmread(emri_name)
        self.emri_rle = dcmread(emri_rle)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [rle_handler, numpy_handler]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_mr_RLE_PixelArray(self):
        a = self.mr_rle.pixel_array
        b = self.mr_small.pixel_array
        self.assertEqual(
            a.mean(),
            b.mean(),
            "Decoded pixel data is not all {0} "
            "(mean == {1})".format(b.mean(), a.mean()))

    def test_emri_RLE_PixelArray(self):
        a = self.emri_rle.pixel_array
        b = self.emri_small.pixel_array
        self.assertEqual(
            a.mean(),
            b.mean(),
            "Decoded pixel data is not all {0} "
            "(mean == {1})".format(b.mean(), a.mean()))
