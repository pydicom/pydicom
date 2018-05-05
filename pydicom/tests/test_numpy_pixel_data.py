import unittest
import os
import sys
import pytest
import pydicom
from pydicom.filereader import dcmread
from pydicom.data import get_testdata_files
from pydicom.tag import Tag
numpy_missing_message = ("numpy is not available "
                         "in this test environment")
numpy_present_message = "numpy is being tested"
numpy_handler = None
have_numpy_handler = True
try:
    import pydicom.pixel_data_handlers.numpy_handler as numpy_handler
except ImportError:
    have_numpy_handler = False

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
one_bit_allocated_name = get_testdata_files(
    "liver.dcm")[0]
dir_name = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()


class numpy_JPEG_LS_Tests_no_numpy(unittest.TestCase):
    def setUp(self):
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [None]
        self.jpeg_ls_lossless = dcmread(jpeg_ls_lossless_name)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_ls_lossless = dcmread(emri_jpeg_ls_lossless)
        self.emri_small = dcmread(emri_name)

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_JPEG_LS_PixelArray(self):
        """JPEG LS Lossless: Now works"""
        with self.assertRaises((NotImplementedError, )):
            _ = self.jpeg_ls_lossless.pixel_array

    def test_emri_JPEG_LS_PixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.emri_jpeg_ls_lossless.pixel_array


class numpy_BigEndian_Tests_no_numpy(unittest.TestCase):
    def setUp(self):
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [None]
        self.emri_big_endian = dcmread(emri_big_endian_name)
        self.emri_small = dcmread(emri_name)

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_big_endian_PixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.emri_big_endian.pixel_array


class OneBitAllocatedTestsNoNumpy(unittest.TestCase):
    def setUp(self):
        self.test_data = dcmread(one_bit_allocated_name)
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [None]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_access_pixel_array_raises(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.test_data.pixel_array


class numpy_JPEG2000Tests_no_numpy(unittest.TestCase):
    def setUp(self):
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [None]
        self.jpeg_2k = dcmread(jpeg2000_name)
        self.jpeg_2k_lossless = dcmread(jpeg2000_lossless_name)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_2k_lossless = dcmread(emri_jpeg_2k_lossless)
        self.emri_small = dcmread(emri_name)

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
        """JPEG2000: Now works"""
        with self.assertRaises((NotImplementedError, )):
            _ = self.jpeg_2k_lossless.pixel_array

    def test_emri_JPEG2000PixelArray(self):
        """JPEG2000: Now works"""
        with self.assertRaises((NotImplementedError, )):
            _ = self.emri_jpeg_2k_lossless.pixel_array


class numpy_JPEGlossyTests_no_numpy(unittest.TestCase):

    def setUp(self):
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [None]
        self.jpeg = dcmread(jpeg_lossy_name)
        self.color_3d_jpeg = dcmread(color_3d_jpeg_baseline)

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def testJPEGlossy(self):
        """JPEG-lossy: Returns correct values for sample data elements"""
        got = self.jpeg.DerivationCodeSequence[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(
            got,
            expected,
            "JPEG-lossy file, Code Meaning got %s, "
            "expected %s" % (got, expected))

    def testJPEGlossyPixelArray(self):
        """JPEG-lossy: Fails gracefully when uncompressed data is asked for"""
        with self.assertRaises((NotImplementedError, )):
            _ = self.jpeg.pixel_array

    def testJPEGBaselineColor3DPixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.color_3d_jpeg.pixel_array


class numpy_JPEGlosslessTests_no_numpy(unittest.TestCase):
    def setUp(self):
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [None]
        self.jpeg = dcmread(jpeg_lossless_name)

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def testJPEGlossless(self):
        """JPEGlossless: Returns correct values for sample data elements"""
        got = self.\
            jpeg.\
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
            _ = self.jpeg.pixel_array


@pytest.mark.skipif(
    not have_numpy_handler,
    reason=numpy_missing_message)
class numpy_JPEG_LS_Tests_with_numpy(unittest.TestCase):
    def setUp(self):
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [numpy_handler]
        self.jpeg_ls_lossless = dcmread(jpeg_ls_lossless_name)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_ls_lossless = dcmread(emri_jpeg_ls_lossless)
        self.emri_small = dcmread(emri_name)

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_JPEG_LS_PixelArray(self):
        """JPEG LS Lossless: Now works"""
        with self.assertRaises((NotImplementedError, )):
            _ = self.jpeg_ls_lossless.pixel_array

    def test_emri_JPEG_LS_PixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.emri_jpeg_ls_lossless.pixel_array


@pytest.mark.skipif(
    not have_numpy_handler,
    reason=numpy_missing_message)
class numpy_BigEndian_Tests_with_numpy(unittest.TestCase):
    def setUp(self):
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [numpy_handler]
        self.emri_big_endian = dcmread(emri_big_endian_name)
        self.emri_small = dcmread(emri_name)

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_big_endian_PixelArray(self):
        a = self.emri_big_endian.pixel_array
        b = self.emri_small.pixel_array
        self.assertEqual(
            a.mean(),
            b.mean(),
            "Decoded big endian pixel data is not "
            "all {0} (mean == {1})".format(b.mean(), a.mean()))


@pytest.mark.skipif(not have_numpy_handler, reason=numpy_missing_message)
class OneBitAllocatedTests(unittest.TestCase):
    def setUp(self):
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [numpy_handler]

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_unpack_pixel_data(self):
        dataset = dcmread(one_bit_allocated_name)
        packed_data = dataset.PixelData
        assert len(packed_data) == 3 * 512 * 512 / 8
        unpacked_data = dataset.pixel_array
        assert len(unpacked_data) == 3
        assert len(unpacked_data[0]) == 512
        assert len(unpacked_data[2]) == 512
        assert len(unpacked_data[0][0]) == 512
        assert len(unpacked_data[2][511]) == 512
        assert unpacked_data[0][0][0] == 0
        assert unpacked_data[2][511][511] == 0
        assert unpacked_data[1][256][256] == 1


@pytest.mark.skipif(
    not have_numpy_handler,
    reason=numpy_missing_message)
class numpy_LittleEndian_Tests(unittest.TestCase):
    def setUp(self):
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [numpy_handler]
        self.odd_size_image = dcmread(
            get_testdata_files('SC_rgb_small_odd.dcm')[0])
        self.emri_small = dcmread(emri_name)

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def test_little_endian_PixelArray_odd_data_size(self):
        pixel_data = self.odd_size_image.pixel_array
        assert pixel_data.nbytes == 27
        assert pixel_data.shape == (3, 3, 3)

    def test_little_endian_PixelArray(self):
        pixel_data = self.emri_small.pixel_array
        assert pixel_data.nbytes == 81920
        assert pixel_data.shape == (10, 64, 64)


@pytest.mark.skipif(
    not have_numpy_handler,
    reason=numpy_missing_message)
class numpy_JPEG2000Tests_with_numpy(unittest.TestCase):
    def setUp(self):
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [numpy_handler]
        self.jpeg_2k = dcmread(jpeg2000_name)
        self.jpeg_2k_lossless = dcmread(jpeg2000_lossless_name)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_2k_lossless = dcmread(emri_jpeg_2k_lossless)
        self.emri_small = dcmread(emri_name)

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


@pytest.mark.skipif(
    not have_numpy_handler,
    reason=numpy_missing_message)
class numpy_JPEGlossyTests_with_numpy(unittest.TestCase):

    def setUp(self):
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [numpy_handler]
        self.jpeg = dcmread(jpeg_lossy_name)
        self.color_3d_jpeg = dcmread(color_3d_jpeg_baseline)

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def testJPEGlossy(self):
        """JPEG-lossy: Returns correct values for sample data elements"""
        got = self.jpeg.DerivationCodeSequence[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(
            got,
            expected,
            "JPEG-lossy file, Code Meaning got %s, "
            "expected %s" % (got, expected))

    def testJPEGlossyPixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.jpeg.pixel_array

    def testJPEGBaselineColor3DPixelArray(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.color_3d_jpeg.pixel_array


@pytest.mark.skipif(
    not have_numpy_handler,
    reason=numpy_missing_message)
class numpy_JPEGlosslessTests_with_numpy(unittest.TestCase):
    def setUp(self):
        self.original_handlers = pydicom.config.image_handlers
        pydicom.config.image_handlers = [numpy_handler]
        self.jpeg = dcmread(jpeg_lossless_name)

    def tearDown(self):
        pydicom.config.image_handlers = self.original_handlers

    def testJPEGlossless(self):
        """JPEGlossless: Returns correct values for sample data elements"""
        got = self.\
            jpeg.\
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
            _ = self.jpeg.pixel_array
