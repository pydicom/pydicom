# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Tests for the pixels.processing module."""

import os
from struct import unpack, pack

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

try:
    import PIL

    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

from pydicom import dcmread, config
from pydicom.data import get_testdata_file, get_palette_files
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.pixels.processing import (
    convert_color_space,
    apply_color_lut,
    _expand_segmented_lut,
    apply_icc_profile,
    apply_modality_lut,
    apply_voi_lut,
    apply_voi,
    apply_windowing,
    apply_presentation_lut,
    create_icc_transform,
)
from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian


# PAL: PALETTE COLOR Photometric Interpretation
# SEG: Segmented Palette Color
# SUP: Supplemental Palette Color
# LE, BE: little endian, big endian encoding
# 8/8, 1 sample/pixel, 1 frame
PAL_08_256_0_16_1F = get_testdata_file("OBXXXX1A.dcm")
PAL_08_200_0_16_1F = get_testdata_file("OT-PAL-8-face.dcm")
# 8/8, 1 sample/pixel, 2 frame
PAL_08_256_0_16_2F = get_testdata_file("OBXXXX1A_2frame.dcm")
# PALETTE COLOR with 16-bit LUTs (no indirect segments)
PAL_SEG_LE_16_1F = get_testdata_file("gdcm-US-ALOKA-16.dcm")
PAL_SEG_BE_16_1F = get_testdata_file("gdcm-US-ALOKA-16_big.dcm")
# Supplemental palette colour + VOI windowing
SUP_16_16_2F = get_testdata_file("eCT_Supplemental.dcm")
# 8 bit, 3 samples/pixel, 1 and 2 frame datasets
# RGB colorspace, uncompressed
RGB_8_3_1F = get_testdata_file("SC_rgb.dcm")
RGB_8_3_2F = get_testdata_file("SC_rgb_2frame.dcm")
# MOD: Modality LUT
# SEQ: Modality LUT Sequence
MOD_16 = get_testdata_file("CT_small.dcm")
MOD_16_SEQ = get_testdata_file("mlut_18.dcm")
# VOI: VOI LUT Sequence
# WIN: Windowing operation
WIN_12_1F = get_testdata_file("MR-SIEMENS-DICOM-WithOverlays.dcm")
VOI_08_1F = get_testdata_file("vlut_04.dcm")
# ICC profile
ICC_PROFILE = get_testdata_file("crayons.icc")


TEST_CMS = HAVE_NP and HAVE_PIL


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestConvertColourSpace:
    """Tests for convert_color_space()."""

    def test_unknown_current_raises(self):
        """Test an unknown current color space raises exception."""
        with pytest.raises(
            NotImplementedError, match="Conversion from TEST to RGB is not suppo"
        ):
            convert_color_space(np.ones((1, 2), dtype="u1"), "TEST", "RGB")

    def test_unknown_desired_raises(self):
        """Test an unknown desdired color space raises exception."""
        with pytest.raises(
            NotImplementedError, match="Conversion from RGB to TEST is not suppo"
        ):
            convert_color_space(np.ones((1, 2), dtype="u1"), "RGB", "TEST")

    @pytest.mark.parametrize(
        "current, desired",
        [
            ("RGB", "RGB"),
            ("YBR_FULL", "YBR_FULL"),
            ("YBR_FULL", "YBR_FULL_422"),
            ("YBR_FULL_422", "YBR_FULL_422"),
            ("YBR_FULL_422", "YBR_FULL"),
        ],
    )
    def test_current_is_desired(self, current, desired):
        """Test that the array is unchanged when current matches desired."""
        arr = np.ones((2, 3), dtype="u1")
        assert np.array_equal(arr, convert_color_space(arr, current, desired))

    def test_rgb_ybr_rgb_single_frame(self):
        """Test round trip conversion of single framed pixel data."""
        ds = dcmread(RGB_8_3_1F)

        arr = ds.pixel_array
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

        ybr = convert_color_space(arr, "RGB", "YBR_FULL")
        assert (76, 85, 255) == tuple(ybr[5, 50, :])
        assert (166, 107, 192) == tuple(ybr[15, 50, :])
        assert (150, 44, 21) == tuple(ybr[25, 50, :])
        assert (203, 86, 75) == tuple(ybr[35, 50, :])
        assert (29, 255, 107) == tuple(ybr[45, 50, :])
        assert (142, 192, 118) == tuple(ybr[55, 50, :])
        assert (0, 128, 128) == tuple(ybr[65, 50, :])
        assert (64, 128, 128) == tuple(ybr[75, 50, :])
        assert (192, 128, 128) == tuple(ybr[85, 50, :])
        assert (255, 128, 128) == tuple(ybr[95, 50, :])

        # Round trip -> rounding errors get compounded
        rgb = convert_color_space(ybr, "YBR_FULL", "RGB")
        # All pixels within +/- 1 units
        assert np.allclose(rgb, arr, atol=1)
        assert rgb.shape == arr.shape

    def test_rgb_ybr_rgb_multi_frame(self):
        """Test round trip conversion of multi-framed pixel data."""
        ds = dcmread(RGB_8_3_2F)

        arr = ds.pixel_array
        assert (255, 0, 0) == tuple(arr[0, 5, 50, :])
        assert (255, 128, 128) == tuple(arr[0, 15, 50, :])
        assert (0, 255, 0) == tuple(arr[0, 25, 50, :])
        assert (128, 255, 128) == tuple(arr[0, 35, 50, :])
        assert (0, 0, 255) == tuple(arr[0, 45, 50, :])
        assert (128, 128, 255) == tuple(arr[0, 55, 50, :])
        assert (0, 0, 0) == tuple(arr[0, 65, 50, :])
        assert (64, 64, 64) == tuple(arr[0, 75, 50, :])
        assert (192, 192, 192) == tuple(arr[0, 85, 50, :])
        assert (255, 255, 255) == tuple(arr[0, 95, 50, :])
        # Frame 2 is frame 1 inverted
        assert np.array_equal((2**ds.BitsAllocated - 1) - arr[1], arr[0])

        ybr = convert_color_space(arr, "RGB", "YBR_FULL")
        assert (76, 85, 255) == tuple(ybr[0, 5, 50, :])
        assert (166, 107, 192) == tuple(ybr[0, 15, 50, :])
        assert (150, 44, 21) == tuple(ybr[0, 25, 50, :])
        assert (203, 86, 75) == tuple(ybr[0, 35, 50, :])
        assert (29, 255, 107) == tuple(ybr[0, 45, 50, :])
        assert (142, 192, 118) == tuple(ybr[0, 55, 50, :])
        assert (0, 128, 128) == tuple(ybr[0, 65, 50, :])
        assert (64, 128, 128) == tuple(ybr[0, 75, 50, :])
        assert (192, 128, 128) == tuple(ybr[0, 85, 50, :])
        assert (255, 128, 128) == tuple(ybr[0, 95, 50, :])
        # Frame 2
        assert (179, 171, 1) == tuple(ybr[1, 5, 50, :])
        assert (89, 149, 65) == tuple(ybr[1, 15, 50, :])
        assert (105, 212, 235) == tuple(ybr[1, 25, 50, :])
        assert (52, 170, 181) == tuple(ybr[1, 35, 50, :])
        assert (226, 1, 149) == tuple(ybr[1, 45, 50, :])
        assert (113, 65, 138) == tuple(ybr[1, 55, 50, :])
        assert (255, 128, 128) == tuple(ybr[1, 65, 50, :])
        assert (191, 128, 128) == tuple(ybr[1, 75, 50, :])
        assert (63, 128, 128) == tuple(ybr[1, 85, 50, :])
        assert (0, 128, 128) == tuple(ybr[1, 95, 50, :])

        # Round trip -> rounding errors get compounded
        rgb = convert_color_space(ybr, "YBR_FULL", "RGB")
        # All pixels within +/- 1 units
        assert np.allclose(rgb, arr, atol=1)
        assert rgb.shape == arr.shape

    def test_frame_by_frame(self):
        """Test processing frame-by-frame."""
        ds = dcmread(RGB_8_3_2F)

        arr = ds.pixel_array
        ybr = convert_color_space(arr, "RGB", "YBR_FULL", per_frame=True)
        assert (76, 85, 255) == tuple(ybr[0, 5, 50, :])
        assert (166, 107, 192) == tuple(ybr[0, 15, 50, :])
        assert (150, 44, 21) == tuple(ybr[0, 25, 50, :])
        assert (203, 86, 75) == tuple(ybr[0, 35, 50, :])
        assert (29, 255, 107) == tuple(ybr[0, 45, 50, :])
        assert (142, 192, 118) == tuple(ybr[0, 55, 50, :])
        assert (0, 128, 128) == tuple(ybr[0, 65, 50, :])
        assert (64, 128, 128) == tuple(ybr[0, 75, 50, :])
        assert (192, 128, 128) == tuple(ybr[0, 85, 50, :])
        assert (255, 128, 128) == tuple(ybr[0, 95, 50, :])
        # Frame 2
        assert (179, 171, 1) == tuple(ybr[1, 5, 50, :])
        assert (89, 149, 65) == tuple(ybr[1, 15, 50, :])
        assert (105, 212, 235) == tuple(ybr[1, 25, 50, :])
        assert (52, 170, 181) == tuple(ybr[1, 35, 50, :])
        assert (226, 1, 149) == tuple(ybr[1, 45, 50, :])
        assert (113, 65, 138) == tuple(ybr[1, 55, 50, :])
        assert (255, 128, 128) == tuple(ybr[1, 65, 50, :])
        assert (191, 128, 128) == tuple(ybr[1, 75, 50, :])
        assert (63, 128, 128) == tuple(ybr[1, 85, 50, :])
        assert (0, 128, 128) == tuple(ybr[1, 95, 50, :])

    def test_unsuitable_dtype_raises(self):
        """Test that non u1 dtypes raise an exception."""
        msg = (
            "Invalid ndarray.dtype 'int8' for color space conversion, "
            "must be 'uint8' or an equivalent"
        )
        with pytest.raises(ValueError, match=msg):
            convert_color_space(np.ones((2, 3), dtype="i1"), "RGB", "YBR_FULL")

        msg = (
            "Invalid ndarray.dtype 'uint16' for color space conversion, "
            "must be 'uint8'"
        )
        with pytest.raises(ValueError, match=msg):
            convert_color_space(np.ones((2, 3), dtype="u2"), "RGB", "YBR_FULL")


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestModalityLUT:
    """Tests for apply_modality_lut()."""

    def test_slope_intercept(self):
        """Test the rescale slope/intercept transform."""
        ds = dcmread(MOD_16)
        assert 1 == ds.RescaleSlope
        assert -1024 == ds.RescaleIntercept
        arr = ds.pixel_array
        out = apply_modality_lut(arr, ds)
        assert out.flags.writeable
        assert np.float64 == out.dtype

        assert np.array_equal(arr - 1024, out)

        ds.RescaleSlope = 2.5
        ds.RescaleIntercept = -2048
        out = apply_modality_lut(arr, ds)
        assert np.array_equal(arr * 2.5 - 2048, out)

    def test_lut_sequence(self):
        """Test the LUT Sequence transform."""
        # Unused bits don't match interpretation!
        ds = dcmread(MOD_16_SEQ)
        assert ds.BitsAllocated == 16
        assert ds.BitsStored == 12
        seq = ds.ModalityLUTSequence[0]
        assert [4096, -2048, 16] == seq.LUTDescriptor

        arr = ds.pixel_array
        assert -2048 == arr.min()
        assert 2047 == arr.max()

        out = apply_modality_lut(arr, ds)
        assert out.flags.writeable
        assert out.dtype == np.uint16
        assert [32759, 32759, 49147, 49147, 32759] == list(out[0, 50:55])
        assert [65535, 0, 0, 65535, 65535] == list(out[50, 50:55])
        assert [65535, 0, 0, 0, 65535] == list(out[100, 50:55])
        assert [32759, 32759, 49147, 49147, 32759] == list(out[150, 50:55])
        assert [32759, 32759, 49147, 49147, 32759] == list(out[200, 50:55])
        assert 39321 == out[185, 340]
        assert 45867 == out[185, 385]
        assert 52428 == out[228, 385]
        assert 58974 == out[291, 385]

    def test_lut_sequence_zero_entries(self):
        """Test that 0 entries is interpreted correctly."""
        # LUTDescriptor[0] of 0 -> 65536, but only 4096 entries so any
        # attempt to access LUTData[4096] or higher will raise IndexError
        ds = dcmread(MOD_16_SEQ)
        seq = ds.ModalityLUTSequence[0]
        seq.LUTDescriptor = [0, 0, 16]
        assert 4096 == len(seq.LUTData)
        arr = np.asarray([0, 4095, 4096, 65535])
        msg = r"index 4096 is out of bounds"
        with pytest.raises(IndexError, match=msg):
            apply_modality_lut(arr, ds)

        # LUTData with 65536 entries
        seq.LUTData = [0] * 65535 + [1]
        out = apply_modality_lut(arr, ds)
        assert [0, 0, 0, 1] == list(out)

    def test_unchanged(self):
        """Test no modality LUT transform."""
        ds = dcmread(MOD_16)
        del ds.RescaleSlope
        del ds.RescaleIntercept
        arr = ds.pixel_array
        out = apply_modality_lut(arr, ds)
        assert arr is out

        ds.ModalityLUTSequence = []
        out = apply_modality_lut(arr, ds)
        assert arr is out

    def test_lutdata_ow(self):
        """Test LUT Data with VR OW."""
        ds = dcmread(MOD_16_SEQ)
        assert ds.original_encoding == (False, True)
        seq = ds.ModalityLUTSequence[0]
        assert [4096, -2048, 16] == seq.LUTDescriptor
        seq["LUTData"].VR = "OW"
        seq.LUTData = pack("<4096H", *seq.LUTData)
        arr = ds.pixel_array
        assert -2048 == arr.min()
        assert 2047 == arr.max()

        out = apply_modality_lut(arr, ds)
        assert out.flags.writeable
        assert out.dtype == np.uint16
        assert [32759, 32759, 49147, 49147, 32759] == list(out[0, 50:55])
        assert [65535, 0, 0, 65535, 65535] == list(out[50, 50:55])
        assert [65535, 0, 0, 0, 65535] == list(out[100, 50:55])
        assert [32759, 32759, 49147, 49147, 32759] == list(out[150, 50:55])
        assert [32759, 32759, 49147, 49147, 32759] == list(out[200, 50:55])
        assert 39321 == out[185, 340]
        assert 45867 == out[185, 385]
        assert 52428 == out[228, 385]
        assert 58974 == out[291, 385]

    def test_no_endianness_raises(self):
        ds = dcmread(MOD_16_SEQ)
        assert ds.original_encoding == (False, True)
        seq = ds.ModalityLUTSequence[0]
        assert [4096, -2048, 16] == seq.LUTDescriptor
        seq["LUTData"].VR = "OW"
        seq.LUTData = pack("<4096H", *seq.LUTData)
        arr = ds.pixel_array
        del ds.file_meta
        ds._read_little = None
        msg = (
            "Unable to determine the endianness of the dataset, please set "
            "an appropriate Transfer Syntax UID in 'FileDataset.file_meta'"
        )
        with pytest.raises(AttributeError, match=msg):
            apply_modality_lut(arr, ds)

    def test_file_meta(self):
        """Test using file meta to determine endianness"""
        ds = dcmread(MOD_16_SEQ)
        seq = ds.ModalityLUTSequence[0]
        assert [4096, -2048, 16] == seq.LUTDescriptor
        seq["LUTData"].VR = "OW"
        seq.LUTData = pack("<4096H", *seq.LUTData)
        arr = ds.pixel_array
        ds._read_little = None
        out = apply_modality_lut(arr, ds)

        assert 39321 == out[185, 340]
        assert 45867 == out[185, 385]
        assert 52428 == out[228, 385]
        assert 58974 == out[291, 385]

    def test_original_encoding(self):
        """Test using original encoding to determine endianness"""
        ds = dcmread(MOD_16_SEQ)
        seq = ds.ModalityLUTSequence[0]
        assert [4096, -2048, 16] == seq.LUTDescriptor
        seq["LUTData"].VR = "OW"
        seq.LUTData = pack("<4096H", *seq.LUTData)
        arr = ds.pixel_array
        del ds.file_meta
        assert ds.original_encoding == (False, True)
        out = apply_modality_lut(arr, ds)

        assert 39321 == out[185, 340]
        assert 45867 == out[185, 385]
        assert 52428 == out[228, 385]
        assert 58974 == out[291, 385]


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestApplyColorLUT:
    """Tests for apply_color_lut()."""

    def setup_method(self):
        """Setup the tests"""
        self.o_palette = get_palette_files("pet.dcm")[0]
        self.n_palette = get_palette_files("pet.dcm")[0][:-3] + "tmp"

    def teardown_method(self):
        """Teardown the tests"""
        if os.path.exists(self.n_palette):
            os.rename(self.n_palette, self.o_palette)

    def test_neither_ds_nor_palette_raises(self):
        """Test missing `ds` and `palette` raise an exception."""
        ds = dcmread(PAL_08_256_0_16_1F)
        msg = r"Either 'ds' or 'palette' is required"
        with pytest.raises(ValueError, match=msg):
            apply_color_lut(ds.pixel_array)

    def test_palette_unknown_raises(self, disable_value_validation):
        """Test using an unknown `palette` raise an exception."""
        ds = dcmread(PAL_08_256_0_16_1F)
        # Palette name
        msg = r"Unknown palette 'TEST'"
        with pytest.raises(ValueError, match=msg):
            apply_color_lut(ds.pixel_array, palette="TEST")

        # SOP Instance UID
        msg = r"Unknown palette '1.2.840.10008.1.1'"
        with pytest.raises(ValueError, match=msg):
            apply_color_lut(ds.pixel_array, palette="1.2.840.10008.1.1")

    def test_palette_unavailable_raises(self, disable_value_validation):
        """Test using a missing `palette` raise an exception."""
        os.rename(self.o_palette, self.n_palette)
        ds = dcmread(PAL_08_256_0_16_1F)
        msg = r"list index out of range"
        with pytest.raises(IndexError, match=msg):
            apply_color_lut(ds.pixel_array, palette="PET")

    def test_supplemental_raises(self):
        """Test that supplemental palette color LUT raises exception."""
        ds = dcmread(SUP_16_16_2F)
        msg = (
            r"Use of this function with the Supplemental Palette Color Lookup "
            r"Table Module is not currently supported"
        )
        with pytest.raises(ValueError, match=msg):
            apply_color_lut(ds.pixel_array, ds)

    def test_invalid_bit_depth_raises(self):
        """Test that an invalid bit depth raises an exception."""
        ds = dcmread(PAL_08_256_0_16_1F)
        ds.RedPaletteColorLookupTableDescriptor[2] = 15
        msg = r"data type ['\"]uint15['\"] not understood"
        with pytest.raises(TypeError, match=msg):
            apply_color_lut(ds.pixel_array, ds)

    def test_invalid_lut_bit_depth_raises(self):
        """Test that an invalid LUT bit depth raises an exception."""
        ds = dcmread(PAL_08_256_0_16_1F)
        ds.RedPaletteColorLookupTableData = ds.RedPaletteColorLookupTableData[:-2]
        ds.GreenPaletteColorLookupTableData = ds.GreenPaletteColorLookupTableData[:-2]
        ds.BluePaletteColorLookupTableData = ds.BluePaletteColorLookupTableData[:-2]
        msg = (
            r"The bit depth of the LUT data '15.9' is invalid \(only 8 or 16 "
            r"bits per entry allowed\)"
        )
        with pytest.raises(ValueError, match=msg):
            apply_color_lut(ds.pixel_array, ds)

    def test_unequal_lut_length_raises(self):
        """Test that an unequal LUT lengths raise an exception."""
        ds = dcmread(PAL_08_256_0_16_1F)
        ds.BluePaletteColorLookupTableData = ds.BluePaletteColorLookupTableData[:-2]
        msg = r"LUT data must be the same length"
        with pytest.raises(ValueError, match=msg):
            apply_color_lut(ds.pixel_array, ds)

    def test_no_palette_color(self):
        """Test that an unequal LUT lengths raise an exception."""
        ds = dcmread(PAL_08_256_0_16_1F)
        del ds.RedPaletteColorLookupTableData
        msg = r"No suitable Palette Color Lookup Table Module found"
        with pytest.raises(ValueError, match=msg):
            apply_color_lut(ds.pixel_array, ds)

    def test_uint08_16(self):
        """Test uint8 Pixel Data with 16-bit LUT entries."""
        ds = dcmread(PAL_08_200_0_16_1F, force=True)
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        assert 8 == ds.BitsStored
        assert 16 == ds.RedPaletteColorLookupTableDescriptor[2]
        arr = ds.pixel_array
        orig = arr.copy()
        rgb = apply_color_lut(arr, ds)
        assert (480, 640, 3) == rgb.shape
        assert [0, 0, 0] == list(rgb[0, 0, :])
        assert [9216, 9216, 9216] == list(rgb[0, 4, :])
        assert [18688, 18688, 18688] == list(rgb[0, 9, :])
        assert [27904, 33536, 0] == list(rgb[0, 638, :])
        assert [18688, 24320, 0] == list(rgb[479, 639, :])

        # original `arr` is unchanged
        assert np.array_equal(orig, arr)

    def test_uint08_16_2frame(self):
        """Test 2 frame uint8 Pixel Data with 16-bit LUT entries."""
        ds = dcmread(PAL_08_256_0_16_2F)
        assert 8 == ds.BitsStored
        assert 16 == ds.RedPaletteColorLookupTableDescriptor[2]
        arr = ds.pixel_array
        orig = arr.copy()
        rgb = apply_color_lut(arr, ds)
        assert (2, 600, 800, 3) == rgb.shape
        assert [9472, 15872, 24064] == list(rgb[0, 0, 0, :])
        assert [34816, 43520, 54016] == list(rgb[0, 12, 12, :])
        assert [65280, 65280, 65280] == list(rgb[0, 17, 110, :])
        assert [0, 0, 0] == list(rgb[0, 77, 103, :])
        assert [23040, 52480, 65280] == list(rgb[0, 478, 793, :])

        # 2nd frame is inverse of 1st, so won't be coloured correctly
        ref = np.asarray(
            [
                [26112, 26112, 26112],
                [54528, 54528, 54528],
                [54528, 54528, 54528],
                [16640, 16640, 16640],
                [49152, 45056, 22016],
                [34816, 43520, 54016],
                [5632, 9984, 14848],
                [62464, 2816, 2816],
                [3072, 5632, 8192],
                [3072, 5632, 8192],
            ]
        )
        assert np.array_equal(ref, rgb[1, 143:153, 355, :])

        # original `arr` is unchanged
        assert np.array_equal(orig, arr)

    def test_uint16_16_segmented_little(self):
        """Test uint16 Pixel Data with 16-bit LUT entries."""
        # Endianness from file_meta
        ds = dcmread(PAL_SEG_LE_16_1F)
        assert 16 == ds.BitsStored
        assert 16 == ds.RedPaletteColorLookupTableDescriptor[2]
        arr = ds.pixel_array
        orig = arr.copy()
        rgb = apply_color_lut(arr, ds)
        assert (480, 640, 3) == rgb.shape
        assert [10280, 11565, 16705] == list(rgb[0, 0, :])
        assert [10280, 11565, 16705] == list(rgb[0, 320, :])
        assert [10280, 11565, 16705] == list(rgb[0, 639, :])
        assert [0, 0, 0] == list(rgb[240, 0, :])
        assert [257, 257, 257] == list(rgb[240, 320, :])
        assert [2313, 2313, 2313] == list(rgb[240, 639, :])
        assert [10280, 11565, 16705] == list(rgb[479, 0, :])
        assert [10280, 11565, 16705] == list(rgb[479, 320, :])
        assert [10280, 11565, 16705] == list(rgb[479, 639, :])

        assert (orig == arr).all()

        # Endianness from original encoding
        ds = dcmread(PAL_SEG_LE_16_1F)
        assert 16 == ds.BitsStored
        assert 16 == ds.RedPaletteColorLookupTableDescriptor[2]
        arr = ds.pixel_array
        orig = arr.copy()
        del ds.file_meta
        rgb = apply_color_lut(arr, ds)
        assert (480, 640, 3) == rgb.shape
        assert [10280, 11565, 16705] == list(rgb[0, 0, :])
        assert [10280, 11565, 16705] == list(rgb[0, 320, :])
        assert [10280, 11565, 16705] == list(rgb[0, 639, :])
        assert [0, 0, 0] == list(rgb[240, 0, :])
        assert [257, 257, 257] == list(rgb[240, 320, :])
        assert [2313, 2313, 2313] == list(rgb[240, 639, :])
        assert [10280, 11565, 16705] == list(rgb[479, 0, :])
        assert [10280, 11565, 16705] == list(rgb[479, 320, :])
        assert [10280, 11565, 16705] == list(rgb[479, 639, :])

        assert (orig == arr).all()

        # No endianness raises
        ds._read_little = None
        msg = (
            "Unable to determine the endianness of the dataset, please set "
            "an appropriate Transfer Syntax UID in 'FileDataset.file_meta'"
        )
        with pytest.raises(AttributeError, match=msg):
            apply_color_lut(arr, ds)

    def test_uint16_16_segmented_big(self):
        """Test big endian uint16 Pixel Data with 16-bit LUT entries."""
        ds = dcmread(PAL_SEG_BE_16_1F)
        assert 16 == ds.BitsStored
        assert 16 == ds.RedPaletteColorLookupTableDescriptor[2]
        arr = ds.pixel_array
        rgb = apply_color_lut(arr, ds)
        assert (480, 640, 3) == rgb.shape
        assert [10280, 11565, 16705] == list(rgb[0, 0, :])
        assert [10280, 11565, 16705] == list(rgb[0, 320, :])
        assert [10280, 11565, 16705] == list(rgb[0, 639, :])
        assert [0, 0, 0] == list(rgb[240, 0, :])
        assert [257, 257, 257] == list(rgb[240, 320, :])
        assert [2313, 2313, 2313] == list(rgb[240, 639, :])
        assert [10280, 11565, 16705] == list(rgb[479, 0, :])
        assert [10280, 11565, 16705] == list(rgb[479, 320, :])
        assert [10280, 11565, 16705] == list(rgb[479, 639, :])

    def test_16_allocated_8_entries(self):
        """Test LUT with 8-bit entries in 16 bits allocated."""
        ds = dcmread(PAL_08_200_0_16_1F, force=True)
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        ds.RedPaletteColorLookupTableDescriptor = [200, 0, 8]
        lut = pack("<200H", *list(range(0, 200)))
        assert 400 == len(lut)
        ds.RedPaletteColorLookupTableData = lut
        ds.GreenPaletteColorLookupTableData = lut
        ds.BluePaletteColorLookupTableData = lut
        arr = ds.pixel_array
        assert (56, 149) == (arr.min(), arr.max())
        out = apply_color_lut(arr, ds)
        # Because the LUTs are mapped index to value (i.e. LUT[0] = 0,
        # LUT[149] = 149), the output array should equal the input array
        # but with three channels of identical values
        assert np.array_equal(arr, out[:, :, 0])
        assert np.array_equal(arr, out[:, :, 1])
        assert np.array_equal(arr, out[:, :, 2])

    def test_alpha(self):
        """Test applying a color palette with an alpha channel."""
        ds = dcmread(PAL_08_256_0_16_1F)
        ds.AlphaPaletteColorLookupTableData = b"\x00\x80" * 256
        arr = ds.pixel_array
        rgba = apply_color_lut(arr, ds)
        assert (600, 800, 4) == rgba.shape
        assert 32768 == rgba[:, :, 3][0, 0]
        assert (32768 == rgba[:, :, 3]).any()

    def test_well_known_palette(self, disable_value_validation):
        """Test using a well-known palette."""
        ds = dcmread(PAL_08_256_0_16_1F)
        # Drop it to 8-bit
        arr = ds.pixel_array
        rgb = apply_color_lut(arr, palette="PET")
        line = rgb[68:88, 364, :]
        ref = [
            [249, 122, 12],
            [255, 130, 4],
            [255, 136, 16],
            [255, 134, 12],
            [253, 126, 4],
            [239, 112, 32],
            [211, 84, 88],
            [197, 70, 116],
            [177, 50, 156],
            [168, 40, 176],
            [173, 46, 164],
            [185, 58, 140],
            [207, 80, 96],
            [209, 82, 92],
            [189, 62, 132],
            [173, 46, 164],
            [168, 40, 176],
            [162, 34, 188],
            [162, 34, 188],
            [154, 26, 204],
        ]
        assert np.array_equal(np.asarray(ref), line)
        uid = apply_color_lut(arr, palette="1.2.840.10008.1.5.2")
        assert np.array_equal(uid, rgb)

    def test_first_map_positive(self):
        """Test a positive first mapping value."""
        ds = dcmread(PAL_08_200_0_16_1F, force=True)
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        ds.RedPaletteColorLookupTableDescriptor[1] = 10
        arr = ds.pixel_array
        rgb = apply_color_lut(arr, ds)
        # All IVs < 10 should be set to LUT[0]
        # All IVs >= 10 should be shifted down 10 entries
        # Original IV range is 56 to 149 -> 46 to 139
        # LUT[88] -> LUT[78] = [33280, 56320, 65280]
        # LUT[149] -> LUT[139] = [50944, 16384, 27904]
        assert [33280, 56320, 65280] == list(rgb[arr == 88][0])
        assert ([33280, 56320, 65280] == rgb[arr == 88]).all()
        assert [50944, 16384, 27904] == list(rgb[arr == 149][0])
        assert ([50944, 16384, 27904] == rgb[arr == 149]).all()

    def test_first_map_negative(self):
        """Test a negative first mapping value."""
        ds = dcmread(PAL_08_200_0_16_1F, force=True)
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        ds["RedPaletteColorLookupTableDescriptor"].VR = "SS"
        ds.RedPaletteColorLookupTableDescriptor[1] = -10
        arr = ds.pixel_array
        rgb = apply_color_lut(arr, ds)
        # All IVs < -10 should be set to LUT[0]
        # All IVs >= -10 should be shifted up 10 entries
        # Original IV range is 56 to 149 -> 66 to 159
        # LUT[60] -> LUT[70] = [33280 61952 65280]
        # LUT[130] -> LUT[140] = [60160, 25600, 37376]
        assert [33280, 61952, 65280] == list(rgb[arr == 60][0])
        assert ([33280, 61952, 65280] == rgb[arr == 60]).all()
        assert [60160, 25600, 37376] == list(rgb[arr == 130][0])
        assert ([60160, 25600, 37376] == rgb[arr == 130]).all()

    def test_unchanged(self):
        """Test dataset with no LUT is unchanged."""
        # Regression test for #1068
        ds = dcmread(MOD_16, force=True)
        assert "RedPaletteColorLookupTableDescriptor" not in ds
        msg = r"No suitable Palette Color Lookup Table Module found"
        with pytest.raises(ValueError, match=msg):
            apply_color_lut(ds.pixel_array, ds)


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestExpandSegmentedLUT:
    """Tests for _expand_segmented_lut()."""

    def test_discrete(self):
        """Test expanding a discrete segment."""
        data = (0, 1, 0)
        assert [0] == _expand_segmented_lut(data, "H")

        data = (0, 2, 0, 112)
        assert [0, 112] == _expand_segmented_lut(data, "H")

        data = (0, 2, 0, -112)
        assert [0, -112] == _expand_segmented_lut(data, "H")

        data = (0, 2, 0, 112, 0, 0)
        assert [0, 112] == _expand_segmented_lut(data, "H")

        data = (0, 2, 0, -112, 0, 0)
        assert [0, -112] == _expand_segmented_lut(data, "H")

    def test_linear(self):
        """Test expanding a linear segment."""
        # Linear can never be the first segment
        # Positive slope
        data = (0, 2, 0, 28672, 1, 5, 49152)
        out = _expand_segmented_lut(data, "H")
        assert [0, 28672, 32768, 36864, 40960, 45056, 49152] == out

        data = (0, 1, -400, 1, 5, 0)
        out = _expand_segmented_lut(data, "H")
        assert [-400, -320, -240, -160, -80, 0] == out

        # Positive slope, floating point steps
        data = (0, 1, 163, 1, 48, 255)
        out = _expand_segmented_lut(data, "H")
        assert (1 + 48) == len(out)

        # No slope
        data = (0, 2, 0, 28672, 1, 5, 28672)
        out = _expand_segmented_lut(data, "H")
        assert [0, 28672, 28672, 28672, 28672, 28672, 28672] == out

        data = (0, 1, -100, 1, 5, -100)
        out = _expand_segmented_lut(data, "H")
        assert [-100, -100, -100, -100, -100, -100] == out

        # Negative slope
        data = (0, 2, 0, 49152, 1, 5, 28672)
        out = _expand_segmented_lut(data, "H")
        assert [0, 49152, 45056, 40960, 36864, 32768, 28672] == out

        data = (0, 1, 0, 1, 5, -400)
        out = _expand_segmented_lut(data, "H")
        assert [0, -80, -160, -240, -320, -400] == out

    def test_indirect_08(self):
        """Test expanding an indirect segment encoded as 8-bit."""
        # No real world test data available for this
        # LSB, MSB
        ref_a = [0, 112, 128, 144, 160, 176, 192, 192, 192, 192, 192, 192]

        # Little endian
        data = (0, 2, 0, 112, 1, 5, 192, 2, 1, 4, 0, 0, 0)
        out = _expand_segmented_lut(data, "<B")
        assert ref_a == out

        data = (0, 2, 0, 112, 2, 1, 0, 0, 0, 0)
        out = _expand_segmented_lut(data, "<B")
        assert [0, 112, 0, 112] == out

        # 0x0100 0x0302 is 66051 in LE 16-bit MSB, LSB
        data = [0, 1, 0] * 22017 + [0, 2, 1, 2] + [2, 1, 3, 2, 1, 0]
        out = _expand_segmented_lut(data, "<B")
        assert [0] * 22017 + [1, 2, 1, 2] == out

        # Big endian
        data = (0, 2, 0, 112, 1, 5, 192, 2, 1, 0, 4, 0, 0)
        out = _expand_segmented_lut(data, ">B")
        assert ref_a == out

        data = (0, 2, 0, 112, 2, 1, 0, 0, 0, 0)
        out = _expand_segmented_lut(data, ">B")
        assert [0, 112, 0, 112] == out

        # 0x0001 0x0203 is 66051 in BE 16-bit MSB, LSB
        data = [0, 1, 0] * 22017 + [0, 2, 1, 2] + [2, 1, 2, 3, 0, 1]
        out = _expand_segmented_lut(data, ">B")
        assert [0] * 22017 + [1, 2, 1, 2] == out

    def test_indirect_16(self):
        """Test expanding an indirect segment encoded as 16-bit."""
        # Start from a discrete segment
        data = (0, 2, 0, 112, 1, 5, 192, 2, 2, 0, 0)
        out = _expand_segmented_lut(data, "H")
        assert [0, 112, 128, 144, 160, 176, 192] * 2 == out

        # Start from a linear segment
        data = (0, 2, 0, 112, 1, 5, 192, 2, 1, 4, 0)
        out = _expand_segmented_lut(data, "H")
        assert [0, 112, 128, 144, 160, 176, 192, 192, 192, 192, 192, 192] == out

    def test_palettes_spring(self):
        """Test expanding the SPRING palette."""
        ds = dcmread(get_palette_files("spring.dcm")[0])

        bs = ds.SegmentedRedPaletteColorLookupTableData
        fmt = f"<{len(bs)}B"
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert [255] * 256 == out

        bs = ds.SegmentedGreenPaletteColorLookupTableData
        fmt = f"<{len(bs)}B"
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert list(range(0, 256)) == out

        bs = ds.SegmentedBluePaletteColorLookupTableData
        fmt = f"<{len(bs)}B"
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert list(range(255, -1, -1)) == out

    def test_palettes_summer(self):
        """Test expanding the SUMMER palette."""
        ds = dcmread(get_palette_files("summer.dcm")[0])

        bs = ds.SegmentedRedPaletteColorLookupTableData
        fmt = f"<{len(bs)}B"
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert [0] * 256 == out

        bs = ds.SegmentedGreenPaletteColorLookupTableData
        fmt = f"<{len(bs)}B"
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert [255, 255, 254, 254, 253] == out[:5]
        assert [130, 129, 129, 128, 128] == out[-5:]

        bs = ds.SegmentedBluePaletteColorLookupTableData
        fmt = f"<{len(bs)}B"
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert [0] * 128 == out[:128]
        assert [246, 248, 250, 252, 254] == out[-5:]

    def test_palettes_fall(self):
        """Test expanding the FALL palette."""
        ds = dcmread(get_palette_files("fall.dcm")[0])

        bs = ds.SegmentedRedPaletteColorLookupTableData
        fmt = f"<{len(bs)}B"
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert [255] * 256 == out

        bs = ds.SegmentedGreenPaletteColorLookupTableData
        fmt = f"<{len(bs)}B"
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert list(range(255, -1, -1)) == out

        bs = ds.SegmentedBluePaletteColorLookupTableData
        fmt = f"<{len(bs)}B"
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert [0] * 256 == out

    def test_palettes_winter(self):
        """Test expanding the WINTER palette."""
        ds = dcmread(get_palette_files("winter.dcm")[0])

        bs = ds.SegmentedRedPaletteColorLookupTableData
        fmt = f"<{len(bs)}B"
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert [0] * 128 == out[:128]
        assert [123, 124, 125, 126, 127] == out[-5:]

        bs = ds.SegmentedGreenPaletteColorLookupTableData
        fmt = f"<{len(bs)}B"
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert list(range(0, 256)) == out

        bs = ds.SegmentedBluePaletteColorLookupTableData
        fmt = f"<{len(bs)}B"
        data = unpack(fmt, bs)
        out = _expand_segmented_lut(data, fmt)
        assert [255, 255, 254, 254, 253] == out[:5]
        assert [130, 129, 129, 128, 128] == out[-5:]

    def test_first_linear_raises(self):
        """Test having a linear segment first raises exception."""
        data = (1, 5, 49152)
        msg = (
            r"Error expanding a segmented palette color lookup table: "
            r"the first segment cannot be a linear segment"
        )
        with pytest.raises(ValueError, match=msg):
            _expand_segmented_lut(data, "H")

    def test_first_indirect_raises(self):
        """Test having a linear segment first raises exception."""
        data = (2, 5, 2, 0)
        msg = (
            r"Error expanding a segmented palette color lookup table: "
            r"the first segment cannot be an indirect segment"
        )
        with pytest.raises(ValueError, match=msg):
            _expand_segmented_lut(data, "H")

    def test_unknown_opcode_raises(self):
        """Test having an unknown opcode raises exception."""
        data = (3, 5, 49152)
        msg = (
            r"Error expanding a segmented palette lookup table: "
            r"unknown segment type '3'"
        )
        with pytest.raises(ValueError, match=msg):
            _expand_segmented_lut(data, "H")


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestApplyWindowing:
    """Tests for apply_windowing()."""

    def test_window_single_view(self):
        """Test windowing with a single view."""
        # 12-bit unsigned
        ds = dcmread(WIN_12_1F)
        assert 16 == ds.BitsAllocated
        assert 12 == ds.BitsStored
        assert 0 == ds.PixelRepresentation
        ds.WindowCenter = 450
        ds.WindowWidth = 790
        assert 450 == ds.WindowCenter
        assert 790 == ds.WindowWidth

        arr = ds.pixel_array
        assert 642 == arr[326, 130]
        out = apply_windowing(arr, ds)
        assert 3046.6 == pytest.approx(out[326, 130], abs=0.1)

    def test_window_multi_view(self):
        """Test windowing with multiple views."""
        ds = dcmread(WIN_12_1F)
        assert 16 == ds.BitsAllocated
        assert 12 == ds.BitsStored
        assert 0 == ds.PixelRepresentation
        if HAVE_NP and config.use_DS_numpy:
            expected = np.array([450, 200])
            assert np.allclose(ds.WindowCenter, expected)
            expected = np.array([790, 443])
            assert np.allclose(ds.WindowWidth, expected)
        else:
            assert [450, 200] == ds.WindowCenter
            assert [790, 443] == ds.WindowWidth

        arr = ds.pixel_array
        assert 642 == arr[326, 130]
        out = apply_windowing(arr, ds)
        assert 3046.6 == pytest.approx(out[326, 130], abs=0.1)
        out = apply_windowing(arr, ds, index=1)
        assert 4095.0 == pytest.approx(out[326, 130], abs=0.1)

    def test_window_uint8(self):
        """Test windowing an 8-bit unsigned array."""
        ds = Dataset()
        ds.PhotometricInterpretation = "MONOCHROME1"
        ds.PixelRepresentation = 0
        ds.BitsStored = 8
        arr = np.asarray([0, 1, 128, 254, 255], dtype="uint8")

        # Linear
        ds.WindowWidth = 1
        ds.WindowCenter = 0
        assert [255, 255, 255, 255, 255] == apply_windowing(arr, ds).tolist()

        ds.WindowWidth = 128
        ds.WindowCenter = 254
        assert [0, 0, 0, 128.5, 130.5] == pytest.approx(
            apply_windowing(arr, ds).tolist(), abs=0.1
        )

        # Linear exact
        ds.VOILUTFunction = "LINEAR_EXACT"
        assert [0, 0, 0, 127.5, 129.5] == pytest.approx(
            apply_windowing(arr, ds).tolist(), abs=0.1
        )

        # Sigmoid
        ds.VOILUTFunction = "SIGMOID"
        assert [0.1, 0.1, 4.9, 127.5, 129.5] == pytest.approx(
            apply_windowing(arr, ds).tolist(), abs=0.1
        )

    def test_window_uint16(self):
        """Test windowing a 16-bit unsigned array."""
        ds = Dataset()
        ds.PhotometricInterpretation = "MONOCHROME1"
        ds.PixelRepresentation = 0
        ds.BitsStored = 16
        arr = np.asarray([0, 1, 32768, 65534, 65535], dtype="uint16")

        ds.WindowWidth = 1
        ds.WindowCenter = 0
        assert [65535] * 5 == apply_windowing(arr, ds).tolist()

        ds.WindowWidth = 32768
        ds.WindowCenter = 254
        assert [32260.5, 32262.5, 65535, 65535, 65535] == pytest.approx(
            apply_windowing(arr, ds).tolist(), abs=0.1
        )

        ds.VOILUTFunction = "LINEAR_EXACT"
        assert [32259.5, 32261.5, 65535, 65535, 65535] == pytest.approx(
            apply_windowing(arr, ds).tolist(), abs=0.1
        )

        ds.VOILUTFunction = "SIGMOID"
        assert [32259.5, 32261.5, 64319.8, 65512.3, 65512.3] == pytest.approx(
            apply_windowing(arr, ds).tolist(), abs=0.1
        )

    def test_window_uint32(self):
        """Test windowing a 32-bit unsigned array."""
        ds = Dataset()
        ds.PhotometricInterpretation = "MONOCHROME1"
        ds.PixelRepresentation = 0
        ds.BitsStored = 32
        y_max = 2**32 - 1
        arr = np.asarray([0, 1, 2**31, y_max - 1, y_max], dtype="uint32")

        ds.WindowWidth = 1
        ds.WindowCenter = 0
        assert [y_max] * 5 == apply_windowing(arr, ds).tolist()

        ds.WindowWidth = 342423423423
        ds.WindowCenter = 757336
        assert [
            2147474148.4,
            2147474148.4,
            2174409724,
            2201345299.7,
            2201345299.7,
        ] == pytest.approx(apply_windowing(arr, ds).tolist(), abs=0.1)

        ds.VOILUTFunction = "LINEAR_EXACT"
        assert [
            2147474148.3,
            2147474148.4,
            2174409724,
            2201345299.7,
            2201345299.7,
        ] == pytest.approx(apply_windowing(arr, ds).tolist(), abs=0.1)

        ds.VOILUTFunction = "SIGMOID"
        assert [
            2147474148.3,
            2147474148.4,
            2174408313.1,
            2201334008.2,
            2201334008.3,
        ] == pytest.approx(apply_windowing(arr, ds).tolist(), abs=0.1)

    def test_window_int8(self):
        """Test windowing an 8-bit signed array."""
        ds = Dataset()
        ds.PhotometricInterpretation = "MONOCHROME1"
        ds.PixelRepresentation = 1
        ds.BitsStored = 8
        arr = np.asarray([-128, -127, -1, 0, 1, 126, 127], dtype="int8")

        # Linear
        ds.WindowWidth = 1
        ds.WindowCenter = 0
        assert [-128, -128, -128, 127, 127, 127, 127] == pytest.approx(
            apply_windowing(arr, ds).tolist()
        )

        ds.WindowWidth = 128
        ds.WindowCenter = -5
        assert [-128, -128, 8.5, 10.5, 12.6, 127, 127] == pytest.approx(
            apply_windowing(arr, ds).tolist(), abs=0.1
        )

        # Linear exact
        ds.VOILUTFunction = "LINEAR_EXACT"
        assert [-128, -128, 7.5, 9.5, 11.5, 127, 127] == pytest.approx(
            apply_windowing(arr, ds).tolist(), abs=0.1
        )

        # Sigmoid
        ds.VOILUTFunction = "SIGMOID"
        assert [-122.7, -122.5, 7.5, 9.4, 11.4, 122.8, 122.9] == pytest.approx(
            apply_windowing(arr, ds).tolist(), abs=0.1
        )

    def test_window_int16(self):
        """Test windowing an 8-bit signed array."""
        ds = Dataset()
        ds.PhotometricInterpretation = "MONOCHROME1"
        ds.PixelRepresentation = 1
        ds.BitsStored = 16
        arr = np.asarray([-128, -127, -1, 0, 1, 126, 127], dtype="int16")

        # Linear
        ds.WindowWidth = 1
        ds.WindowCenter = 0
        assert [-32768, -32768, -32768, 32767, 32767, 32767, 32767] == pytest.approx(
            apply_windowing(arr, ds).tolist(), abs=0.1
        )

        ds.WindowWidth = 128
        ds.WindowCenter = -5
        assert [-32768, -32768, 2321.6, 2837.6, 3353.7, 32767, 32767] == pytest.approx(
            apply_windowing(arr, ds).tolist(), abs=0.1
        )

        # Linear exact
        ds.VOILUTFunction = "LINEAR_EXACT"
        assert [-32768, -32768, 2047.5, 2559.5, 3071.5, 32767, 32767] == pytest.approx(
            apply_windowing(arr, ds).tolist(), abs=0.1
        )

        # Sigmoid
        ds.VOILUTFunction = "SIGMOID"
        assert [
            -31394.1,
            -31351.4,
            2044.8,
            2554.3,
            3062.5,
            31692,
            31724.6,
        ] == pytest.approx(apply_windowing(arr, ds).tolist(), abs=0.1)

    def test_window_int32(self):
        """Test windowing an 32-bit signed array."""
        ds = Dataset()
        ds.PhotometricInterpretation = "MONOCHROME1"
        ds.PixelRepresentation = 1
        ds.BitsStored = 32
        arr = np.asarray([-128, -127, -1, 0, 1, 126, 127], dtype="int32")

        # Linear
        ds.WindowWidth = 1
        ds.WindowCenter = 0
        assert [
            -(2**31),
            -(2**31),
            -(2**31),
            2**31 - 1,
            2**31 - 1,
            2**31 - 1,
            2**31 - 1,
        ] == pytest.approx(apply_windowing(arr, ds).tolist(), abs=0.1)

        ds.WindowWidth = 128
        ds.WindowCenter = -5
        assert [
            -2147483648,
            -2147483648,
            152183880,
            186002520.1,
            219821160.3,
            2147483647,
            2147483647,
        ] == pytest.approx(apply_windowing(arr, ds).tolist(), abs=0.1)

        # Linear exact
        ds.VOILUTFunction = "LINEAR_EXACT"
        assert [
            -2147483648,
            -2147483648,
            134217727.5,
            167772159.5,
            201326591.5,
            2147483647,
            2147483647,
        ] == pytest.approx(apply_windowing(arr, ds).tolist(), abs=0.1)

        # Sigmoid
        ds.VOILUTFunction = "SIGMOID"
        assert [
            -2057442919.3,
            -2054646500.7,
            134043237.4,
            167431657.4,
            200738833.7,
            2077033158.8,
            2079166214.8,
        ] == pytest.approx(apply_windowing(arr, ds).tolist(), abs=0.1)

    def test_window_multi_frame(self):
        """Test windowing with a multiple frames."""
        ds = dcmread(WIN_12_1F)
        assert 16 == ds.BitsAllocated
        assert 12 == ds.BitsStored
        assert 0 == ds.PixelRepresentation
        ds.WindowCenter = 450
        ds.WindowWidth = 790
        assert 450 == ds.WindowCenter
        assert 790 == ds.WindowWidth

        arr = ds.pixel_array
        arr = np.stack([arr, 4095 - arr])
        assert (2, 484, 484) == arr.shape
        assert 642 == arr[0, 326, 130]
        assert 3453 == arr[1, 326, 130]
        out = apply_windowing(arr, ds)
        assert 3046.6 == pytest.approx(out[0, 326, 130], abs=0.1)
        assert 4095.0 == pytest.approx(out[1, 326, 130], abs=0.1)

    def test_window_rescale(self):
        """Test windowing after a rescale operation."""
        ds = dcmread(WIN_12_1F)
        assert 16 == ds.BitsAllocated
        assert 12 == ds.BitsStored
        assert 0 == ds.PixelRepresentation
        if HAVE_NP and config.use_DS_numpy:
            expected = np.array([450, 200])
            assert np.allclose(ds.WindowCenter, expected)
            expected = np.array([790, 443])
            assert np.allclose(ds.WindowWidth, expected)
        else:
            assert [450, 200] == ds.WindowCenter
            assert [790, 443] == ds.WindowWidth
        ds.RescaleSlope = 1.2
        ds.RescaleIntercept = 0

        arr = ds.pixel_array
        assert 0 == arr[16, 60]
        assert 642 == arr[326, 130]
        assert 1123 == arr[316, 481]
        hu = apply_modality_lut(arr, ds)
        assert 0 == hu[16, 60]
        assert 770.4 == hu[326, 130]
        assert 1347.6 == hu[316, 481]
        # With rescale -> output range is 0 to 4914
        out = apply_windowing(hu, ds)
        assert 0 == pytest.approx(out[16, 60], abs=0.1)
        assert 4455.6 == pytest.approx(out[326, 130], abs=0.1)
        assert 4914.0 == pytest.approx(out[316, 481], abs=0.1)

    def test_window_modality_lut(self):
        """Test windowing after a modality LUT operation."""
        ds = dcmread(MOD_16_SEQ)
        ds.WindowCenter = [49147, 200]
        ds.WindowWidth = [790, 443]
        assert 16 == ds.BitsAllocated
        assert 12 == ds.BitsStored
        assert 1 == ds.PixelRepresentation  # Signed
        assert "RescaleSlope" not in ds
        assert "ModalityLUTSequence" in ds

        seq = ds.ModalityLUTSequence[0]
        assert [4096, -2048, 16] == seq.LUTDescriptor
        arr = ds.pixel_array
        assert -2048 == arr.min()
        assert 2047 == arr.max()

        arr = ds.pixel_array
        assert 2047 == arr[16, 60]
        assert 1023 == arr[0, 1]
        hu = apply_modality_lut(arr, ds)
        assert 65535 == hu[16, 60]
        assert 49147 == hu[0, 1]
        out = apply_windowing(hu, ds)
        assert 65535.0 == pytest.approx(out[16, 60], abs=0.1)
        assert 32809.0 == pytest.approx(out[0, 1], abs=0.1)
        # Output range must be 0 to 2**16 - 1
        assert 65535 == out.max()
        assert 0 == out.min()

    def test_window_bad_photometric_interp(self):
        """Test bad photometric interpretation raises exception."""
        ds = dcmread(WIN_12_1F)
        ds.PhotometricInterpretation = "RGB"
        msg = r"only 'MONOCHROME1' and 'MONOCHROME2' are allowed"
        with pytest.raises(ValueError, match=msg):
            apply_windowing(ds.pixel_array, ds)

    def test_window_bad_parameters(self):
        """Test bad windowing parameters raise exceptions."""
        ds = dcmread(WIN_12_1F)
        ds.WindowWidth = 0
        ds.VOILUTFunction = "LINEAR"
        msg = r"Width must be greater than or equal to 1"
        with pytest.raises(ValueError, match=msg):
            apply_windowing(ds.pixel_array, ds)

        ds.VOILUTFunction = "LINEAR_EXACT"
        msg = r"Width must be greater than 0"
        with pytest.raises(ValueError, match=msg):
            apply_windowing(ds.pixel_array, ds)

        ds.VOILUTFunction = "SIGMOID"
        msg = r"Width must be greater than 0"
        with pytest.raises(ValueError, match=msg):
            apply_windowing(ds.pixel_array, ds)

        ds.VOILUTFunction = "UNKNOWN"
        msg = r"Unsupported \(0028,1056\) VOI LUT Function value 'UNKNOWN'"
        with pytest.raises(ValueError, match=msg):
            apply_windowing(ds.pixel_array, ds)

    def test_window_bad_index(self, no_numpy_use):
        """Test windowing with a bad view index."""
        ds = dcmread(WIN_12_1F)
        assert 2 == len(ds.WindowWidth)
        arr = ds.pixel_array
        with pytest.raises(IndexError, match=r"list index out of range"):
            apply_windowing(arr, ds, index=2)

    def test_unchanged(self):
        """Test input array is unchanged if no VOI LUT"""
        ds = Dataset()
        ds.PhotometricInterpretation = "MONOCHROME1"
        ds.PixelRepresentation = 1
        ds.BitsStored = 8
        arr = np.asarray([-128, -127, -1, 0, 1, 126, 127], dtype="int8")
        out = apply_windowing(arr, ds)
        assert [-128, -127, -1, 0, 1, 126, 127] == out.tolist()

        ds.ModalityLUTSequence = []
        out = apply_windowing(arr, ds)
        assert [-128, -127, -1, 0, 1, 126, 127] == out.tolist()

    def test_rescale_empty(self):
        """Test RescaleSlope and RescaleIntercept being empty."""
        ds = dcmread(WIN_12_1F)
        ds.RescaleSlope = None
        ds.RescaleIntercept = None

        arr = ds.pixel_array
        assert 0 == arr[16, 60]
        assert 642 == arr[326, 130]
        assert 1123 == arr[316, 481]
        out = apply_windowing(arr, ds)
        assert 0 == pytest.approx(out[16, 60], abs=0.1)
        assert 3046.6 == pytest.approx(out[326, 130], abs=0.1)
        assert 4095.0 == pytest.approx(out[316, 481], abs=0.1)


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestApplyVOI:
    """Tests for apply_voi()."""

    def test_voi_single_view(self):
        """Test VOI LUT with a single view."""
        ds = dcmread(VOI_08_1F)
        assert 8 == ds.BitsAllocated
        assert 8 == ds.BitsStored
        assert 0 == ds.PixelRepresentation
        item = ds.VOILUTSequence[0]
        assert [256, 0, 16] == item.LUTDescriptor
        lut = item.LUTData
        assert 0 == lut[0]
        assert 19532 == lut[76]
        assert 45746 == lut[178]
        assert 65535 == lut[255]

        arr = ds.pixel_array
        assert 0 == arr[387, 448]
        assert 76 == arr[178, 126]
        assert 178 == arr[186, 389]
        assert 255 == arr[129, 79]

        out = apply_voi(arr, ds)
        assert 0 == out[387, 448]
        assert 19532 == out[178, 126]
        assert 45746 == out[186, 389]
        assert 65535 == out[129, 79]

    def test_voi_multi_view(self):
        """Test VOI LUT with multiple views."""
        ds = dcmread(VOI_08_1F)
        assert 8 == ds.BitsAllocated
        assert 8 == ds.BitsStored
        assert 0 == ds.PixelRepresentation
        item0 = ds.VOILUTSequence[0]
        # Add another view that's the inverse
        ds.VOILUTSequence.append(Dataset())
        item1 = ds.VOILUTSequence[1]
        item1.LUTDescriptor = [256, 0, 16]
        item1.LUTData = item0.LUTData[::-1]

        arr = ds.pixel_array
        assert 0 == arr[387, 448]
        assert 76 == arr[178, 126]
        assert 178 == arr[186, 389]
        assert 255 == arr[129, 79]

        out0 = apply_voi(arr, ds)
        assert 0 == out0[387, 448]
        assert 19532 == out0[178, 126]
        assert 45746 == out0[186, 389]
        assert 65535 == out0[129, 79]

        out1 = apply_voi(arr, ds, index=1)
        assert 65535 == out1[387, 448]
        assert 46003 == out1[178, 126]
        assert 19789 == out1[186, 389]
        assert 0 == out1[129, 79]

    def test_voi_multi_frame(self):
        """Test VOI with a multiple frames."""
        ds = dcmread(VOI_08_1F)
        assert 8 == ds.BitsAllocated
        assert 8 == ds.BitsStored
        assert 0 == ds.PixelRepresentation

        arr = ds.pixel_array
        arr = np.stack([arr, 255 - arr])
        assert (2, 512, 512) == arr.shape

        out = apply_voi(arr, ds)
        assert 0 == out[0, 387, 448]
        assert 19532 == out[0, 178, 126]
        assert 45746 == out[0, 186, 389]
        assert 65535 == out[0, 129, 79]
        assert 65535 == out[1, 387, 448]
        assert 46003 == out[1, 178, 126]
        assert 19789 == out[1, 186, 389]
        assert 0 == out[1, 129, 79]

    def test_voi_zero_entries(self):
        """Test that 0 entries is interpreted correctly."""
        ds = dcmread(VOI_08_1F)
        seq = ds.VOILUTSequence[0]
        seq.LUTDescriptor = [0, 0, 16]
        assert 256 == len(seq.LUTData)
        arr = np.asarray([0, 255, 256, 65535])
        msg = r"index 256 is out of bounds"
        with pytest.raises(IndexError, match=msg):
            apply_voi(arr, ds)

        # LUTData with 65536 entries
        seq.LUTData = [0] * 65535 + [1]
        out = apply_voi(arr, ds)
        assert [0, 0, 0, 1] == list(out)

    def test_voi_uint8(self):
        """Test uint VOI LUT with an 8-bit LUT."""
        ds = Dataset()
        ds.PixelRepresentation = 0
        ds.BitsStored = 8
        ds.VOILUTSequence = [Dataset()]
        item = ds.VOILUTSequence[0]
        item.LUTDescriptor = [4, 0, 8]
        item.LUTData = [0, 127, 128, 255]
        arr = np.asarray([0, 1, 128, 254, 255], dtype="uint8")
        out = apply_voi(arr, ds)
        assert "uint8" == out.dtype
        assert [0, 127, 255, 255, 255] == out.tolist()

    def test_voi_uint16(self):
        """Test uint VOI LUT with an 16-bit LUT."""
        ds = Dataset()
        ds.PixelRepresentation = 0
        ds.BitsStored = 16
        ds.VOILUTSequence = [Dataset()]
        item = ds.VOILUTSequence[0]
        item.LUTDescriptor = [4, 0, 16]
        item.LUTData = [0, 127, 32768, 65535]
        arr = np.asarray([0, 1, 2, 3, 255], dtype="uint16")
        out = apply_voi(arr, ds)
        assert "uint16" == out.dtype
        assert [0, 127, 32768, 65535, 65535] == out.tolist()

    def test_voi_int8(self):
        """Test int VOI LUT with an 8-bit LUT."""
        ds = Dataset()
        ds.PixelRepresentation = 1
        ds.BitsStored = 8
        ds.VOILUTSequence = [Dataset()]
        item = ds.VOILUTSequence[0]
        item.LUTDescriptor = [4, 0, 8]
        item.LUTData = [0, 127, 128, 255]
        arr = np.asarray([0, -1, 2, -128, 127], dtype="int8")
        out = apply_voi(arr, ds)
        assert "uint8" == out.dtype
        assert [0, 0, 128, 0, 255] == out.tolist()

    def test_voi_int16(self):
        """Test int VOI LUT with an 16-bit LUT."""
        ds = Dataset()
        ds.PixelRepresentation = 0
        ds.BitsStored = 16
        ds.VOILUTSequence = [Dataset()]
        item = ds.VOILUTSequence[0]
        item.LUTDescriptor = [4, 0, 16]
        item.LUTData = [0, 127, 32768, 65535]
        arr = np.asarray([0, -1, 2, -128, 255], dtype="int16")
        out = apply_voi(arr, ds)
        assert "uint16" == out.dtype
        assert [0, 0, 32768, 0, 65535] == out.tolist()

    def test_voi_bad_depth(self):
        """Test bad LUT depth raises exception."""
        ds = dcmread(VOI_08_1F)
        item = ds.VOILUTSequence[0]
        item.LUTDescriptor[2] = 7
        msg = r"'7' bits per LUT entry is not supported"
        with pytest.raises(NotImplementedError, match=msg):
            apply_voi(ds.pixel_array, ds)

        item.LUTDescriptor[2] = 17
        msg = r"'17' bits per LUT entry is not supported"
        with pytest.raises(NotImplementedError, match=msg):
            apply_voi(ds.pixel_array, ds)

    def test_voi_uint16_array_float(self):
        """Test warning when array is float and VOI LUT with an 16-bit LUT"""
        ds = Dataset()
        ds.PixelRepresentation = 0
        ds.BitsStored = 16
        ds.VOILUTSequence = [Dataset()]
        item = ds.VOILUTSequence[0]
        item.LUTDescriptor = [4, 0, 16]
        item.LUTData = [0, 127, 32768, 65535]
        arr = np.asarray([0, 1, 2, 3, 255], dtype="float64")
        msg = r"Applying a VOI LUT on a float input array may give incorrect results"

        with pytest.warns(UserWarning, match=msg):
            out = apply_voi(arr, ds)
            assert [0, 127, 32768, 65535, 65535] == out.tolist()

    def test_unchanged(self):
        """Test input array is unchanged if no VOI LUT"""
        ds = Dataset()
        ds.PhotometricInterpretation = "MONOCHROME1"
        ds.PixelRepresentation = 1
        ds.BitsStored = 8
        arr = np.asarray([-128, -127, -1, 0, 1, 126, 127], dtype="int8")
        out = apply_voi(arr, ds)
        assert [-128, -127, -1, 0, 1, 126, 127] == out.tolist()

        ds.VOILUTSequence = []
        out = apply_voi(arr, ds)
        assert [-128, -127, -1, 0, 1, 126, 127] == out.tolist()

    def test_voi_lutdata_ow(self):
        """Test LUT Data with VR OW."""
        ds = Dataset()
        ds.set_original_encoding(False, True)
        ds.PixelRepresentation = 0
        ds.BitsStored = 16
        ds.VOILUTSequence = [Dataset()]
        item = ds.VOILUTSequence[0]
        item.LUTDescriptor = [4, 0, 16]
        item.LUTData = [0, 127, 32768, 65535]
        item.LUTData = pack("<4H", *item.LUTData)
        item["LUTData"].VR = "OW"
        arr = np.asarray([0, 1, 2, 3, 255], dtype="uint16")
        out = apply_voi(arr, ds)
        assert "uint16" == out.dtype
        assert [0, 127, 32768, 65535, 65535] == out.tolist()

    def test_file_meta(self):
        """Test using file meta to determine endianness"""
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.PixelRepresentation = 0
        ds.BitsStored = 16
        ds.VOILUTSequence = [Dataset()]
        item = ds.VOILUTSequence[0]
        item.LUTDescriptor = [4, 0, 16]
        item.LUTData = [0, 127, 32768, 65535]
        item.LUTData = pack("<4H", *item.LUTData)
        item["LUTData"].VR = "OW"
        arr = np.asarray([0, 1, 2, 3, 255], dtype="uint16")
        out = apply_voi(arr, ds)
        assert "uint16" == out.dtype
        assert [0, 127, 32768, 65535, 65535] == out.tolist()

    def test_no_endianness_raises(self):
        """Test unable to determine endianness"""
        ds = Dataset()
        ds.PixelRepresentation = 0
        ds.BitsStored = 16
        ds.VOILUTSequence = [Dataset()]
        item = ds.VOILUTSequence[0]
        item.LUTDescriptor = [4, 0, 16]
        item.LUTData = [0, 127, 32768, 65535]
        item.LUTData = pack("<4H", *item.LUTData)
        item["LUTData"].VR = "OW"
        arr = np.asarray([0, 1, 2, 3, 255], dtype="uint16")
        msg = (
            "Unable to determine the endianness of the dataset, please set "
            "an appropriate Transfer Syntax UID in 'Dataset.file_meta'"
        )
        with pytest.raises(AttributeError, match=msg):
            apply_voi(arr, ds)


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestApplyVOILUT:
    """Tests for apply_voi_lut()"""

    def test_unchanged(self):
        """Test input array is unchanged if no VOI LUT"""
        ds = Dataset()
        ds.PhotometricInterpretation = "MONOCHROME1"
        ds.PixelRepresentation = 1
        ds.BitsStored = 8
        arr = np.asarray([-128, -127, -1, 0, 1, 126, 127], dtype="int8")
        out = apply_voi_lut(arr, ds)
        assert [-128, -127, -1, 0, 1, 126, 127] == out.tolist()

        ds.VOILUTSequence = []
        out = apply_voi_lut(arr, ds)
        assert [-128, -127, -1, 0, 1, 126, 127] == out.tolist()

    def test_only_windowing(self):
        """Test only windowing operation elements present."""
        ds = Dataset()
        ds.PhotometricInterpretation = "MONOCHROME1"
        ds.PixelRepresentation = 0
        ds.BitsStored = 8
        arr = np.asarray([0, 1, 128, 254, 255], dtype="uint8")

        ds.WindowWidth = 1
        ds.WindowCenter = 0
        assert [255, 255, 255, 255, 255] == apply_voi_lut(arr, ds).tolist()

    def test_only_voi(self):
        """Test only LUT operation elements present."""
        ds = Dataset()
        ds.PixelRepresentation = 0
        ds.BitsStored = 8
        ds.VOILUTSequence = [Dataset()]
        item = ds.VOILUTSequence[0]
        item.LUTDescriptor = [4, 0, 8]
        item.LUTData = [0, 127, 128, 255]
        arr = np.asarray([0, 1, 128, 254, 255], dtype="uint8")
        out = apply_voi_lut(arr, ds)
        assert "uint8" == out.dtype
        assert [0, 127, 255, 255, 255] == out.tolist()

    def test_voi_windowing(self):
        """Test both LUT and windowing operation elements present."""
        ds = Dataset()
        ds.PhotometricInterpretation = "MONOCHROME1"
        ds.PixelRepresentation = 0
        ds.BitsStored = 8
        ds.WindowWidth = 1
        ds.WindowCenter = 0
        ds.VOILUTSequence = [Dataset()]
        item = ds.VOILUTSequence[0]
        item.LUTDescriptor = [4, 0, 8]
        item.LUTData = [0, 127, 128, 255]
        arr = np.asarray([0, 1, 128, 254, 255], dtype="uint8")

        # Defaults to LUT
        out = apply_voi_lut(arr, ds)
        assert [0, 127, 255, 255, 255] == out.tolist()

        out = apply_voi_lut(arr, ds, prefer_lut=False)
        assert [255, 255, 255, 255, 255] == out.tolist()

    def test_voi_windowing_empty(self):
        """Test empty VOI elements."""
        ds = Dataset()
        ds.PhotometricInterpretation = "MONOCHROME1"
        ds.PixelRepresentation = 0
        ds.BitsStored = 8
        ds.WindowWidth = 1
        ds.WindowCenter = 0
        ds.VOILUTSequence = [Dataset()]
        item = ds.VOILUTSequence[0]
        item.LUTDescriptor = [4, 0, 8]
        item.LUTData = [0, 127, 128, 255]
        arr = np.asarray([0, 1, 128, 254, 255], dtype="uint8")

        # Test empty VOI elements
        item.LUTData = None
        out = apply_voi_lut(arr, ds)
        assert [255, 255, 255, 255, 255] == out.tolist()

        # Test empty windowing elements
        ds.WindowWidth = None
        out = apply_voi_lut(arr, ds)
        assert [0, 1, 128, 254, 255] == out.tolist()


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestApplyPresentationLUT:
    """Tests for apply_presentation_lut()"""

    def test_shape(self):
        """Test Presentation LUT Shape"""
        ds = dcmread(VOI_08_1F)
        ds.PresentationLUTShape = "IDENTITY"
        arr = ds.pixel_array

        out = apply_presentation_lut(arr, ds)
        assert arr is out

        ds.PresentationLUTShape = "INVERSE"
        out = apply_presentation_lut(arr, ds)

        arr = arr.max() - arr
        assert np.array_equal(out, arr)

    def test_shape_unknown_raises(self):
        """Test an unknown Presentation LUT Shape raises an exception"""
        ds = dcmread(VOI_08_1F)
        ds.PresentationLUTShape = "FOO"

        msg = (
            r"A \(2050,0020\) 'Presentation LUT Shape' value of 'FOO' is not supported"
        )
        with pytest.raises(NotImplementedError, match=msg):
            apply_presentation_lut(ds.pixel_array, ds)

    def test_sequence_8bit_unsigned(self):
        """Test Presentation LUT Sequence with 8-bit unsigned input"""
        # 8 bit unsigned input
        ds = dcmread(VOI_08_1F)
        assert ds.BitsStored == 8
        assert ds.PixelRepresentation == 0
        ds.PresentationLUTSequence = [Dataset()]
        seq = ds.PresentationLUTSequence

        # 256 entries, 10 bit output
        seq[0].LUTDescriptor = [256, 0, 10]
        seq[0].LUTData = [int(round(x * (2**10 - 1) / 255, 0)) for x in range(0, 256)]
        seq[0]["LUTData"].VR = "US"

        arr = ds.pixel_array
        assert (arr.min(), arr.max()) == (0, 255)

        coords = [(335, 130), (285, 130), (235, 130), (185, 130), (185, 180)]
        coords.extend(
            [(185, 230), (185, 330), (185, 380), (235, 380), (285, 380), (335, 380)]
        )

        results = [0, 25, 51, 76, 102, 127, 153, 178, 204, 229, 255]
        for (y, x), result in zip(coords, results):
            assert arr[y, x] == result

        out = apply_presentation_lut(arr, ds)
        assert out.dtype == "uint16"
        assert (out.min(), out.max()) == (0, 1023)

        results = [0, 100, 205, 305, 409, 509, 614, 714, 818, 919, 1023]
        for (y, x), result in zip(coords, results):
            assert out[y, x] == result

        # Reversed output
        seq[0].LUTData.reverse()
        out = apply_presentation_lut(arr, ds)
        assert out.dtype == "uint16"
        assert (out.min(), out.max()) == (0, 1023)

        results = [1023, 923, 818, 718, 614, 514, 409, 309, 205, 104, 0]
        for (y, x), result in zip(coords, results):
            assert out[y, x] == result

        # 4096 entries, 16-bit output
        seq[0].LUTDescriptor = [4096, 0, 16]
        seq[0].LUTData = [int(round(x * (2**16 - 1) / 4095, 0)) for x in range(0, 4096)]
        out = apply_presentation_lut(arr, ds)
        assert out.dtype == "uint16"
        assert (out.min(), out.max()) == (0, 65535)

        results = [
            0,
            6417,
            13107,
            19524,
            26214,
            32631,
            39321,
            45738,
            52428,
            58845,
            65535,
        ]
        for (y, x), result in zip(coords, results):
            assert out[y, x] == result

        # 4096 entries, 8-bit output
        seq[0].LUTDescriptor = [4096, 0, 8]
        seq[0].LUTData = [int(round(x * (2**8 - 1) / 4095, 0)) for x in range(0, 4096)]
        out = apply_presentation_lut(arr, ds)

        results = [0, 25, 51, 76, 102, 127, 153, 178, 204, 229, 255]
        for (y, x), result in zip(coords, results):
            assert out[y, x] == result

        # 4096 entries, 8-bit output, LUTData as 8-bit bytes
        seq[0].LUTDescriptor = [4096, 0, 8]
        seq[0]["LUTData"].VR = "OW"
        seq[0].LUTData = b"".join(
            x.to_bytes(length=1, byteorder="little") for x in seq[0].LUTData
        )
        out = apply_presentation_lut(arr, ds)
        for (y, x), result in zip(coords, results):
            assert out[y, x] == result

        # 4096 entries, 8-bit output, LUTData as 16-bit bytes
        seq[0].LUTDescriptor = [4096, 0, 16]
        seq[0]["LUTData"].VR = "OW"
        data = [int(round(x * (2**16 - 1) / 4095, 0)) for x in range(0, 4096)]
        seq[0].LUTData = b"".join(
            x.to_bytes(length=2, byteorder="little") for x in data
        )
        out = apply_presentation_lut(arr, ds)
        results = [
            0,
            6417,
            13107,
            19524,
            26214,
            32631,
            39321,
            45738,
            52428,
            58845,
            65535,
        ]
        for (y, x), result in zip(coords, results):
            assert out[y, x] == result

        # 4096 entries, 8-bit output, LUTData ambiguous
        seq[0]["LUTData"].VR = "US or OW"
        out = apply_presentation_lut(arr, ds)
        for (y, x), result in zip(coords, results):
            assert out[y, x] == result

    def test_sequence_12bit_signed(self):
        """Test Presentation LUT Sequence with 12-bit signed input."""
        ds = dcmread(MOD_16_SEQ)
        assert ds.BitsStored == 12
        assert ds.PixelRepresentation == 1
        ds.PresentationLUTSequence = [Dataset()]
        seq = ds.PresentationLUTSequence

        # 256 entries, 10 bit output
        seq[0].LUTDescriptor = [256, 0, 10]
        seq[0].LUTData = [int(round(x * (2**10 - 1) / 255, 0)) for x in range(0, 256)]
        seq[0]["LUTData"].VR = "US"

        arr = ds.pixel_array
        assert (arr.min(), arr.max()) == (-2048, 2047)

        coords = [(335, 130), (285, 130), (235, 130), (185, 130), (185, 180)]
        coords.extend(
            [(185, 230), (185, 330), (185, 380), (235, 380), (285, 380), (335, 380)]
        )

        results = [-2048, -1639, -1229, -820, -410, -1, 409, 818, 1228, 1637, 2047]
        for (y, x), result in zip(coords, results):
            assert arr[y, x] == result

        out = apply_presentation_lut(arr, ds)
        assert out.dtype == "uint16"
        assert (out.min(), out.max()) == (0, 1023)

        results = [0, 100, 205, 305, 409, 509, 614, 714, 818, 919, 1023]
        for (y, x), result in zip(coords, results):
            assert out[y, x] == result

        # Reversed output
        seq[0].LUTData.reverse()
        out = apply_presentation_lut(arr, ds)
        assert out.dtype == "uint16"
        assert (out.min(), out.max()) == (0, 1023)

        results = [1023, 923, 818, 718, 614, 514, 409, 309, 205, 104, 0]
        for (y, x), result in zip(coords, results):
            assert out[y, x] == result

        # 4096 entries, 16-bit output
        seq[0].LUTDescriptor = [4096, 0, 16]
        seq[0].LUTData = [int(round(x * (2**16 - 1) / 4095, 0)) for x in range(0, 4096)]
        out = apply_presentation_lut(arr, ds)
        assert out.dtype == "uint16"
        assert (out.min(), out.max()) == (0, 65535)

        results = [
            0,
            6545,
            13107,
            19652,
            26214,
            32759,
            39321,
            45866,
            52428,
            58973,
            65535,
        ]
        for (y, x), result in zip(coords, results):
            assert out[y, x] == result

        # 4096 entries, 8-bit output
        seq[0].LUTDescriptor = [4096, 0, 8]
        seq[0].LUTData = [int(round(x * (2**8 - 1) / 4095, 0)) for x in range(0, 4096)]
        out = apply_presentation_lut(arr, ds)

        results = [0, 25, 51, 76, 102, 127, 153, 178, 204, 229, 255]
        for (y, x), result in zip(coords, results):
            assert out[y, x] == result

    def test_sequence_bit_shift(self):
        """Test bit shifting read-only LUTData"""
        ds = dcmread(MOD_16_SEQ)
        assert ds.BitsStored == 12
        assert ds.PixelRepresentation == 1
        ds.PresentationLUTSequence = [Dataset()]
        seq = ds.PresentationLUTSequence

        # 256 entries, 10 bit output
        seq[0].LUTDescriptor = [256, 0, 10]
        seq[0].LUTData = [int(round(x * (2**10 - 1) / 255, 0)) for x in range(0, 256)]
        seq[0].LUTData = b"".join(
            x.to_bytes(length=2, byteorder="little") for x in seq[0].LUTData
        )
        seq[0]["LUTData"].VR = "OW"

        out = apply_presentation_lut(ds.pixel_array, ds)
        results = [0, 100, 205, 305, 409, 509, 614, 714, 818, 919, 1023]
        coords = [(335, 130), (285, 130), (235, 130), (185, 130), (185, 180)]
        coords.extend(
            [(185, 230), (185, 330), (185, 380), (235, 380), (285, 380), (335, 380)]
        )
        for (y, x), result in zip(coords, results):
            assert out[y, x] == result


@pytest.mark.skipif(not TEST_CMS, reason="Numpy or PIL are not available")
class TestApplyICCProfile:
    """Tests for apply_icc_profile()"""

    def setup_method(self):
        with open(ICC_PROFILE, "rb") as f:
            self.profile = f.read()

    def test_invalid_args_raises(self):
        """Test exception raised if invalid args passed."""
        arr = np.empty((3, 3), dtype="u1")
        msg = "Either 'ds' or 'transform' must be supplied"
        with pytest.raises(ValueError, match=msg):
            apply_icc_profile(arr)

        msg = "Only one of 'ds' and 'transform' should be used, not both"
        with pytest.raises(ValueError, match=msg):
            apply_icc_profile(arr, ds="foo", transform="bar")

    def test_invalid_arr_raises(self):
        """Test exception raised if invalid ndarray passed."""
        arr = np.empty((3, 3), dtype="u1")
        msg = "The ndarray must have 3 or 4 dimensions, not 2"
        with pytest.raises(ValueError, match=msg):
            apply_icc_profile(arr, Dataset())

        arr = np.empty((3, 3, 2), dtype="u1")
        msg = (
            r"Invalid ndarray shape, must be \(rows, columns, 3\) or \(frames, rows, "
            r"columns, 3\), not \(3, 3, 2\)"
        )
        with pytest.raises(ValueError, match=msg):
            apply_icc_profile(arr, Dataset())

    def test_invalid_intent_raises(self):
        """Test an invalid intent raises an exception."""
        ds = Dataset()
        ds.ICCProfile = self.profile

        msg = "Invalid 'intent' value '-1', must be 0, 1, 2 or 3"
        with pytest.raises(ValueError, match=msg):
            apply_icc_profile(np.empty((3, 3, 3)), ds, intent=-1)

    def test_invalid_color_space_raises(self):
        """Test an invalid color_space raises an exception."""
        ds = Dataset()
        ds.ICCProfile = b"\x00\x01"
        ds.ColorSpace = "ROMMRGB"
        arr = np.empty((3, 3, 3))
        msg = (
            r"The \(0028,2002\) 'Color Space' value 'ROMMRGB' is not supported by "
            "Pillow, please use the 'color_space' argument to specify a "
            "supported value"
        )
        with pytest.raises(ValueError, match=msg):
            apply_icc_profile(arr, ds)

        msg = (
            "Unsupported 'color_space' value 'ADOBERGB', must be 'sRGB', 'LAB' or "
            "'XYZ'"
        )
        with pytest.raises(ValueError, match=msg):
            apply_icc_profile(arr, ds, color_space="ADOBERGB")

    def test_ds_profile(self):
        """Test applying the profile in a dataset"""
        # Single frame
        ds = dcmread(RGB_8_3_1F)
        ds.ICCProfile = self.profile

        arr = ds.pixel_array
        out = apply_icc_profile(arr.copy(), ds=ds)
        assert not np.array_equal(arr, out)

        # Multiframe
        ds = dcmread(RGB_8_3_2F)
        ds.ICCProfile = self.profile

        arr = ds.pixel_array
        out = apply_icc_profile(arr.copy(), ds)
        assert not np.array_equal(arr, out)

    def test_transform(self):
        """Test applying the profile in a dataset"""
        # Single frame
        transform = create_icc_transform(icc_profile=self.profile)

        ds = dcmread(RGB_8_3_1F)
        arr = ds.pixel_array
        arr_copy = arr.copy()
        out = apply_icc_profile(arr_copy, transform=transform)
        assert not np.array_equal(arr, out)
        # In-place update
        assert out is arr_copy

        # Multiframe
        ds = dcmread(RGB_8_3_2F)
        arr = ds.pixel_array
        arr_copy = arr.copy()
        out = apply_icc_profile(arr_copy, transform=transform)
        assert not np.array_equal(arr, out)
        # In-place update
        assert out is arr_copy


@pytest.mark.skipif(not HAVE_NP or HAVE_PIL, reason="Numpy missing PIL not")
def test_apply_icc_profile_no_pillow_raises():
    """Test exception raised if PIL is missing."""
    msg = "Pillow is required to apply an ICC profile to an ndarray"
    with pytest.raises(ImportError, match=msg):
        apply_icc_profile(np.empty((3, 3)))


@pytest.mark.skipif(not TEST_CMS, reason="Numpy or PIL are not available")
class TestCreateICCTransform:
    """Tests for create_icc_transform()"""

    def setup_method(self):
        with open(ICC_PROFILE, "rb") as f:
            self.profile = f.read()

    def test_invalid_args_raises(self):
        """Test exception raised if invalid args passed."""
        msg = "Either 'ds' or 'icc_profile' must be supplied"
        with pytest.raises(ValueError, match=msg):
            create_icc_transform()

        msg = "Only one of 'ds' and 'icc_profile' should be used, not both"
        with pytest.raises(ValueError, match=msg):
            create_icc_transform(ds="foo", icc_profile="bar")

    def test_ds_no_profile_raises(self):
        """Test passing dataset without an ICC Profile raises an exception."""
        msg = r"No \(0028,2000\) 'ICC Profile' element was found in 'ds'"
        with pytest.raises(ValueError, match=msg):
            create_icc_transform(ds=Dataset())

    def test_invalid_intent_raises(self):
        """Test an invalid intent raises an exception."""
        ds = Dataset()
        ds.ICCProfile = self.profile

        msg = "Invalid 'intent' value '-1', must be 0, 1, 2 or 3"
        with pytest.raises(ValueError, match=msg):
            create_icc_transform(ds, intent=-1)

    def test_invalid_color_space_raises(self):
        """Test an invalid color_space raises an exception."""
        ds = Dataset()
        ds.ICCProfile = self.profile
        ds.ColorSpace = "ROMMRGB"

        msg = (
            r"The \(0028,2002\) 'Color Space' value 'ROMMRGB' is not supported by "
            "Pillow, please use the 'color_space' argument to specify a "
            "supported value"
        )
        with pytest.raises(ValueError, match=msg):
            create_icc_transform(ds)

        msg = (
            "Unsupported 'color_space' value 'ADOBERGB', must be 'sRGB', 'LAB' or "
            "'XYZ'"
        )
        with pytest.raises(ValueError, match=msg):
            create_icc_transform(ds, color_space="ADOBERGB")

    def test_transform(self):
        """Test creating transforms"""
        transform = create_icc_transform(icc_profile=self.profile)
        assert isinstance(transform, PIL.ImageCms.ImageCmsTransform)
        p = transform.output_profile
        assert "sRGB" in p.profile.profile_description

        ds = Dataset()
        ds.ICCProfile = self.profile
        transform = create_icc_transform(ds)
        p = transform.output_profile
        assert "sRGB" in p.profile.profile_description


@pytest.mark.skipif(TEST_CMS, reason="Numpy or PIL are available")
def test_create_icc_transform_no_pillow_raises():
    """Test exception raised if PIL is missing."""
    msg = "Pillow is required to create a color transformation object"
    with pytest.raises(ImportError, match=msg):
        create_icc_transform()
