import unittest
import os
import sys
import pydicom
from pydicom.filereader import read_file
from pydicom.tag import Tag

have_numpy = True
try:
    import numpy  # NOQA
except ImportError:
    have_numpy = False

have_pillow = True
try:
    from PIL import Image as PILImg
except ImportError:
    # If that failed, try the alternate import syntax for PIL.
    try:
        import Image as PILImg
    except ImportError:
        # Neither worked, so it's likely not installed.
        have_pillow = False


test_dir = os.path.dirname(__file__)
test_files = os.path.join(test_dir, 'test_files')

empty_number_tags_name = os.path.join(test_files, "reportsi_with_empty_number_tags.dcm")
rtplan_name = os.path.join(test_files, "rtplan.dcm")
rtdose_name = os.path.join(test_files, "rtdose.dcm")
ct_name = os.path.join(test_files, "CT_small.dcm")
mr_name = os.path.join(test_files, "MR_small.dcm")
truncated_mr_name = os.path.join(test_files, "MR_truncated.dcm")
jpeg2000_name = os.path.join(test_files, "JPEG2000.dcm")
jpeg2000_lossless_name = os.path.join(test_files, "MR_small_jp2klossless.dcm")
jpeg_ls_lossless_name = os.path.join(test_files, "MR_small_jpeg_ls_lossless.dcm")
jpeg_lossy_name = os.path.join(test_files, "JPEG-lossy.dcm")
jpeg_lossless_name = os.path.join(test_files, "JPEG-LL.dcm")
deflate_name = os.path.join(test_files, "image_dfl.dcm")
rtstruct_name = os.path.join(test_files, "rtstruct.dcm")
priv_SQ_name = os.path.join(test_files, "priv_SQ.dcm")
nested_priv_SQ_name = os.path.join(test_files, "nested_priv_SQ.dcm")
meta_missing_tsyntax_name = os.path.join(test_files, "meta_missing_tsyntax.dcm")
no_meta_group_length = os.path.join(test_files, "no_meta_group_length.dcm")
gzip_name = os.path.join(test_files, "zipMR.gz")
color_px_name = os.path.join(test_files, "color-px.dcm")
color_pl_name = os.path.join(test_files, "color-pl.dcm")
explicit_vr_le_no_meta = os.path.join(test_files, "ExplVR_LitEndNoMeta.dcm")
explicit_vr_be_no_meta = os.path.join(test_files, "ExplVR_BigEndNoMeta.dcm")
emri_name = os.path.join(test_files, "emri_small.dcm")
emri_big_endian_name = os.path.join(test_files, "emri_small_big_endian.dcm")
emri_jpeg_ls_lossless = os.path.join(test_files, "emri_small_jpeg_ls_lossless.dcm")
emri_jpeg_2k_lossless = os.path.join(test_files, "emri_small_jpeg_2k_lossless.dcm")
color_3d_jpeg_baseline = os.path.join(test_files, "color3d_jpeg_baseline.dcm")
dir_name = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()


class pillow_JPEG_LS_Tests(unittest.TestCase):
    def setUp(self):
        self.jpeg_ls_lossless = read_file(jpeg_ls_lossless_name)
        self.mr_small = read_file(mr_name)
        self.emri_jpeg_ls_lossless = read_file(emri_jpeg_ls_lossless)
        self.emri_small = read_file(emri_name)
        pydicom.config.image_handlers = ['pillow']

    def tearDown(self):
        pydicom.config.image_handlers = ['numpy', 'pillow', 'jpeg_ls', 'gdcm']

    def test_JPEG_LS_PixelArray(self):
        self.assertRaises(NotImplementedError, self.jpeg_ls_lossless._get_pixel_array)

    def test_emri_JPEG_LS_PixelArray(self):
        self.assertRaises(NotImplementedError, self.emri_jpeg_ls_lossless._get_pixel_array)


class pillow_BigEndian_Tests(unittest.TestCase):
    def setUp(self):
        self.emri_big_endian = read_file(emri_big_endian_name)
        self.emri_small = read_file(emri_name)

    def test_big_endian_PixelArray(self):
        """Test big endian pixel data vs little endian"""
        if have_numpy:
            a = self.emri_big_endian.pixel_array
            b = self.emri_small.pixel_array
            self.assertEqual(a.mean(), b.mean(),
                             "Decoded big endian pixel data is not all {0} (mean == {1})".format(b.mean(), a.mean()))
        else:
            self.assertRaises(ImportError, self.emri_big_endian._get_pixel_array)


class pillow_JPEG2000Tests(unittest.TestCase):
    def setUp(self):
        self.jpeg = read_file(jpeg2000_name)
        self.jpegls = read_file(jpeg2000_lossless_name)
        self.mr_small = read_file(mr_name)
        self.emri_jpeg_2k_lossless = read_file(emri_jpeg_2k_lossless)
        self.emri_small = read_file(emri_name)

    def testJPEG2000(self):
        """JPEG2000: Returns correct values for sample data elements............"""
        expected = [Tag(0x0054, 0x0010), Tag(0x0054, 0x0020)]  # XX also tests multiple-valued AT data element
        got = self.jpeg.FrameIncrementPointer
        self.assertEqual(got, expected, "JPEG2000 file, Frame Increment Pointer: expected %s, got %s" % (expected, got))

        got = self.jpeg.DerivationCodeSequence[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(got, expected, "JPEG200 file, Code Meaning got %s, expected %s" % (got, expected))

    def testJPEG2000PixelArray(self):
        """JPEG2000: Now works"""
        if have_numpy and have_pillow:
            a = self.jpegls.pixel_array
            b = self.mr_small.pixel_array
            self.assertEqual(a.mean(), b.mean(),
                             "Decoded pixel data is not all {0} (mean == {1})".format(b.mean(), a.mean()))
        else:
            self.assertRaises(NotImplementedError, self.jpegls._get_pixel_array)

    def test_emri_JPEG2000PixelArray(self):
        """JPEG2000: Now works"""
        if have_numpy and have_pillow:
            a = self.emri_jpeg_2k_lossless.pixel_array
            b = self.emri_small.pixel_array
            self.assertEqual(a.mean(), b.mean(),
                             "Decoded pixel data is not all {0} (mean == {1})".format(b.mean(), a.mean()))
        else:
            self.assertRaises(NotImplementedError, self.emri_jpeg_2k_lossless._get_pixel_array)


class pillow_JPEGlossyTests(unittest.TestCase):

    def setUp(self):
        self.jpeg = read_file(jpeg_lossy_name)
        self.color_3d_jpeg = read_file(color_3d_jpeg_baseline)

    def testJPEGlossy(self):
        """JPEG-lossy: Returns correct values for sample data elements.........."""
        got = self.jpeg.DerivationCodeSequence[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(got, expected, "JPEG-lossy file, Code Meaning got %s, expected %s" % (got, expected))

    def testJPEGlossyPixelArray(self):
        """JPEG-lossy: Fails gracefully when uncompressed data is asked for....."""
        if have_pillow and have_numpy:
            self.assertRaises(NotImplementedError, self.jpeg._get_pixel_array)
        else:
            self.assertRaises(NotImplementedError, self.jpeg._get_pixel_array)

    def testJPEGBaselineColor3DPixelArray(self):
        if have_pillow and have_numpy:
            a = self.color_3d_jpeg.pixel_array
            self.assertEqual(a.shape, (120, 480, 640, 3))
            # this test points were manually identified in Osirix viewer
            self.assertEqual(tuple(a[3, 159, 290, :]), (41, 41, 41))
            self.assertEqual(tuple(a[3, 169, 290, :]), (57, 57, 57))
        else:
            self.assertRaises(NotImplementedError, self.color_3d_jpeg._get_pixel_array)


class pillow_JPEGlosslessTests(unittest.TestCase):
    def setUp(self):
        self.jpeg = read_file(jpeg_lossless_name)

    def testJPEGlossless(self):
        """JPEGlossless: Returns correct values for sample data elements........"""
        got = self.jpeg.SourceImageSequence[0].PurposeOfReferenceCodeSequence[0].CodeMeaning
        expected = 'Uncompressed predecessor'
        self.assertEqual(got, expected, "JPEG-lossless file, Code Meaning got %s, expected %s" % (got, expected))

    def testJPEGlosslessPixelArray(self):
        """JPEGlossless: Fails gracefully when uncompressed data is asked for..."""
        # This test passes if the call raises either an
        # ImportError when there is no Pillow module
        # Or
        # NotImplementedError when there is a Pillow module
        #    but it lacks JPEG Lossless Dll's
        # Or
        # the call does not raise any Exceptions
        # This test fails if any other exception is raised
        with self.assertRaises((ImportError, NotImplementedError)):
            try:
                _x = self.jpeg._get_pixel_array()
            except Exception:
                raise
            else:
                raise ImportError()
