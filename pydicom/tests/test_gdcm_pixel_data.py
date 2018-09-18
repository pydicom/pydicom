# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
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
from pydicom.pixel_data_handlers.util import _convert_YBR_FULL_to_RGB
from pydicom.tag import Tag
from pydicom import compat
gdcm_missing_message = "GDCM is not available in this test environment"
gdcm_present_message = "GDCM is being tested"
have_numpy_testing = True
try:
    import numpy.testing
except ImportError as e:
    have_numpy_testing = False

# Python 3.4 pytest does not have pytest.param?
have_pytest_param = True
try:
    x = pytest.param
except AttributeError:
    have_pytest_param = False

try:
    import pydicom.pixel_data_handlers.gdcm_handler as gdcm_handler
    HAVE_GDCM = gdcm_handler.HAVE_GDCM
except ImportError as e:
    HAVE_GDCM = False
    gdcm_handler = None

try:
    import pydicom.pixel_data_handlers.numpy_handler as numpy_handler
    HAVE_NP = numpy_handler.HAVE_NP
except ImportError:
    HAVE_NP = False
    numpy_handler = None


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
sc_rgb_jpeg_dcmtk_411_YBR_FULL_422 = get_testdata_files(
    "SC_rgb_dcmtk_+eb+cy+np.dcm")[0]
sc_rgb_jpeg_dcmtk_411_YBR_FULL = get_testdata_files(
    "SC_rgb_dcmtk_+eb+cy+n1.dcm")[0]
sc_rgb_jpeg_dcmtk_422_YBR_FULL = get_testdata_files(
    "SC_rgb_dcmtk_+eb+cy+n2.dcm")[0]
sc_rgb_jpeg_dcmtk_444_YBR_FULL = get_testdata_files(
    "SC_rgb_dcmtk_+eb+cy+s4.dcm")[0]
sc_rgb_jpeg_dcmtk_422_YBR_FULL_422 = get_testdata_files(
    "SC_rgb_dcmtk_+eb+cy+s2.dcm")[0]
sc_rgb_jpeg_dcmtk_RGB = get_testdata_files(
    "SC_rgb_dcmtk_+eb+cr.dcm")[0]
sc_rgb_jpeg2k_gdcm_KY = get_testdata_files(
    "SC_rgb_gdcm_KY.dcm")[0]
ground_truth_sc_rgb_jpeg2k_gdcm_KY_gdcm = get_testdata_files(
    "SC_rgb_gdcm2k_uncompressed.dcm")[0]

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
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = []

    def tearDown(self):
        pydicom.config.pixel_data_handlers = self.original_handlers
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
        self.sc_rgb_jpeg2k_gdcm_KY = dcmread(sc_rgb_jpeg2k_gdcm_KY)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = []

    def tearDown(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

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

    def test_jpeg2000_lossy(self):
        with self.assertRaises((NotImplementedError, )):
            _ = self.sc_rgb_jpeg2k_gdcm_KY.pixel_array


class GDCM_JPEGlossyTests_no_gdcm(unittest.TestCase):

    def setUp(self):
        self.jpeg_lossy = dcmread(jpeg_lossy_name)
        self.color_3d_jpeg = dcmread(color_3d_jpeg_baseline)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = []

    def tearDown(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

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
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = []

    def tearDown(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

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


@pytest.mark.skipif(not HAVE_GDCM, reason=gdcm_missing_message)
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
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [numpy_handler, gdcm_handler]

    def tearDown(self):
        pydicom.config.pixel_data_handlers = self.original_handlers
        os.remove(self.unicode_filename)

    def test_JPEG_LS_PixelArray(self):
        a = self.jpeg_ls_lossless.pixel_array
        b = self.mr_small.pixel_array
        self.assertEqual(
            a.mean(),
            b.mean(),
            "using GDCM Decoded pixel data is not "
            "all {0} (mean == {1})".format(b.mean(), a.mean()))

        assert a.flags.writeable

    def test_emri_JPEG_LS_PixelArray_with_gdcm(self):
        a = self.emri_jpeg_ls_lossless.pixel_array
        b = self.emri_small.pixel_array
        self.assertEqual(
            a.mean(),
            b.mean(),
            "Decoded pixel data is not all {0} "
            "(mean == {1})".format(b.mean(), a.mean()))

        assert a.flags.writeable


@pytest.mark.skipif(not HAVE_GDCM, reason=gdcm_missing_message)
class GDCM_JPEG2000Tests_with_gdcm(unittest.TestCase):
    def setUp(self):
        self.jpeg_2k = dcmread(jpeg2000_name)
        self.jpeg_2k_lossless = dcmread(jpeg2000_lossless_name)
        self.mr_small = dcmread(mr_name)
        self.emri_jpeg_2k_lossless = dcmread(emri_jpeg_2k_lossless)
        self.emri_small = dcmread(emri_name)
        self.sc_rgb_jpeg2k_gdcm_KY = dcmread(sc_rgb_jpeg2k_gdcm_KY)
        self.ground_truth_sc_rgb_jpeg2k_gdcm_KY_gdcm = dcmread(
            ground_truth_sc_rgb_jpeg2k_gdcm_KY_gdcm)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [numpy_handler, gdcm_handler]

    def tearDown(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

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

        assert a.flags.writeable

    def test_emri_JPEG2000PixelArray(self):
        a = self.emri_jpeg_2k_lossless.pixel_array
        b = self.emri_small.pixel_array
        self.assertEqual(
            a.mean(),
            b.mean(),
            "Decoded pixel data is not all {0} "
            "(mean == {1})".format(b.mean(), a.mean()))

        assert a.flags.writeable

    def test_jpeg2000_lossy(self):
        a = self.sc_rgb_jpeg2k_gdcm_KY.pixel_array
        b = self.ground_truth_sc_rgb_jpeg2k_gdcm_KY_gdcm.pixel_array
        if have_numpy_testing:
            numpy.testing.assert_array_equal(a, b)
        else:
            self.assertEqual(
                a.mean(),
                b.mean(),
                "Decoded pixel data is not all {0} "
                "(mean == {1})".format(b.mean(), a.mean()))

        assert a.flags.writeable


@pytest.mark.skipif(not HAVE_GDCM, reason=gdcm_missing_message)
class GDCM_JPEGlossyTests_with_gdcm(unittest.TestCase):

    def setUp(self):
        self.jpeg_lossy = dcmread(jpeg_lossy_name)
        self.color_3d_jpeg = dcmread(color_3d_jpeg_baseline)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [numpy_handler, gdcm_handler]

    def tearDown(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def testJPEGlossless_odd_data_size(self):
        test_file = get_testdata_files('SC_rgb_small_odd_jpeg.dcm')[0]
        ds = dcmread(test_file)
        pixel_data = ds.pixel_array
        assert pixel_data.nbytes == 27
        assert pixel_data.shape == (3, 3, 3)

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

        assert a.flags.writeable

    def test_JPEGBaselineColor3DPixelArray(self):
        self.assertEqual(
            self.color_3d_jpeg.PhotometricInterpretation,
            "YBR_FULL_422")
        a = self.color_3d_jpeg.pixel_array

        assert a.flags.writeable

        self.assertEqual(a.shape, (120, 480, 640, 3))
        a = _convert_YBR_FULL_to_RGB(a)
        # this test points were manually identified in Osirix viewer
        self.assertEqual(tuple(a[3, 159, 290, :]), (41, 41, 41))
        self.assertEqual(tuple(a[3, 169, 290, :]), (57, 57, 57))
        self.assertEqual(
            self.color_3d_jpeg.PhotometricInterpretation,
            "YBR_FULL_422")


@pytest.fixture(scope="module")
def test_with_gdcm():
    original_handlers = pydicom.config.pixel_data_handlers
    pydicom.config.pixel_data_handlers = [numpy_handler, gdcm_handler]
    yield original_handlers
    pydicom.config.pixel_data_handlers = original_handlers


if have_pytest_param:
    test_ids = [
        "JPEG_RGB_RGB",
        "JPEG_RGB_411_AS_YBR_FULL",
        "JPEG_RGB_411_AS_YBR_FULL_422",
        "JPEG_RGB_422_AS_YBR_FULL",
        "JPEG_RGB_422_AS_YBR_FULL_422",
        "JPEG_RGB_444_AS_YBR_FULL",
    ]

    testdata = [
        (sc_rgb_jpeg_dcmtk_RGB,
         "RGB",
         [
             (255, 0, 0),
             (255, 128, 128),
             (0, 255, 0),
             (128, 255, 128),
             (0, 0, 255),
             (128, 128, 255),
             (0, 0, 0),
             (64, 64, 64),
             (192, 192, 192),
             (255, 255, 255),
         ],
         False),
        pytest.param(
            sc_rgb_jpeg_dcmtk_411_YBR_FULL,
            "YBR_FULL",
            [
                (253, 1, 0),
                (253, 128, 132),
                (0, 255, 5),
                (127, 255, 127),
                (1, 0, 254),
                (127, 128, 255),
                (0, 0, 0),
                (64, 64, 64),
                (192, 192, 192),
                (255, 255, 255),
            ],
            True,
            marks=pytest.mark.xfail(
                reason="GDCM does not support "
                "non default jpeg lossy colorspaces")),
        pytest.param(
            sc_rgb_jpeg_dcmtk_411_YBR_FULL_422,
            "YBR_FULL_422",
            [
                (253, 1, 0),
                (253, 128, 132),
                (0, 255, 5),
                (127, 255, 127),
                (1, 0, 254),
                (127, 128, 255),
                (0, 0, 0),
                (64, 64, 64),
                (192, 192, 192),
                (255, 255, 255),
            ],
            True,
            marks=pytest.mark.xfail(
                reason="GDCM does not support "
                "non default jpeg lossy colorspaces")),
        pytest.param(
            sc_rgb_jpeg_dcmtk_422_YBR_FULL,
            "YBR_FULL",
            [
                (254, 0, 0),
                (255, 127, 127),
                (0, 255, 5),
                (129, 255, 129),
                (0, 0, 254),
                (128, 127, 255),
                (0, 0, 0),
                (64, 64, 64),
                (192, 192, 192),
                (255, 255, 255),
            ],
            True,
            marks=pytest.mark.xfail(
                reason="GDCM does not support "
                "non default jpeg lossy colorspaces")),
        pytest.param(
            sc_rgb_jpeg_dcmtk_422_YBR_FULL_422,
            "YBR_FULL_422",
            [
                (254, 0, 0),
                (255, 127, 127),
                (0, 255, 5),
                (129, 255, 129),
                (0, 0, 254),
                (128, 127, 255),
                (0, 0, 0),
                (64, 64, 64),
                (192, 192, 192),
                (255, 255, 255),
            ],
            True,
            marks=pytest.mark.xfail(
                reason="GDCM does not support "
                "non default jpeg lossy colorspaces")),
        pytest.param(
            sc_rgb_jpeg_dcmtk_444_YBR_FULL,
            "YBR_FULL",
            [
                (254, 0, 0),
                (255, 127, 127),
                (0, 255, 5),
                (129, 255, 129),
                (0, 0, 254),
                (128, 127, 255),
                (0, 0, 0),
                (64, 64, 64),
                (192, 192, 192),
                (255, 255, 255),
            ],
            True,
            marks=pytest.mark.xfail(
                reason="GDCM does not support "
                "non default jpeg lossy colorspaces"))]
else:
    # python 3.4 can't parameterize with xfails...
    test_ids = [
        "JPEG_RGB_RGB",
    ]
    testdata = [
        (sc_rgb_jpeg_dcmtk_RGB,
         "RGB",
         [
             (255, 0, 0),
             (255, 128, 128),
             (0, 255, 0),
             (128, 255, 128),
             (0, 0, 255),
             (128, 128, 255),
             (0, 0, 0),
             (64, 64, 64),
             (192, 192, 192),
             (255, 255, 255),
         ],
         False),
    ]


@pytest.mark.skipif(
    not HAVE_GDCM,
    reason=gdcm_missing_message)
@pytest.mark.parametrize(
    "image,PhotometricInterpretation,results,convert_yuv_to_rgb",
    testdata,
    ids=test_ids)
def test_PI_RGB(test_with_gdcm,
                image,
                PhotometricInterpretation,
                results,
                convert_yuv_to_rgb):
    t = dcmread(image)
    assert t.PhotometricInterpretation == PhotometricInterpretation
    a = t.pixel_array

    assert a.flags.writeable

    assert a.shape == (100, 100, 3)
    if convert_yuv_to_rgb:
        a = _convert_YBR_FULL_to_RGB(a)
    # this test points are from the ImageComments tag
    assert tuple(a[5, 50, :]) == results[0]
    assert tuple(a[15, 50, :]) == results[1]
    assert tuple(a[25, 50, :]) == results[2]
    assert tuple(a[35, 50, :]) == results[3]
    assert tuple(a[45, 50, :]) == results[4]
    assert tuple(a[55, 50, :]) == results[5]
    assert tuple(a[65, 50, :]) == results[6]
    assert tuple(a[75, 50, :]) == results[7]
    assert tuple(a[85, 50, :]) == results[8]
    assert tuple(a[95, 50, :]) == results[9]
    assert t.PhotometricInterpretation == PhotometricInterpretation


@pytest.mark.skipif(not HAVE_GDCM, reason=gdcm_missing_message)
class GDCM_JPEGlosslessTests_with_gdcm(unittest.TestCase):
    def setUp(self):
        self.jpeg_lossless = dcmread(jpeg_lossless_name)
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [numpy_handler, gdcm_handler]

    def tearDown(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

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

        assert a.flags.writeable
