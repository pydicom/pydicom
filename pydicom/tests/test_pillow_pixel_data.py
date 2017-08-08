import unittest
import os
import sys
import pytest
import pydicom
from pydicom.filereader import read_file
from pydicom.data import DATA_ROOT
from pydicom.tag import Tag
pillow_missing_message = ("pillow is not available "
                          "in this test environment")
pillow_present_message = "pillow is being tested"
pillow_handler = None
have_pillow_handler = True
numpy_handler = None
have_numpy_handler = True
have_pillow_jpeg_plugin = False
have_pillow_jpeg2000_plugin = False
try:
    import pydicom.pixel_data_handlers.numpy_handler as numpy_handler
except ImportError:
    have_numpy_handler = False
try:
    import pydicom.pixel_data_handlers.pillow_handler as pillow_handler
    have_pillow_jpeg_plugin = pillow_handler.have_pillow_jpeg_plugin
    have_pillow_jpeg2000_plugin = \
        pillow_handler.have_pillow_jpeg2000_plugin
except ImportError:
    have_pillow_handler = False

test_pillow_decoder = have_numpy_handler and have_pillow_handler
test_pillow_jpeg_decoder = (test_pillow_decoder and
                            have_pillow_jpeg_plugin)
test_pillow_jpeg2000_decoder = (test_pillow_decoder and
                                have_pillow_jpeg2000_plugin)

test_files = os.path.join(DATA_ROOT, 'test_files')

empty_number_tags_name = os.path.join(
    test_files, "reportsi_with_empty_number_tags.dcm")
rtplan_name = os.path.join(test_files, "rtplan.dcm")
rtdose_name = os.path.join(test_files, "rtdose.dcm")
ct_name = os.path.join(test_files, "CT_small.dcm")
mr_name = os.path.join(test_files, "MR_small.dcm")
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
color_3d_jpeg_baseline = os.path.join(
    test_files, "color3d_jpeg_baseline.dcm")
dir_name = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()


class pillow_JPEG_LS_Tests_no_pillow(unittest.TestCase):
    def setUp(self):
        self.jpeg_ls_lossless = read_file(jpeg_ls_lossless_name)
        self.mr_small = read_file(mr_name)
        self.emri_jpeg_ls_lossless = read_file(emri_jpeg_ls_lossless)
        self.emri_small = read_file(emri_name)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [None, numpy_handler]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_JPEG_LS_PixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.jpeg_ls_lossless.pixel_array

    def test_emri_JPEG_LS_PixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.emri_jpeg_ls_lossless.pixel_array


class pillow_JPEG2000Tests_no_pillow(unittest.TestCase):
    def setUp(self):
        self.jpeg_2k = read_file(jpeg2000_name)
        self.jpeg_2k_lossless = read_file(jpeg2000_lossless_name)
        self.mr_small = read_file(mr_name)
        self.emri_jpeg_2k_lossless = read_file(emri_jpeg_2k_lossless)
        self.emri_small = read_file(emri_name)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [None, numpy_handler]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def testJPEG2000(self):
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

    def testJPEG2000PixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.jpeg_2k_lossless.pixel_array

    def test_emri_JPEG2000PixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.emri_jpeg_2k_lossless.pixel_array


class pillow_JPEGlossyTests_no_pillow(unittest.TestCase):

    def setUp(self):
        self.jpeg_lossy = read_file(jpeg_lossy_name)
        self.color_3d_jpeg = read_file(color_3d_jpeg_baseline)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [None, numpy_handler]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def testJPEGlossy(self):
        """JPEG-lossy: Returns correct values for sample data elements"""
        got = self.jpeg_lossy.DerivationCodeSequence[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(
            got,
            expected,
            "JPEG-lossy file, Code Meaning got %s, "
            "expected %s" % (got, expected))

    def testJPEGlossyPixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.jpeg_lossy.pixel_array

    def testJPEGBaselineColor3DPixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.color_3d_jpeg.pixel_array


class pillow_JPEGlosslessTests_no_pillow(unittest.TestCase):
    def setUp(self):
        self.jpeg_lossless = read_file(jpeg_lossless_name)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [None, numpy_handler]

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
        with self.assertRaises((NotImplementedError, )):
            _ = self.jpeg_lossless.pixel_array


@pytest.mark.skipif(
    not test_pillow_decoder,
    reason=pillow_missing_message)
class pillow_JPEG_LS_Tests_with_pillow(unittest.TestCase):
    def setUp(self):
        self.jpeg_ls_lossless = read_file(jpeg_ls_lossless_name)
        self.mr_small = read_file(mr_name)
        self.emri_jpeg_ls_lossless = read_file(emri_jpeg_ls_lossless)
        self.emri_small = read_file(emri_name)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [pillow_handler, numpy_handler]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_JPEG_LS_PixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.jpeg_ls_lossless.pixel_array

    def test_emri_JPEG_LS_PixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.emri_jpeg_ls_lossless.pixel_array


@pytest.mark.skipif(
    not test_pillow_jpeg2000_decoder,
    reason=pillow_missing_message)
class pillow_JPEG2000Tests_with_pillow(unittest.TestCase):
    def setUp(self):
        self.jpeg_2k = read_file(jpeg2000_name)
        self.jpeg_2k_lossless = read_file(jpeg2000_lossless_name)
        self.mr_small = read_file(mr_name)
        self.emri_jpeg_2k_lossless = read_file(emri_jpeg_2k_lossless)
        self.emri_small = read_file(emri_name)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [pillow_handler, numpy_handler]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def testJPEG2000(self):
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

    def testJPEG2000PixelArray(self):
        a = self.jpeg_2k_lossless.pixel_array
        b = self.mr_small.pixel_array
        self.assertEqual(
            a.mean(),
            b.mean(),
            "Decoded pixel data is not all {0} "
            "(mean == {1})".format(b.mean(), a.mean()))

    def test_emri_JPEG2000PixelArray(self):
        a = self.emri_jpeg_2k_lossless.pixel_array
        b = self.emri_small.pixel_array
        self.assertEqual(
            a.mean(),
            b.mean(),
            "Decoded pixel data is not all {0} "
            "(mean == {1})".format(b.mean(), a.mean()))


@pytest.mark.skipif(
    not test_pillow_jpeg_decoder,
    reason=pillow_missing_message)
class pillow_JPEGlossyTests_with_pillow(unittest.TestCase):

    def setUp(self):
        self.jpeg_lossy = read_file(jpeg_lossy_name)
        self.color_3d_jpeg = read_file(color_3d_jpeg_baseline)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [pillow_handler, numpy_handler]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def testJPEGlossy(self):
        """JPEG-lossy: Returns correct values for sample data elements"""
        got = self.jpeg_lossy.DerivationCodeSequence[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(
            got,
            expected,
            "JPEG-lossy file, Code Meaning got %s, "
            "expected %s" % (got, expected))

    def testJPEGlossyPixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.jpeg_lossy.pixel_array

    def testJPEGBaselineColor3DPixelArray(self):
        a = self.color_3d_jpeg.pixel_array
        self.assertEqual(a.shape, (120, 480, 640, 3))
        # this test points were manually identified in Osirix viewer
        self.assertEqual(tuple(a[3, 159, 290, :]), (41, 41, 41))
        self.assertEqual(tuple(a[3, 169, 290, :]), (57, 57, 57))


@pytest.mark.skipif(
    not test_pillow_jpeg_decoder,
    reason=pillow_missing_message)
class pillow_JPEGlosslessTests_with_pillow(unittest.TestCase):
    def setUp(self):
        self.jpeg_lossless = read_file(jpeg_lossless_name)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [pillow_handler, numpy_handler]

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
        with self.assertRaises((NotImplementedError, )):
            _ = self.jpeg_lossless.pixel_array
