# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Tests for the pixel_data_handlers.numpy_handler module.

There are the following possibilities:

* numpy is not available and
  * the numpy handler is not available
  * the numpy handler is available
* numpy is available and
  * the numpy handler is not available
  * the numpy handler is available

**Supported transfer syntaxes**

* 1.2.840.10008.1.2 : Implicit VR Little Endian
* 1.2.840.10008.1.2.1 : Explicit VR Little Endian
* 1.2.840.10008.1.2.1.99 : Deflated Explicit VR Little Endian
* 1.2.840.10008.1.2.2 : Explicit VR Big Endian

**Elements affecting the handler**

* PixelRepresentation
* BitsAllocated
* SamplesPerPixel
* NumberOfFrames
* PlanarConfiguration
"""

from sys import byteorder

import pytest

import pydicom
from pydicom.data import get_testdata_files
from pydicom.dataset import Dataset
from pydicom.filereader import dcmread

from pydicom.tests._handler_common import ALL_TRANSFER_SYNTAXES
from pydicom.pixel_data_handlers.util import convert_color_space
from pydicom.uid import (
    ImplicitVRLittleEndian,
    ExplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian,
    ExplicitVRBigEndian
)

try:
    import numpy as np
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

try:
    from pydicom.pixel_data_handlers import numpy_handler as NP_HANDLER
    from pydicom.pixel_data_handlers.numpy_handler import (
        get_pixeldata,
        unpack_bits,
        pack_bits,
        get_expected_length,
        pixel_dtype,
    )
except ImportError:
    NP_HANDLER = None


# Paths to the test datasets
# IMPL: Implicit VR Little Endian
# EXPL: Explicit VR Little Endian
# DEFL: Deflated Explicit VR Little Endian
# EXPB: Explicit VR Big Endian
# 1/1, 1 sample/pixel, 1 frame
EXPL_1_1_1F = get_testdata_files("liver_1frame.dcm")[0]
EXPB_1_1_1F = get_testdata_files("liver_expb_1frame.dcm")[0]
# 1/1, 1 sample/pixel, 3 frame
EXPL_1_1_3F = get_testdata_files("liver.dcm")[0]
EXPB_1_1_3F = get_testdata_files("liver_expb.dcm")[0]
# 1/1, 3 sample/pixel, 1 frame
EXPL_1_3_1F = None
EXPB_1_3_1F = None
# 1/1, 3 sample/pixel, XXX frame
EXPL_1_3_XF = None
EXPB_1_3_XF = None
# 8/8, 1 sample/pixel, 1 frame
DEFL_8_1_1F = get_testdata_files("image_dfl.dcm")[0]
EXPL_8_1_1F = get_testdata_files("OBXXXX1A.dcm")[0]
EXPB_8_1_1F = get_testdata_files("OBXXXX1A_expb.dcm")[0]
# 8/8, 1 sample/pixel, 2 frame
EXPL_8_1_2F = get_testdata_files("OBXXXX1A_2frame.dcm")[0]
EXPB_8_1_2F = get_testdata_files("OBXXXX1A_expb_2frame.dcm")[0]
# 8/8, 3 sample/pixel, 1 frame
EXPL_8_3_1F = get_testdata_files("SC_rgb.dcm")[0]
EXPB_8_3_1F = get_testdata_files("SC_rgb_expb.dcm")[0]
# 8/8, 3 samples/pixel, 1 frame, 3 x 3
EXPL_8_3_1F_ODD = get_testdata_files('SC_rgb_small_odd.dcm')[0]
# 8/8, 3 sample/pixel, 2 frame
EXPL_8_3_2F = get_testdata_files("SC_rgb_2frame.dcm")[0]
EXPB_8_3_2F = get_testdata_files("SC_rgb_expb_2frame.dcm")[0]
# 16/16, 1 sample/pixel, 1 frame
IMPL_16_1_1F = get_testdata_files("MR_small_implicit.dcm")[0]
EXPL_16_1_1F = get_testdata_files("MR_small.dcm")[0]
EXPB_16_1_1F = get_testdata_files("MR_small_expb.dcm")[0]
# 16/12, 1 sample/pixel, 10 frame
EXPL_16_1_10F = get_testdata_files("emri_small.dcm")[0]
EXPB_16_1_10F = get_testdata_files("emri_small_big_endian.dcm")[0]
# 16/16, 3 sample/pixel, 1 frame
EXPL_16_3_1F = get_testdata_files("SC_rgb_16bit.dcm")[0]
EXPB_16_3_1F = get_testdata_files("SC_rgb_expb_16bit.dcm")[0]
# 16/16, 3 sample/pixel, 2 frame
EXPL_16_3_2F = get_testdata_files("SC_rgb_16bit_2frame.dcm")[0]
EXPB_16_3_2F = get_testdata_files("SC_rgb_expb_16bit_2frame.dcm")[0]
# 32/32, 1 sample/pixel, 1 frame
IMPL_32_1_1F = get_testdata_files("rtdose_1frame.dcm")[0]
EXPB_32_1_1F = get_testdata_files("rtdose_expb_1frame.dcm")[0]
# 32/32, 1 sample/pixel, 15 frame
IMPL_32_1_15F = get_testdata_files("rtdose.dcm")[0]
EXPB_32_1_15F = get_testdata_files("rtdose_expb.dcm")[0]
# 32/32, 3 sample/pixel, 1 frame
EXPL_32_3_1F = get_testdata_files("SC_rgb_32bit.dcm")[0]
EXPB_32_3_1F = get_testdata_files("SC_rgb_expb_32bit.dcm")[0]
# 32/32, 3 sample/pixel, 2 frame
EXPL_32_3_2F = get_testdata_files("SC_rgb_32bit_2frame.dcm")[0]
EXPB_32_3_2F = get_testdata_files("SC_rgb_expb_32bit_2frame.dcm")[0]

# Transfer syntaxes supported by other handlers
# JPEG Baseline (Process 1)
JPEG_BASELINE_1 = get_testdata_files("SC_rgb_jpeg_dcmtk.dcm")[0]
# JPEG Baseline (Process 2 and 4)
JPEG_EXTENDED_2 = get_testdata_files("JPEG-lossy.dcm")[0]
# JPEG Lossless (Process 14)
JPEG_LOSSLESS_14 = None
# JPEG Lossless (Process 14, Selection Value 1)
JPEG_LOSSLESS_14_1 = get_testdata_files("SC_rgb_jpeg_gdcm.dcm")[0]
# JPEG-LS Lossless
JPEG_LS_LOSSLESS = get_testdata_files("MR_small_jpeg_ls_lossless.dcm")[0]
# JPEG-LS Lossy
JPEG_LS_LOSSY = None
# JPEG2k Lossless
JPEG_2K_LOSSLESS = get_testdata_files("emri_small_jpeg_2k_lossless.dcm")[0]
# JPEG2k
JPEG_2K = get_testdata_files("JPEG2000.dcm")[0]
# RLE Lossless
RLE = get_testdata_files("MR_small_RLE.dcm")[0]

# Transfer Syntaxes (non-retired + Explicit VR Big Endian)
SUPPORTED_SYNTAXES = [
    ImplicitVRLittleEndian,
    ExplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian,
    ExplicitVRBigEndian
]
UNSUPPORTED_SYNTAXES = list(
    set(ALL_TRANSFER_SYNTAXES) ^ set(SUPPORTED_SYNTAXES)
)


def test_unsupported_syntaxes():
    """Test that UNSUPPORTED_SYNTAXES is as expected."""
    for syntax in SUPPORTED_SYNTAXES:
        assert syntax not in UNSUPPORTED_SYNTAXES


REFERENCE_DATA_UNSUPPORTED = [
    (JPEG_BASELINE_1, ('1.2.840.10008.1.2.4.50', 'Lestrade^G')),
    (JPEG_EXTENDED_2, ('1.2.840.10008.1.2.4.51', 'CompressedSamples^NM1')),
    # (JPEG_LOSSLESS_14, ('1.2.840.10008.1.2.4.57')),  # No dataset available
    (JPEG_LOSSLESS_14_1, ('1.2.840.10008.1.2.4.70', 'Lestrade^G')),
    (JPEG_LS_LOSSLESS, ('1.2.840.10008.1.2.4.80', 'CompressedSamples^MR1')),
    # (JPEG_LS_LOSSY, ('1.2.840.10008.1.2.4.81')),  # No dataset available
    (JPEG_2K_LOSSLESS, ('1.2.840.10008.1.2.4.90', '')),
    (JPEG_2K, ('1.2.840.10008.1.2.4.91', 'CompressedSamples^NM1')),
    (RLE, ('1.2.840.10008.1.2.5', 'CompressedSamples^MR1')),
]


# Numpy and the numpy handler are unavailable
@pytest.mark.skipif(HAVE_NP, reason='Numpy is available')
class TestNoNumpy_NoNumpyHandler(object):
    """Tests for handling datasets without numpy and the handler."""
    def setup(self):
        """Setup the environment."""
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = []

    def teardown(self):
        """Restore the environment."""
        pydicom.config.pixel_data_handlers = self.original_handlers

    def test_environment(self):
        """Check that the testing environment is as expected."""
        assert not HAVE_NP
        assert NP_HANDLER is not None

    def test_can_access_supported_dataset(self):
        """Test that we can read and access elements in dataset."""
        # Explicit little
        ds = dcmread(EXPL_16_1_1F)
        assert 'CompressedSamples^MR1' == ds.PatientName
        assert 8192 == len(ds.PixelData)

        # Implicit little
        ds = dcmread(IMPL_16_1_1F)
        assert 'CompressedSamples^MR1' == ds.PatientName
        assert 8192 == len(ds.PixelData)

        # Deflated little
        ds = dcmread(DEFL_8_1_1F)
        assert '^^^^' == ds.PatientName
        assert 262144 == len(ds.PixelData)

        # Explicit big
        ds = dcmread(EXPB_16_1_1F)
        assert 'CompressedSamples^MR1' == ds.PatientName
        assert 8192 == len(ds.PixelData)

    @pytest.mark.parametrize("fpath,data", REFERENCE_DATA_UNSUPPORTED)
    def test_can_access_unsupported_dataset(self, fpath, data):
        """Test can read and access elements in unsupported datasets."""
        ds = dcmread(fpath)
        assert data[0] == ds.file_meta.TransferSyntaxUID
        assert data[1] == ds.PatientName

    def test_pixel_array_raises(self):
        """Test pixel_array raises exception for all syntaxes."""
        ds = dcmread(EXPL_16_1_1F)
        for uid in ALL_TRANSFER_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            with pytest.raises(NotImplementedError,
                               match="UID of '{}'".format(uid)):
                ds.pixel_array


# Numpy unavailable and the numpy handler is available
@pytest.mark.skipif(HAVE_NP, reason='Numpy is available')
class TestNoNumpy_NumpyHandler(object):
    """Tests for handling datasets without numpy and the handler."""
    def setup(self):
        """Setup the environment."""
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [NP_HANDLER]

    def teardown(self):
        """Restore the environment."""
        pydicom.config.pixel_data_handlers = self.original_handlers

    def test_environment(self):
        """Check that the testing environment is as expected."""
        assert not HAVE_NP
        assert NP_HANDLER is not None

    def test_can_access_supported_dataset(self):
        """Test that we can read and access elements in dataset."""
        # Explicit little
        ds = dcmread(EXPL_16_1_1F)
        assert 'CompressedSamples^MR1' == ds.PatientName
        assert 8192 == len(ds.PixelData)

        # Implicit little
        ds = dcmread(IMPL_16_1_1F)
        assert 'CompressedSamples^MR1' == ds.PatientName
        assert 8192 == len(ds.PixelData)

        # Deflated little
        ds = dcmread(DEFL_8_1_1F)
        assert '^^^^' == ds.PatientName
        assert 262144 == len(ds.PixelData)

        # Explicit big
        ds = dcmread(EXPB_16_1_1F)
        assert 'CompressedSamples^MR1' == ds.PatientName
        assert 8192 == len(ds.PixelData)

    @pytest.mark.parametrize("fpath,data", REFERENCE_DATA_UNSUPPORTED)
    def test_can_access_unsupported_dataset(self, fpath, data):
        """Test can read and access elements in unsupported datasets."""
        ds = dcmread(fpath)
        assert data[0] == ds.file_meta.TransferSyntaxUID
        assert data[1] == ds.PatientName

    def test_unsupported_pixel_array_raises(self):
        """Test pixel_array raises exception for unsupported syntaxes."""
        ds = dcmread(EXPL_16_1_1F)
        for uid in UNSUPPORTED_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            with pytest.raises(NotImplementedError,
                               match="UID of '{}'".format(uid)):
                ds.pixel_array

    def test_supported_pixel_array_raises(self):
        """Test pixel_array raises exception for supported syntaxes."""
        ds = dcmread(EXPL_16_1_1F)
        for uid in SUPPORTED_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            exc_msg = (
                r"The following handlers are available to decode the pixel "
                r"data however they are missing required dependencies: "
                r"Numpy \(req. NumPy\)"
            )
            with pytest.raises(RuntimeError, match=exc_msg):
                ds.pixel_array


# Numpy is available, the numpy handler is unavailable
@pytest.mark.skipif(not HAVE_NP, reason='Numpy is unavailable')
class TestNumpy_NoNumpyHandler(object):
    """Tests for handling datasets without the handler."""
    def setup(self):
        """Setup the environment."""
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = []

    def teardown(self):
        """Restore the environment."""
        pydicom.config.pixel_data_handlers = self.original_handlers

    def test_environment(self):
        """Check that the testing environment is as expected."""
        assert HAVE_NP
        # We numpy handler should still be available
        assert NP_HANDLER is not None

    def test_can_access_supported_dataset(self):
        """Test that we can read and access elements in dataset."""
        # Explicit little
        ds = dcmread(EXPL_16_1_1F)
        assert 'CompressedSamples^MR1' == ds.PatientName
        assert 8192 == len(ds.PixelData)

        # Implicit little
        ds = dcmread(IMPL_16_1_1F)
        assert 'CompressedSamples^MR1' == ds.PatientName
        assert 8192 == len(ds.PixelData)

        # Deflated little
        ds = dcmread(DEFL_8_1_1F)
        assert '^^^^' == ds.PatientName
        assert 262144 == len(ds.PixelData)

        # Explicit big
        ds = dcmread(EXPB_16_1_1F)
        assert 'CompressedSamples^MR1' == ds.PatientName
        assert 8192 == len(ds.PixelData)

    @pytest.mark.parametrize("fpath,data", REFERENCE_DATA_UNSUPPORTED)
    def test_can_access_unsupported_dataset(self, fpath, data):
        """Test can read and access elements in unsupported datasets."""
        ds = dcmread(fpath)
        assert data[0] == ds.file_meta.TransferSyntaxUID
        assert data[1] == ds.PatientName

    def test_pixel_array_raises(self):
        """Test pixel_array raises exception for all syntaxes."""
        ds = dcmread(EXPL_16_1_1F)
        for uid in ALL_TRANSFER_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            with pytest.raises((NotImplementedError, RuntimeError)):
                ds.pixel_array


# Numpy and the numpy handler are available
MATCHING_DATASETS = [
    (EXPL_1_1_1F, EXPB_1_1_1F),
    (EXPL_1_1_3F, EXPB_1_1_3F),
    (EXPL_8_1_1F, EXPB_8_1_1F),
    (EXPL_8_1_2F, EXPB_8_1_2F),
    (EXPL_8_3_1F, EXPB_8_3_1F),
    (EXPL_8_3_2F, EXPB_8_3_2F),
    (EXPL_16_1_1F, EXPB_16_1_1F),
    (EXPL_16_1_10F, EXPB_16_1_10F),
    # (EXPL_16_3_1F, EXPB_16_3_1F),  # Not supported yet
    (EXPL_16_3_2F, EXPB_16_3_2F),
    (IMPL_32_1_1F, EXPB_32_1_1F),
    (IMPL_32_1_15F, EXPB_32_1_15F),
    # (EXPL_32_3_1F, EXPB_32_3_1F),  # Not supported yet
    (EXPL_32_3_2F, EXPB_32_3_2F)
]

EXPL = ExplicitVRLittleEndian
IMPL = ImplicitVRLittleEndian
REFERENCE_DATA_LITTLE = [
    # fpath, (syntax, bits, nr samples, pixel repr, nr frames, shape, dtype)
    (EXPL_1_1_1F, (EXPL, 1, 1, 0, 1, (512, 512), 'uint8')),
    (EXPL_1_1_3F, (EXPL, 1, 1, 0, 3, (3, 512, 512), 'uint8')),
    (EXPL_8_1_1F, (EXPL, 8, 1, 0, 1, (600, 800), 'uint8')),
    (EXPL_8_3_1F_ODD, (EXPL, 8, 3, 0, 1, (3, 3, 3), 'uint8')),
    (EXPL_8_1_2F, (EXPL, 8, 1, 0, 2, (2, 600, 800), 'uint8')),
    (EXPL_8_3_1F, (EXPL, 8, 3, 0, 1, (100, 100, 3), 'uint8')),
    (EXPL_8_3_2F, (EXPL, 8, 3, 0, 2, (2, 100, 100, 3), 'uint8')),
    (EXPL_16_1_1F, (EXPL, 16, 1, 1, 1, (64, 64), 'int16')),
    (EXPL_16_1_10F, (EXPL, 16, 1, 0, 10, (10, 64, 64), 'uint16')),
    # (EXPL_16_3_1F, (EXPL, 16, 3, 0, 1, (100, 100, 3), 'uint16')),
    (EXPL_16_3_2F, (EXPL, 16, 3, 0, 2, (2, 100, 100, 3), 'uint16')),
    (IMPL_32_1_1F, (IMPL, 32, 1, 0, 1, (10, 10), 'uint32')),
    (IMPL_32_1_15F, (IMPL, 32, 1, 0, 15, (15, 10, 10), 'uint32')),
    # (EXPL_32_3_1F, (EXPL, 32, 3, 0, 1, (100, 100, 3), 'uint32')),
    (EXPL_32_3_2F, (EXPL, 32, 3, 0, 2, (2, 100, 100, 3), 'uint32')),
]


@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class TestNumpy_NumpyHandler(object):
    """Tests for handling Pixel Data with the handler."""
    def setup(self):
        """Setup the test datasets and the environment."""
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [NP_HANDLER]

    def teardown(self):
        """Restore the environment."""
        pydicom.config.pixel_data_handlers = self.original_handlers

    def test_environment(self):
        """Check that the testing environment is as expected."""
        assert HAVE_NP
        assert NP_HANDLER is not None

    def test_unsupported_syntax_raises(self):
        """Test pixel_array raises exception for unsupported syntaxes."""
        ds = dcmread(EXPL_16_1_1F)

        for uid in UNSUPPORTED_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            with pytest.raises((NotImplementedError, RuntimeError)):
                ds.pixel_array

    def test_dataset_pixel_array_handler_needs_convert(self):
        """Test Dataset.pixel_array when converting to RGB."""
        ds = dcmread(EXPL_8_3_1F)
        # Convert to YBR first
        arr = ds.pixel_array
        assert (255, 0, 0) == tuple(arr[5, 50, :])
        arr = convert_color_space(arr, 'RGB', 'YBR_FULL')
        ds.PixelData = arr.tobytes()
        del ds._pixel_array  # Weird PyPy2 issue without this

        # Test normal functioning (False)
        assert (76, 85, 255) == tuple(ds.pixel_array[5, 50, :])

        def needs_convert(ds):
            """Change the default return to True"""
            return True

        # Test modified
        orig_fn = NP_HANDLER.needs_to_convert_to_RGB
        NP_HANDLER.needs_to_convert_to_RGB = needs_convert

        # Ensure the pixel array gets updated
        ds._pixel_id = None
        assert (254, 0, 0) == tuple(ds.pixel_array[5, 50, :])

        # Reset
        NP_HANDLER.needs_to_convert_to_RGB = orig_fn

    @pytest.mark.parametrize("fpath, data", REFERENCE_DATA_UNSUPPORTED)
    def test_can_access_unsupported_dataset(self, fpath, data):
        """Test can read and access elements in unsupported datasets."""
        ds = dcmread(fpath)
        assert data[0] == ds.file_meta.TransferSyntaxUID
        assert data[1] == ds.PatientName

    def test_pixel_array_8bit_un_signed(self):
        """Test pixel_array for 8-bit unsigned -> signed data."""
        ds = dcmread(EXPL_8_1_1F)
        # 0 is unsigned int, 1 is 2's complement
        assert ds.PixelRepresentation == 0
        ds.PixelRepresentation = 1
        arr = ds.pixel_array
        ref = dcmread(EXPL_8_1_1F)

        assert not np.array_equal(arr, ref.pixel_array)
        assert (600, 800) == arr.shape
        assert -12 == arr[0].min() == arr[0].max()
        assert (1, -10, 1) == tuple(arr[300, 491:494])
        assert 0 == arr[-1].min() == arr[-1].max()

    def test_pixel_array_16bit_un_signed(self):
        """Test pixel_array for 16-bit unsigned -> signed."""
        ds = dcmread(EXPL_16_3_1F)
        # 0 is unsigned int, 1 is 2's complement
        assert ds.PixelRepresentation == 0
        ds.PixelRepresentation = 1
        arr = ds.pixel_array
        ref = dcmread(EXPL_16_3_1F)

        assert not np.array_equal(arr, ref.pixel_array)
        assert (100, 100, 3) == arr.shape
        assert -1 == arr[0, :, 0].min() == arr[0, :, 0].max()
        assert -32640 == arr[50, :, 0].min() == arr[50, :, 0].max()

    def test_pixel_array_32bit_un_signed(self):
        """Test pixel_array for 32-bit unsigned -> signed."""
        ds = dcmread(EXPL_32_3_1F)
        # 0 is unsigned int, 1 is 2's complement
        assert ds.PixelRepresentation == 0
        ds.PixelRepresentation = 1
        arr = ds.pixel_array
        ref = dcmread(EXPL_32_3_1F)

        assert not np.array_equal(arr, ref.pixel_array)
        assert (100, 100, 3) == arr.shape
        assert -1 == arr[0, :, 0].min() == arr[0, :, 0].max()
        assert -2139062144 == arr[50, :, 0].min() == arr[50, :, 0].max()

    # Endian independent datasets
    def test_8bit_1sample_1frame(self):
        """Test pixel_array for 8-bit, 1 sample/pixel, 1 frame."""
        # Check supported syntaxes
        ds = dcmread(EXPL_8_1_1F)
        for uid in SUPPORTED_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

            assert arr.flags.writeable

            assert (600, 800) == arr.shape
            assert 244 == arr[0].min() == arr[0].max()
            assert (1, 246, 1) == tuple(arr[300, 491:494])
            assert 0 == arr[-1].min() == arr[-1].max()

    def test_8bit_1sample_2frame(self):
        """Test pixel_array for 8-bit, 1 sample/pixel, 2 frame."""
        # Check supported syntaxes
        ds = dcmread(EXPL_8_1_2F)
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

            assert arr.flags.writeable

            assert (2, 600, 800) == arr.shape
            # Frame 1
            assert 244 == arr[0, 0].min() == arr[0, 0].max()
            assert (1, 246, 1) == tuple(arr[0, 300, 491:494])
            assert 0 == arr[0, -1].min() == arr[0, -1].max()
            # Frame 2 is frame 1 inverted
            assert np.array_equal((2**ds.BitsAllocated - 1) - arr[1], arr[0])

    def test_8bit_3sample_1frame_odd_size(self):
        """Test pixel_array for odd sized (3x3) pixel data."""
        # Check supported syntaxes
        ds = dcmread(EXPL_8_3_1F_ODD)
        for uid in SUPPORTED_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

            assert ds.pixel_array[0].tolist() == [
                [166, 141, 52], [166, 141, 52], [166, 141, 52]
            ]
            assert ds.pixel_array[1].tolist() == [
                [63, 87, 176], [63, 87, 176], [63, 87, 176]
            ]
            assert ds.pixel_array[2].tolist() == [
                [158, 158, 158], [158, 158, 158], [158, 158, 158]
            ]

    def test_8bit_3sample_1frame(self):
        """Test pixel_array for 8-bit, 3 sample/pixel, 1 frame."""
        # Check supported syntaxes
        ds = dcmread(EXPL_8_3_1F)
        for uid in SUPPORTED_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

            assert arr.flags.writeable

            assert (255, 0, 0) == tuple(arr[5, 50, :])
            assert (255, 128, 128) == tuple(arr[15, 50, :])
            assert (0, 255, 0) == tuple(arr[25, 50, :])
            assert (128, 255, 128) == tuple(arr[35, 50, :])
            assert (0, 0, 255) == tuple(arr[45, 50, :])
            assert (128, 128, 255) == tuple(arr[55, 50, :])
            assert (0, 0, 0) == tuple(arr[65, 50, :])
            assert (64, 64, 64) == tuple(arr[75, 50, :])
            assert (192, 192, 192) == tuple(arr[85, 50, :])
            assert (255, 255, 255) == tuple(arr[95, 50, :])

    def test_8bit_3sample_2frame(self):
        """Test pixel_array for 8-bit, 3 sample/pixel, 2 frame."""
        # Check supported syntaxes
        ds = dcmread(EXPL_8_3_2F)
        for uid in SUPPORTED_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

            assert arr.flags.writeable

            # Frame 1
            frame = arr[0]
            assert (255, 0, 0) == tuple(frame[5, 50, :])
            assert (255, 128, 128) == tuple(frame[15, 50, :])
            assert (0, 255, 0) == tuple(frame[25, 50, :])
            assert (128, 255, 128) == tuple(frame[35, 50, :])
            assert (0, 0, 255) == tuple(frame[45, 50, :])
            assert (128, 128, 255) == tuple(frame[55, 50, :])
            assert (0, 0, 0) == tuple(frame[65, 50, :])
            assert (64, 64, 64) == tuple(frame[75, 50, :])
            assert (192, 192, 192) == tuple(frame[85, 50, :])
            assert (255, 255, 255) == tuple(frame[95, 50, :])
            # Frame 2 is frame 1 inverted
            assert np.array_equal((2**ds.BitsAllocated - 1) - arr[1], arr[0])

    # Little endian datasets
    @pytest.mark.parametrize('fpath, data', REFERENCE_DATA_LITTLE)
    def test_properties(self, fpath, data):
        """Test dataset and pixel array properties are as expected."""
        ds = dcmread(fpath)
        assert ds.file_meta.TransferSyntaxUID == data[0]
        assert ds.BitsAllocated == data[1]
        assert ds.SamplesPerPixel == data[2]
        assert ds.PixelRepresentation == data[3]
        assert getattr(ds, 'NumberOfFrames', 1) == data[4]

        # Check all little endian syntaxes
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array
            assert data[5] == arr.shape
            assert arr.dtype == data[6]

            # Default to 1 if element not present
            nr_frames = getattr(ds, 'NumberOfFrames', 1)
            # Odd sized data is padded by a final 0x00 byte
            size = ds.Rows * ds.Columns * nr_frames * data[1] / 8 * data[2]
            assert len(ds.PixelData) == size + size % 2
            if size % 2:
                assert ds.PixelData[-1] == b'\x00'[0]

    def test_little_1bit_1sample_1frame(self):
        """Test pixel_array for little 1-bit, 1 sample/pixel, 1 frame."""
        # Check all little endian syntaxes
        ds = dcmread(EXPL_1_1_1F)
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

            assert arr.flags.writeable

            assert arr.max() == 1
            assert arr.min() == 0

            assert (0, 1, 1) == tuple(arr[155, 180:183])
            assert (1, 0, 1, 0) == tuple(arr[155, 310:314])
            assert (0, 1, 1) == tuple(arr[254, 78:81])
            assert (1, 0, 0, 1, 1, 0) == tuple(arr[254, 304:310])

    def test_little_1bit_1sample_3frame(self):
        """Test pixel_array for little 1-bit, 1 sample/pixel, 3 frame."""
        # Check all little endian syntaxes
        ds = dcmread(EXPL_1_1_3F)
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

            assert arr.flags.writeable

            assert arr.max() == 1
            assert arr.min() == 0

            # Frame 1
            assert (0, 1, 1) == tuple(arr[0, 155, 180:183])
            assert (1, 0, 1, 0) == tuple(arr[0, 155, 310:314])
            assert (0, 1, 1) == tuple(arr[0, 254, 78:81])
            assert (1, 0, 0, 1, 1, 0) == tuple(arr[0, 254, 304:310])

            assert 0 == arr[0][0][0]
            assert 0 == arr[2][511][511]
            assert 1 == arr[1][256][256]

            # Frame 2
            assert 0 == arr[1, 146, :254].max()
            assert (0, 1, 1, 1, 1, 1, 0, 1) == tuple(arr[1, 146, 253:261])
            assert 0 == arr[1, 146, 261:].max()

            assert 0 == arr[1, 210, :97].max()
            assert 1 == arr[1, 210, 97:350].max()
            assert 0 == arr[1, 210, 350:].max()

            # Frame 3
            assert 0 == arr[2, 147, :249].max()
            assert (0, 1, 0, 1, 1, 1) == tuple(arr[2, 147, 248:254])
            assert (1, 0, 1, 0, 1, 1) == tuple(arr[2, 147, 260:266])
            assert 0 == arr[2, 147, 283:].max()

            assert 0 == arr[2, 364, :138].max()
            assert (0, 1, 0, 1, 1, 0, 0, 1) == tuple(arr[2, 364, 137:145])
            assert (1, 0, 0, 1, 0) == tuple(arr[2, 364, 152:157])
            assert 0 == arr[2, 364, 157:].max()

    @pytest.mark.skip(reason='No suitable dataset available')
    def test_little_1bit_3sample_1frame(self):
        """Test pixel_array for little 1-bit, 3 sample/pixel, 1 frame."""
        # Check all little endian syntaxes
        ds = dcmread(None)
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    @pytest.mark.skip(reason='No suitable dataset available')
    def test_little_1bit_3sample_10frame(self):
        """Test pixel_array for little 1-bit, 3 sample/pixel, 10 frame."""
        # Check all little endian syntaxes
        ds = dcmread(None)
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

    def test_little_16bit_1sample_1frame(self):
        """Test pixel_array for little 16-bit, 1 sample/pixel, 1 frame."""
        # Check all little endian syntaxes
        ds = dcmread(EXPL_16_1_1F)
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

            assert arr.flags.writeable

            assert (422, 319, 361) == tuple(arr[0, 31:34])
            assert (366, 363, 322) == tuple(arr[31, :3])
            assert (1369, 1129, 862) == tuple(arr[-1, -3:])

    def test_little_16bit_1sample_10frame(self):
        """Test pixel_array for little 16-bit, 1 sample/pixel, 10 frame."""
        # Check all little endian syntaxes
        ds = dcmread(EXPL_16_1_10F)
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

            assert arr.flags.writeable

            # Frame 1
            assert (206, 197, 159) == tuple(arr[0, 0, 31:34])
            assert (49, 78, 128) == tuple(arr[0, 31, :3])
            assert (362, 219, 135) == tuple(arr[0, -1, -3:])
            # Frame 5
            assert (67, 82, 44) == tuple(arr[4, 0, 31:34])
            assert (37, 41, 17) == tuple(arr[4, 31, :3])
            assert (225, 380, 355) == tuple(arr[4, -1, -3:])
            # Frame 10
            assert (72, 86, 69) == tuple(arr[-1, 0, 31:34])
            assert (25, 4, 9) == tuple(arr[-1, 31, :3])
            assert (227, 300, 147) == tuple(arr[-1, -1, -3:])

    def test_little_16bit_3sample_1frame(self):
        """Test pixel_array for little 16-bit, 3 sample/pixel, 1 frame."""
        # Check all little endian syntaxes
        ds = dcmread(EXPL_16_3_1F)
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

            assert arr.flags.writeable

            assert (65535, 0, 0) == tuple(arr[5, 50, :])
            assert (65535, 32896, 32896) == tuple(arr[15, 50, :])
            assert (0, 65535, 0) == tuple(arr[25, 50, :])
            assert (32896, 65535, 32896) == tuple(arr[35, 50, :])
            assert (0, 0, 65535) == tuple(arr[45, 50, :])
            assert (32896, 32896, 65535) == tuple(arr[55, 50, :])
            assert (0, 0, 0) == tuple(arr[65, 50, :])
            assert (16448, 16448, 16448) == tuple(arr[75, 50, :])
            assert (49344, 49344, 49344) == tuple(arr[85, 50, :])
            assert (65535, 65535, 65535) == tuple(arr[95, 50, :])

    def test_little_16bit_3sample_2frame(self):
        """Test pixel_array for little 16-bit, 3 sample/pixel, 2 frame."""
        # Check all little endian syntaxes
        ds = dcmread(EXPL_16_3_2F)
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

            assert arr.flags.writeable

            # Frame 1
            assert (65535, 0, 0) == tuple(arr[0, 5, 50, :])
            assert (65535, 32896, 32896) == tuple(arr[0, 15, 50, :])
            assert (0, 65535, 0) == tuple(arr[0, 25, 50, :])
            assert (32896, 65535, 32896) == tuple(arr[0, 35, 50, :])
            assert (0, 0, 65535) == tuple(arr[0, 45, 50, :])
            assert (32896, 32896, 65535) == tuple(arr[0, 55, 50, :])
            assert (0, 0, 0) == tuple(arr[0, 65, 50, :])
            assert (16448, 16448, 16448) == tuple(arr[0, 75, 50, :])
            assert (49344, 49344, 49344) == tuple(arr[0, 85, 50, :])
            assert (65535, 65535, 65535) == tuple(arr[0, 95, 50, :])
            # Frame 2 is frame 1 inverted
            assert np.array_equal((2**ds.BitsAllocated - 1) - arr[1], arr[0])

    def test_little_32bit_1sample_1frame(self):
        """Test pixel_array for little 32-bit, 1 sample/pixel, 1 frame."""
        # Check all little endian syntaxes
        ds = dcmread(IMPL_32_1_1F)
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

            assert arr.flags.writeable

            assert (1249000, 1249000, 1250000) == tuple(arr[0, :3])
            assert (1031000, 1029000, 1027000) == tuple(arr[4, 3:6])
            assert (803000, 801000, 798000) == tuple(arr[-1, -3:])

    def test_little_32bit_1sample_15frame(self):
        """Test pixel_array for little 32-bit, 1 sample/pixel, 15 frame."""
        # Check all little endian syntaxes
        ds = dcmread(IMPL_32_1_15F)
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

            assert arr.flags.writeable

            # Frame 1
            assert (1249000, 1249000, 1250000) == tuple(arr[0, 0, :3])
            assert (1031000, 1029000, 1027000) == tuple(arr[0, 4, 3:6])
            assert (803000, 801000, 798000) == tuple(arr[0, -1, -3:])
            # Frame 8
            assert (1253000, 1253000, 1249000) == tuple(arr[7, 0, :3])
            assert (1026000, 1023000, 1022000) == tuple(arr[7, 4, 3:6])
            assert (803000, 803000, 803000) == tuple(arr[7, -1, -3:])
            # Frame 15
            assert (1249000, 1250000, 1251000) == tuple(arr[-1, 0, :3])
            assert (1031000, 1031000, 1031000) == tuple(arr[-1, 4, 3:6])
            assert (801000, 800000, 799000) == tuple(arr[-1, -1, -3:])

    def test_little_32bit_3sample_1frame(self):
        """Test pixel_array for little 32-bit, 3 sample/pixel, 1 frame."""
        # Check all little endian syntaxes
        ds = dcmread(EXPL_32_3_1F)
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            ar = ds.pixel_array

            assert ar.flags.writeable

            assert (4294967295, 0, 0) == tuple(ar[5, 50, :])
            assert (4294967295, 2155905152, 2155905152) == tuple(ar[15, 50, :])
            assert (0, 4294967295, 0) == tuple(ar[25, 50, :])
            assert (2155905152, 4294967295, 2155905152) == tuple(ar[35, 50, :])
            assert (0, 0, 4294967295) == tuple(ar[45, 50, :])
            assert (2155905152, 2155905152, 4294967295) == tuple(ar[55, 50, :])
            assert (0, 0, 0) == tuple(ar[65, 50, :])
            assert (1077952576, 1077952576, 1077952576) == tuple(ar[75, 50, :])
            assert (3233857728, 3233857728, 3233857728) == tuple(ar[85, 50, :])
            assert (4294967295, 4294967295, 4294967295) == tuple(ar[95, 50, :])

    def test_little_32bit_3sample_2frame(self):
        """Test pixel_array for little 32-bit, 3 sample/pixel, 10 frame."""
        # Check all little endian syntaxes
        ds = dcmread(EXPL_32_3_2F)
        for uid in SUPPORTED_SYNTAXES[:3]:
            ds.file_meta.TransferSyntaxUID = uid
            arr = ds.pixel_array

            assert arr.flags.writeable

            # Frame 1
            assert (4294967295, 0, 0) == tuple(arr[0, 5, 50, :])
            assert (4294967295, 2155905152, 2155905152) == tuple(
                arr[0, 15, 50, :]
            )
            assert (0, 4294967295, 0) == tuple(arr[0, 25, 50, :])
            assert (2155905152, 4294967295, 2155905152) == tuple(
                arr[0, 35, 50, :]
            )
            assert (0, 0, 4294967295) == tuple(arr[0, 45, 50, :])
            assert (2155905152, 2155905152, 4294967295) == tuple(
                arr[0, 55, 50, :]
            )
            assert (0, 0, 0) == tuple(arr[0, 65, 50, :])
            assert (1077952576, 1077952576, 1077952576) == tuple(
                arr[0, 75, 50, :]
            )
            assert (3233857728, 3233857728, 3233857728) == tuple(
                arr[0, 85, 50, :]
            )
            assert (4294967295, 4294967295, 4294967295) == tuple(
                arr[0, 95, 50, :]
            )
            # Frame 2 is frame 1 inverted
            assert np.array_equal((2**ds.BitsAllocated - 1) - arr[1], arr[0])

    # Big endian datasets
    @pytest.mark.parametrize('little, big', MATCHING_DATASETS)
    def test_big_endian_datasets(self, little, big):
        """Test pixel_array for big endian matches little."""
        ds = dcmread(big)
        assert ds.file_meta.TransferSyntaxUID == ExplicitVRBigEndian
        ref = dcmread(little)
        assert ref.file_meta.TransferSyntaxUID != ExplicitVRBigEndian
        assert np.array_equal(ds.pixel_array, ref.pixel_array)

    # Regression tests
    def test_endianness_not_set(self):
        """Test for #704, Dataset.is_little_endian unset."""
        ds = Dataset()
        ds.file_meta = Dataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.Rows = 10
        ds.Columns = 10
        ds.BitsAllocated = 16
        ds.PixelRepresentation = 0
        ds.SamplesPerPixel = 1
        arr = np.ones((10, 10), dtype='uint16')
        ds.PixelData = arr.tobytes()

        assert ds.pixel_array.max() == 1

    def test_read_only(self):
        """Test for #717, returned array read-only."""
        ds = dcmread(EXPL_8_1_1F)
        arr = ds.pixel_array
        assert 0 != arr[0, 0]
        arr[0, 0] = 0
        assert 0 == arr[0, 0]
        assert arr.flags.writeable


# Tests for numpy_handler module with Numpy available
@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class TestNumpy_GetPixelData(object):
    """Tests for numpy_handler.get_pixeldata with numpy."""
    def test_no_pixel_data_raises(self):
        """Test get_pixeldata raises if dataset has no PixelData."""
        ds = dcmread(EXPL_16_1_1F)
        del ds.PixelData
        assert 'PixelData' not in ds
        with pytest.raises(AttributeError, match=' dataset: PixelData'):
            get_pixeldata(ds)

    def test_unknown_pixel_representation_raises(self):
        """Test get_pixeldata raises if unsupported PixelRepresentation."""
        ds = dcmread(EXPL_16_1_1F)
        ds.PixelRepresentation = 2
        with pytest.raises(ValueError,
                           match=r"value of '2' for '\(0028,0103"):
            get_pixeldata(ds)

    def test_unsupported_syntaxes_raises(self):
        """Test get_pixeldata raises if unsupported Transfer Syntax."""
        ds = dcmread(EXPL_16_1_1F)
        ds.file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.4.50'
        with pytest.raises(NotImplementedError,
                           match=' the transfer syntax is not supported'):
            get_pixeldata(ds)

    def test_bad_length_raises(self):
        """Test bad pixel data length raises exception."""
        ds = dcmread(EXPL_8_1_1F)
        # Too short
        ds.PixelData = ds.PixelData[:-1]
        msg = (
            r"The length of the pixel data in the dataset doesn't match the "
            r"expected amount \(479999 vs. 480000 bytes\). The dataset may be "
            r"corrupted or there may be an issue with the pixel data handler."
        )
        with pytest.raises(ValueError, match=msg):
            get_pixeldata(ds)

        # Too long
        ds.PixelData += b'\x00\x00'
        with pytest.raises(ValueError, match=r"480001 vs. 480000 bytes"):
            get_pixeldata(ds)

    def test_change_photometric_interpretation(self):
        """Test get_pixeldata changes PhotometricInterpretation if required."""
        def to_rgb(ds):
            """Override the original function that returned False"""
            return True

        # Test default
        ds = dcmread(EXPL_16_1_1F)
        assert ds.PhotometricInterpretation == 'MONOCHROME2'

        get_pixeldata(ds)
        assert ds.PhotometricInterpretation == 'MONOCHROME2'

        # Test modified
        orig_fn = NP_HANDLER.should_change_PhotometricInterpretation_to_RGB
        NP_HANDLER.should_change_PhotometricInterpretation_to_RGB = to_rgb

        get_pixeldata(ds)
        assert ds.PhotometricInterpretation == 'RGB'

        NP_HANDLER.should_change_PhotometricInterpretation_to_RGB = orig_fn

    def test_array_read_only(self):
        """Test returning a read only array for BitsAllocated > 8."""
        ds = dcmread(EXPL_8_1_1F)
        arr = get_pixeldata(ds, read_only=False)
        assert arr.flags.writeable
        assert 0 != arr[10]
        arr[10] = 0
        assert 0 == arr[10]

        arr = get_pixeldata(ds, read_only=True)
        assert not arr.flags.writeable
        with pytest.raises(ValueError, match="is read-only"):
            arr[10] = 0

    def test_array_read_only_bit_packed(self):
        """Test returning a read only array for BitsAllocated = 1."""
        ds = dcmread(EXPL_1_1_1F)
        arr = get_pixeldata(ds, read_only=False)
        assert arr.flags.writeable

        arr = get_pixeldata(ds, read_only=True)
        assert arr.flags.writeable


REFERENCE_PACK_UNPACK = [
    (b'', []),
    (b'\x00', [0, 0, 0, 0, 0, 0, 0, 0]),
    (b'\x01', [1, 0, 0, 0, 0, 0, 0, 0]),
    (b'\x02', [0, 1, 0, 0, 0, 0, 0, 0]),
    (b'\x04', [0, 0, 1, 0, 0, 0, 0, 0]),
    (b'\x08', [0, 0, 0, 1, 0, 0, 0, 0]),
    (b'\x10', [0, 0, 0, 0, 1, 0, 0, 0]),
    (b'\x20', [0, 0, 0, 0, 0, 1, 0, 0]),
    (b'\x40', [0, 0, 0, 0, 0, 0, 1, 0]),
    (b'\x80', [0, 0, 0, 0, 0, 0, 0, 1]),
    (b'\xAA', [0, 1, 0, 1, 0, 1, 0, 1]),
    (b'\xF0', [0, 0, 0, 0, 1, 1, 1, 1]),
    (b'\x0F', [1, 1, 1, 1, 0, 0, 0, 0]),
    (b'\xFF', [1, 1, 1, 1, 1, 1, 1, 1]),
    #              | 1st byte              | 2nd byte
    (b'\x00\x00', [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
    (b'\x00\x01', [0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0]),
    (b'\x00\x80', [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b'\x00\xFF', [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1]),
    (b'\x01\x80', [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b'\x80\x80', [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b'\xFF\x80', [1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 1]),
]


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestNumpy_UnpackBits(object):
    """Tests for numpy_handler.unpack_bits."""
    @pytest.mark.parametrize('input, output', REFERENCE_PACK_UNPACK)
    def test_unpack(self, input, output):
        """Test unpacking data."""
        assert np.array_equal(np.asarray(output), unpack_bits(input))


REFERENCE_PACK_PARTIAL = [
    #              | 1st byte              | 2nd byte
    (b'\x00\x40', [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),  # 15-bits
    (b'\x00\x20', [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b'\x00\x10', [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b'\x00\x08', [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b'\x00\x04', [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b'\x00\x02', [0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b'\x00\x01', [0, 0, 0, 0, 0, 0, 0, 0, 1]),  # 9-bits
    (b'\x80', [0, 0, 0, 0, 0, 0, 0, 1]),  # 8-bits
    (b'\x40', [0, 0, 0, 0, 0, 0, 1]),
    (b'\x20', [0, 0, 0, 0, 0, 1]),
    (b'\x10', [0, 0, 0, 0, 1]),
    (b'\x08', [0, 0, 0, 1]),
    (b'\x04', [0, 0, 1]),
    (b'\x02', [0, 1]),
    (b'\x01', [1]),
    (b'', []),
]


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestNumpy_PackBits(object):
    """Tests for numpy_handler.pack_bits."""
    @pytest.mark.parametrize('output, input', REFERENCE_PACK_UNPACK)
    def test_pack(self, input, output):
        """Test packing data."""
        assert output == pack_bits(np.asarray(input))

    def test_non_binary_input(self):
        """Test non-binary input raises exception."""
        with pytest.raises(ValueError,
                           match=r"Only binary arrays \(containing ones or"):
            pack_bits(np.asarray([0, 0, 2, 0, 0, 0, 0, 0]))

    def test_non_array_input(self):
        """Test non 1D input raises exception."""
        with pytest.raises(ValueError, match='Only 1D arrays are supported'):
            pack_bits(
                np.asarray(
                    [[0, 0, 0, 0, 0, 0, 0, 0],
                     [1, 0, 1, 0, 1, 0, 1, 0]]
                )
            )

    @pytest.mark.parametrize('output, input', REFERENCE_PACK_PARTIAL)
    def test_pack_partial(self, input, output):
        """Test packing data that isn't a full byte long."""
        assert output == pack_bits(np.asarray(input))

    def test_functional(self):
        """Test against a real dataset."""
        ds = dcmread(EXPL_1_1_3F)
        arr = ds.pixel_array
        arr = arr.ravel()
        assert ds.PixelData == pack_bits(arr)


REFERENCE_LENGTH = [
    # (frames, rows, cols, samples), bit depth, result in (bytes, pixels)
    # No 'NumberOfFrames' in dataset
    ((0, 0, 0, 0), 1, (0, 0)),
    ((0, 1, 1, 1), 1, (1, 1)),  # 1 bit -> 1 byte
    ((0, 1, 1, 3), 1, (1, 3)),  # 3 bits -> 1 byte
    ((0, 1, 3, 3), 1, (2, 9)),  # 9 bits -> 2 bytes
    ((0, 2, 2, 1), 1, (1, 4)),  # 4 bits -> 1 byte
    ((0, 2, 4, 1), 1, (1, 8)),  # 8 bits -> 1 byte
    ((0, 3, 3, 1), 1, (2, 9)),  # 9 bits -> 2 bytes
    ((0, 512, 512, 1), 1, (32768, 262144)),  # Typical length
    ((0, 512, 512, 3), 1, (98304, 786432)),
    ((0, 0, 0, 0), 8, (0, 0)),
    ((0, 1, 1, 1), 8, (1, 1)),  # Odd length
    ((0, 9, 1, 1), 8, (9, 9)),  # Odd length
    ((0, 1, 2, 1), 8, (2, 2)),  # Even length
    ((0, 512, 512, 1), 8, (262144, 262144)),
    ((0, 512, 512, 3), 8, (786432, 786432)),
    ((0, 0, 0, 0), 16, (0, 0)),
    ((0, 1, 1, 1), 16, (2, 1)),  # 16 bit data can't be odd length
    ((0, 1, 2, 1), 16, (4, 2)),
    ((0, 512, 512, 1), 16, (524288, 262144)),
    ((0, 512, 512, 3), 16, (1572864, 786432)),
    ((0, 0, 0, 0), 32, (0, 0)),
    ((0, 1, 1, 1), 32, (4, 1)),  # 32 bit data can't be odd length
    ((0, 1, 2, 1), 32, (8, 2)),
    ((0, 512, 512, 1), 32, (1048576, 262144)),
    ((0, 512, 512, 3), 32, (3145728, 786432)),
    # NumberOfFrames odd
    ((3, 0, 0, 0), 1, (0, 0)),
    ((3, 1, 1, 1), 1, (1, 3)),
    ((3, 1, 1, 3), 1, (2, 9)),
    ((3, 1, 3, 3), 1, (4, 27)),
    ((3, 2, 4, 1), 1, (3, 24)),
    ((3, 2, 2, 1), 1, (2, 12)),
    ((3, 3, 3, 1), 1, (4, 27)),
    ((3, 512, 512, 1), 1, (98304, 786432)),
    ((3, 512, 512, 3), 1, (294912, 2359296)),
    ((3, 0, 0, 0), 8, (0, 0)),
    ((3, 1, 1, 1), 8, (3, 3)),
    ((3, 9, 1, 1), 8, (27, 27)),
    ((3, 1, 2, 1), 8, (6, 6)),
    ((3, 512, 512, 1), 8, (786432, 786432)),
    ((3, 512, 512, 3), 8, (2359296, 2359296)),
    ((3, 0, 0, 0), 16, (0, 0)),
    ((3, 512, 512, 1), 16, (1572864, 786432)),
    ((3, 512, 512, 3), 16, (4718592, 2359296)),
    ((3, 0, 0, 0), 32, (0, 0)),
    ((3, 512, 512, 1), 32, (3145728, 786432)),
    ((3, 512, 512, 3), 32, (9437184, 2359296)),
    # NumberOfFrames even
    ((4, 0, 0, 0), 1, (0, 0)),
    ((4, 1, 1, 1), 1, (1, 4)),
    ((4, 1, 1, 3), 1, (2, 12)),
    ((4, 1, 3, 3), 1, (5, 36)),
    ((4, 2, 4, 1), 1, (4, 32)),
    ((4, 2, 2, 1), 1, (2, 16)),
    ((4, 3, 3, 1), 1, (5, 36)),
    ((4, 512, 512, 1), 1, (131072, 1048576)),
    ((4, 512, 512, 3), 1, (393216, 3145728)),
    ((4, 0, 0, 0), 8, (0, 0)),
    ((4, 512, 512, 1), 8, (1048576, 1048576)),
    ((4, 512, 512, 3), 8, (3145728, 3145728)),
    ((4, 0, 0, 0), 16, (0, 0)),
    ((4, 512, 512, 1), 16, (2097152, 1048576)),
    ((4, 512, 512, 3), 16, (6291456, 3145728)),
    ((4, 0, 0, 0), 32, (0, 0)),
    ((4, 512, 512, 1), 32, (4194304, 1048576)),
    ((4, 512, 512, 3), 32, (12582912, 3145728)),
]


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestNumpy_GetExpectedLength(object):
    """Tests for numpy_handler.get_expected_length."""
    @pytest.mark.parametrize('shape, bits, length', REFERENCE_LENGTH)
    def test_length_in_bytes(self, shape, bits, length):
        """Test get_expected_length(ds, unit='bytes')."""
        ds = Dataset()
        ds.Rows = shape[1]
        ds.Columns = shape[2]
        ds.BitsAllocated = bits
        if shape[0] != 0:
            ds.NumberOfFrames = shape[0]
        ds.SamplesPerPixel = shape[3]

        assert length[0] == get_expected_length(ds, unit='bytes')

    @pytest.mark.parametrize('shape, bits, length', REFERENCE_LENGTH)
    def test_length_in_pixels(self, shape, bits, length):
        """Test get_expected_length(ds, unit='pixels')."""
        ds = Dataset()
        ds.Rows = shape[1]
        ds.Columns = shape[2]
        ds.BitsAllocated = bits
        if shape[0] != 0:
            ds.NumberOfFrames = shape[0]
        ds.SamplesPerPixel = shape[3]

        assert length[1] == get_expected_length(ds, unit='pixels')
