import unittest
import os
import sys
import pytest
import pydicom
import pydicom.config
from pydicom.filereader import read_file
from pydicom.data import DATA_ROOT

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

test_files = os.path.join(DATA_ROOT, 'test_files')

empty_number_tags_name = os.path.join(
    test_files, "reportsi_with_empty_number_tags.dcm")
rtplan_name = os.path.join(test_files, "rtplan.dcm")
rtdose_name = os.path.join(test_files, "rtdose.dcm")
ct_name = os.path.join(test_files, "CT_small.dcm")
mr_name = os.path.join(test_files, "MR_small.dcm")
mr_rle = os.path.join(test_files, "MR_small_RLE.dcm")
truncated_mr_name = os.path.join(test_files, "MR_truncated.dcm")
jpeg2000_name = os.path.join(test_files, "JPEG2000.dcm")
jpeg2000_lossless_name = os.path.join(
    test_files, "MR_small_jp2klossless.dcm")
jpeg_ls_lossless_name = os.path.join(
    test_files, "MR_small_jpeg_ls_lossless.dcm")
jpeg_lossy_name = os.path.join(test_files, "JPEG-lossy.dcm")
jpeg_lossless_name = os.path.join(test_files, "JPEG-LL.dcm")
deflate_name = os.path.join(test_files, "image_dfl.dcm")
rtstruct_name = os.path.join(test_files, "rtstruct.dcm")
priv_SQ_name = os.path.join(test_files, "priv_SQ.dcm")
nested_priv_SQ_name = os.path.join(test_files, "nested_priv_SQ.dcm")
meta_missing_tsyntax_name = os.path.join(
    test_files, "meta_missing_tsyntax.dcm")
no_meta_group_length = os.path.join(
    test_files, "no_meta_group_length.dcm")
gzip_name = os.path.join(test_files, "zipMR.gz")
color_px_name = os.path.join(test_files, "color-px.dcm")
color_pl_name = os.path.join(test_files, "color-pl.dcm")
explicit_vr_le_no_meta = os.path.join(
    test_files, "ExplVR_LitEndNoMeta.dcm")
explicit_vr_be_no_meta = os.path.join(
    test_files, "ExplVR_BigEndNoMeta.dcm")
emri_name = os.path.join(test_files, "emri_small.dcm")
emri_big_endian_name = os.path.join(
    test_files, "emri_small_big_endian.dcm")
emri_jpeg_ls_lossless = os.path.join(
    test_files, "emri_small_jpeg_ls_lossless.dcm")
emri_jpeg_2k_lossless = os.path.join(
    test_files, "emri_small_jpeg_2k_lossless.dcm")
emri_rle = os.path.join(
    test_files, "emri_small_RLE.dcm")
color_3d_jpeg_baseline = os.path.join(
    test_files, "color3d_jpeg_baseline.dcm")
dir_name = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()


@pytest.mark.skipif(
    test_rle_decoder,
    reason=rle_present_message)
class rle_RLE_Tests_no_rle(unittest.TestCase):
    def setUp(self):
        self.mr_small = read_file(mr_name)
        self.mr_rle = read_file(mr_rle)
        self.emri = read_file(emri_name)
        self.emri_rle = read_file(emri_rle)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [rle_handler, numpy_handler]

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
        self.mr_small = read_file(mr_name)
        self.mr_rle = read_file(mr_rle)
        self.emri_small = read_file(emri_name)
        self.emri_rle = read_file(emri_rle)
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
