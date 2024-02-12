import importlib
from io import BytesIO
import logging
import os

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom import dcmread, Dataset
from pydicom.encaps import get_frame
from pydicom.pixel_data_handlers.util import convert_color_space
from pydicom.pixels import pixel_array, iter_pixels
from pydicom.pixels.utils import (
    _as_options,
    _passes_version_check,
    _get_jpg_parameters,
)
from pydicom.uid import EnhancedMRImageStorage, ExplicitVRLittleEndian

from .pixels_reference import (
    PIXEL_REFERENCE,
    RLE_16_1_10F,
    EXPL_16_1_10F,
    EXPL_8_3_1F_YBR422,
    IMPL_16_1_1F,
    JPGB_08_08_3_0_1F_RGB_NO_APP14,
    JPGB_08_08_3_0_1F_RGB_APP14,
    JPGB_08_08_3_0_1F_RGB,
    JLSL_08_08_3_0_1F_ILV0,
    JLSL_08_08_3_0_1F_ILV1,
    JLSL_08_08_3_0_1F_ILV2,
    JLSN_08_01_1_0_1F,
)

HAVE_PYLJ = bool(importlib.util.find_spec("pylibjpeg"))
HAVE_RLE = bool(importlib.util.find_spec("rle"))

SKIP_RLE = not (HAVE_NP and HAVE_PYLJ and HAVE_RLE)


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
class TestPixelArray:
    """Tests for pixel_array()"""

    def test_src(self):
        """Test the supported `src` types."""
        # Explicit VR
        # str
        p = EXPL_16_1_10F.path
        arr = pixel_array(os.fspath(p))
        EXPL_16_1_10F.test(arr)

        # Path
        arr = pixel_array(p)
        EXPL_16_1_10F.test(arr)

        # BinaryIO (io.BufferedReader)
        with open(p, "rb") as f:
            arr = pixel_array(f)
            EXPL_16_1_10F.test(arr)
            assert not f.closed

        # Implicit VR
        arr = pixel_array(IMPL_16_1_1F.path)
        IMPL_16_1_1F.test(arr)

    def test_ds_out(self):
        """Test the `ds_out` kwarg works as intended"""
        p = EXPL_16_1_10F.path
        ds = Dataset()
        arr = pixel_array(os.fspath(p), ds_out=ds)
        EXPL_16_1_10F.test(arr)
        assert ds.SamplesPerPixel == 1
        assert ds.PixelRepresentation == 0
        assert ds.file_meta.SourceApplicationEntityTitle == "gdcmanon"

    def test_specific_tags(self):
        """Test the `specific_tags` kwarg works as intended"""
        p = EXPL_16_1_10F.path
        ds = Dataset()
        tags = [0x00100010, 0x00080016]
        arr = pixel_array(os.fspath(p), ds_out=ds)
        EXPL_16_1_10F.test(arr)
        assert "PatientName" not in ds
        assert "SOPClassUID" not in ds

        arr = pixel_array(os.fspath(p), ds_out=ds, specific_tags=tags)
        EXPL_16_1_10F.test(arr)
        assert "PatientName" in ds
        assert ds.SOPClassUID == EnhancedMRImageStorage

    def test_index(self):
        """Test the `index` kwarg."""
        for index in (0, 4, 9):
            arr = pixel_array(EXPL_16_1_10F.path, index=index)
            assert arr.shape == (64, 64)
            EXPL_16_1_10F.test(arr, index=index)

    def test_raw(self):
        """Test the `raw` kwarg."""
        rgb = pixel_array(EXPL_8_3_1F_YBR422.path, raw=False)
        ybr = pixel_array(EXPL_8_3_1F_YBR422.path, raw=True)

        assert np.array_equal(
            convert_color_space(ybr, "YBR_FULL", "RGB"),
            rgb,
        )

    @pytest.mark.skipif(SKIP_RLE, reason="pylibjpeg-rle not available")
    def test_decoding_plugin(self):
        """Test the `decoding_plugin` kwarg."""
        arr1 = pixel_array(RLE_16_1_10F.path, decoding_plugin="pydicom")
        arr2 = pixel_array(RLE_16_1_10F.path, decoding_plugin="pylibjpeg")
        assert np.array_equal(arr1, arr2)

    def test_missing_file_meta(self):
        """Test a dataset with no file meta."""
        ds = dcmread(EXPL_16_1_10F.path)
        b = BytesIO()
        del ds.file_meta
        ds.save_as(b)
        b.seek(0)

        msg = (
            "'transfer_syntax_uid' is required if the dataset in 'src' is not "
            "in the DICOM File Format"
        )
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b)

        arr = pixel_array(b, transfer_syntax_uid=ExplicitVRLittleEndian)
        EXPL_16_1_10F.test(arr)

    def test_missing_required_element(self):
        """Test a dataset missing required elements."""
        ds = dcmread(EXPL_8_3_1F_YBR422.path)
        b = BytesIO()
        del ds.Columns
        del ds.Rows
        del ds.BitsAllocated
        del ds.BitsStored
        del ds.PhotometricInterpretation
        del ds.SamplesPerPixel
        del ds.PlanarConfiguration
        del ds.PixelRepresentation
        ds.save_as(b)
        b.seek(0)

        msg = (
            r"The dataset in 'src' is missing a required element: \(0028,0100\) "
            "Bits Allocated"
        )
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b)

        msg = r"required element: \(0028,0101\) Bits Stored"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"required element: \(0028,0011\) Columns"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"required element: \(0028,0010\) Rows"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
            "columns": EXPL_8_3_1F_YBR422.ds.Columns,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"required element: \(0028,0004\) Photometric Interpretation"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
            "columns": EXPL_8_3_1F_YBR422.ds.Columns,
            "rows": EXPL_8_3_1F_YBR422.ds.Rows,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"required element: \(0028,0002\) Samples per Pixel"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
            "columns": EXPL_8_3_1F_YBR422.ds.Columns,
            "rows": EXPL_8_3_1F_YBR422.ds.Rows,
            "photometric_interpretation": EXPL_8_3_1F_YBR422.ds.PhotometricInterpretation,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"required element: \(0028,0006\) Planar Configuration"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
            "columns": EXPL_8_3_1F_YBR422.ds.Columns,
            "rows": EXPL_8_3_1F_YBR422.ds.Rows,
            "photometric_interpretation": EXPL_8_3_1F_YBR422.ds.PhotometricInterpretation,
            "samples_per_pixel": EXPL_8_3_1F_YBR422.ds.SamplesPerPixel,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"required element: \(0028,0103\) Pixel Representation"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
            "columns": EXPL_8_3_1F_YBR422.ds.Columns,
            "rows": EXPL_8_3_1F_YBR422.ds.Rows,
            "photometric_interpretation": EXPL_8_3_1F_YBR422.ds.PhotometricInterpretation,
            "samples_per_pixel": EXPL_8_3_1F_YBR422.ds.SamplesPerPixel,
            "planar_configuration": EXPL_8_3_1F_YBR422.ds.PlanarConfiguration,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

    def test_missing_pixel_data(self):
        """Test dataset missing Pixel Data"""
        ds = dcmread(EXPL_8_3_1F_YBR422.path)
        b = BytesIO()
        del ds.PixelData
        ds.save_as(b)
        b.seek(0)

        msg = (
            "The dataset in 'src' has no 'Pixel Data', 'Float Pixel Data' or "
            "'Double Float Pixel Data' element, no pixel data to decode"
        )
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b)

    def test_extended_offsets(self):
        """Test that the extended offset table values are retrieved OK"""
        ds = EXPL_8_3_1F_YBR422.ds
        offsets = (
            b"\x00\x00\x00\x00\x00\x00\x00\x01",
            b"\x00\x00\x00\x00\x00\x00\x00\x02",
        )
        ds.ExtendedOffsetTable = offsets[0]
        ds.ExtendedOffsetTableLengths = offsets[1]
        opts = _as_options(ds, {})
        assert opts["extended_offsets"] == offsets

        offsets = (
            b"\x00\x00\x00\x00\x00\x00\x00\x03",
            b"\x00\x00\x00\x00\x00\x00\x00\x04",
        )
        opts = _as_options(ds, {"extended_offsets": offsets})
        assert opts["extended_offsets"] == offsets


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
class TestIterPixels:
    """Tests for iter_pixels()"""

    def test_src(self):
        """Test the supported `src` types."""
        # Explicit VR
        # str
        p = EXPL_16_1_10F.path
        for index, frame in enumerate(iter_pixels(os.fspath(p))):
            EXPL_16_1_10F.test(frame, index=index)

        # Path
        for index, frame in enumerate(iter_pixels(p)):
            EXPL_16_1_10F.test(frame, index=index)

        # BinaryIO (io.BufferedReader)
        with open(p, "rb") as f:
            for index, frame in enumerate(iter_pixels(f)):
                EXPL_16_1_10F.test(frame, index=index)

            assert not f.closed

        # Implicit VR
        for index, frame in enumerate(iter_pixels(IMPL_16_1_1F.path)):
            IMPL_16_1_1F.test(frame, index=index)

    def test_ds_out(self):
        """Test the `ds_out` kwarg works as intended"""
        p = EXPL_16_1_10F.path
        ds = Dataset()
        frame_gen = iter_pixels(p, ds_out=ds)
        frame = next(frame_gen)
        assert ds.SamplesPerPixel == 1
        assert ds.PixelRepresentation == 0
        assert ds.file_meta.SourceApplicationEntityTitle == "gdcmanon"
        EXPL_16_1_10F.test(frame, index=0)

        for index, frame in enumerate(frame_gen):
            EXPL_16_1_10F.test(frame, index=index + 1)

    def test_specific_tags(self):
        """Test the `specific_tags` kwarg works as intended"""
        p = EXPL_16_1_10F.path
        ds = Dataset()
        tags = [0x00100010, 0x00080016]

        frame_gen = iter_pixels(p, ds_out=ds)
        frame = next(frame_gen)
        assert "PatientName" not in ds
        assert "SOPClassUID" not in ds
        assert ds.SamplesPerPixel == 1
        assert ds.PixelRepresentation == 0
        assert ds.file_meta.SourceApplicationEntityTitle == "gdcmanon"
        EXPL_16_1_10F.test(frame, index=0)
        for index, frame in enumerate(frame_gen):
            EXPL_16_1_10F.test(frame, index=index + 1)

        frame_gen = iter_pixels(p, ds_out=ds, specific_tags=tags)
        frame = next(frame_gen)
        assert "PatientName" in ds
        assert ds.SOPClassUID == EnhancedMRImageStorage
        EXPL_16_1_10F.test(frame, index=0)
        for index, frame in enumerate(frame_gen):
            EXPL_16_1_10F.test(frame, index=index + 1)

    def test_indices(self):
        """Test the `indices` kwarg."""
        p = EXPL_16_1_10F.path
        indices = [0, 4, 9]
        frame_gen = iter_pixels(p, indices=indices)
        count = 0
        for frame in frame_gen:
            EXPL_16_1_10F.test(frame, index=indices[count])
            count += 1

        assert count == 3

    def test_raw(self):
        """Test the `raw` kwarg."""
        processed = iter_pixels(EXPL_8_3_1F_YBR422.path, raw=False)
        raw = iter_pixels(EXPL_8_3_1F_YBR422.path, raw=True)
        for rgb, ybr in zip(processed, raw):
            assert np.array_equal(
                convert_color_space(ybr, "YBR_FULL", "RGB"),
                rgb,
            )

    @pytest.mark.skipif(SKIP_RLE, reason="pylibjpeg-rle not available")
    def test_decoding_plugin(self):
        """Test the `decoding_plugin` kwarg."""
        pydicom_gen = iter_pixels(RLE_16_1_10F.path, decoding_plugin="pydicom")
        pylibjpeg_gen = iter_pixels(RLE_16_1_10F.path, decoding_plugin="pylibjpeg")
        for frame1, frame2 in zip(pydicom_gen, pylibjpeg_gen):
            assert np.array_equal(frame1, frame2)


def test_version_check(caplog):
    """Test _passes_version_check() when the package is absent"""
    with caplog.at_level(logging.ERROR, logger="pydicom"):
        assert _passes_version_check("foo", (3, 0)) is False
        assert "No module named 'foo'" in caplog.text


class TestGetJpgParameters:
    """Tests for _get_jpg_parameters()"""

    def test_jpg_no_app(self):
        """Test parsing a JPEG codestream with no APP markers."""
        data = get_frame(JPGB_08_08_3_0_1F_RGB_NO_APP14.ds.PixelData, 0)
        info = _get_jpg_parameters(data)
        assert info["precision"] == 8
        assert info["height"] == 256
        assert info["width"] == 256
        assert info["components"] == 3
        assert info["component_ids"] == [0, 1, 2]
        assert "app" not in info
        assert "lossy_error" not in info
        assert "interleave_mode" not in info

    def test_jpg_app(self):
        """Test parsing a JPEG codestream with APP markers."""
        data = get_frame(JPGB_08_08_3_0_1F_RGB_APP14.ds.PixelData, 0)
        info = _get_jpg_parameters(data)
        assert info["precision"] == 8
        assert info["height"] == 256
        assert info["width"] == 256
        assert info["components"] == 3
        assert info["component_ids"] == [0, 1, 2]
        assert isinstance(info["app"][b"\xFF\xEE"], bytes)
        assert "lossy_error" not in info
        assert "interleave_mode" not in info

    def test_jpg_component_ids(self):
        """Test parsing a JPEG codestream with ASCII component IDs."""
        data = get_frame(JPGB_08_08_3_0_1F_RGB.ds.PixelData, 0)
        info = _get_jpg_parameters(data)
        assert info["precision"] == 8
        assert info["height"] == 100
        assert info["width"] == 100
        assert info["components"] == 3
        assert info["component_ids"] == [82, 71, 66]  # R, G, B
        assert isinstance(info["app"][b"\xFF\xEE"], bytes)
        assert "lossy_error" not in info
        assert "interleave_mode" not in info

    def test_jls_ilv0(self):
        """Test parsing a lossless JPEG-LS codestream with ILV 0."""
        data = get_frame(JLSL_08_08_3_0_1F_ILV0.ds.PixelData, 0)
        info = _get_jpg_parameters(data)
        assert info["precision"] == 8
        assert info["height"] == 256
        assert info["width"] == 256
        assert info["components"] == 3
        assert info["component_ids"] == [1, 2, 3]
        assert "app" not in info
        assert info["lossy_error"] == 0
        assert info["interleave_mode"] == 0

    def test_jls_ilv1(self):
        """Test parsing a lossless JPEG-LS codestream with ILV 1."""
        data = get_frame(JLSL_08_08_3_0_1F_ILV1.ds.PixelData, 0)
        info = _get_jpg_parameters(data)
        assert info["precision"] == 8
        assert info["height"] == 256
        assert info["width"] == 256
        assert info["components"] == 3
        assert info["component_ids"] == [1, 2, 3]
        assert "app" not in info
        assert info["lossy_error"] == 0
        assert info["interleave_mode"] == 1

    def test_jls_ilv2(self):
        """Test parsing a lossless JPEG-LS codestream with ILV 2."""
        data = get_frame(JLSL_08_08_3_0_1F_ILV2.ds.PixelData, 0)
        info = _get_jpg_parameters(data)
        assert info["precision"] == 8
        assert info["height"] == 256
        assert info["width"] == 256
        assert info["components"] == 3
        assert info["component_ids"] == [1, 2, 3]
        assert "app" not in info
        assert info["lossy_error"] == 0
        assert info["interleave_mode"] == 2

    def test_jls_lossy(self):
        """Test parsing a lossy JPEG-LS codestream."""
        data = get_frame(JLSN_08_01_1_0_1F.ds.PixelData, 0)
        info = _get_jpg_parameters(data)
        assert info["precision"] == 8
        assert info["height"] == 45
        assert info["width"] == 10
        assert info["components"] == 1
        assert info["component_ids"] == [1]
        assert "app" not in info
        assert info["lossy_error"] == 2
        assert info["interleave_mode"] == 0
