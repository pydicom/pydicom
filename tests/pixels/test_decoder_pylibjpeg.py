"""Test the pylibjpeg decoder."""

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom.pixels import get_decoder
from pydicom.pixels.decoders.pylibjpeg import is_available
from pydicom.uid import (
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEGLossless,
    JPEGLosslessSV1,
    JPEGLSLossless,
    JPEGLSNearLossless,
    JPEG2000Lossless,
    JPEG2000,
    RLELossless,
)

from .pixels_reference import PIXEL_REFERENCE


# # RLE Lossless - PackBits algorithm
# RLE_8_1_1F = get_testdata_file("OBXXXX1A_rle.dcm")
# RLE_8_1_2F = get_testdata_file("OBXXXX1A_rle_2frame.dcm")
# RLE_8_3_1F = get_testdata_file("SC_rgb_rle.dcm")
# RLE_8_3_2F = get_testdata_file("SC_rgb_rle_2frame.dcm")
# RLE_16_1_1F = get_testdata_file("MR_small_RLE.dcm")
# RLE_16_1_10F = get_testdata_file("emri_small_RLE.dcm")
# RLE_16_3_1F = get_testdata_file("SC_rgb_rle_16bit.dcm")
# RLE_16_3_2F = get_testdata_file("SC_rgb_rle_16bit_2frame.dcm")
# RLE_32_1_1F = get_testdata_file("rtdose_rle_1frame.dcm")
# RLE_32_1_15F = get_testdata_file("rtdose_rle.dcm")
# RLE_32_3_1F = get_testdata_file("SC_rgb_rle_32bit.dcm")
# RLE_32_3_2F = get_testdata_file("SC_rgb_rle_32bit_2frame.dcm")
#
# # JPEG - ISO/IEC 10918 Standard
# # FMT_BA_BV_SPX_PR_FRAMESF_PI
# # JPGB: 1.2.840.10008.1.2.4.50 - JPEG Baseline (8-bit only)
# JPGB_08_08_3_0_1F_YBR_FULL = get_testdata_file("SC_rgb_small_odd_jpeg.dcm")
# JPGB_08_08_3_0_120F_YBR_FULL_422 = get_testdata_file(
#     "color3d_jpeg_baseline.dcm"
# )  # noqa
# # Different subsampling 411, 422, 444
# JPGB_08_08_3_0_1F_YBR_FULL_422_411 = get_testdata_file(
#     "SC_rgb_dcmtk_+eb+cy+np.dcm"
# )  # noqa
# JPGB_08_08_3_0_1F_YBR_FULL_422_422 = get_testdata_file(
#     "SC_rgb_dcmtk_+eb+cy+s2.dcm"
# )  # noqa
# JPGB_08_08_3_0_1F_YBR_FULL_411 = get_testdata_file("SC_rgb_dcmtk_+eb+cy+n1.dcm")  # noqa
# JPGB_08_08_3_0_1F_YBR_FULL_422 = get_testdata_file("SC_rgb_dcmtk_+eb+cy+n2.dcm")  # noqa
# JPGB_08_08_3_0_1F_YBR_FULL_444 = get_testdata_file("SC_rgb_dcmtk_+eb+cy+s4.dcm")  # noqa
# JPGB_08_08_3_0_1F_RGB = get_testdata_file("SC_rgb_dcmtk_+eb+cr.dcm")
# # JPGE: 1.2.840.1.2.4.51 - JPEG Extended
# JPGE_BAD = get_testdata_file("JPEG-lossy.dcm")  # Bad JPEG file
# JPGE_16_12_1_0_1F_M2 = get_testdata_file("JPGExtended.dcm")  # Fixed version
# # JPGL: 1.2.840.10008.1.2.4.70 - JPEG Lossless, Non-hierarchical, 1st Order
# JPGL_08_08_1_0_1F = get_testdata_file("JPGLosslessP14SV1_1s_1f_8b.dcm")
# JPGL_16_16_1_1_1F_M2 = get_testdata_file("JPEG-LL.dcm")
#
# JPGB = JPEGBaseline8Bit
# JPGE = JPEGExtended12Bit
# JPGL = JPEGLosslessSV1
#
# JPG_REFERENCE_DATA = [
#     # fpath, (syntax, bits, nr samples, pixel repr, nr frames, shape, dtype)
#     (
#         JPGB_08_08_3_0_120F_YBR_FULL_422,
#         (JPGB, 8, 3, 0, 120, (120, 480, 640, 3), "uint8"),
#     ),  # noqa
#     (
#         JPGB_08_08_3_0_1F_YBR_FULL_422_411,
#         (JPGB, 8, 3, 0, 1, (100, 100, 3), "uint8"),
#     ),  # noqa
#     (
#         JPGB_08_08_3_0_1F_YBR_FULL_422_422,
#         (JPGB, 8, 3, 0, 1, (100, 100, 3), "uint8"),
#     ),  # noqa
#     (
#         JPGB_08_08_3_0_1F_YBR_FULL_411,
#         (JPGB, 8, 3, 0, 1, (100, 100, 3), "uint8"),
#     ),  # noqa
#     (
#         JPGB_08_08_3_0_1F_YBR_FULL_422,
#         (JPGB, 8, 3, 0, 1, (100, 100, 3), "uint8"),
#     ),  # noqa
#     (
#         JPGB_08_08_3_0_1F_YBR_FULL_444,
#         (JPGB, 8, 3, 0, 1, (100, 100, 3), "uint8"),
#     ),  # noqa
#     (JPGB_08_08_3_0_1F_RGB, (JPGB, 8, 3, 0, 1, (100, 100, 3), "uint8")),
#     (JPGE_16_12_1_0_1F_M2, (JPGE, 16, 1, 0, 1, (1024, 256), "uint16")),
#     (JPGL_08_08_1_0_1F, (JPGL, 8, 1, 0, 1, (768, 1024), "uint8")),
#     (JPGL_16_16_1_1_1F_M2, (JPGL, 16, 1, 1, 1, (1024, 256), "int16")),
# ]
# JPG_MATCHING_DATASETS = [
#     # (compressed, reference, hard coded check values), px tolerance
#     pytest.param(
#         JPGB_08_08_3_0_1F_YBR_FULL_422_411,
#         get_testdata_file("SC_rgb_dcmtk_ebcynp_dcmd.dcm"),
#         [
#             (253, 1, 0),
#             (253, 129, 131),
#             (0, 255, 5),
#             (127, 255, 129),
#             (0, 0, 254),
#             (127, 128, 255),
#             (0, 0, 0),
#             (64, 64, 64),
#             (192, 192, 192),
#             (255, 255, 255),
#         ],
#         2,
#     ),
#     pytest.param(
#         JPGB_08_08_3_0_1F_YBR_FULL_422_422,
#         get_testdata_file("SC_rgb_dcmtk_ebcys2_dcmd.dcm"),
#         [
#             (254, 0, 0),
#             (255, 127, 127),
#             (0, 255, 5),
#             (129, 255, 129),
#             (0, 0, 254),
#             (128, 127, 255),
#             (0, 0, 0),
#             (64, 64, 64),
#             (192, 192, 192),
#             (255, 255, 255),
#         ],
#         0,
#     ),
#     pytest.param(
#         JPGB_08_08_3_0_1F_YBR_FULL_411,
#         get_testdata_file("SC_rgb_dcmtk_ebcyn1_dcmd.dcm"),
#         [
#             (253, 1, 0),
#             (253, 129, 131),
#             (0, 255, 5),
#             (127, 255, 129),
#             (0, 0, 254),
#             (127, 128, 255),
#             (0, 0, 0),
#             (64, 64, 64),
#             (192, 192, 192),
#             (255, 255, 255),
#         ],
#         2,
#     ),
#     pytest.param(
#         JPGB_08_08_3_0_1F_YBR_FULL_422,
#         get_testdata_file("SC_rgb_dcmtk_ebcyn2_dcmd.dcm"),
#         [
#             (254, 0, 0),
#             (255, 127, 127),
#             (0, 255, 5),
#             (129, 255, 129),
#             (0, 0, 254),
#             (128, 127, 255),
#             (0, 0, 0),
#             (64, 64, 64),
#             (192, 192, 192),
#             (255, 255, 255),
#         ],
#         0,
#     ),
#     pytest.param(
#         JPGB_08_08_3_0_1F_YBR_FULL_444,
#         get_testdata_file("SC_rgb_dcmtk_ebcys4_dcmd.dcm"),
#         [
#             (254, 0, 0),
#             (255, 127, 127),
#             (0, 255, 5),
#             (129, 255, 129),
#             (0, 0, 254),
#             (128, 127, 255),
#             (0, 0, 0),
#             (64, 64, 64),
#             (192, 192, 192),
#             (255, 255, 255),
#         ],
#         0,
#     ),
#     pytest.param(
#         JPGB_08_08_3_0_1F_RGB,
#         get_testdata_file("SC_rgb_dcmtk_ebcr_dcmd.dcm"),
#         [
#             (255, 0, 0),
#             (255, 128, 128),
#             (0, 255, 0),
#             (128, 255, 128),
#             (0, 0, 255),
#             (128, 128, 255),
#             (0, 0, 0),
#             (64, 64, 64),
#             (192, 192, 192),
#             (255, 255, 255),
#         ],
#         1,
#     ),
# ]
#
#
# # JPEG-LS - ISO/IEC 14495 Standard
# JLSL = JPEGLSNearLossless
# JLSN = JPEGLSLossless
# JPEG_LS_LOSSLESS = get_testdata_file("MR_small_jpeg_ls_lossless.dcm")
# JLS_REFERENCE_DATA = [
#     # fpath, (syntax, bits, nr samples, pixel repr, nr frames, shape, dtype)
#     (JPEG_LS_LOSSLESS, (JLSN, 16, 1, 1, 1, (64, 64), "int16")),
# ]
#
# # JPEG 2000 - ISO/IEC 15444 Standard
# J2KR = JPEG2000Lossless
# J2KI = JPEG2000
# # J2KR: 1.2.840.100008.1.2.4.90 - JPEG 2000 Lossless
# J2KR_08_08_3_0_1F_YBR_ICT = get_testdata_file("US1_J2KR.dcm")
# J2KR_16_10_1_0_1F_M1 = get_testdata_file("RG3_J2KR.dcm")
# J2KR_16_12_1_0_1F_M2 = get_testdata_file("MR2_J2KR.dcm")
# J2KR_16_15_1_0_1F_M1 = get_testdata_file("RG1_J2KR.dcm")
# J2KR_16_16_1_0_10F_M2 = get_testdata_file("emri_small_jpeg_2k_lossless.dcm")
# J2KR_16_14_1_1_1F_M2 = get_testdata_file("693_J2KR.dcm")
# J2KR_16_16_1_1_1F_M2 = get_testdata_file("MR_small_jp2klossless.dcm")
# J2KR_16_13_1_1_1F_M2_MISMATCH = get_testdata_file("J2K_pixelrep_mismatch.dcm")
# # Non-conformant pixel data -> JP2 header present
# J2KR_08_08_3_0_1F_YBR_RCT = get_testdata_file("GDCMJ2K_TextGBR.dcm")
# # J2KI: 1.2.840.10008.1.2.4.91 - JPEG 2000
# J2KI_08_08_3_0_1F_RGB = get_testdata_file("SC_rgb_gdcm_KY.dcm")
# J2KI_08_08_3_0_1F_YBR_ICT = get_testdata_file("US1_J2KI.dcm")
# J2KI_16_10_1_0_1F_M1 = get_testdata_file("RG3_J2KI.dcm")
# J2KI_16_12_1_0_1F_M2 = get_testdata_file("MR2_J2KI.dcm")
# J2KI_16_15_1_0_1F_M1 = get_testdata_file("RG1_J2KI.dcm")
# J2KI_16_14_1_1_1F_M2 = get_testdata_file("693_J2KI.dcm")
# J2KI_16_16_1_1_1F_M2 = get_testdata_file("JPEG2000.dcm")
#
# J2K_REFERENCE_DATA = [
#     # fpath, (syntax, bits, nr samples, pixel repr, nr frames, shape, dtype)
#     (J2KR_08_08_3_0_1F_YBR_ICT, (J2KR, 8, 3, 0, 1, (480, 640, 3), "uint8")),
#     (J2KR_16_10_1_0_1F_M1, (J2KR, 16, 1, 0, 1, (1760, 1760), "uint16")),
#     (J2KR_16_12_1_0_1F_M2, (J2KR, 16, 1, 0, 1, (1024, 1024), "uint16")),
#     (J2KR_16_15_1_0_1F_M1, (J2KR, 16, 1, 0, 1, (1955, 1841), "uint16")),
#     # should be Bits Stored = 12
#     (J2KR_16_16_1_0_10F_M2, (J2KR, 16, 1, 0, 10, (10, 64, 64), "uint16")),
#     # should be Bits Stored = 16
#     (J2KR_16_14_1_1_1F_M2, (J2KR, 16, 1, 1, 1, (512, 512), "int16")),
#     (J2KR_16_16_1_1_1F_M2, (J2KR, 16, 1, 1, 1, (64, 64), "int16")),
#     (J2KI_08_08_3_0_1F_RGB, (J2KI, 8, 3, 0, 1, (100, 100, 3), "uint8")),
#     (J2KI_08_08_3_0_1F_YBR_ICT, (J2KI, 8, 3, 0, 1, (480, 640, 3), "uint8")),
#     (J2KI_16_10_1_0_1F_M1, (J2KI, 16, 1, 0, 1, (1760, 1760), "uint16")),
#     (J2KI_16_12_1_0_1F_M2, (J2KI, 16, 1, 0, 1, (1024, 1024), "uint16")),
#     (J2KI_16_15_1_0_1F_M1, (J2KI, 16, 1, 0, 1, (1955, 1841), "uint16")),
#     # should be Bits Stored = 16
#     (J2KI_16_14_1_1_1F_M2, (J2KI, 16, 1, 1, 1, (512, 512), "int16")),
#     (J2KI_16_16_1_1_1F_M2, (J2KI, 16, 1, 1, 1, (1024, 256), "int16")),
# ]
# J2K_MATCHING_DATASETS = [
#     # (compressed, reference, fixes)
#     pytest.param(
#         J2KR_08_08_3_0_1F_YBR_ICT,
#         get_testdata_file("US1_UNCR.dcm"),
#         {},
#     ),
#     pytest.param(
#         J2KR_16_10_1_0_1F_M1,
#         get_testdata_file("RG3_UNCR.dcm"),
#         {},
#     ),
#     pytest.param(
#         J2KR_16_12_1_0_1F_M2,
#         get_testdata_file("MR2_UNCR.dcm"),
#         {},
#     ),
#     pytest.param(
#         J2KR_16_15_1_0_1F_M1,
#         get_testdata_file("RG1_UNCR.dcm"),
#         {},
#     ),
#     pytest.param(
#         J2KR_16_16_1_0_10F_M2,
#         get_testdata_file("emri_small.dcm"),
#         {"BitsStored": 16},
#     ),
#     pytest.param(
#         J2KR_16_14_1_1_1F_M2,
#         get_testdata_file("693_UNCR.dcm"),
#         {"BitsStored": 14},
#     ),
#     pytest.param(
#         J2KR_16_16_1_1_1F_M2,
#         get_testdata_file("MR_small.dcm"),
#         {},
#     ),
#     pytest.param(
#         J2KI_08_08_3_0_1F_RGB,
#         get_testdata_file("SC_rgb_gdcm2k_uncompressed.dcm"),
#         {},
#     ),
#     pytest.param(
#         J2KI_08_08_3_0_1F_YBR_ICT,
#         get_testdata_file("US1_UNCI.dcm"),
#         {},
#     ),
#     pytest.param(
#         J2KI_16_10_1_0_1F_M1,
#         get_testdata_file("RG3_UNCI.dcm"),
#         {},
#     ),
#     pytest.param(
#         J2KI_16_12_1_0_1F_M2,
#         get_testdata_file("MR2_UNCI.dcm"),
#         {},
#     ),
#     pytest.param(
#         J2KI_16_15_1_0_1F_M1,
#         get_testdata_file("RG1_UNCI.dcm"),
#         {},
#     ),
#     pytest.param(
#         J2KI_16_14_1_1_1F_M2,
#         get_testdata_file("693_UNCI.dcm"),
#         {"BitsStored": 16},
#     ),
#     pytest.param(
#         J2KI_16_16_1_1_1F_M2,
#         get_testdata_file("JPEG2000_UNC.dcm"),
#         {},
#     ),
# ]
#


class TestHandler:
    """Tests for handling Pixel Data with the handler."""

    pass


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
class TestAsArray:
    @pytest.mark.skipif(not is_available(JPEGBaseline8Bit), reason="no -libjpeg plugin")
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGBaseline8Bit])
    def test_jpg_baseline(self, reference):
        """Test against the reference data JPEG Baseline 8-bit."""
        decoder = get_decoder(JPEGBaseline8Bit)

        arr = decoder.as_array(reference.ds, decoding_plugin="pylibjpeg", raw=True)
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        # Test with `index` argument
        for index in range(reference.number_of_frames):
            arr = decoder.as_array(reference.ds, raw=True, index=index)
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

    @pytest.mark.skipif(
        not is_available(JPEGExtended12Bit), reason="no -libjpeg plugin"
    )
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGExtended12Bit])
    def test_jpg_extended(self, reference):
        """Test against the reference data JPEG Extended 12-bit."""
        decoder = get_decoder(JPEGExtended12Bit)

        arr = decoder.as_array(reference.ds, decoding_plugin="pylibjpeg", raw=True)
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        # Test with `index` argument
        for index in range(reference.number_of_frames):
            arr = decoder.as_array(reference.ds, raw=True, index=index)
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

    @pytest.mark.skipif(not is_available(JPEGLossless), reason="no -libjpeg plugin")
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLossless])
    def test_jpg_lossless(self, reference):
        """Test against the reference data JPEG Lossless P14."""
        decoder = get_decoder(JPEGLossless)

        arr = decoder.as_array(reference.ds, decoding_plugin="pylibjpeg", raw=True)
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        # Test with `index` argument
        for index in range(reference.number_of_frames):
            arr = decoder.as_array(reference.ds, raw=True, index=index)
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

    @pytest.mark.skipif(not is_available(JPEGLosslessSV1), reason="no -libjpeg plugin")
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLosslessSV1])
    def test_jpg_lossless_sv1(self, reference):
        """Test against the reference data JPEG Lossless SV1."""
        decoder = get_decoder(JPEGLosslessSV1)

        arr = decoder.as_array(reference.ds, decoding_plugin="pylibjpeg", raw=True)
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        # Test with `index` argument
        for index in range(reference.number_of_frames):
            arr = decoder.as_array(reference.ds, raw=True, index=index)
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

    @pytest.mark.skipif(not is_available(JPEGLSLossless), reason="no -libjpeg plugin")
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLSLossless])
    def test_jpgls_lossless(self, reference):
        """Test against the reference data JPEG-LS Lossless."""
        decoder = get_decoder(JPEGLSLossless)

        arr = decoder.as_array(reference.ds, decoding_plugin="pylibjpeg", raw=True)
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        # Test with `index` argument
        for index in range(reference.number_of_frames):
            arr = decoder.as_array(reference.ds, raw=True, index=index)
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

    @pytest.mark.skipif(
        not is_available(JPEGLSNearLossless), reason="no -libjpeg plugin"
    )
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLSNearLossless])
    def test_jpgls(self, reference):
        """Test against the reference data JPEG-LS Near Lossless."""
        decoder = get_decoder(JPEGLSNearLossless)

        arr = decoder.as_array(reference.ds, decoding_plugin="pylibjpeg", raw=True)
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        # Test with `index` argument
        for index in range(reference.number_of_frames):
            arr = decoder.as_array(reference.ds, raw=True, index=index)
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

    @pytest.mark.skipif(
        not is_available(JPEG2000Lossless), reason="no -openjpeg plugin"
    )
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEG2000Lossless])
    def test_j2k_lossless(self, reference):
        """Test against the reference data JPEG2000 Lossless."""
        decoder = get_decoder(JPEG2000Lossless)

        arr = decoder.as_array(reference.ds, decoding_plugin="pylibjpeg", raw=True)
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        # Test with `index` argument
        for index in range(reference.number_of_frames):
            arr = decoder.as_array(reference.ds, raw=True, index=index)
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

    @pytest.mark.skipif(not is_available(JPEG2000), reason="no -openjpeg plugin")
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEG2000])
    def test_j2k(self, reference):
        """Test against the reference data JPEG2000."""
        decoder = get_decoder(JPEG2000)

        arr = decoder.as_array(reference.ds, decoding_plugin="pylibjpeg", raw=True)
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        # Test with `index` argument
        for index in range(reference.number_of_frames):
            arr = decoder.as_array(reference.ds, raw=True, index=index)
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

    @pytest.mark.skipif(not is_available(RLELossless), reason="no -openjpeg plugin")
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[RLELossless])
    def test_j2k(self, reference):
        """Test against the reference data RLE Lossless."""
        decoder = get_decoder(RLELossless)

        arr = decoder.as_array(reference.ds, decoding_plugin="pylibjpeg", raw=True)
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        # Test with `index` argument
        for index in range(reference.number_of_frames):
            arr = decoder.as_array(reference.ds, raw=True, index=index)
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]
