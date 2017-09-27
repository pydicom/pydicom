# -*- coding: utf-8 -*-
import unittest
import os
import sys
import tempfile
import shutil
import pytest
import pydicom
from pydicom.filereader import dcmread
from pydicom.data import get_testdata_files
from pydicom.tag import Tag
from pydicom import compat
gdcm_missing_message = "GDCM is not available in this test environment"
gdcm_present_message = "GDCM is being tested"

gdcm_handler = None
have_gdcm_handler = True
try:
    import pydicom.pixel_data_handlers.gdcm_handler as gdcm_handler
except ImportError as e:
    have_gdcm_handler = False
numpy_handler = None
have_numpy_handler = True
try:
    import pydicom.pixel_data_handlers.numpy_handler as numpy_handler
except ImportError:
    have_numpy_handler = False
test_gdcm_decoder = have_gdcm_handler

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


class GDCM_JPEG_LS_Tests_no_gdcm(unittest.TestCase):
    def setUp(self):
        if compat.in_py2:
            self.utf8_filename = os.path.join(
                tempfile.gettempdir(), "ДИКОМ.dcm")
            self.unicode_filename = self.utf8_filename.decode("utf8")
            shutil.copyfile(jpeg_ls_lossless_name.decode("utf8"),
                            self.unicode_filename)
        else:
            self.unicode_filename = os.path.join(
                tempfile.gettempdir(), "ДИКОМ.dcm")
            shutil.copyfile(jpeg_ls_lossless_name, self.unicode_filename)
        self.jpeg_ls_lossless = dcmread(self.unicode_filename)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_ls_lossless = dcmread(emri_jpeg_ls_lossless)
        self.emri_small = dcmread(emri_name)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [None]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers
        os.remove(self.unicode_filename)

    def test_JPEG_LS_PixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.jpeg_ls_lossless.pixel_array

    def test_emri_JPEG_LS_PixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.emri_jpeg_ls_lossless.pixel_array


class GDCM_JPEG2000Tests_no_gdcm(unittest.TestCase):
    def setUp(self):
        self.jpeg_2k = dcmread(jpeg2000_name)
        self.jpeg_2k_lossless = dcmread(jpeg2000_lossless_name)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_2k_lossless = dcmread(emri_jpeg_2k_lossless)
        self.emri_small = dcmread(emri_name)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [None]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_JPEG2000(self):
        """JPEG2000: Returns correct values for sample data elements"""
        # XX also tests multiple-valued AT data element
        expected = [Tag(0x0054, 0x0010), Tag(0x0054, 0x0020)]
        got = self.jpeg_2k.FrameIncrementPointer
        self.assertEqual(
            got,
            expected,
            "JPEG2000 file, Frame Increment Pointer: "
            "expected %s, got %s" % (expected, got))

        got = self.jpeg_2k.DerivationCodeSequence[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(
            got,
            expected,
            "JPEG200 file, Code Meaning got %s, "
            "expected %s" % (got, expected))

    def test_JPEG2000PixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.jpeg_2k_lossless.pixel_array

    def test_emri_JPEG2000PixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.emri_jpeg_2k_lossless.pixel_array


class GDCM_JPEGlossyTests_no_gdcm(unittest.TestCase):

    def setUp(self):
        self.jpeg_lossy = dcmread(jpeg_lossy_name)
        self.color_3d_jpeg = dcmread(color_3d_jpeg_baseline)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [None]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_JPEGlossy(self):
        """JPEG-lossy: Returns correct values for sample data elements"""
        got = self.jpeg_lossy.DerivationCodeSequence[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(
            got,
            expected,
            "JPEG-lossy file, Code Meaning got %s, "
            "expected %s" % (got, expected))

    def test_JPEGlossyPixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.jpeg_lossy.pixel_array

    def test_JPEGBaselineColor3DPixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.color_3d_jpeg.pixel_array


class GDCM_JPEGlosslessTests_no_gdcm(unittest.TestCase):
    def setUp(self):
        self.jpeg_lossless = dcmread(jpeg_lossless_name)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [None]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def testJPEGlossless(self):
        """JPEGlossless: Returns correct values for sample data elements"""
        got = self.\
            jpeg_lossless.\
            SourceImageSequence[0].\
            PurposeOfReferenceCodeSequence[0].CodeMeaning
        expected = 'Uncompressed predecessor'
        self.assertEqual(
            got,
            expected,
            "JPEG-lossless file, Code Meaning got %s, "
            "expected %s" % (got, expected))

    def testJPEGlosslessPixelArray(self):
        """JPEGlossless: Fails gracefully when uncompressed data asked for"""
        with self.assertRaises((NotImplementedError, )):
            _ = self.jpeg_lossless.pixel_array


@pytest.mark.skipif(not test_gdcm_decoder, reason=gdcm_missing_message)
class GDCM_JPEG_LS_Tests_with_gdcm(unittest.TestCase):
    def setUp(self):
        if compat.in_py2:
            self.utf8_filename = os.path.join(
                tempfile.gettempdir(), "ДИКОМ.dcm")
            self.unicode_filename = self.utf8_filename.decode("utf8")
            shutil.copyfile(jpeg_ls_lossless_name.decode("utf8"),
                            self.unicode_filename)
        else:
            self.unicode_filename = os.path.join(
                tempfile.gettempdir(), "ДИКОМ.dcm")
            shutil.copyfile(jpeg_ls_lossless_name, self.unicode_filename)
        self.jpeg_ls_lossless = dcmread(self.unicode_filename)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_ls_lossless = dcmread(emri_jpeg_ls_lossless)
        self.emri_small = dcmread(emri_name)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [numpy_handler, gdcm_handler]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers
        os.remove(self.unicode_filename)

    def test_JPEG_LS_PixelArray(self):
        a = self.jpeg_ls_lossless.pixel_array
        b = self.mr_small.pixel_array
        self.assertEqual(
            a.mean(),
            b.mean(),
            "using GDCM Decoded pixel data is not "
            "all {0} (mean == {1})".format(b.mean(), a.mean()))

    @pytest.mark.xfail(reason="GDCM does not support EMRI?")
    def test_emri_JPEG_LS_PixelArray_with_gdcm(self):
        a = self.emri_jpeg_ls_lossless.pixel_array
        b = self.emri_small.pixel_array
        self.assertEqual(
            a.mean(),
            b.mean(),
            "Decoded pixel data is not all {0} "
            "(mean == {1})".format(b.mean(), a.mean()))


@pytest.mark.skipif(not test_gdcm_decoder, reason=gdcm_missing_message)
class GDCM_JPEG2000Tests_with_gdcm(unittest.TestCase):
    def setUp(self):
        self.jpeg_2k = dcmread(jpeg2000_name)
        self.jpeg_2k_lossless = dcmread(jpeg2000_lossless_name)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_2k_lossless = dcmread(emri_jpeg_2k_lossless)
        self.emri_small = dcmread(emri_name)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [numpy_handler, gdcm_handler]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_JPEG2000(self):
        """JPEG2000: Returns correct values for sample data elements"""
        # XX also tests multiple-valued AT data element
        expected = [Tag(0x0054, 0x0010), Tag(0x0054, 0x0020)]
        got = self.jpeg_2k.FrameIncrementPointer
        self.assertEqual(
            got,
            expected,
            "JPEG2000 file, Frame Increment Pointer: "
            "expected %s, got %s" % (expected, got))

        got = self.jpeg_2k.DerivationCodeSequence[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(
            got,
            expected,
            "JPEG200 file, Code Meaning got %s, "
            "expected %s" % (got, expected))

    def test_JPEG2000PixelArray(self):
        a = self.jpeg_2k_lossless.pixel_array
        b = self.mr_small.pixel_array
        self.assertEqual(
            a.mean(),
            b.mean(),
            "Decoded pixel data is not all {0} "
            "(mean == {1})".format(b.mean(), a.mean()))

    @pytest.mark.xfail(reason="GDCM does not support EMRI?")
    def test_emri_JPEG2000PixelArray(self):
        a = self.emri_jpeg_2k_lossless.pixel_array
        b = self.emri_small.pixel_array
        self.assertEqual(
            a.mean(),
            b.mean(),
            "Decoded pixel data is not all {0} "
            "(mean == {1})".format(b.mean(), a.mean()))


@pytest.mark.skipif(not test_gdcm_decoder, reason=gdcm_missing_message)
class GDCM_JPEGlossyTests_with_gdcm(unittest.TestCase):

    def setUp(self):
        self.jpeg_lossy = dcmread(jpeg_lossy_name)
        self.color_3d_jpeg = dcmread(color_3d_jpeg_baseline)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [numpy_handler, gdcm_handler]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_JPEGlossy(self):
        """JPEG-lossy: Returns correct values for sample data elements"""
        got = self.jpeg_lossy.DerivationCodeSequence[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(
            got,
            expected,
            "JPEG-lossy file, Code Meaning got %s, "
            "expected %s" % (got, expected))

    def test_JPEGlossyPixelArray(self):
        a = self.jpeg_lossy.pixel_array
        self.assertEqual(a.shape, (1024, 256))
        # this test points were manually identified in Osirix viewer
        self.assertEqual(a[420, 140], 244)
        self.assertEqual(a[230, 120], 95)

    @pytest.mark.xfail(reason="GDCM does not support 3D color?")
    def test_JPEGBaselineColor3DPixelArray(self):
        a = self.color_3d_jpeg.pixel_array
        self.assertEqual(a.shape, (120, 480, 640, 3))
        # this test points were manually identified in Osirix viewer
        self.assertEqual(tuple(a[3, 159, 290, :]), (41, 41, 41))
        self.assertEqual(tuple(a[3, 169, 290, :]), (57, 57, 57))


@pytest.mark.skipif(not test_gdcm_decoder, reason=gdcm_missing_message)
class GDCM_JPEGlosslessTests_with_gdcm(unittest.TestCase):
    def setUp(self):
        self.jpeg_lossless = dcmread(jpeg_lossless_name)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [numpy_handler, gdcm_handler]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def testJPEGlossless(self):
        """JPEGlossless: Returns correct values for sample data elements"""
        got = self.\
            jpeg_lossless.\
            SourceImageSequence[0].\
            PurposeOfReferenceCodeSequence[0].CodeMeaning
        expected = 'Uncompressed predecessor'
        self.assertEqual(
            got,
            expected,
            "JPEG-lossless file, Code Meaning got %s, "
            "expected %s" % (got, expected))

    def testJPEGlosslessPixelArray(self):
        """JPEGlossless: Fails gracefully when uncompressed data asked for"""
        a = self.jpeg_lossless.pixel_array
        self.assertEqual(a.shape, (1024, 256))
        # this test points were manually identified in Osirix viewer
        self.assertEqual(a[420, 140], 227)
        self.assertEqual(a[230, 120], 105)
