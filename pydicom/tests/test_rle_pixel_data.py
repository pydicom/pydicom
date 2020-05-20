# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Tests for the pixel_data_handlers.rle_handler module.

There are the following possibilities:

* numpy is not available and
  * the RLE handler is not available
  * the RLE handler is available
* numpy is available and
  * The RLE handler is not available
  * The RLE handler is available

**Supported transfer syntaxes**

* 1.2.840.10008.1.2.5 : RLE Lossless

**Elements affecting the handler**

* PixelRepresentation (0, 1)
* BitsAllocated (1, 8, 16, 32, ...)
* SamplesPerPixel (1, 2, 3, ...)
* NumberOfFrames (1, 2, ...)
"""

from struct import pack, unpack
import sys

import pytest

from pydicom import dcmread, Dataset, config
import pydicom.config
from pydicom.data import get_testdata_files
from pydicom.dataset import FileMetaDataset
from pydicom.encaps import defragment_data
from pydicom.uid import RLELossless, UID
from pydicom.tests._handler_common import ALL_TRANSFER_SYNTAXES

try:
    import numpy as np
    from pydicom.pixel_data_handlers import numpy_handler as NP_HANDLER
    from pydicom.pixel_data_handlers.util import reshape_pixel_array
    HAVE_NP = NP_HANDLER.HAVE_NP
except ImportError:
    NP_HANDLER = None
    HAVE_NP = False

try:
    from pydicom.pixel_data_handlers import rle_handler as RLE_HANDLER
    from pydicom.pixel_data_handlers.rle_handler import (
        get_pixeldata,
        _rle_decode_frame,
        _rle_decode_segment,
        _parse_rle_header,
        rle_encode_frame,
        _rle_encode_plane,
        _rle_encode_segment,
        _rle_encode_row,
    )
    HAVE_RLE = RLE_HANDLER.HAVE_RLE
except ImportError:
    HAVE_RLE = False
    RLE_HANDLER = None


# Paths to the test datasets
# EXPL: Explicit VR Little Endian
# RLE: RLE Lossless
# 8/8-bit, 1 sample/pixel, 1 frame
EXPL_8_1_1F = get_testdata_files("OBXXXX1A.dcm")[0]
RLE_8_1_1F = get_testdata_files("OBXXXX1A_rle.dcm")[0]
# 8/8-bit, 1 sample/pixel, 2 frame
EXPL_8_1_2F = get_testdata_files("OBXXXX1A_2frame.dcm")[0]
RLE_8_1_2F = get_testdata_files("OBXXXX1A_rle_2frame.dcm")[0]
# 8/8-bit, 3 sample/pixel, 1 frame
EXPL_8_3_1F = get_testdata_files("SC_rgb.dcm")[0]
RLE_8_3_1F = get_testdata_files("SC_rgb_rle.dcm")[0]
# 8/8-bit, 3 sample/pixel, 2 frame
EXPL_8_3_2F = get_testdata_files("SC_rgb_2frame.dcm")[0]
RLE_8_3_2F = get_testdata_files("SC_rgb_rle_2frame.dcm")[0]
# 16/16-bit, 1 sample/pixel, 1 frame
EXPL_16_1_1F = get_testdata_files("MR_small.dcm")[0]
RLE_16_1_1F = get_testdata_files("MR_small_RLE.dcm")[0]
# 16/12-bit, 1 sample/pixel, 10 frame
EXPL_16_1_10F = get_testdata_files("emri_small.dcm")[0]
RLE_16_1_10F = get_testdata_files("emri_small_RLE.dcm")[0]
# 16/16-bit, 3 sample/pixel, 1 frame
EXPL_16_3_1F = get_testdata_files("SC_rgb_16bit.dcm")[0]
RLE_16_3_1F = get_testdata_files("SC_rgb_rle_16bit.dcm")[0]
# 16/16-bit, 3 sample/pixel, 2 frame
EXPL_16_3_2F = get_testdata_files("SC_rgb_16bit_2frame.dcm")[0]
RLE_16_3_2F = get_testdata_files("SC_rgb_rle_16bit_2frame.dcm")[0]
# 32/32-bit, 1 sample/pixel, 1 frame
EXPL_32_1_1F = get_testdata_files("rtdose_1frame.dcm")[0]
RLE_32_1_1F = get_testdata_files("rtdose_rle_1frame.dcm")[0]
# 32/32-bit, 1 sample/pixel, 15 frame
EXPL_32_1_15F = get_testdata_files("rtdose.dcm")[0]
RLE_32_1_15F = get_testdata_files("rtdose_rle.dcm")[0]
# 32/32-bit, 3 sample/pixel, 1 frame
EXPL_32_3_1F = get_testdata_files("SC_rgb_32bit.dcm")[0]
RLE_32_3_1F = get_testdata_files("SC_rgb_rle_32bit.dcm")[0]
# 32/32-bit, 3 sample/pixel, 2 frame
EXPL_32_3_2F = get_testdata_files("SC_rgb_32bit_2frame.dcm")[0]
RLE_32_3_2F = get_testdata_files("SC_rgb_rle_32bit_2frame.dcm")[0]

# Transfer syntaxes supported by other handlers
# Implicit VR Little Endian
IMPL = get_testdata_files("rtdose_1frame.dcm")[0]
# Deflated Explicit VR Little Endian
DELF = get_testdata_files("image_dfl.dcm")[0]
# Explicit VR Big Endian
EXPB = get_testdata_files("SC_rgb_expb_2frame.dcm")[0]
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
SUPPORTED_SYNTAXES = [RLELossless]
UNSUPPORTED_SYNTAXES = list(
    set(ALL_TRANSFER_SYNTAXES) ^ set(SUPPORTED_SYNTAXES)
)


def test_unsupported_syntaxes():
    """Test that UNSUPPORTED_SYNTAXES is as expected."""
    assert RLELossless not in UNSUPPORTED_SYNTAXES


def _get_pixel_array(fpath):
    """Return the pixel data as a numpy ndarray.

    Only suitable for transfer syntaxes supported by the numpy pixel data
    handler.

    Parameters
    ----------
    fpath : str
        Path to the dataset containing the Pixel Data.

    Returns
    -------
    numpy.ndarray
    """
    if not HAVE_NP:
        raise RuntimeError(
            'Function only usable if the numpy handler is available'
        )

    original_handlers = pydicom.config.pixel_data_handlers
    pydicom.config.pixel_data_handlers = [NP_HANDLER]

    ds = dcmread(fpath)
    arr = ds.pixel_array

    pydicom.config.pixel_data_handlers = original_handlers

    return arr


REFERENCE_DATA_UNSUPPORTED = [
    (IMPL, ('1.2.840.10008.1.2', 'Lastname^Firstname')),
    (EXPL_8_3_1F, ('1.2.840.10008.1.2.1', 'Lestrade^G')),
    (DELF, ('1.2.840.10008.1.2.1.99', '^^^^')),
    (EXPB, ('1.2.840.10008.1.2.2', 'Lestrade^G')),
    (JPEG_BASELINE_1, ('1.2.840.10008.1.2.4.50', 'Lestrade^G')),
    (JPEG_EXTENDED_2, ('1.2.840.10008.1.2.4.51', 'CompressedSamples^NM1')),
    # (JPEG_LOSSLESS_14, ('1.2.840.10008.1.2.4.57')),  # No dataset available
    (JPEG_LOSSLESS_14_1, ('1.2.840.10008.1.2.4.70', 'Lestrade^G')),
    (JPEG_LS_LOSSLESS, ('1.2.840.10008.1.2.4.80', 'CompressedSamples^MR1')),
    # (JPEG_LS_LOSSY, ('1.2.840.10008.1.2.4.81')),  # No dataset available
    (JPEG_2K_LOSSLESS, ('1.2.840.10008.1.2.4.90', '')),
    (JPEG_2K, ('1.2.840.10008.1.2.4.91', 'CompressedSamples^NM1')),
]


# Numpy and the RLE handler are unavailable
@pytest.mark.skipif(HAVE_NP, reason='Numpy is available')
class TestNoNumpy_NoRLEHandler:
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
        # The RLE handler should still be available
        assert RLE_HANDLER is not None

    def test_can_access_supported_dataset(self):
        """Test that we can read and access elements in an RLE dataset."""
        ds = dcmread(RLE_16_1_1F)
        assert 'CompressedSamples^MR1' == ds.PatientName
        assert 6128 == len(ds.PixelData)

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
            exc_msg = (
                r"Unable to decode pixel data with a transfer syntax UID of "
                r"'{}'".format(uid)
            )
            with pytest.raises(NotImplementedError, match=exc_msg):
                ds.pixel_array


# Numpy unavailable and the RLE handler is available
@pytest.mark.skipif(HAVE_NP, reason='Numpy is available')
class TestNoNumpy_RLEHandler:
    """Tests for handling datasets without numpy and the handler."""
    def setup(self):
        """Setup the environment."""
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [RLE_HANDLER]

    def teardown(self):
        """Restore the environment."""
        pydicom.config.pixel_data_handlers = self.original_handlers

    def test_environment(self):
        """Check that the testing environment is as expected."""
        assert not HAVE_NP
        # The RLE handler should still be available
        assert RLE_HANDLER is not None

    def test_can_access_supported_dataset(self):
        """Test that we can read and access elements in an RLE dataset."""
        ds = dcmread(RLE_16_1_1F)
        assert 'CompressedSamples^MR1' == ds.PatientName
        assert 6128 == len(ds.PixelData)

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
            exc_msg = (
                r"Unable to decode pixel data with a transfer syntax UID of "
                r"'{}'".format(uid)
            )
            with pytest.raises(RuntimeError, match=exc_msg):
                ds.pixel_array

    def test_supported_pixel_array_raises(self):
        """Test pixel_array raises exception for supported syntaxes."""
        ds = dcmread(EXPL_16_1_1F)
        for uid in SUPPORTED_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            exc_msg = (
                r"The following handlers are available to decode the pixel "
                r"data however they are missing required dependencies: "
                r"RLE Lossless \(req. NumPy\)"
            )
            with pytest.raises(RuntimeError, match=exc_msg):
                ds.pixel_array


# Numpy is available, the RLE handler is unavailable
@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class TestNumpy_NoRLEHandler:
    """Tests for handling datasets with no handler."""
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
        # The RLE handler should still be available
        assert RLE_HANDLER is not None

    def test_can_access_supported_dataset(self):
        """Test that we can read and access elements in an RLE dataset."""
        ds = dcmread(RLE_16_1_1F)
        assert 'CompressedSamples^MR1' == ds.PatientName
        assert 6128 == len(ds.PixelData)

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
            exc_msg = (
                r"Unable to decode pixel data with a transfer syntax UID of "
                r"'{}'".format(uid)
            )
            with pytest.raises(NotImplementedError, match=exc_msg):
                ds.pixel_array


# Numpy and the RLE handler are available
@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class TestNumpy_RLEHandler:
    """Tests for handling datasets with the handler."""
    def setup(self):
        """Setup the environment."""
        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = [RLE_HANDLER]

    def teardown(self):
        """Restore the environment."""
        pydicom.config.pixel_data_handlers = self.original_handlers

    def test_environment(self):
        """Check that the testing environment is as expected."""
        assert HAVE_NP
        assert RLE_HANDLER is not None

    def test_unsupported_syntax_raises(self):
        """Test pixel_array raises exception for unsupported syntaxes."""
        ds = dcmread(EXPL_16_1_1F)
        for uid in UNSUPPORTED_SYNTAXES:
            ds.file_meta.TransferSyntaxUID = uid
            exc_msg = (
                r"Unable to decode pixel data with a transfer syntax UID of "
                r"'{}'".format(uid)
            )
            with pytest.raises(NotImplementedError, match=exc_msg):
                ds.pixel_array
            with pytest.raises(NotImplementedError, match=exc_msg):
                ds.decompress(handler_name='rle')

    @pytest.mark.parametrize("fpath,data", REFERENCE_DATA_UNSUPPORTED)
    def test_can_access_unsupported_dataset(self, fpath, data):
        """Test can read and access elements in unsupported datasets."""
        ds = dcmread(fpath)
        assert data[0] == ds.file_meta.TransferSyntaxUID
        assert data[1] == ds.PatientName
        assert len(ds.PixelData)

    def test_pixel_array_signed(self):
        """Test pixel_array for unsigned -> signed data."""
        ds = dcmread(RLE_8_1_1F)
        # 0 is unsigned int, 1 is 2's complement
        assert ds.PixelRepresentation == 0
        ds.PixelRepresentation = 1
        ref = _get_pixel_array(EXPL_8_1_1F)
        arr = ds.pixel_array

        assert not np.array_equal(arr, ref)
        assert (600, 800) == arr.shape
        assert -12 == arr[0].min() == arr[0].max()
        assert (1, -10, 1) == tuple(arr[300, 491:494])
        assert 0 == arr[-1].min() == arr[-1].max()

    def test_pixel_array_1bit_raises(self):
        """Test pixel_array for 1-bit raises exception."""
        ds = dcmread(RLE_8_3_1F)
        ds.BitsAllocated = 1
        with pytest.raises(NotImplementedError,
                           match="Bits Allocated' value of 1"):
            ds.pixel_array

    def test_pixel_array_8bit_1sample_1f(self):
        """Test pixel_array for 8-bit, 1 sample/pixel, 1 frame."""
        ds = dcmread(RLE_8_1_1F)
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert ds.BitsAllocated == 8
        assert ds.SamplesPerPixel == 1
        assert 'NumberOfFrames' not in ds
        ref = _get_pixel_array(EXPL_8_1_1F)
        arr = ds.pixel_array

        assert arr.flags.writeable

        assert np.array_equal(arr, ref)
        assert (600, 800) == arr.shape
        assert 244 == arr[0].min() == arr[0].max()
        assert (1, 246, 1) == tuple(arr[300, 491:494])
        assert 0 == arr[-1].min() == arr[-1].max()

    def test_decompress_with_handler(self):
        """Test that decompress works with the correct handler."""
        ds = dcmread(RLE_8_1_1F)
        with pytest.raises(ValueError,
                           match="'zip' is not a known handler name"):
            ds.decompress(handler_name='zip')
        with pytest.raises(NotImplementedError, match='Unable to decode*'):
            ds.decompress(handler_name='numpy')
        ds.decompress(handler_name='rle')
        assert hasattr(ds, '_pixel_array')
        arr = ds.pixel_array
        assert (600, 800) == arr.shape
        assert 244 == arr[0].min() == arr[0].max()
        assert (1, 246, 1) == tuple(arr[300, 491:494])
        assert 0 == arr[-1].min() == arr[-1].max()

    def test_pixel_array_8bit_1sample_2f(self):
        """Test pixel_array for 8-bit, 1 sample/pixel, 2 frame."""
        ds = dcmread(RLE_8_1_2F)
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert ds.BitsAllocated == 8
        assert ds.SamplesPerPixel == 1
        assert ds.NumberOfFrames == 2
        ref = _get_pixel_array(EXPL_8_1_2F)
        arr = ds.pixel_array

        assert arr.flags.writeable

        assert np.array_equal(arr, ref)
        assert (2, 600, 800) == arr.shape
        assert 244 == arr[0, 0].min() == arr[0, 0].max()
        assert (1, 246, 1) == tuple(arr[0, 300, 491:494])
        assert 0 == arr[0, -1].min() == arr[0, -1].max()

        # Frame 2 is frame 1 inverted
        assert np.array_equal((2**ds.BitsAllocated - 1) - arr[1], arr[0])

    def test_pixel_array_8bit_3sample_1f(self):
        """Test pixel_array for 8-bit, 3 sample/pixel, 1 frame."""
        ds = dcmread(RLE_8_3_1F)
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert ds.BitsAllocated == 8
        assert ds.SamplesPerPixel == 3
        assert 'NumberOfFrames' not in ds
        ref = _get_pixel_array(EXPL_8_3_1F)
        arr = ds.pixel_array

        assert arr.flags.writeable

        assert np.array_equal(arr, ref)
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

    def test_pixel_array_8bit_3sample_2f(self):
        """Test pixel_array for 8-bit, 3 sample/pixel, 2 frame."""
        ds = dcmread(RLE_8_3_2F)
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert ds.BitsAllocated == 8
        assert ds.SamplesPerPixel == 3
        assert ds.NumberOfFrames == 2
        ref = _get_pixel_array(EXPL_8_3_2F)
        arr = ds.pixel_array

        assert arr.flags.writeable

        assert np.array_equal(arr, ref)

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

    def test_pixel_array_16bit_1sample_1f(self):
        """Test pixel_array for 16-bit, 1 sample/pixel, 1 frame."""
        ds = dcmread(RLE_16_1_1F)
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert ds.BitsAllocated == 16
        assert ds.SamplesPerPixel == 1
        assert 'NumberOfFrames' not in ds
        assert ds.PixelRepresentation == 1
        ref = _get_pixel_array(EXPL_16_1_1F)
        arr = ds.pixel_array

        assert arr.flags.writeable

        assert np.array_equal(arr, ref)
        assert (64, 64) == arr.shape

        assert (422, 319, 361) == tuple(arr[0, 31:34])
        assert (366, 363, 322) == tuple(arr[31, :3])
        assert (1369, 1129, 862) == tuple(arr[-1, -3:])

    def test_pixel_array_16bit_1sample_10f(self):
        """Test pixel_array for 16-bit, 1, sample/pixel, 10 frame."""
        ds = dcmread(RLE_16_1_10F)
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert ds.BitsAllocated == 16
        assert ds.SamplesPerPixel == 1
        assert ds.NumberOfFrames == 10
        ref = _get_pixel_array(EXPL_16_1_10F)
        arr = ds.pixel_array

        assert arr.flags.writeable

        assert np.array_equal(arr, ref)
        assert (10, 64, 64) == arr.shape

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

    def test_pixel_array_16bit_3sample_1f(self):
        """Test pixel_array for 16-bit, 3 sample/pixel, 1 frame."""
        ds = dcmread(RLE_16_3_1F)
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert ds.BitsAllocated == 16
        assert ds.SamplesPerPixel == 3
        assert 'NumberOfFrames' not in ds
        arr = ds.pixel_array
        ref = _get_pixel_array(EXPL_16_3_1F)

        assert arr.flags.writeable

        assert np.array_equal(ds.pixel_array, ref)

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

    def test_pixel_array_16bit_3sample_2f(self):
        """Test pixel_array for 16-bit, 3, sample/pixel, 10 frame."""
        ds = dcmread(RLE_16_3_2F)
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert ds.BitsAllocated == 16
        assert ds.SamplesPerPixel == 3
        assert ds.NumberOfFrames == 2
        arr = ds.pixel_array
        ref = _get_pixel_array(EXPL_16_3_2F)

        assert arr.flags.writeable

        assert np.array_equal(ds.pixel_array, ref)

        # Frame 1
        frame = arr[0]
        assert (65535, 0, 0) == tuple(frame[5, 50, :])
        assert (65535, 32896, 32896) == tuple(frame[15, 50, :])
        assert (0, 65535, 0) == tuple(frame[25, 50, :])
        assert (32896, 65535, 32896) == tuple(frame[35, 50, :])
        assert (0, 0, 65535) == tuple(frame[45, 50, :])
        assert (32896, 32896, 65535) == tuple(frame[55, 50, :])
        assert (0, 0, 0) == tuple(frame[65, 50, :])
        assert (16448, 16448, 16448) == tuple(frame[75, 50, :])
        assert (49344, 49344, 49344) == tuple(frame[85, 50, :])
        assert (65535, 65535, 65535) == tuple(frame[95, 50, :])

        # Frame 2 is frame 1 inverted
        assert np.array_equal((2**ds.BitsAllocated - 1) - arr[1], arr[0])

    def test_pixel_array_32bit_1sample_1f(self):
        """Test pixel_array for 32-bit, 1 sample/pixel, 1 frame."""
        ds = dcmread(RLE_32_1_1F)
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert ds.BitsAllocated == 32
        assert ds.SamplesPerPixel == 1
        assert 'NumberOfFrames' not in ds
        ref = _get_pixel_array(EXPL_32_1_1F)
        arr = ds.pixel_array

        assert arr.flags.writeable

        assert np.array_equal(arr, ref)
        assert (10, 10) == arr.shape
        assert (1249000, 1249000, 1250000) == tuple(arr[0, :3])
        assert (1031000, 1029000, 1027000) == tuple(arr[4, 3:6])
        assert (803000, 801000, 798000) == tuple(arr[-1, -3:])

    def test_pixel_array_32bit_1sample_15f(self):
        """Test pixel_array for 32-bit, 1, sample/pixel, 15 frame."""
        ds = dcmread(RLE_32_1_15F)
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert ds.BitsAllocated == 32
        assert ds.SamplesPerPixel == 1
        assert ds.NumberOfFrames == 15
        ref = _get_pixel_array(EXPL_32_1_15F)
        arr = ds.pixel_array

        assert arr.flags.writeable

        assert np.array_equal(arr, ref)
        assert (15, 10, 10) == arr.shape

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

    def test_pixel_array_32bit_3sample_1f(self):
        """Test pixel_array for 32-bit, 3 sample/pixel, 1 frame."""
        ds = dcmread(RLE_32_3_1F)
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert ds.BitsAllocated == 32
        assert ds.SamplesPerPixel == 3
        assert 'NumberOfFrames' not in ds
        arr = ds.pixel_array
        ref = _get_pixel_array(EXPL_32_3_1F)

        assert arr.flags.writeable

        assert np.array_equal(ds.pixel_array, ref)

        assert (4294967295, 0, 0) == tuple(arr[5, 50, :])
        assert (4294967295, 2155905152, 2155905152) == tuple(arr[15, 50, :])
        assert (0, 4294967295, 0) == tuple(arr[25, 50, :])
        assert (2155905152, 4294967295, 2155905152) == tuple(arr[35, 50, :])
        assert (0, 0, 4294967295) == tuple(arr[45, 50, :])
        assert (2155905152, 2155905152, 4294967295) == tuple(arr[55, 50, :])
        assert (0, 0, 0) == tuple(arr[65, 50, :])
        assert (1077952576, 1077952576, 1077952576) == tuple(arr[75, 50, :])
        assert (3233857728, 3233857728, 3233857728) == tuple(arr[85, 50, :])
        assert (4294967295, 4294967295, 4294967295) == tuple(arr[95, 50, :])

    def test_pixel_array_32bit_3sample_2f(self):
        """Test pixel_array for 32-bit, 3, sample/pixel, 2 frame."""
        ds = dcmread(RLE_32_3_2F)
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert ds.BitsAllocated == 32
        assert ds.SamplesPerPixel == 3
        assert ds.NumberOfFrames == 2
        arr = ds.pixel_array
        ref = _get_pixel_array(EXPL_32_3_2F)

        assert arr.flags.writeable

        assert np.array_equal(ds.pixel_array, ref)

        # Frame 1
        assert (4294967295, 0, 0) == tuple(arr[0, 5, 50, :])
        assert (4294967295, 2155905152, 2155905152) == tuple(arr[0, 15, 50, :])
        assert (0, 4294967295, 0) == tuple(arr[0, 25, 50, :])
        assert (2155905152, 4294967295, 2155905152) == tuple(arr[0, 35, 50, :])
        assert (0, 0, 4294967295) == tuple(arr[0, 45, 50, :])
        assert (2155905152, 2155905152, 4294967295) == tuple(arr[0, 55, 50, :])
        assert (0, 0, 0) == tuple(arr[0, 65, 50, :])
        assert (1077952576, 1077952576, 1077952576) == tuple(arr[0, 75, 50, :])
        assert (3233857728, 3233857728, 3233857728) == tuple(arr[0, 85, 50, :])
        assert (4294967295, 4294967295, 4294967295) == tuple(arr[0, 95, 50, :])

        # Frame 2 is frame 1 inverted
        assert np.array_equal((2**ds.BitsAllocated - 1) - arr[1], arr[0])


# Tests for rle_handler module with Numpy available
@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class TestNumpy_GetPixelData:
    """Tests for rle_handler.get_pixeldata with numpy."""
    def test_no_pixel_data_raises(self):
        """Test get_pixeldata raises if dataset has no PixelData."""
        ds = dcmread(RLE_16_1_1F)
        del ds.PixelData
        assert 'PixelData' not in ds
        with pytest.raises(AttributeError, match=' dataset: PixelData'):
            get_pixeldata(ds)

    def test_unknown_pixel_representation_raises(self):
        """Test get_pixeldata raises if invalid PixelRepresentation."""
        ds = dcmread(RLE_16_1_1F)
        ds.PixelRepresentation = 2
        with pytest.raises(ValueError, match=r"value of '2' for '\(0028,0103"):
            get_pixeldata(ds)

    def test_unsupported_syntaxes_raises(self):
        """Test get_pixeldata raises if unsupported Transfer Syntax."""
        ds = dcmread(EXPL_16_1_1F)
        with pytest.raises(NotImplementedError,
                           match='syntax is not supported by the RLE pixel'):
            get_pixeldata(ds)

    def test_change_photometric_interpretation(self):
        """Test get_pixeldata changes PhotometricInterpretation if required."""
        def to_rgb(ds):
            """Override the original function that returned False"""
            return True

        # Test default
        ds = dcmread(RLE_16_1_1F)
        assert ds.PhotometricInterpretation == 'MONOCHROME2'

        get_pixeldata(ds)
        assert ds.PhotometricInterpretation == 'MONOCHROME2'

        # Test opposite
        orig_fn = RLE_HANDLER.should_change_PhotometricInterpretation_to_RGB
        RLE_HANDLER.should_change_PhotometricInterpretation_to_RGB = to_rgb

        get_pixeldata(ds)
        assert ds.PhotometricInterpretation == 'RGB'

        RLE_HANDLER.should_change_PhotometricInterpretation_to_RGB = orig_fn

    def test_little_endian_segment_order(self):
        """Test interpreting segment order as little endian."""
        ds = dcmread(RLE_16_1_1F)
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert ds.BitsAllocated == 16
        assert ds.SamplesPerPixel == 1
        assert 'NumberOfFrames' not in ds
        assert ds.PixelRepresentation == 1  # signed

        # Big endian
        arr = get_pixeldata(ds, rle_segment_order='>')
        arr = reshape_pixel_array(ds, arr)

        assert (64, 64) == arr.shape
        assert (422, 319, 361) == tuple(arr[0, 31:34])
        assert (366, 363, 322) == tuple(arr[31, :3])
        assert (1369, 1129, 862) == tuple(arr[-1, -3:])

        # Little endian
        arr = get_pixeldata(ds, rle_segment_order='<')
        arr = reshape_pixel_array(ds, arr)

        assert (64, 64) == arr.shape
        assert (-23039, 16129, 26881) == tuple(arr[0, 31:34])
        assert (28161, 27393, 16897) == tuple(arr[31, :3])
        assert (22789, 26884, 24067) == tuple(arr[-1, -3:])


# RLE encodes data by first splitting a frame into 8-bit segments
BAD_SEGMENT_DATA = [
    # (RLE header, ds.SamplesPerPixel, ds.BitsAllocated)
    (b'\x00\x00\x00\x00', 1, 8),  # 0 segments, 1 expected
    (b'\x02\x00\x00\x00', 1, 8),  # 2 segments, 1 expected
    (b'\x02\x00\x00\x00', 3, 8),  # 2 segments, 3 expected
    (b'\x04\x00\x00\x00', 3, 8),  # 4 segments, 3 expected
    (b'\x01\x00\x00\x00', 1, 16),  # 1 segment, 2 expected
    (b'\x03\x00\x00\x00', 1, 16),  # 3 segments, 2 expected
    (b'\x05\x00\x00\x00', 3, 16),  # 5 segments, 6 expected
    (b'\x07\x00\x00\x00', 3, 16),  # 7 segments, 6 expected
    (b'\x03\x00\x00\x00', 1, 32),  # 3 segments, 4 expected
    (b'\x05\x00\x00\x00', 1, 32),  # 5 segments, 4 expected
    (b'\x0B\x00\x00\x00', 3, 32),  # 11 segments, 12 expected
    (b'\x0D\x00\x00\x00', 3, 32),  # 13 segments, 12 expected
    (b'\x07\x00\x00\x00', 1, 64),  # 7 segments, 8 expected
    (b'\x09\x00\x00\x00', 1, 64),  # 9 segments, 8 expected
]

HEADER_DATA = [
    # (Number of segments, offsets)
    (0, []),
    (1, [64]),
    (2, [64, 16]),
    (8, [64, 16, 31, 55, 62, 110, 142, 551]),
    (14, [64, 16, 31, 55, 62, 110, 142, 551, 641, 456, 43, 11, 6, 55]),
    (15, [64, 16, 31, 55, 62, 110, 142, 551, 641, 456, 43, 11, 6, 55, 9821]),
]


@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class TestNumpy_RLEParseHeader:
    """Tests for rle_handler._parse_rle_header."""
    def test_invalid_header_length(self):
        """Test exception raised if header is not 64 bytes long."""
        for length in [0, 1, 63, 65]:
            with pytest.raises(ValueError,
                               match='RLE header can only be 64 bytes long'):
                _parse_rle_header(b'\x00' * length)

    def test_invalid_nr_segments_raises(self):
        """Test that more than 15 segments raises exception."""
        with pytest.raises(ValueError, match="invalid number of segments"):
            _parse_rle_header(b'\x10' + b'\x00' * 63)

    @pytest.mark.parametrize('nr_segments, offsets', HEADER_DATA)
    def test_parse_header(self, nr_segments, offsets):
        """Test parsing header data."""
        # Encode the header
        header = bytearray()
        header.extend(pack('<L', nr_segments))
        header.extend(pack('<{}L'.format(len(offsets)), *offsets))
        # Add padding
        header.extend(b'\x00' * (64 - len(header)))

        assert len(header) == 64
        assert offsets == _parse_rle_header(header)


@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class TestNumpy_RLEDecodeFrame:
    """Tests for rle_handler._rle_decode_frame."""
    def test_unsupported_bits_allocated_raises(self):
        """Test exception raised for BitsAllocated not a multiple of 8."""
        msg = (
            r"Unable to decode RLE encoded pixel data with a \(0028,0100\) "
            r"'Bits Allocated' value of 12"
        )
        with pytest.raises(NotImplementedError, match=msg):
            _rle_decode_frame(b'\x00\x00\x00\x00', 1, 1, 1, 12)

    @pytest.mark.parametrize('header,samples,bits', BAD_SEGMENT_DATA)
    def test_invalid_nr_segments_raises(self, header, samples, bits):
        """Test having too many segments in the data raises exception."""
        # This should probably be ValueError
        expected = samples * bits // 8
        actual = unpack('<L', header)[0]
        header += b'\x00' * (64 - len(header))
        msg = (
            r"expected amount \({} vs. {} segments\)".format(actual, expected)
        )
        with pytest.raises(ValueError, match=msg):
            _rle_decode_frame(header,
                              rows=1,
                              columns=1,
                              nr_samples=samples,
                              nr_bits=bits)

    def test_invalid_frame_data_raises(self):
        """Test that invalid segment data raises exception."""
        ds = dcmread(RLE_16_1_1F)
        pixel_data = defragment_data(ds.PixelData)
        # Missing byte
        with pytest.raises(ValueError,
                           match=r'amount \(4095 vs. 4096 bytes\)'):
            _rle_decode_frame(pixel_data[:-1],
                              ds.Rows,
                              ds.Columns,
                              ds.SamplesPerPixel,
                              ds.BitsAllocated)

        # Extra byte
        with pytest.raises(ValueError,
                           match=r'amount \(4097 vs. 4096 bytes\)'):
            _rle_decode_frame(pixel_data + b'\x00\x01',
                              ds.Rows,
                              ds.Columns,
                              ds.SamplesPerPixel,
                              ds.BitsAllocated)

    def test_8bit_1sample(self):
        """Test decoding 8-bit, 1 sample/pixel."""
        header = (
            b'\x01\x00\x00\x00'
            b'\x40\x00\x00\x00'
        )
        header += (64 - len(header)) * b'\x00'
        # 2 x 3 data
        # 0, 64, 128, 160, 192, 255
        data = b'\x05\x00\x40\x80\xA0\xC0\xFF'
        decoded = _rle_decode_frame(header + data, 2, 3, 1, 8)
        arr = np.frombuffer(decoded, np.dtype('>u1'))
        assert [0, 64, 128, 160, 192, 255] == arr.tolist()

    def test_8bit_3sample(self):
        """Test decoding 8-bit, 3 sample/pixel."""
        header = (
            b'\x03\x00\x00\x00'  # 3 segments
            b'\x40\x00\x00\x00'  # 64
            b'\x47\x00\x00\x00'  # 71
            b'\x4E\x00\x00\x00'  # 78
        )
        header += (64 - len(header)) * b'\x00'
        # 2 x 3 data
        # 0, 64, 128, 160, 192, 255
        data = (
            b'\x05\x00\x40\x80\xA0\xC0\xFF'  # R
            b'\x05\xFF\xC0\x80\x40\x00\xFF'  # B
            b'\x05\x01\x40\x80\xA0\xC0\xFE'  # G
        )
        decoded = _rle_decode_frame(header + data, 2, 3, 3, 8)
        arr = np.frombuffer(decoded, np.dtype('>u1'))
        # Ordered all R, all G, all B
        assert [0, 64, 128, 160, 192, 255] == arr[:6].tolist()
        assert [255, 192, 128, 64, 0, 255] == arr[6:12].tolist()
        assert [1, 64, 128, 160, 192, 254] == arr[12:].tolist()

    def test_16bit_1sample(self):
        """Test decoding 16-bit, 1 sample/pixel."""
        header = (
            b'\x02\x00\x00\x00'
            b'\x40\x00\x00\x00'
            b'\x47\x00\x00\x00'
        )
        header += (64 - len(header)) * b'\x00'
        # 2 x 3 data
        data = (
            # 0, 1, 256, 255, 65280, 65535
            b'\x05\x00\x00\x01\x00\xFF\xFF'  # MSB
            b'\x05\x00\x01\x00\xFF\x00\xFF'  # LSB
        )
        decoded = _rle_decode_frame(header + data, 2, 3, 1, 16)
        arr = np.frombuffer(decoded, np.dtype('>u2'))
        assert [0, 1, 256, 255, 65280, 65535] == arr.tolist()

    def test_16bit_3sample(self):
        """Test decoding 16-bit, 3 sample/pixel."""
        header = (
            b'\x06\x00\x00\x00'  # 6 segments
            b'\x40\x00\x00\x00'  # 64
            b'\x47\x00\x00\x00'  # 71
            b'\x4E\x00\x00\x00'  # 78
            b'\x55\x00\x00\x00'  # 85
            b'\x5C\x00\x00\x00'  # 92
            b'\x63\x00\x00\x00'  # 99
        )
        header += (64 - len(header)) * b'\x00'
        # 2 x 3 data
        data = (
            # 0, 1, 256, 255, 65280, 65535
            b'\x05\x00\x00\x01\x00\xFF\xFF'  # MSB
            b'\x05\x00\x01\x00\xFF\x00\xFF'  # LSB
            b'\x05\xFF\x00\x01\x00\xFF\x00'  # MSB
            b'\x05\xFF\x01\x00\xFF\x00\x00'  # LSB
            b'\x05\x00\x00\x01\x00\xFF\xFF'  # MSB
            b'\x05\x01\x01\x00\xFF\x00\xFE'  # LSB
        )
        decoded = _rle_decode_frame(header + data, 2, 3, 3, 16)
        arr = np.frombuffer(decoded, np.dtype('>u2'))
        assert [0, 1, 256, 255, 65280, 65535] == arr[:6].tolist()
        assert [65535, 1, 256, 255, 65280, 0] == arr[6:12].tolist()
        assert [1, 1, 256, 255, 65280, 65534] == arr[12:].tolist()

    def test_32bit_1sample(self):
        """Test decoding 32-bit, 1 sample/pixel."""
        header = (
            b'\x04\x00\x00\x00'  # 4 segments
            b'\x40\x00\x00\x00'  # 64 offset
            b'\x47\x00\x00\x00'  # 71 offset
            b'\x4E\x00\x00\x00'  # 78 offset
            b'\x55\x00\x00\x00'  # 85 offset
        )
        header += (64 - len(header)) * b'\x00'
        # 2 x 3 data
        data = (
            # 0, 16777216, 65536, 256, 4294967295
            b'\x05\x00\x01\x00\x00\x00\xFF'  # MSB
            b'\x05\x00\x00\x01\x00\x00\xFF'
            b'\x05\x00\x00\x00\x01\x00\xFF'
            b'\x05\x00\x00\x00\x00\x01\xFF'  # LSB
        )
        decoded = _rle_decode_frame(header + data, 2, 3, 1, 32)
        arr = np.frombuffer(decoded, np.dtype('>u4'))
        assert [0, 16777216, 65536, 256, 1, 4294967295] == arr.tolist()

    def test_32bit_3sample(self):
        """Test decoding 32-bit, 3 sample/pixel."""
        header = (
            b'\x0C\x00\x00\x00'  # 12 segments
            b'\x40\x00\x00\x00'  # 64
            b'\x47\x00\x00\x00'  # 71
            b'\x4E\x00\x00\x00'  # 78
            b'\x55\x00\x00\x00'  # 85
            b'\x5C\x00\x00\x00'  # 92
            b'\x63\x00\x00\x00'  # 99
            b'\x6A\x00\x00\x00'  # 106
            b'\x71\x00\x00\x00'  # 113
            b'\x78\x00\x00\x00'  # 120
            b'\x7F\x00\x00\x00'  # 127
            b'\x86\x00\x00\x00'  # 134
            b'\x8D\x00\x00\x00'  # 141
        )
        header += (64 - len(header)) * b'\x00'
        # 2 x 3 data
        data = (
            # 0, 16777216, 65536, 256, 4294967295
            b'\x05\x00\x01\x00\x00\x00\xFF'  # MSB
            b'\x05\x00\x00\x01\x00\x00\xFF'
            b'\x05\x00\x00\x00\x01\x00\xFF'
            b'\x05\x00\x00\x00\x00\x01\xFF'  # LSB
            b'\x05\xFF\x01\x00\x00\x00\x00'  # MSB
            b'\x05\xFF\x00\x01\x00\x00\x00'
            b'\x05\xFF\x00\x00\x01\x00\x00'
            b'\x05\xFF\x00\x00\x00\x01\x00'  # LSB
            b'\x05\x00\x01\x00\x00\x00\xFF'  # MSB
            b'\x05\x00\x00\x01\x00\x00\xFF'
            b'\x05\x00\x00\x00\x01\x00\xFF'
            b'\x05\x01\x00\x00\x00\x01\xFE'  # LSB
        )
        decoded = _rle_decode_frame(header + data, 2, 3, 3, 32)
        arr = np.frombuffer(decoded, np.dtype('>u4'))
        assert [0, 16777216, 65536, 256, 1, 4294967295] == arr[:6].tolist()
        assert [4294967295, 16777216, 65536, 256, 1, 0] == arr[6:12].tolist()
        assert [1, 16777216, 65536, 256, 1, 4294967294] == arr[12:].tolist()


@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class TestNumpy_RLEDecodeSegment:
    """Tests for rle_handler._rle_decode_segment.

    Using int8
    ----------
    if n >= 0 and n < 127:
        read next (n + 1) bytes literally
    elif n <= -1 and n >= -127:
        copy the next byte (-n + 1) times
    elif n = -128:
        do nothing

    Using uint8 (as in handler)
    ---------------------------
    if n < 128
        read next (n + 1) bytes literally
    elif n > 128
        copy the next byte (256 - n + 1) times
    elif n == 128
        do nothing

    References
    ----------
    DICOM Standard, Part 5, Annex G.3.2
    """
    def test_noop(self):
        """Test no-operation output."""
        # For n == 128, do nothing
        # data is only noop, 0x80 = 128
        data = b'\x80\x80\x80'
        assert b'' == bytes(_rle_decode_segment(data))

        # noop at start, data after
        data = (
            b'\x80\x80'  # No operation
            b'\x05\x01\x02\x03\x04\x05\x06'  # Literal
            b'\xFE\x01'  # Copy
            b'\x80'
        )
        assert (
            b'\x01\x02\x03\x04\x05\x06'
            b'\x01\x01\x01'
        ) == bytes(_rle_decode_segment(data))

        # data at start, noop middle, data at end
        data = (
            b'\x05\x01\x02\x03\x04\x05\x06'  # Literal
            b'\x80'  # No operation
            b'\xFE\x01'  # Copy
            b'\x80'
        )
        assert (
            b'\x01\x02\x03\x04\x05\x06'
            b'\x01\x01\x01'
        ) == bytes(_rle_decode_segment(data))

        # data at start, noop end
        # Copy 6 bytes literally, then 3 x 0x01
        data = (
            b'\x05\x01\x02\x03\x04\x05\x06'
            b'\xFE\x01'
            b'\x80'
        )
        assert (
            b'\x01\x02\x03\x04\x05\x06'
            b'\x01\x01\x01'
        ) == bytes(_rle_decode_segment(data))

    def test_literal(self):
        """Test literal output."""
        # For n < 128, read the next (n + 1) bytes literally
        # n = 0 (0x80 is 128 -> no operation)
        data = b'\x00\x02\x80'
        assert b'\x02' == bytes(_rle_decode_segment(data))
        # n = 1
        data = b'\x01\x02\x03\x80'
        assert b'\x02\x03' == bytes(_rle_decode_segment(data))
        # n = 127
        data = b'\x7f' + b'\x40' * 128 + b'\x80'
        assert b'\x40' * 128 == bytes(_rle_decode_segment(data))

    def test_copy(self):
        """Test copy output."""
        # For n > 128, copy the next byte (257 - n) times
        # n = 255, copy x2 (0x80 is 128 -> no operation)
        data = b'\xFF\x02\x80'
        assert b'\x02\x02' == bytes(_rle_decode_segment(data))
        # n = 254, copy x3
        data = b'\xFE\x02\x80'
        assert b'\x02\x02\x02' == bytes(_rle_decode_segment(data))
        # n = 129, copy x128
        data = b'\x81\x02\x80'
        assert b'\x02' * 128 == bytes(_rle_decode_segment(data))


# Tests for RLE encoding
REFERENCE_ENCODE_ROW = [
    # Input, output
    ([], b''),
    # Replicate run tests
    # 2 (min) replicate
    ([0] * 2, b'\xff\x00'),
    ([0] * 3, b'\xfe\x00'),
    ([0] * 64, b'\xc1\x00'),
    ([0] * 127, b'\x82\x00'),
    # 128 (max) replicate
    ([0] * 128, b'\x81\x00'),
    # 128 (max) replicate, 1 (min) literal
    ([0] * 129, b'\x81\x00\x00\x00'),
    # 128 (max) replicate, 2 (min) replicate
    ([0] * 130, b'\x81\x00\xff\x00'),
    # 128 (max) x 5 replicates
    ([0] * 128 * 5, b'\x81\x00' * 5),
    # Literal run tests
    # 1 (min) literal
    ([0], b'\x00\x00'),
    ([0, 1], b'\x01\x00\x01'),
    ([0, 1, 2], b'\x02\x00\x01\x02'),
    ([0, 1] * 32, b'\x3f' + b'\x00\x01' * 32),
    # 127 literal
    ([0, 1] * 63 + [2], b'\x7e' + b'\x00\x01' * 63 + b'\x02'),
    # 128 literal (max)
    ([0, 1] * 64, b'\x7f' + b'\x00\x01' * 64),
    # 128 (max) literal, 1 (min) literal
    ([0, 1] * 64 + [2], b'\x7f' + b'\x00\x01' * 64 + b'\x00\x02'),
    # 128 (max) x 5 literals
    ([0, 1] * 64 * 5, (b'\x7f' + b'\x00\x01' * 64) * 5),
    # Combination run tests
    # 1 (min) literal, 1 (min) replicate
    ([0, 1, 1], b'\x00\x00\xff\x01'),
    # 1 (min) literal, 128 (max) replicate
    ([0] + [1] * 128, b'\x00\x00\x81\x01'),
    # 128 (max) literal, 2 (min) replicate
    ([0, 1] * 64 + [2] * 2, b'\x7f' + b'\x00\x01' * 64 + b'\xff\x02'),
    # 128 (max) literal, 128 (max) replicate
    ([0, 1] * 64 + [2] * 128, b'\x7f' + b'\x00\x01' * 64 + b'\x81\x02'),
    # 2 (min) replicate, 1 (min) literal
    ([0, 0, 1], b'\xff\x00\x00\x01'),
    # 2 (min) replicate, 128 (max) literal
    ([0, 0] + [1, 2] * 64, b'\xff\x00\x7f' + b'\x01\x02' * 64),
    # 128 (max) replicate, 1 (min) literal
    ([0] * 128 + [1], b'\x81\x00\x00\x01'),
    # 128 (max) replicate, 128 (max) literal
    ([0] * 128 + [1, 2] * 64, b'\x81\x00\x7f' + b'\x01\x02' * 64),
]


@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class TestNumpy_RLEEncodeRow:
    """Tests for rle_handler._rle_encode_row."""
    @pytest.mark.parametrize('input, output', REFERENCE_ENCODE_ROW)
    def test_encode(self, input, output):
        """Test encoding an empty row."""
        assert output == _rle_encode_row(np.asarray(input))


@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class TestNumpy_RLEEncodeFrame:
    """Tests for rle_handler.rle_encode_frame."""
    def setup(self):
        """Setup the tests."""
        # Create a dataset skeleton for use in the cycle tests
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = '1.2.840.10008.1.2'
        ds.Rows = 2
        ds.Columns = 4
        ds.SamplesPerPixel = 3
        ds.PlanarConfiguration = 1
        self.ds = ds

    def test_cycle_8bit_1sample(self):
        """Test an encode/decode cycle for 8-bit 1 sample/pixel."""
        ds = dcmread(EXPL_8_1_1F)
        ref = ds.pixel_array
        assert 8 == ds.BitsAllocated
        assert 1 == ds.SamplesPerPixel

        encoded = rle_encode_frame(ref)
        decoded = _rle_decode_frame(encoded, ds.Rows, ds.Columns,
                                    ds.SamplesPerPixel, ds.BitsAllocated)
        dtype = np.dtype('uint8').newbyteorder('>')
        arr = np.frombuffer(decoded, dtype)
        arr = reshape_pixel_array(ds, arr)

        assert np.array_equal(ref, arr)

    def test_cycle_8bit_3sample(self):
        """Test an encode/decode cycle for 8-bit 3 sample/pixel."""
        ds = dcmread(EXPL_8_3_1F)
        ref = ds.pixel_array
        assert 8 == ds.BitsAllocated
        assert 3 == ds.SamplesPerPixel

        encoded = rle_encode_frame(ref)
        decoded = _rle_decode_frame(encoded, ds.Rows, ds.Columns,
                                    ds.SamplesPerPixel, ds.BitsAllocated)
        arr = np.frombuffer(decoded, 'uint8')
        # The decoded data is planar configuration 1
        ds.PlanarConfiguration = 1
        arr = reshape_pixel_array(ds, arr)

        assert np.array_equal(ref, arr)

    def test_cycle_16bit_1sample(self):
        """Test an encode/decode cycle for 16-bit 1 sample/pixel."""
        ds = dcmread(EXPL_16_1_1F)
        ref = ds.pixel_array
        assert 16 == ds.BitsAllocated
        assert 1 == ds.SamplesPerPixel

        encoded = rle_encode_frame(ref)
        decoded = _rle_decode_frame(encoded, ds.Rows, ds.Columns,
                                    ds.SamplesPerPixel, ds.BitsAllocated)
        dtype = np.dtype('uint16').newbyteorder('>')
        arr = np.frombuffer(decoded, dtype)
        arr = reshape_pixel_array(ds, arr)

        assert np.array_equal(ref, arr)

    def test_cycle_16bit_3sample(self):
        """Test an encode/decode cycle for 16-bit 3 sample/pixel."""
        ds = dcmread(EXPL_16_3_1F)
        ref = ds.pixel_array
        assert 16 == ds.BitsAllocated
        assert 3 == ds.SamplesPerPixel

        encoded = rle_encode_frame(ref)
        decoded = _rle_decode_frame(encoded, ds.Rows, ds.Columns,
                                    ds.SamplesPerPixel, ds.BitsAllocated)
        dtype = np.dtype('uint16').newbyteorder('>')
        arr = np.frombuffer(decoded, dtype)
        # The decoded data is planar configuration 1
        ds.PlanarConfiguration = 1
        arr = reshape_pixel_array(ds, arr)

        assert np.array_equal(ref, arr)

    def test_cycle_32bit_1sample(self):
        """Test an encode/decode cycle for 32-bit 1 sample/pixel."""
        ds = dcmread(EXPL_32_1_1F)
        ref = ds.pixel_array
        assert 32 == ds.BitsAllocated
        assert 1 == ds.SamplesPerPixel

        encoded = rle_encode_frame(ref)
        decoded = _rle_decode_frame(encoded, ds.Rows, ds.Columns,
                                    ds.SamplesPerPixel, ds.BitsAllocated)
        dtype = np.dtype('uint32').newbyteorder('>')
        arr = np.frombuffer(decoded, dtype)
        arr = reshape_pixel_array(ds, arr)

        assert np.array_equal(ref, arr)

    def test_cycle_32bit_3sample(self):
        """Test an encode/decode cycle for 32-bit 3 sample/pixel."""
        ds = dcmread(EXPL_32_3_1F)
        ref = ds.pixel_array
        assert 32 == ds.BitsAllocated
        assert 3 == ds.SamplesPerPixel

        encoded = rle_encode_frame(ref)
        decoded = _rle_decode_frame(encoded, ds.Rows, ds.Columns,
                                    ds.SamplesPerPixel, ds.BitsAllocated)
        dtype = np.dtype('uint32').newbyteorder('>')
        arr = np.frombuffer(decoded, dtype)
        # The decoded data is planar configuration 1
        ds.PlanarConfiguration = 1
        arr = reshape_pixel_array(ds, arr)

        assert np.array_equal(ref, arr)

    def test_16_segments_raises(self):
        """Test that trying to encode 16-segments raises exception."""
        arr = np.asarray([[[1, 2, 3, 4]]], dtype='uint32')
        assert (1, 1, 4) == arr.shape
        assert 4 == arr.dtype.itemsize

        msg = (
            r"Unable to encode as the DICOM standard only allows "
            r"a maximum of 15 segments in RLE encoded data"
        )
        with pytest.raises(ValueError, match=msg):
            rle_encode_frame(arr)

    def test_15_segment(self):
        """Test encoding 15-segments works as expected."""
        arr = np.asarray(
            [[[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]]],
            dtype='uint8'
        )
        assert (1, 1, 15) == arr.shape
        assert 1 == arr.dtype.itemsize

        encoded = rle_encode_frame(arr)
        header = (
            b'\x0f\x00\x00\x00'
            b'\x40\x00\x00\x00'
            b'\x42\x00\x00\x00'
            b'\x44\x00\x00\x00'
            b'\x46\x00\x00\x00'
            b'\x48\x00\x00\x00'
            b'\x4a\x00\x00\x00'
            b'\x4c\x00\x00\x00'
            b'\x4e\x00\x00\x00'
            b'\x50\x00\x00\x00'
            b'\x52\x00\x00\x00'
            b'\x54\x00\x00\x00'
            b'\x56\x00\x00\x00'
            b'\x58\x00\x00\x00'
            b'\x5a\x00\x00\x00'
            b'\x5c\x00\x00\x00'
        )
        assert header == encoded[:64]
        assert (
            b'\x00\x01\x00\x02\x00\x03\x00\x04\x00\x05\x00\x06'
            b'\x00\x07\x00\x08\x00\x09\x00\x0a\x00\x0b\x00\x0c'
            b'\x00\x0d\x00\x0e\x00\x0f'
        ) == encoded[64:]

    def test_encoding_multiple_frames_raises(self):
        """Test encoding multiple framed pixel data raises exception."""
        # Note: only works with multi-sample data
        ds = dcmread(EXPL_8_3_2F)
        arr = ds.pixel_array
        assert ds.NumberOfFrames > 1
        assert len(arr.shape) == 4
        msg = (
            r"Unable to encode multiple frames at once, please encode one "
            r"frame at a time"
        )
        with pytest.raises(ValueError, match=msg):
            rle_encode_frame(arr)

    def test_single_row_1sample(self):
        """Test encoding a single row of 1 sample/pixel data."""
        # Rows 1, Columns 5, SamplesPerPixel 1
        arr = np.asarray([[0, 1, 2, 3, 4]], dtype='uint8')
        assert (1, 5) == arr.shape
        encoded = rle_encode_frame(arr)
        header = b'\x01\x00\x00\x00\x40\x00\x00\x00' + b'\x00' * 56
        assert header == encoded[:64]
        assert b'\x04\x00\x01\x02\x03\x04' == encoded[64:]

    def test_single_row_3sample(self):
        """Test encoding a single row of 3 samples/pixel data."""
        # Rows 1, Columns 5, SamplesPerPixel 3
        arr = np.asarray(
            [[[0, 0, 0], [1, 1, 1], [2, 2, 2], [3, 3, 3], [4, 4, 4]]],
            dtype='uint8'
        )
        assert (1, 5, 3) == arr.shape
        encoded = rle_encode_frame(arr)
        header = (
            b'\x03\x00\x00\x00'
            b'\x40\x00\x00\x00'
            b'\x46\x00\x00\x00'
            b'\x4c\x00\x00\x00'
        )
        header += b'\x00' * (64 - len(header))
        assert header == encoded[:64]
        assert (
            b'\x04\x00\x01\x02\x03\x04'
            b'\x04\x00\x01\x02\x03\x04'
            b'\x04\x00\x01\x02\x03\x04'
        ) == encoded[64:]


@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class TestNumpy_RLEEncodePlane:
    """Tests for rle_handler._rle_encode_plane."""
    def test_8bit(self):
        """Test encoding an 8-bit plane into 1 segment."""
        ds = dcmread(RLE_8_1_1F)
        pixel_data = defragment_data(ds.PixelData)
        decoded = _rle_decode_frame(pixel_data, ds.Rows, ds.Columns,
                                    ds.SamplesPerPixel, ds.BitsAllocated)
        assert ds.Rows * ds.Columns * ds.BitsAllocated // 8 == len(decoded)
        arr = np.frombuffer(decoded, 'uint8').reshape(ds.Rows, ds.Columns)
        # Re-encode the decoded data
        encoded = bytearray()
        nr_segments = 0
        for segment in _rle_encode_plane(arr):
            encoded.extend(segment)
            nr_segments += 1

        # Add header
        header = b'\x01\x00\x00\x00\x40\x00\x00\x00'
        header += b'\x00' * (64 - len(header))

        assert 1 == nr_segments

        # Decode the re-encoded data and check that it's the same
        redecoded = _rle_decode_frame(header + encoded,
                                      ds.Rows, ds.Columns,
                                      ds.SamplesPerPixel, ds.BitsAllocated)
        assert ds.Rows * ds.Columns * ds.SamplesPerPixel == len(redecoded)
        assert decoded == redecoded

    def test_16bit(self):
        """Test encoding a 16-bit plane into 2 segments."""
        ds = dcmread(RLE_16_1_1F)
        pixel_data = defragment_data(ds.PixelData)
        decoded = _rle_decode_frame(pixel_data, ds.Rows, ds.Columns,
                                    ds.SamplesPerPixel, ds.BitsAllocated)
        assert ds.Rows * ds.Columns * ds.BitsAllocated // 8 == len(decoded)

        # `decoded` is in big endian byte ordering
        dtype = np.dtype('uint16').newbyteorder('>')
        arr = np.frombuffer(decoded, dtype).reshape(ds.Rows, ds.Columns)

        # Re-encode the decoded data
        encoded = bytearray()
        nr_segments = 0
        offsets = [64]
        for segment in _rle_encode_plane(arr):
            offsets.append(offsets[nr_segments] + len(segment))
            encoded.extend(segment)
            nr_segments += 1

        assert 2 == nr_segments

        # Add header
        header = b'\x02\x00\x00\x00'
        header += pack('<2L', *offsets[:-1])
        header += b'\x00' * (64 - len(header))

        # Decode the re-encoded data and check that it's the same
        redecoded = _rle_decode_frame(header + encoded,
                                      ds.Rows, ds.Columns,
                                      ds.SamplesPerPixel, ds.BitsAllocated)
        assert ds.Rows * ds.Columns * ds.BitsAllocated // 8 == len(redecoded)
        assert decoded == redecoded

    def test_16bit_segment_order(self):
        """Test that the segment order per 16-bit sample is correct."""
        # Native byte ordering
        data = b'\x00\x00\x01\xFF\xFE\x00\xFF\xFF\x10\x12'
        dtype = np.dtype('uint16')
        arr = np.frombuffer(data, dtype)

        segments = []
        for segment in _rle_encode_plane(arr):
            segments.append(segment)

        assert 2 == len(segments)

        # Each segment should start with a literal run marker of 0x04
        # and MSB should be first segment, then LSB in second
        if sys.byteorder == 'little':
            assert b'\x04\x00\xFF\x00\xFF\x12' == segments[0]
            assert b'\x04\x00\x01\xFE\xFF\x10' == segments[1]
        else:
            assert b'\x04\x00\x01\xFE\xFF\x10' == segments[0]
            assert b'\x04\x00\xFF\x00\xFF\x12' == segments[1]

        # Little endian
        arr = np.frombuffer(data, dtype.newbyteorder('<'))
        assert [0, 65281, 254, 65535, 4624] == arr.tolist()

        segments = []
        for segment in _rle_encode_plane(arr):
            segments.append(segment)

        assert 2 == len(segments)
        assert b'\x04\x00\xFF\x00\xFF\x12' == segments[0]
        assert b'\x04\x00\x01\xFE\xFF\x10' == segments[1]

        # Big endian
        arr = np.frombuffer(data, dtype.newbyteorder('>'))
        assert [0, 511, 65024, 65535, 4114] == arr.tolist()

        segments = []
        for segment in _rle_encode_plane(arr):
            segments.append(segment)

        assert 2 == len(segments)
        assert b'\x04\x00\x01\xFE\xFF\x10' == segments[0]
        assert b'\x04\x00\xFF\x00\xFF\x12' == segments[1]

    def test_32bit(self):
        """Test encoding a 32-bit plane into 4 segments."""
        ds = dcmread(RLE_32_1_1F)
        pixel_data = defragment_data(ds.PixelData)
        decoded = _rle_decode_frame(pixel_data, ds.Rows, ds.Columns,
                                    ds.SamplesPerPixel, ds.BitsAllocated)
        assert ds.Rows * ds.Columns * ds.BitsAllocated // 8 == len(decoded)

        # `decoded` is in big endian byte ordering
        dtype = np.dtype('uint32').newbyteorder('>')
        arr = np.frombuffer(decoded, dtype).reshape(ds.Rows, ds.Columns)

        # Re-encode the decoded data
        encoded = bytearray()
        nr_segments = 0
        offsets = [64]
        for segment in _rle_encode_plane(arr):
            offsets.append(offsets[nr_segments] + len(segment))
            encoded.extend(segment)
            nr_segments += 1

        assert 4 == nr_segments

        # Add header
        header = b'\x04\x00\x00\x00'
        header += pack('<4L', *offsets[:-1])
        header += b'\x00' * (64 - len(header))

        # Decode the re-encoded data and check that it's the same
        redecoded = _rle_decode_frame(header + encoded,
                                      ds.Rows, ds.Columns,
                                      ds.SamplesPerPixel, ds.BitsAllocated)
        assert ds.Rows * ds.Columns * ds.BitsAllocated // 8 == len(redecoded)
        assert decoded == redecoded

    def test_32bit_segment_order(self):
        """Test that the segment order per 32-bit sample is correct."""
        # Native byte ordering
        data = b'\x00\x00\x00\x00\x01\xFF\xFE\x0A\xFF\xFC\x10\x12'
        dtype = np.dtype('uint32')
        arr = np.frombuffer(data, dtype)

        segments = []
        for segment in _rle_encode_plane(arr):
            segments.append(segment)

        assert 4 == len(segments)

        # Each segment should start with a literal run marker of 0x02
        if sys.byteorder == 'little':
            assert b'\x02\x00\x0A\x12' == segments[0]
            assert b'\x02\x00\xFE\x10' == segments[1]
            assert b'\x02\x00\xFF\xFC' == segments[2]
            assert b'\x02\x00\x01\xFF' == segments[3]
        else:
            assert b'\x02\x00\x01\xFF' == segments[0]
            assert b'\x02\x00\xFF\xFC' == segments[1]
            assert b'\x02\x00\xFE\x10' == segments[2]
            assert b'\x02\x00\x0A\x12' == segments[3]

        # Little endian
        arr = np.frombuffer(data, dtype.newbyteorder('<'))
        assert [0, 184483585, 303103231] == arr.tolist()

        segments = []
        for segment in _rle_encode_plane(arr):
            segments.append(segment)

        assert 4 == len(segments)
        assert b'\x02\x00\x0A\x12' == segments[0]
        assert b'\x02\x00\xFE\x10' == segments[1]
        assert b'\x02\x00\xFF\xFC' == segments[2]
        assert b'\x02\x00\x01\xFF' == segments[3]

        # Big endian
        arr = np.frombuffer(data, dtype.newbyteorder('>'))
        assert [0, 33553930, 4294709266] == arr.tolist()

        segments = []
        for segment in _rle_encode_plane(arr):
            segments.append(segment)

        assert 4 == len(segments)
        assert b'\x02\x00\x01\xFF' == segments[0]
        assert b'\x02\x00\xFF\xFC' == segments[1]
        assert b'\x02\x00\xFE\x10' == segments[2]
        assert b'\x02\x00\x0A\x12' == segments[3]

    def test_padding(self):
        """Test that odd length encoded segments are padded."""
        data = b'\x00\x04\x01\x15'
        arr = np.frombuffer(data, 'uint8')
        segments = []
        for segment in _rle_encode_plane(arr):
            segments.append(segment)

        # The segment should start with a literal run marker of 0x03
        #   then 4 bytes of RLE encoded data, then 0x00 padding
        assert b'\x03\x00\x04\x01\x15\x00' == segments[0]


@pytest.mark.skipif(not HAVE_NP, reason='Numpy is not available')
class TestNumpy_RLEEncodeSegment:
    """Tests for rle_handler._rle_encode_segment."""
    def test_one_row(self):
        """Test encoding data that contains only a single row."""
        ds = dcmread(RLE_8_1_1F)
        pixel_data = defragment_data(ds.PixelData)
        decoded = _rle_decode_segment(pixel_data[64:])
        assert ds.Rows * ds.Columns == len(decoded)
        arr = np.frombuffer(decoded, 'uint8').reshape(ds.Rows, ds.Columns)

        # Re-encode a single row of the decoded data
        row = arr[0]
        assert (ds.Columns,) == row.shape
        encoded = _rle_encode_segment(row)

        # Decode the re-encoded data and check that it's the same
        redecoded = _rle_decode_segment(encoded)
        assert ds.Columns == len(redecoded)
        assert decoded[:ds.Columns] == redecoded

    def test_cycle(self):
        """Test the decoded data remains the same after encoding/decoding."""
        ds = dcmread(RLE_8_1_1F)
        pixel_data = defragment_data(ds.PixelData)
        decoded = _rle_decode_segment(pixel_data[64:])
        assert ds.Rows * ds.Columns == len(decoded)
        arr = np.frombuffer(decoded, 'uint8').reshape(ds.Rows, ds.Columns)
        # Re-encode the decoded data
        encoded = _rle_encode_segment(arr)

        # Decode the re-encoded data and check that it's the same
        redecoded = _rle_decode_segment(encoded)
        assert ds.Rows * ds.Columns == len(redecoded)
        assert decoded == redecoded
