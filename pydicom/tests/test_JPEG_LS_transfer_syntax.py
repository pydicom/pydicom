import os
import sys
import re
import pytest
import pydicom
from pydicom.filereader import read_file
pillow_missing_message = ("pillow is not available "
                          "in this test environment")
pillow_present_message = "pillow is being tested"
gdcm_missing_message = "GDCM is not available in this test environment"
numpy_missing_message = ("numpy is not available "
                         "in this test environment")
jpeg_ls_missing_message = ("jpeg_ls is not available "
                           "in this test environment")
pillow_handler = None
numpy_handler = None
gdcm_handler = None
jpeg_ls_handler = None

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
try:
    import pydicom.pixel_data_handlers.jpeg_ls_handler as jpeg_ls_handler
except ImportError:
    jpeg_ls_handler = None
try:
    import pydicom.pixel_data_handlers.gdcm_handler as gdcm_handler
except ImportError:
    gdcm_handler = None

test_dir = os.path.dirname(__file__)
test_files = os.path.join(test_dir, 'test_files')

mr_name = os.path.join(test_files, "MR_small.dcm")
jpeg_ls_lossless_name = os.path.join(
    test_files, "MR_small_jpeg_ls_lossless.dcm")
emri_name = os.path.join(test_files, "emri_small.dcm")
emri_jpeg_ls_lossless = os.path.join(
    test_files, "emri_small_jpeg_ls_lossless.dcm")
dir_name = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()


class Test_JPEG_LS_Lossless_transfer_syntax():
    def setup_method(self, method):
        self.jpeg_ls_lossless = read_file(jpeg_ls_lossless_name)
        self.mr_small = read_file(mr_name)
        self.emri_jpeg_ls_lossless = read_file(emri_jpeg_ls_lossless)
        self.emri_small = read_file(emri_name)
        self.original_handlers = pydicom.config.image_handlers

    def teardown_method(self, method):
        pydicom.config.image_handlers = self.original_handlers

    @pytest.mark.skipif(numpy_handler is None, reason=numpy_missing_message)
    def test_read_mr_with_numpy(self):
        pydicom.config.image_handlers = [numpy_handler]
        with pytest.raises((NotImplementedError, )) as e:
            _ = self.jpeg_ls_lossless.pixel_array
        assert re.match(
            ".*No available image handler could decode this transfer "
            "syntax JPEG-LS Lossless Image Compression.*", str(e))

    @pytest.mark.skipif(numpy_handler is None, reason=numpy_missing_message)
    def test_read_emri_with_numpy(self):
        pydicom.config.image_handlers = [numpy_handler]
        with pytest.raises((NotImplementedError, )) as e:
            _ = self.emri_jpeg_ls_lossless.pixel_array
        assert re.match(
            ".*No available image handler could decode this transfer "
            "syntax JPEG-LS Lossless Image Compression.*", str(e))

    @pytest.mark.skipif(pillow_handler is None, reason=pillow_missing_message)
    def test_read_mr_with_pillow(self):
        pydicom.config.image_handlers = [pillow_handler]
        with pytest.raises((NotImplementedError, )) as e:
            _ = self.jpeg_ls_lossless.pixel_array
        assert re.match(
            ".*No available image handler could decode this transfer "
            "syntax JPEG-LS Lossless Image Compression.*", str(e))

    @pytest.mark.skipif(pillow_handler is None, reason=pillow_missing_message)
    def test_read_emri_with_pillow(self):
        pydicom.config.image_handlers = [pillow_handler]
        with pytest.raises((NotImplementedError, )) as e:
            _ = self.emri_jpeg_ls_lossless.pixel_array
        assert re.match(
            ".*No available image handler could decode this transfer "
            "syntax JPEG-LS Lossless Image Compression.*", str(e))

    @pytest.mark.skipif(gdcm_handler is None, reason=gdcm_missing_message)
    def test_read_mr_with_gdcm(self):
        pydicom.config.image_handlers = [numpy_handler, gdcm_handler]
        a = self.jpeg_ls_lossless.pixel_array
        b = self.mr_small.pixel_array
        assert a.mean() == b.mean(), \
            "using GDCM Decoded pixel data is not " \
            "all {0} (mean == {1})".format(b.mean(), a.mean())

    @pytest.mark.skipif(gdcm_handler is None, reason=gdcm_missing_message)
    @pytest.mark.xfail(reason="GDCM only returns the first frame of EMRI?")
    def test_read_emri_with_gdcm(self):
        pydicom.config.image_handlers = [numpy_handler, gdcm_handler]
        a = self.emri_jpeg_ls_lossless.pixel_array
        b = self.emri_small.pixel_array
        assert a.mean() == b.mean(), \
            "using GDCM Decoded pixel data is not " \
            "all {0} (mean == {1})".format(b.mean(), a.mean())

    @pytest.mark.skipif(
        jpeg_ls_handler is None,
        reason=jpeg_ls_missing_message)
    def test_read_mr_with_jpeg_ls(self):
        pydicom.config.image_handlers = [numpy_handler, jpeg_ls_handler]
        a = self.jpeg_ls_lossless.pixel_array
        b = self.mr_small.pixel_array
        assert a.mean() == b.mean(), \
            "using jpeg_ls decoded pixel data is not " \
            "all {0} (mean == {1})".format(b.mean(), a.mean())

    @pytest.mark.skipif(
        jpeg_ls_handler is None,
        reason=jpeg_ls_missing_message)
    def test_read_emri_with_jpeg_ls(self):
        pydicom.config.image_handlers = [numpy_handler, jpeg_ls_handler]
        a = self.emri_jpeg_ls_lossless.pixel_array
        b = self.emri_small.pixel_array
        assert a.mean() == b.mean(), \
            "using jpeg_ls decoded pixel data is not all {0} " \
            "(mean == {1})".format(b.mean(), a.mean())

    def test_read_mr_without_any_handler(self):
        pydicom.config.image_handlers = []
        with pytest.raises((NotImplementedError, )) as e:
            _ = self.jpeg_ls_lossless.pixel_array
        assert re.match(
            ".*No available image handler could decode this transfer "
            "syntax JPEG-LS Lossless Image Compression.*", str(e))

    def test_read_emri_without_any_handler(self):
        pydicom.config.image_handlers = []
        with pytest.raises((NotImplementedError, )) as e:
            _ = self.emri_jpeg_ls_lossless.pixel_array
        assert re.match(
            ".*No available image handler could decode this transfer "
            "syntax JPEG-LS Lossless Image Compression.*", str(e))
