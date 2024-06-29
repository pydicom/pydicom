# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Tests for the pixels.utils module."""

import importlib
from io import BytesIO
import logging
import os
import random
from struct import pack
from sys import byteorder

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom import dcmread, config
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.encaps import get_frame, encapsulate
from pydicom.pixels import pixel_array, iter_pixels, convert_color_space
from pydicom.pixels.decoders.base import _PIXEL_DATA_DECODERS
from pydicom.pixels.encoders import RLELosslessEncoder
from pydicom.pixels.utils import (
    as_pixel_options,
    _passes_version_check,
    _get_jpg_parameters,
    reshape_pixel_array,
    pixel_dtype,
    get_expected_length,
    get_j2k_parameters,
    get_nr_frames,
    pack_bits,
    set_pixel_data,
    unpack_bits,
    expand_ybr422,
    compress,
    decompress,
)
from pydicom.uid import (
    EnhancedMRImageStorage,
    ExplicitVRLittleEndian,
    ExplicitVRBigEndian,
    ImplicitVRLittleEndian,
    UncompressedTransferSyntaxes,
    RLELossless,
    JPEG2000Lossless,
    JPEG2000,
    JPEG2000MC,
    JPEGLSNearLossless,
    JPEGLSLossless,
    UID,
    MPEG2MPHLF,
)

from .pixels_reference import (
    PIXEL_REFERENCE,
    RLE_8_3_1F,
    RLE_16_1_1F,
    RLE_16_1_10F,
    RLE_32_3_2F,
    EXPL_16_1_10F,
    EXPL_16_16_1F,
    EXPL_8_3_1F_ODD,
    EXPL_8_3_1F_YBR422,
    IMPL_16_1_1F,
    JPGB_08_08_3_0_1F_RGB_NO_APP14,
    JPGB_08_08_3_0_1F_RGB_APP14,
    JPGB_08_08_3_0_1F_RGB,
    JPGB_08_08_3_1F_YBR_FULL,
    JLSL_08_08_3_0_1F_ILV0,
    JLSL_08_08_3_0_1F_ILV1,
    JLSL_08_08_3_0_1F_ILV2,
    JLSN_08_01_1_0_1F,
    J2KR_08_08_3_0_1F_YBR_RCT,
    EXPL_1_1_3F,
)
from ..test_helpers import assert_no_warning


HAVE_PYLJ = bool(importlib.util.find_spec("pylibjpeg"))
HAVE_RLE = bool(importlib.util.find_spec("rle"))
HAVE_JLS = bool(importlib.util.find_spec("jpeg_ls"))
HAVE_LJ = bool(importlib.util.find_spec("libjpeg"))
HAVE_OJ = bool(importlib.util.find_spec("openjpeg"))

SKIP_RLE = not (HAVE_NP and HAVE_PYLJ and HAVE_RLE)
SKIP_JPG = not (HAVE_NP and HAVE_PYLJ and HAVE_LJ)
SKIP_JLS = not (HAVE_NP and HAVE_JLS)
SKIP_J2K = not (HAVE_NP and HAVE_PYLJ and HAVE_OJ)


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

        msg = r"Missing required element: \(0028,0100\) 'Bits Allocated'"
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b)

        msg = r"Missing required element: \(0028,0101\) 'Bits Stored'"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"Missing required element: \(0028,0011\) 'Columns'"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"Missing required element: \(0028,0004\) 'Photometric Interpretation'"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
            "columns": EXPL_8_3_1F_YBR422.ds.Columns,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"Missing required element: \(0028,0103\) 'Pixel Representation'"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
            "columns": EXPL_8_3_1F_YBR422.ds.Columns,
            "photometric_interpretation": EXPL_8_3_1F_YBR422.ds.PhotometricInterpretation,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"Missing required element: \(0028,0010\) 'Rows'"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
            "columns": EXPL_8_3_1F_YBR422.ds.Columns,
            "photometric_interpretation": EXPL_8_3_1F_YBR422.ds.PhotometricInterpretation,
            "pixel_representation": EXPL_8_3_1F_YBR422.ds.PixelRepresentation,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"Missing required element: \(0028,0002\) 'Samples per Pixel'"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
            "columns": EXPL_8_3_1F_YBR422.ds.Columns,
            "photometric_interpretation": EXPL_8_3_1F_YBR422.ds.PhotometricInterpretation,
            "pixel_representation": EXPL_8_3_1F_YBR422.ds.PixelRepresentation,
            "rows": EXPL_8_3_1F_YBR422.ds.Rows,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"Missing required element: \(0028,0006\) 'Planar Configuration'"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
            "columns": EXPL_8_3_1F_YBR422.ds.Columns,
            "rows": EXPL_8_3_1F_YBR422.ds.Rows,
            "photometric_interpretation": EXPL_8_3_1F_YBR422.ds.PhotometricInterpretation,
            "samples_per_pixel": EXPL_8_3_1F_YBR422.ds.SamplesPerPixel,
            "pixel_representation": EXPL_8_3_1F_YBR422.ds.PixelRepresentation,
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
        opts = as_pixel_options(ds)
        assert opts["extended_offsets"] == offsets

        offsets = (
            b"\x00\x00\x00\x00\x00\x00\x00\x03",
            b"\x00\x00\x00\x00\x00\x00\x00\x04",
        )
        opts = as_pixel_options(ds, **{"extended_offsets": offsets})
        assert opts["extended_offsets"] == offsets

    def test_dataset(self):
        """Test passing a dataset"""
        ds = EXPL_16_1_10F.ds
        arr = pixel_array(ds)
        EXPL_16_1_10F.test(arr)

    def test_dataset_unknown_tsyntax_raises(self):
        """Test no transfer syntax raises exception"""
        ds = dcmread(EXPL_16_1_10F.path)
        del ds.file_meta.TransferSyntaxUID
        msg = (
            "Unable to decode the pixel data as the dataset's 'file_meta' has no "
            r"\(0002,0010\) 'Transfer Syntax UID' element"
        )
        with pytest.raises(AttributeError, match=msg):
            pixel_array(ds)

    def test_no_matching_decoder_raises(self):
        """Test no matching decoding plugin raises exception."""
        ds = dcmread(EXPL_16_1_10F.path)
        ds.file_meta.TransferSyntaxUID = MPEG2MPHLF
        msg = (
            r"Unable to decode the pixel data as a \(0002,0010\) 'Transfer Syntax "
            "UID' value of 'Fragmentable MPEG2 Main Profile / High Level' is not "
            "supported"
        )
        with pytest.raises(NotImplementedError, match=msg):
            pixel_array(ds)

        ds.PixelData = encapsulate([ds.PixelData])
        b = BytesIO()
        ds.save_as(b)
        b.seek(0)
        with pytest.raises(NotImplementedError, match=msg):
            pixel_array(b)


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

    def test_dataset(self):
        """Test passing a dataset"""
        ds = EXPL_16_1_10F.ds
        for idx, arr in enumerate(iter_pixels(ds)):
            EXPL_16_1_10F.test(arr, index=idx)

    def test_dataset_unknown_tsyntax_raises(self):
        """Test no transfer syntax raises exception"""
        ds = dcmread(EXPL_16_1_10F.path)
        del ds.file_meta.TransferSyntaxUID
        msg = (
            "Unable to decode the pixel data as the dataset's 'file_meta' has no "
            r"\(0002,0010\) 'Transfer Syntax UID' element"
        )
        with pytest.raises(AttributeError, match=msg):
            next(iter_pixels(ds))

    def test_no_matching_decoder_raises(self):
        """Test no matching decoding plugin raises exception."""
        ds = dcmread(EXPL_16_1_10F.path)
        ds.file_meta.TransferSyntaxUID = MPEG2MPHLF
        msg = (
            r"Unable to decode the pixel data as a \(0002,0010\) 'Transfer Syntax "
            "UID' value of 'Fragmentable MPEG2 Main Profile / High Level' is not "
            "supported"
        )
        with pytest.raises(NotImplementedError, match=msg):
            next(iter_pixels(ds))

        ds.PixelData = encapsulate([ds.PixelData])
        b = BytesIO()
        ds.save_as(b)
        b.seek(0)
        with pytest.raises(NotImplementedError, match=msg):
            next(iter_pixels(b))


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
        assert info["app"][b"\xFF\xEE"] == (
            b"\x41\x64\x6F\x62\x65\x00\x65\x00\x00\x00\x00\x00"
        )
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

    def test_invalid(self):
        """Test invalid codestreams."""
        assert _get_jpg_parameters(b"\x00\x00") == {}
        data = get_frame(JLSN_08_01_1_0_1F.ds.PixelData, 0)
        assert _get_jpg_parameters(data[:20]) == {}


REFERENCE_DTYPE = [
    # BitsAllocated, PixelRepresentation, as_float, numpy dtype string
    (1, 0, False, "uint8"),
    (1, 1, False, "uint8"),
    (8, 0, False, "uint8"),
    (8, 1, False, "int8"),
    (16, 0, False, "uint16"),
    (16, 1, False, "int16"),
    (32, 0, False, "uint32"),
    (32, 1, False, "int32"),
    (32, 0, True, "float32"),
    (64, 0, True, "float64"),
]


@pytest.mark.skipif(HAVE_NP, reason="Numpy is available")
def test_pixel_dtype_raises():
    """Test that pixel_dtype raises exception without numpy."""
    with pytest.raises(ImportError, match="Numpy is required to determine the dtype"):
        pixel_dtype(None)


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestPixelDtype:
    """Tests for pixel_dtype()."""

    def setup_method(self):
        """Setup the test dataset."""
        self.ds = Dataset()
        self.ds.file_meta = FileMetaDataset()
        self.ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    def test_unknown_pixel_representation_raises(self):
        """Test an unknown PixelRepresentation value raises exception."""
        self.ds.BitsAllocated = 16
        with pytest.warns(UserWarning):
            self.ds.PixelRepresentation = -1
        # The bracket needs to be escaped
        with pytest.raises(ValueError, match=r"value of '-1' for '\(0028,0103"):
            pixel_dtype(self.ds)

        self.ds.PixelRepresentation = 2
        with pytest.raises(ValueError, match=r"value of '2' for '\(0028,0103"):
            pixel_dtype(self.ds)

    def test_unknown_bits_allocated_raises(self):
        """Test an unknown BitsAllocated value raises exception."""
        self.ds.BitsAllocated = 0
        self.ds.PixelRepresentation = 0
        # The bracket needs to be escaped
        with pytest.raises(ValueError, match=r"value of '0' for '\(0028,0100"):
            pixel_dtype(self.ds)

        self.ds.BitsAllocated = 2
        with pytest.raises(ValueError, match=r"value of '2' for '\(0028,0100"):
            pixel_dtype(self.ds)

        self.ds.BitsAllocated = 15
        with pytest.raises(ValueError, match=r"value of '15' for '\(0028,0100"):
            pixel_dtype(self.ds)

    def test_unsupported_dtypes(self):
        """Test unsupported dtypes raise exception."""
        self.ds.BitsAllocated = 24
        self.ds.PixelRepresentation = 0

        with pytest.raises(
            NotImplementedError, match="data type 'uint24' needed to contain"
        ):
            pixel_dtype(self.ds)

    @pytest.mark.parametrize("bits, pixel_repr, as_float, dtype", REFERENCE_DTYPE)
    def test_supported_dtypes(self, bits, pixel_repr, as_float, dtype):
        """Test supported dtypes."""
        self.ds.BitsAllocated = bits
        self.ds.PixelRepresentation = pixel_repr
        # Correct for endianness of system
        ref_dtype = np.dtype(dtype)
        endianness = self.ds.file_meta.TransferSyntaxUID.is_little_endian
        if endianness != (byteorder == "little"):
            ref_dtype = ref_dtype.newbyteorder("S")

        assert ref_dtype == pixel_dtype(self.ds, as_float=as_float)

    def test_byte_swapping(self):
        """Test that the endianness of the system is taken into account."""
        # The main problem is that our testing environments are probably
        #   all little endian, but we'll try our best
        self.ds.BitsAllocated = 16
        self.ds.PixelRepresentation = 0

        # explicit little
        meta = self.ds.file_meta

        # < is little, = is native, > is big
        if byteorder == "little":
            self.ds._read_little = True
            assert pixel_dtype(self.ds).byteorder in ["<", "="]
            meta.TransferSyntaxUID = ExplicitVRBigEndian
            self.ds._read_little = False
            assert pixel_dtype(self.ds).byteorder == ">"
        elif byteorder == "big":
            self.ds._read_little = True
            assert pixel_dtype(self.ds).byteorder == "<"
            meta.TransferSyntaxUID = ExplicitVRBigEndian
            self.ds._read_little = False
            assert pixel_dtype(self.ds).byteorder in [">", "="]

    def test_no_endianness_raises(self):
        ds = Dataset()
        ds.BitsAllocated = 8
        ds.PixelRepresentation = 1
        msg = (
            "Unable to determine the endianness of the dataset, please set "
            "an appropriate Transfer Syntax UID in 'Dataset.file_meta'"
        )
        with pytest.raises(AttributeError, match=msg):
            pixel_dtype(ds)


if HAVE_NP:
    _arr1_1 = [1, 2, 3, 4, 5, 2, 3, 4, 5, 6, 3, 4, 5, 6, 7, 4, 5, 6, 7, 8]

    _arr2_1 = _arr1_1[:]
    _arr2_1.extend(
        [25, 26, 27, 28, 29, 26, 27, 28, 29, 30, 27, 28, 29, 30, 31, 28, 29, 30, 31, 32]
    )

    _arr1_3_0 = [1, 9, 17, 2, 10, 18, 3, 11, 19, 4, 12, 20, 5, 13, 21, 2, 10, 18, 3, 11]
    _arr1_3_0.extend(
        [19, 4, 12, 20, 5, 13, 21, 6, 14, 22, 3, 11, 19, 4, 12, 20, 5, 13, 21, 6]
    )
    _arr1_3_0.extend(
        [14, 22, 7, 15, 23, 4, 12, 20, 5, 13, 21, 6, 14, 22, 7, 15, 23, 8, 16, 24]
    )

    _arr1_3_1 = _arr1_1[:]
    _arr1_3_1.extend(
        [9, 10, 11, 12, 13, 10, 11, 12, 13, 14, 11, 12, 13, 14, 15, 12, 13, 14, 15, 16]
    )
    _arr1_3_1.extend(
        [17, 18, 19, 20, 21, 18, 19, 20, 21, 22, 19, 20, 21, 22, 23, 20, 21, 22, 23, 24]
    )

    _arr2_3_0 = _arr1_3_0[:]
    _arr2_3_0.extend(
        [25, 33, 41, 26, 34, 42, 27, 35, 43, 28, 36, 44, 29, 37, 45, 26, 34, 42, 27, 35]
    )
    _arr2_3_0.extend(
        [43, 28, 36, 44, 29, 37, 45, 30, 38, 46, 27, 35, 43, 28, 36, 44, 29, 37, 45, 30]
    )
    _arr2_3_0.extend(
        [38, 46, 31, 39, 47, 28, 36, 44, 29, 37, 45, 30, 38, 46, 31, 39, 47, 32, 40, 48]
    )

    _arr2_3_1 = _arr1_3_1[:]
    _arr2_3_1.extend(
        [25, 26, 27, 28, 29, 26, 27, 28, 29, 30, 27, 28, 29, 30, 31, 28, 29, 30, 31, 32]
    )
    _arr2_3_1.extend(
        [33, 34, 35, 36, 37, 34, 35, 36, 37, 38, 35, 36, 37, 38, 39, 36, 37, 38, 39, 40]
    )
    _arr2_3_1.extend(
        [41, 42, 43, 44, 45, 42, 43, 44, 45, 46, 43, 44, 45, 46, 47, 44, 45, 46, 47, 48]
    )

    RESHAPE_ARRAYS = {
        "reference": np.asarray(
            [
                [  # Frame 1
                    [[1, 9, 17], [2, 10, 18], [3, 11, 19], [4, 12, 20], [5, 13, 21]],
                    [[2, 10, 18], [3, 11, 19], [4, 12, 20], [5, 13, 21], [6, 14, 22]],
                    [[3, 11, 19], [4, 12, 20], [5, 13, 21], [6, 14, 22], [7, 15, 23]],
                    [[4, 12, 20], [5, 13, 21], [6, 14, 22], [7, 15, 23], [8, 16, 24]],
                ],
                [  # Frame 2
                    [
                        [25, 33, 41],
                        [26, 34, 42],
                        [27, 35, 43],
                        [28, 36, 44],
                        [29, 37, 45],
                    ],
                    [
                        [26, 34, 42],
                        [27, 35, 43],
                        [28, 36, 44],
                        [29, 37, 45],
                        [30, 38, 46],
                    ],
                    [
                        [27, 35, 43],
                        [28, 36, 44],
                        [29, 37, 45],
                        [30, 38, 46],
                        [31, 39, 47],
                    ],
                    [
                        [28, 36, 44],
                        [29, 37, 45],
                        [30, 38, 46],
                        [31, 39, 47],
                        [32, 40, 48],
                    ],
                ],
            ]
        ),
        "1frame_1sample": np.asarray(_arr1_1),
        "2frame_1sample": np.asarray(_arr2_1),
        "1frame_3sample_0config": np.asarray(_arr1_3_0),
        "1frame_3sample_1config": np.asarray(_arr1_3_1),
        "2frame_3sample_0config": np.asarray(_arr2_3_0),
        "2frame_3sample_1config": np.asarray(_arr2_3_1),
    }


@pytest.mark.skipif(HAVE_NP, reason="Numpy is available")
def test_reshape_pixel_array_raises():
    """Test that reshape_pixel_array raises exception without numpy."""
    with pytest.raises(ImportError, match="Numpy is required to reshape"):
        reshape_pixel_array(None, None)


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestReshapePixelArray:
    """Tests for reshape_pixel_array()."""

    def setup_method(self):
        """Setup the test dataset."""
        self.ds = Dataset()
        self.ds.file_meta = FileMetaDataset()
        self.ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        self.ds.Rows = 4
        self.ds.Columns = 5

        # Expected output ref_#frames_#samples
        self.ref_1_1 = RESHAPE_ARRAYS["reference"][0, :, :, 0]
        self.ref_1_3 = RESHAPE_ARRAYS["reference"][0]
        self.ref_2_1 = RESHAPE_ARRAYS["reference"][:, :, :, 0]
        self.ref_2_3 = RESHAPE_ARRAYS["reference"]

    def test_reference_1frame_1sample(self):
        """Test the 1 frame 1 sample/pixel reference array is as expected."""
        # (rows, columns)
        assert (4, 5) == self.ref_1_1.shape
        assert np.array_equal(
            self.ref_1_1,
            np.asarray(
                [[1, 2, 3, 4, 5], [2, 3, 4, 5, 6], [3, 4, 5, 6, 7], [4, 5, 6, 7, 8]]
            ),
        )

    def test_reference_1frame_3sample(self):
        """Test the 1 frame 3 sample/pixel reference array is as expected."""
        # (rows, columns, planes)
        assert (4, 5, 3) == self.ref_1_3.shape

        # Red channel
        assert np.array_equal(
            self.ref_1_3[:, :, 0],
            np.asarray(
                [[1, 2, 3, 4, 5], [2, 3, 4, 5, 6], [3, 4, 5, 6, 7], [4, 5, 6, 7, 8]]
            ),
        )
        # Green channel
        assert np.array_equal(
            self.ref_1_3[:, :, 1],
            np.asarray(
                [
                    [9, 10, 11, 12, 13],
                    [10, 11, 12, 13, 14],
                    [11, 12, 13, 14, 15],
                    [12, 13, 14, 15, 16],
                ]
            ),
        )
        # Blue channel
        assert np.array_equal(
            self.ref_1_3[:, :, 2],
            np.asarray(
                [
                    [17, 18, 19, 20, 21],
                    [18, 19, 20, 21, 22],
                    [19, 20, 21, 22, 23],
                    [20, 21, 22, 23, 24],
                ]
            ),
        )

    def test_reference_2frame_1sample(self):
        """Test the 2 frame 1 sample/pixel reference array is as expected."""
        # (nr frames, rows, columns)
        assert (2, 4, 5) == self.ref_2_1.shape

        # Frame 1
        assert np.array_equal(
            self.ref_2_1[0, :, :],
            np.asarray(
                [[1, 2, 3, 4, 5], [2, 3, 4, 5, 6], [3, 4, 5, 6, 7], [4, 5, 6, 7, 8]]
            ),
        )
        # Frame 2
        assert np.array_equal(
            self.ref_2_1[1, :, :],
            np.asarray(
                [
                    [25, 26, 27, 28, 29],
                    [26, 27, 28, 29, 30],
                    [27, 28, 29, 30, 31],
                    [28, 29, 30, 31, 32],
                ]
            ),
        )

    def test_reference_2frame_3sample(self):
        """Test the 2 frame 3 sample/pixel reference array is as expected."""
        # (nr frames, row, columns, planes)
        assert (2, 4, 5, 3) == self.ref_2_3.shape

        # Red channel, frame 1
        assert np.array_equal(
            self.ref_2_3[0, :, :, 0],
            np.asarray(
                [[1, 2, 3, 4, 5], [2, 3, 4, 5, 6], [3, 4, 5, 6, 7], [4, 5, 6, 7, 8]]
            ),
        )
        # Green channel, frame 2
        assert np.array_equal(
            self.ref_2_3[1, :, :, 1],
            np.asarray(
                [
                    [33, 34, 35, 36, 37],
                    [34, 35, 36, 37, 38],
                    [35, 36, 37, 38, 39],
                    [36, 37, 38, 39, 40],
                ]
            ),
        )

    def test_1frame_1sample(self):
        """Test reshaping 1 frame, 1 sample/pixel."""
        self.ds.SamplesPerPixel = 1
        arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_1sample"])
        assert (4, 5) == arr.shape
        assert np.array_equal(arr, self.ref_1_1)

    def test_1frame_3sample_0conf(self):
        """Test reshaping 1 frame, 3 sample/pixel for 0 planar config."""
        self.ds.NumberOfFrames = 1
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 0
        arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_3sample_0config"])
        assert (4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_1_3)

    def test_1frame_3sample_1conf(self):
        """Test reshaping 1 frame, 3 sample/pixel for 1 planar config."""
        self.ds.NumberOfFrames = 1
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 1
        arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_3sample_1config"])
        assert (4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_1_3)

    def test_2frame_1sample(self):
        """Test reshaping 2 frame, 1 sample/pixel."""
        self.ds.NumberOfFrames = 2
        self.ds.SamplesPerPixel = 1
        arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["2frame_1sample"])
        assert (2, 4, 5) == arr.shape
        assert np.array_equal(arr, self.ref_2_1)

    def test_2frame_3sample_0conf(self):
        """Test reshaping 2 frame, 3 sample/pixel for 0 planar config."""
        self.ds.NumberOfFrames = 2
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 0
        arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["2frame_3sample_0config"])
        assert (2, 4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_2_3)

    def test_2frame_3sample_1conf(self):
        """Test reshaping 2 frame, 3 sample/pixel for 1 planar config."""
        self.ds.NumberOfFrames = 2
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 1
        arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["2frame_3sample_1config"])
        assert (2, 4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_2_3)

    def test_compressed_syntaxes_0conf(self):
        """Test the compressed syntaxes that are always 0 planar conf."""
        for uid in [
            "1.2.840.10008.1.2.4.50",
            "1.2.840.10008.1.2.4.57",
            "1.2.840.10008.1.2.4.70",
            "1.2.840.10008.1.2.4.90",
            "1.2.840.10008.1.2.4.91",
        ]:
            self.ds.file_meta.TransferSyntaxUID = uid
            self.ds.PlanarConfiguration = 1
            self.ds.NumberOfFrames = 1
            self.ds.SamplesPerPixel = 3

            arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_3sample_0config"])
            assert (4, 5, 3) == arr.shape
            assert np.array_equal(arr, self.ref_1_3)

    def test_compressed_syntaxes_1conf(self):
        """Test the compressed syntaxes that are always 1 planar conf."""
        for uid in ["1.2.840.10008.1.2.5"]:
            self.ds.file_meta.TransferSyntaxUID = uid
            self.ds.PlanarConfiguration = 0
            self.ds.NumberOfFrames = 1
            self.ds.SamplesPerPixel = 3

            arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_3sample_1config"])
            assert (4, 5, 3) == arr.shape
            assert np.array_equal(arr, self.ref_1_3)

    def test_uncompressed_syntaxes(self):
        """Test that uncompressed syntaxes use the dataset planar conf."""
        for uid in UncompressedTransferSyntaxes:
            self.ds.file_meta.TransferSyntaxUID = uid
            self.ds.PlanarConfiguration = 0
            self.ds.NumberOfFrames = 1
            self.ds.SamplesPerPixel = 3

            arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_3sample_0config"])
            assert (4, 5, 3) == arr.shape
            assert np.array_equal(arr, self.ref_1_3)

            self.ds.PlanarConfiguration = 1
            arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_3sample_1config"])
            assert (4, 5, 3) == arr.shape
            assert np.array_equal(arr, self.ref_1_3)

    def test_invalid_nr_frames_warns(self):
        """Test an invalid Number of Frames value shows an warning."""
        self.ds.SamplesPerPixel = 1
        self.ds.NumberOfFrames = 0
        # Need to escape brackets
        with pytest.warns(UserWarning, match=r"value of 0 for \(0028,0008\)"):
            reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_1sample"])

    def test_invalid_samples_raises(self):
        """Test an invalid Samples per Pixel value raises exception."""
        self.ds.SamplesPerPixel = 0
        # Need to escape brackets
        with pytest.raises(ValueError, match=r"value of 0 for \(0028,0002\)"):
            reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_1sample"])

    def test_invalid_planar_conf_raises(self):
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 2
        # Need to escape brackets
        with pytest.raises(ValueError, match=r"value of 2 for \(0028,0006\)"):
            reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_3sample_0config"])


REFERENCE_LENGTH = [
    # (frames, rows, cols, samples), bit depth,
    #   result in (bytes, pixels, ybr_bytes)
    # YBR can only be 3 samples/px and > 1 bit depth
    # No 'NumberOfFrames' in dataset
    ((0, 0, 0, 0), 1, (0, 0, None)),
    ((0, 1, 1, 1), 1, (1, 1, None)),  # 1 bit -> 1 byte
    ((0, 1, 1, 3), 1, (1, 3, None)),  # 3 bits -> 1 byte
    ((0, 1, 3, 3), 1, (2, 9, None)),  # 9 bits -> 2 bytes
    ((0, 2, 2, 1), 1, (1, 4, None)),  # 4 bits -> 1 byte
    ((0, 2, 4, 1), 1, (1, 8, None)),  # 8 bits -> 1 byte
    ((0, 3, 3, 1), 1, (2, 9, None)),  # 9 bits -> 2 bytes
    ((0, 512, 512, 1), 1, (32768, 262144, None)),  # Typical length
    ((0, 512, 512, 3), 1, (98304, 786432, None)),
    ((0, 0, 0, 0), 8, (0, 0, None)),
    ((0, 1, 1, 1), 8, (1, 1, None)),  # Odd length
    ((0, 9, 1, 1), 8, (9, 9, None)),  # Odd length
    ((0, 1, 2, 1), 8, (2, 2, None)),  # Even length
    ((0, 512, 512, 1), 8, (262144, 262144, None)),
    ((0, 512, 512, 3), 8, (786432, 786432, 524288)),
    ((0, 0, 0, 0), 16, (0, 0, None)),
    ((0, 1, 1, 1), 16, (2, 1, None)),  # 16 bit data can't be odd length
    ((0, 1, 2, 1), 16, (4, 2, None)),
    ((0, 512, 512, 1), 16, (524288, 262144, None)),
    ((0, 512, 512, 3), 16, (1572864, 786432, 1048576)),
    ((0, 0, 0, 0), 32, (0, 0, None)),
    ((0, 1, 1, 1), 32, (4, 1, None)),  # 32 bit data can't be odd length
    ((0, 1, 2, 1), 32, (8, 2, None)),
    ((0, 512, 512, 1), 32, (1048576, 262144, None)),
    ((0, 512, 512, 3), 32, (3145728, 786432, 2097152)),
    # NumberOfFrames odd
    ((3, 0, 0, 0), 1, (0, 0, None)),
    ((3, 1, 1, 1), 1, (1, 3, None)),
    ((3, 1, 1, 3), 1, (2, 9, None)),
    ((3, 1, 3, 3), 1, (4, 27, None)),
    ((3, 2, 4, 1), 1, (3, 24, None)),
    ((3, 2, 2, 1), 1, (2, 12, None)),
    ((3, 3, 3, 1), 1, (4, 27, None)),
    ((3, 512, 512, 1), 1, (98304, 786432, None)),
    ((3, 512, 512, 3), 1, (294912, 2359296, 196608)),
    ((3, 0, 0, 0), 8, (0, 0, None)),
    ((3, 1, 1, 1), 8, (3, 3, None)),
    ((3, 9, 1, 1), 8, (27, 27, None)),
    ((3, 1, 2, 1), 8, (6, 6, None)),
    ((3, 512, 512, 1), 8, (786432, 786432, None)),
    ((3, 512, 512, 3), 8, (2359296, 2359296, 1572864)),
    ((3, 0, 0, 0), 16, (0, 0, None)),
    ((3, 512, 512, 1), 16, (1572864, 786432, None)),
    ((3, 512, 512, 3), 16, (4718592, 2359296, 3145728)),
    ((3, 0, 0, 0), 32, (0, 0, None)),
    ((3, 512, 512, 1), 32, (3145728, 786432, None)),
    ((3, 512, 512, 3), 32, (9437184, 2359296, 6291456)),
    # NumberOfFrames even
    ((4, 0, 0, 0), 1, (0, 0, None)),
    ((4, 1, 1, 1), 1, (1, 4, None)),
    ((4, 1, 1, 3), 1, (2, 12, None)),
    ((4, 1, 3, 3), 1, (5, 36, None)),
    ((4, 2, 4, 1), 1, (4, 32, None)),
    ((4, 2, 2, 1), 1, (2, 16, None)),
    ((4, 3, 3, 1), 1, (5, 36, None)),
    ((4, 512, 512, 1), 1, (131072, 1048576, None)),
    ((4, 512, 512, 3), 1, (393216, 3145728, 262144)),
    ((4, 0, 0, 0), 8, (0, 0, None)),
    ((4, 512, 512, 1), 8, (1048576, 1048576, None)),
    ((4, 512, 512, 3), 8, (3145728, 3145728, 2097152)),
    ((4, 0, 0, 0), 16, (0, 0, None)),
    ((4, 512, 512, 1), 16, (2097152, 1048576, None)),
    ((4, 512, 512, 3), 16, (6291456, 3145728, 4194304)),
    ((4, 0, 0, 0), 32, (0, 0, None)),
    ((4, 512, 512, 1), 32, (4194304, 1048576, None)),
    ((4, 512, 512, 3), 32, (12582912, 3145728, 8388608)),
]


class TestGetExpectedLength:
    """Tests for get_expected_length()."""

    @pytest.mark.parametrize("shape, bits, length", REFERENCE_LENGTH)
    def test_length_in_bytes(self, shape, bits, length):
        """Test get_expected_length(ds, unit='bytes')."""
        ds = Dataset()
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.Rows = shape[1]
        ds.Columns = shape[2]
        ds.BitsAllocated = bits
        if shape[0] != 0:
            ds.NumberOfFrames = shape[0]
        ds.SamplesPerPixel = shape[3]

        assert length[0] == get_expected_length(ds, unit="bytes")

    @pytest.mark.parametrize("shape, bits, length", REFERENCE_LENGTH)
    def test_length_in_pixels(self, shape, bits, length):
        """Test get_expected_length(ds, unit='pixels')."""
        ds = Dataset()
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.Rows = shape[1]
        ds.Columns = shape[2]
        ds.BitsAllocated = bits
        if shape[0] != 0:
            ds.NumberOfFrames = shape[0]
        ds.SamplesPerPixel = shape[3]

        assert length[1] == get_expected_length(ds, unit="pixels")

    @pytest.mark.parametrize("shape, bits, length", REFERENCE_LENGTH)
    def test_length_ybr_422(self, shape, bits, length):
        """Test get_expected_length for YBR_FULL_422."""
        if shape[3] != 3 or bits == 1:
            return

        ds = Dataset()
        ds.PhotometricInterpretation = "YBR_FULL_422"
        ds.Rows = shape[1]
        ds.Columns = shape[2]
        ds.BitsAllocated = bits
        if shape[0] != 0:
            ds.NumberOfFrames = shape[0]
        ds.SamplesPerPixel = shape[3]

        assert length[2] == get_expected_length(ds, unit="bytes")


class TestGetJ2KParameters:
    """Tests for get_j2k_parameters()."""

    def test_precision(self):
        """Test getting the precision for a JPEG2K bytestream."""
        base = b"\xff\x4f\xff\x51" + b"\x00" * 38
        # Signed
        for ii in range(135, 144):
            params = get_j2k_parameters(base + bytes([ii]))
            assert ii - 127 == params["precision"]
            assert params["is_signed"]
            assert params["jp2"] is False

        # Unsigned
        for ii in range(7, 16):
            params = get_j2k_parameters(base + bytes([ii]))
            assert ii + 1 == params["precision"]
            assert not params["is_signed"]
            assert params["jp2"] is False

    def test_not_j2k(self):
        """Test result when no JPEG2K SOF marker present"""
        base = b"\xff\x4e\xff\x51" + b"\x00" * 38
        assert {} == get_j2k_parameters(base + b"\x8F")

    def test_no_siz(self):
        """Test result when no SIZ box present"""
        base = b"\xff\x4f\xff\x52" + b"\x00" * 38
        assert {} == get_j2k_parameters(base + b"\x8F")

    def test_short_bytestream(self):
        """Test result when no SIZ box present"""
        assert {} == get_j2k_parameters(b"")
        assert {} == get_j2k_parameters(b"\xff\x4f\xff\x51" + b"\x00" * 20)

    def test_jp2(self):
        """Test result when JP2 file format is used."""
        ds = J2KR_08_08_3_0_1F_YBR_RCT.ds
        info = get_j2k_parameters(get_frame(ds.PixelData, 0))
        assert info["precision"] == 8
        assert info["is_signed"] is False
        assert info["jp2"] is True


class TestGetNrFrames:
    """Tests for get_nr_frames()."""

    def test_none(self):
        """Test warning when (0028,0008) 'Number of Frames' has a value of
        None"""
        ds = Dataset()
        ds.NumberOfFrames = None
        msg = (
            r"A value of None for \(0028,0008\) 'Number of Frames' is "
            r"non-conformant. It's recommended that this value be "
            r"changed to 1"
        )
        with pytest.warns(UserWarning, match=msg):
            assert 1 == get_nr_frames(ds)

    def test_zero(self):
        """Test warning when (0028,0008) 'Number of Frames' has a value of 0"""
        ds = Dataset()
        ds.NumberOfFrames = 0
        msg = (
            r"A value of 0 for \(0028,0008\) 'Number of Frames' is "
            r"non-conformant. It's recommended that this value be "
            r"changed to 1"
        )
        with pytest.warns(UserWarning, match=msg):
            assert 1 == get_nr_frames(ds)

    def test_missing(self):
        """Test return value when (0028,0008) 'Number of Frames' does not
        exist"""
        ds = Dataset()
        with assert_no_warning():
            assert 1 == get_nr_frames(ds)

    def test_existing(self):
        """Test return value when (0028,0008) 'Number of Frames' exists."""
        ds = Dataset()
        ds.NumberOfFrames = random.randint(1, 10)
        with assert_no_warning():
            assert ds.NumberOfFrames == get_nr_frames(ds)


REFERENCE_PACK_UNPACK = [
    (b"", []),
    (b"\x00", [0, 0, 0, 0, 0, 0, 0, 0]),
    (b"\x01", [1, 0, 0, 0, 0, 0, 0, 0]),
    (b"\x02", [0, 1, 0, 0, 0, 0, 0, 0]),
    (b"\x04", [0, 0, 1, 0, 0, 0, 0, 0]),
    (b"\x08", [0, 0, 0, 1, 0, 0, 0, 0]),
    (b"\x10", [0, 0, 0, 0, 1, 0, 0, 0]),
    (b"\x20", [0, 0, 0, 0, 0, 1, 0, 0]),
    (b"\x40", [0, 0, 0, 0, 0, 0, 1, 0]),
    (b"\x80", [0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\xAA", [0, 1, 0, 1, 0, 1, 0, 1]),
    (b"\xF0", [0, 0, 0, 0, 1, 1, 1, 1]),
    (b"\x0F", [1, 1, 1, 1, 0, 0, 0, 0]),
    (b"\xFF", [1, 1, 1, 1, 1, 1, 1, 1]),
    #              | 1st byte              | 2nd byte
    (b"\x00\x00", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
    (b"\x00\x01", [0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0]),
    (b"\x00\x80", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\x00\xFF", [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1]),
    (b"\x01\x80", [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\x80\x80", [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\xFF\x80", [1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 1]),
]


class TestUnpackBits:
    """Tests for unpack_bits()."""

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
    @pytest.mark.parametrize("src, output", REFERENCE_PACK_UNPACK)
    def test_unpack_np(self, src, output):
        """Test unpacking data using numpy."""
        assert np.array_equal(unpack_bits(src, as_array=True), np.asarray(output))

        as_bytes = pack(f"{len(output)}B", *output)
        assert unpack_bits(src, as_array=False) == as_bytes

    @pytest.mark.skipif(HAVE_NP, reason="Numpy is available")
    @pytest.mark.parametrize("src, output", REFERENCE_PACK_UNPACK)
    def test_unpack_bytes(self, src, output):
        """Test unpacking data without numpy."""
        as_bytes = pack(f"{len(output)}B", *output)
        assert unpack_bits(src, as_array=False) == as_bytes

        msg = r"unpack_bits\(\) requires NumPy if 'as_array = True'"
        with pytest.raises(ValueError, match=msg):
            unpack_bits(src, as_array=True)


REFERENCE_PACK_PARTIAL = [
    #              | 1st byte              | 2nd byte
    (b"\x00\x40", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),  # 15-bits
    (b"\x00\x20", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\x00\x10", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\x00\x08", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\x00\x04", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\x00\x02", [0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\x00\x01", [0, 0, 0, 0, 0, 0, 0, 0, 1]),  # 9-bits
    (b"\x80", [0, 0, 0, 0, 0, 0, 0, 1]),  # 8-bits
    (b"\x40", [0, 0, 0, 0, 0, 0, 1]),
    (b"\x20", [0, 0, 0, 0, 0, 1]),
    (b"\x10", [0, 0, 0, 0, 1]),
    (b"\x08", [0, 0, 0, 1]),
    (b"\x04", [0, 0, 1]),
    (b"\x02", [0, 1]),
    (b"\x01", [1]),
    (b"", []),
]


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestPackBits:
    """Tests for pack_bits()."""

    @pytest.mark.parametrize("output, input", REFERENCE_PACK_UNPACK)
    def test_pack(self, input, output):
        """Test packing data."""
        assert output == pack_bits(np.asarray(input), pad=False)

    def test_non_binary_input(self):
        """Test non-binary input raises exception."""
        with pytest.raises(
            ValueError, match=r"Only binary arrays \(containing ones or"
        ):
            pack_bits(np.asarray([0, 0, 2, 0, 0, 0, 0, 0]))

    def test_ndarray_input(self):
        """Test non 1D input gets ravelled."""
        arr = np.asarray(
            [
                [0, 0, 0, 0, 0, 0, 0, 0],
                [1, 0, 1, 0, 1, 0, 1, 0],
                [1, 1, 1, 1, 1, 1, 1, 1],
            ]
        )
        assert (3, 8) == arr.shape
        b = pack_bits(arr, pad=False)
        assert b"\x00\x55\xff" == b

    def test_padding(self):
        """Test odd length packed data is padded."""
        arr = np.asarray(
            [
                [0, 0, 0, 0, 0, 0, 0, 0],
                [1, 0, 1, 0, 1, 0, 1, 0],
                [1, 1, 1, 1, 1, 1, 1, 1],
            ]
        )
        assert 3 == len(pack_bits(arr, pad=False))
        b = pack_bits(arr, pad=True)
        assert 4 == len(b)
        assert 0 == b[-1]

    @pytest.mark.parametrize("output, input", REFERENCE_PACK_PARTIAL)
    def test_pack_partial(self, input, output):
        """Test packing data that isn't a full byte long."""
        assert output == pack_bits(np.asarray(input), pad=False)

    def test_functional(self):
        """Test against a real dataset."""
        ds = EXPL_1_1_3F.ds
        arr = ds.pixel_array
        arr = arr.ravel()
        assert ds.PixelData == pack_bits(arr)


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestExpandYBR422:
    """Tests for expand_ybr422()."""

    def test_8bit(self):
        """Test 8-bit expansion."""
        ds = EXPL_8_3_1F_YBR422.ds
        assert ds.PhotometricInterpretation == "YBR_FULL_422"
        ds.pixel_array_options(as_rgb=False)
        ref = ds.pixel_array

        expanded = expand_ybr422(ds.PixelData, ds.BitsAllocated)
        arr = np.frombuffer(expanded, dtype="u1")
        assert np.array_equal(arr, ref.ravel())

    def test_16bit(self):
        """Test 16-bit expansion."""
        # Have to make our own 16-bit data
        ds = EXPL_8_3_1F_YBR422.ds
        ref = ds.pixel_array.astype("float32")
        ref *= 65535 / 255
        ref = ref.astype("u2")
        # Subsample
        # YY BB RR YY BB RR YY BB RR YY BB RR -> YY YY BB RR YY YY BB RR
        src = bytearray(ref.tobytes())
        del src[2::12]
        del src[2::11]
        del src[2::10]
        del src[2::9]

        # Should be 2/3rds of the original number of bytes
        nr_bytes = ds.Rows * ds.Columns * ds.SamplesPerPixel * 2
        assert len(src) == nr_bytes * 2 // 3
        arr = np.frombuffer(expand_ybr422(src, 16), "u2")
        assert np.array_equal(arr, ref.ravel())
        # Spot check values
        arr = arr.reshape(100, 100, 3)
        assert (19532, 21845, 65535) == tuple(arr[5, 50, :])
        assert (42662, 27242, 49601) == tuple(arr[15, 50, :])


class TestCompressRLE:
    """Tests for compress() with RLE Lossless"""

    def test_compress(self):
        """Test compressing a dataset."""
        ds = dcmread(EXPL_16_16_1F.path)
        assert not ds["PixelData"].is_undefined_length
        assert ds["PixelData"].VR == "OW"
        compress(ds, RLELossless, encoding_plugin="pydicom")

        assert ds.SamplesPerPixel == 1
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert len(ds.PixelData) == 21370
        assert "PlanarConfiguration" not in ds
        assert ds["PixelData"].is_undefined_length
        assert ds["PixelData"].VR == "OB"

        assert ds._pixel_array is None
        assert ds._pixel_id == {}

    def test_no_file_meta_raises(self):
        """Test compressing a dataset with no file meta."""
        ds = dcmread(EXPL_16_16_1F.path)
        assert ds["PixelData"].VR == "OW"
        del ds.file_meta

        msg = (
            "Unable to determine the initial compression state of the dataset as "
            r"there's no \(0002,0010\) 'Transfer Syntax UID' element in the dataset's "
            "'file_meta' attribute"
        )
        with pytest.raises(AttributeError, match=msg):
            compress(ds, RLELossless, encoding_plugin="pydicom")

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_already_compressed(self):
        """Test compressing an already compressed dataset."""
        ds = dcmread(RLE_8_3_1F.path)
        arr = ds.pixel_array
        ds.file_meta.TransferSyntaxUID = JPEG2000

        msg = "Only uncompressed datasets may be compressed"
        with pytest.raises(ValueError, match=msg):
            compress(ds, RLELossless, encoding_plugin="pydicom")

        # Skip compression state check if passing arr
        compress(ds, RLELossless, arr, encoding_plugin="pydicom")
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert ds["PixelData"].is_undefined_length
        assert ds["PixelData"].VR == "OB"

        assert ds._pixel_array is None
        assert ds._pixel_id == {}

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_compress_arr(self):
        """Test compressing using pixel data from an arr."""
        ds = dcmread(EXPL_16_16_1F.path)
        assert hasattr(ds, "file_meta")
        arr = ds.pixel_array
        del ds.PixelData
        del ds.file_meta

        compress(ds, RLELossless, arr, encoding_plugin="pydicom")
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert len(ds.PixelData) == 21370

        assert ds._pixel_array is None
        assert ds._pixel_id == {}

    @pytest.mark.skipif(HAVE_NP, reason="Numpy is available")
    def test_encoder_unavailable(self, monkeypatch):
        """Test the required encoder being unavailable."""
        ds = dcmread(EXPL_16_16_1F.path)
        monkeypatch.delitem(RLELosslessEncoder._available, "pydicom")
        msg = (
            r"The pixel data encoder for 'RLE Lossless' is unavailable because "
            r"all of its plugins are missing dependencies:\n"
            r"    gdcm - requires gdcm>=3.0.10\n"
            r"    pylibjpeg - requires numpy, pylibjpeg>=2.0 and pylibjpeg-rle>=2.0"
        )
        with pytest.raises(RuntimeError, match=msg):
            compress(ds, RLELossless)

    def test_uid_not_supported(self):
        """Test the UID not having any encoders."""
        ds = dcmread(EXPL_16_16_1F.path)

        msg = (
            r"No pixel data encoders have been implemented for "
            r"'JPEG 2000 Part 2 Multi-component Image Compression'"
        )
        with pytest.raises(NotImplementedError, match=msg):
            compress(ds, JPEG2000MC, encoding_plugin="pydicom")

    def test_encapsulate_extended(self):
        """Test forcing extended encapsulation."""
        ds = dcmread(EXPL_16_16_1F.path)
        assert "ExtendedOffsetTable" not in ds
        assert "ExtendedOffsetTableLengths" not in ds

        compress(ds, RLELossless, encapsulate_ext=True, encoding_plugin="pydicom")
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        assert len(ds.PixelData) == 21366
        assert ds.ExtendedOffsetTable == b"\x00" * 8
        assert ds.ExtendedOffsetTableLengths == b"\x66\x53" + b"\x00" * 6

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_round_trip(self):
        """Test an encoding round-trip"""
        ds = dcmread(RLE_16_1_1F.path)
        arr = ds.pixel_array
        # Setting PixelData to None frees the memory which may
        #   sometimes be reused, causes the _pixel_id check to fail
        ds.PixelData = None
        ds._pixel_array = None
        compress(ds, RLELossless, arr, encoding_plugin="pydicom")
        assert ds.PixelData is not None
        assert np.array_equal(arr, ds.pixel_array)

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_cant_override_kwargs(self):
        """Test we can't override using kwargs."""
        ds = dcmread(EXPL_8_3_1F_ODD.path)
        ref = ds.pixel_array
        assert ds.SamplesPerPixel == 3
        compress(
            ds,
            RLELossless,
            encoding_plugin="pydicom",
            samples_per_pixel=1,
        )

        assert np.array_equal(ref, ds.pixel_array)

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_instance_uid(self):
        """Test generating new SOP Instance UID."""
        ds = dcmread(EXPL_16_16_1F.path)
        original = ds.SOPInstanceUID

        compress(ds, RLELossless, encoding_plugin="pydicom", generate_instance_uid=True)
        assert ds.SOPInstanceUID != original
        assert ds.SOPInstanceUID == ds.file_meta.MediaStorageSOPInstanceUID

        ds = dcmread(EXPL_16_16_1F.path)
        compress(
            ds, RLELossless, encoding_plugin="pydicom", generate_instance_uid=False
        )
        assert ds.SOPInstanceUID == original
        assert ds.SOPInstanceUID == ds.file_meta.MediaStorageSOPInstanceUID


@pytest.mark.skipif(SKIP_JLS, reason="JPEG-LS plugins unavailable")
class TestCompressJLS:
    """Tests for compress() with JPEG-LS"""

    def test_lossless(self):
        """Test JPEG-LS Lossless."""
        ds = dcmread(EXPL_16_16_1F.path)
        ref = ds.pixel_array
        compress(ds, JPEGLSLossless, encoding_plugin="pyjpegls")

        assert ds.file_meta.TransferSyntaxUID == JPEGLSLossless
        frame = get_frame(ds.PixelData, 0)
        info = _get_jpg_parameters(frame)
        assert info["lossy_error"] == 0

        assert np.array_equal(ds.pixel_array, ref)

    def test_lossy(self):
        """Test JPEG-LS Near Lossless and the jls_error kwarg."""
        ds = dcmread(EXPL_16_16_1F.path)
        ref = ds.pixel_array
        compress(ds, JPEGLSNearLossless, jls_error=3, encoding_plugin="pyjpegls")

        assert ds.file_meta.TransferSyntaxUID == JPEGLSNearLossless
        frame = get_frame(ds.PixelData, 0)
        info = _get_jpg_parameters(frame)
        assert info["lossy_error"] == 3

        assert np.allclose(ds.pixel_array, ref, atol=3)


@pytest.mark.skipif(SKIP_J2K, reason="JPEG 2000 plugins unavailable")
class TestCompressJ2K:
    """Tests for compress() with JPEG 2000"""

    def test_lossless(self):
        """Test JPEG 2000 Lossless."""
        ds = dcmread(EXPL_16_16_1F.path)
        ref = ds.pixel_array
        compress(ds, JPEG2000Lossless, encoding_plugin="pylibjpeg")
        assert ds.file_meta.TransferSyntaxUID == JPEG2000Lossless
        assert np.array_equal(ds.pixel_array, ref)

    def test_lossy(self):
        """Test JPEG 2000 and the j2k_cr and j2k_psnr kwargs."""
        ds = dcmread(EXPL_16_16_1F.path)
        ref = ds.pixel_array
        compress(ds, JPEG2000, j2k_cr=[2], encoding_plugin="pylibjpeg")
        assert ds.file_meta.TransferSyntaxUID == JPEG2000
        out = ds.pixel_array
        assert not np.array_equal(out, ref)
        assert np.allclose(out, ref, atol=2)

        ds = dcmread(EXPL_16_16_1F.path)
        ref = ds.pixel_array
        compress(ds, JPEG2000, j2k_psnr=[100], encoding_plugin="pylibjpeg")
        assert ds.file_meta.TransferSyntaxUID == JPEG2000
        out = ds.pixel_array
        assert not np.array_equal(out, ref)
        assert np.allclose(out, ref, atol=3)


@pytest.fixture()
def add_dummy_decoder():
    """Add a dummy decoder to the pixel data decoders"""

    class DummyDecoder:
        is_available = True

        def iter_array(self, ds, **kwargs):
            # Yield a total of 2**32 bytes
            arr = np.frombuffer(b"\x00" * 2**20, dtype="u1")
            for _ in range(2**12):
                yield arr, {}

    _PIXEL_DATA_DECODERS["1.2.3.4"] = [DummyDecoder()]
    yield
    del _PIXEL_DATA_DECODERS["1.2.3.4"]


class TestDecompress:
    """Tests for decompress()"""

    def test_no_file_meta_raises(self):
        """Test exception raised if no file meta or transfer syntax."""
        ds = dcmread(EXPL_16_16_1F.path)
        del ds.file_meta.TransferSyntaxUID

        msg = (
            "Unable to determine the initial compression state as there's no "
            r"\(0002,0010\) 'Transfer Syntax UID' element in the dataset's 'file_meta' "
            "attribute"
        )
        with pytest.raises(AttributeError, match=msg):
            decompress(ds)

        del ds.file_meta
        with pytest.raises(AttributeError, match=msg):
            decompress(ds)

    def test_no_pixel_data_raises(self):
        """Test exception raised if no pixel data."""
        ds = dcmread(EXPL_16_16_1F.path)
        del ds.PixelData

        msg = (
            r"Unable to decompress as the dataset has no \(7FE0,0010\) 'Pixel "
            "Data' element"
        )
        with pytest.raises(AttributeError, match=msg):
            decompress(ds)

    def test_uncompressed_raises(self):
        """Test exception raised if already uncompressed."""
        ds = dcmread(EXPL_16_16_1F.path)
        msg = "The dataset is already uncompressed"
        with pytest.raises(ValueError, match=msg):
            decompress(ds)

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy is unavailable")
    def test_too_long_raises(self, add_dummy_decoder):
        """Test too much uncompressed data raises"""
        ds = dcmread(RLE_8_3_1F.path)
        uid = UID("1.2.3.4")
        uid.set_private_encoding(False, True)
        ds.file_meta.TransferSyntaxUID = uid

        msg = (
            "Unable to decompress as the length of the uncompressed pixel data "
            "will be greater than the maximum allowed by the DICOM Standard"
        )
        with pytest.raises(ValueError, match=msg):
            decompress(ds)

    @pytest.mark.skipif(SKIP_RLE, reason="RLE plugins unavailable")
    def test_rle_8_1f_3s(self):
        """Test decoding RLE Lossless - 1 frame, 3 sample (RGB)"""
        ds = dcmread(RLE_8_3_1F.path)
        ref = ds.pixel_array
        assert ds.BitsAllocated == 8
        assert ds.PhotometricInterpretation == "RGB"
        decompress(ds, decoding_plugin="pydicom")

        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
        elem = ds["PixelData"]
        assert len(elem.value) == ds.Rows * ds.Columns * (ds.BitsAllocated // 8) * 3
        assert elem.is_undefined_length is False
        assert elem.VR == "OB"
        assert "NumberOfFrames" not in ds
        assert ds.PlanarConfiguration == 0
        assert ds.PhotometricInterpretation == "RGB"
        assert ds._pixel_array is None
        assert ds._pixel_id == {}

        assert np.array_equal(ds.pixel_array, ref)

    @pytest.mark.skipif(SKIP_RLE, reason="RLE plugins unavailable")
    def test_rle_16_1f_1s(self):
        """Test decoding RLE Lossless - 1 frame, 1 sample"""
        ds = dcmread(RLE_16_1_1F.path)
        ref = ds.pixel_array
        assert ds.BitsAllocated == 16
        decompress(ds, decoding_plugin="pydicom")

        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
        elem = ds["PixelData"]
        assert len(elem.value) == ds.Rows * ds.Columns * (ds.BitsAllocated // 8)
        assert elem.is_undefined_length is False
        assert elem.VR == "OW"
        assert "NumberOfFrames" not in ds
        assert "PlanarConfiguration" not in ds
        assert ds._pixel_array is None
        assert ds._pixel_id == {}

        assert np.array_equal(ds.pixel_array, ref)

    @pytest.mark.skipif(SKIP_RLE, reason="RLE plugins unavailable")
    def test_rle_16_10f_1s(self):
        """Test decoding RLE Lossless - 10 frame, 1 sample"""
        ds = dcmread(RLE_16_1_10F.path)
        ref = ds.pixel_array
        assert ds.BitsAllocated == 16
        assert ds.NumberOfFrames == 10
        # `index` should be ignored
        decompress(ds, decoding_plugin="pydicom", index=1)

        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
        elem = ds["PixelData"]
        assert len(elem.value) == (
            ds.Rows * ds.Columns * (ds.BitsAllocated // 8) * ds.NumberOfFrames
        )
        assert elem.is_undefined_length is False
        assert elem.VR == "OW"
        assert "PlanarConfiguration" not in ds
        assert ds.NumberOfFrames == 10
        assert ds._pixel_array is None
        assert ds._pixel_id == {}

        assert np.array_equal(ds.pixel_array, ref)

    @pytest.mark.skipif(SKIP_RLE, reason="RLE plugins unavailable")
    def test_rle_32_2f_3s(self):
        """Test decoding RLE Lossless - 2 frame, 3 sample (RGB)"""
        ds = dcmread(RLE_32_3_2F.path)
        ref = ds.pixel_array
        assert ds.BitsAllocated == 32
        assert ds.NumberOfFrames == 2
        assert ds.PhotometricInterpretation == "RGB"
        decompress(ds, decoding_plugin="pydicom")

        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
        elem = ds["PixelData"]
        assert len(elem.value) == (
            ds.Rows * ds.Columns * (ds.BitsAllocated // 8) * ds.NumberOfFrames * 3
        )
        assert elem.is_undefined_length is False
        assert elem.VR == "OW"
        assert ds.PlanarConfiguration == 0
        assert ds.PhotometricInterpretation == "RGB"
        assert ds.NumberOfFrames == 2
        assert ds._pixel_array is None
        assert ds._pixel_id == {}

        assert np.array_equal(ds.pixel_array, ref)

    @pytest.mark.skipif(SKIP_RLE, reason="RLE plugins unavailable")
    def test_odd_length_padded(self):
        """Test odd length Pixel Data gets padded to even length."""
        ds = dcmread(EXPL_8_3_1F_ODD.path)
        assert ds.Rows * ds.Columns * ds.SamplesPerPixel % 2 == 1
        compress(ds, RLELossless, encoding_plugin="pydicom")
        assert ds.file_meta.TransferSyntaxUID == RLELossless
        decompress(ds, decoding_plugin="pydicom")
        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
        assert len(ds.PixelData) % 2 == 0

    @pytest.mark.skipif(not SKIP_J2K, reason="J2K plugin available")
    def test_no_decoders_raises(self):
        """Test exception raised if no decoders are available."""
        ds = dcmread(J2KR_08_08_3_0_1F_YBR_RCT.path)
        msg = (
            "Unable to decompress as the plugins for the 'JPEG 2000 Image "
            r"Compression \(Lossless Only\)' decoder are all missing dependencies:"
        )
        with pytest.raises(RuntimeError, match=msg):
            decompress(ds, decoding_plugin="pylibjpeg")

    @pytest.mark.skipif(SKIP_J2K, reason="J2K plugins unavailable")
    def test_j2k_ybr_rct(self):
        """Test decoding J2K YBR_RCT -> RGB"""
        ds = dcmread(J2KR_08_08_3_0_1F_YBR_RCT.path)
        ref = ds.pixel_array
        assert ds.BitsAllocated == 8
        assert ds.PhotometricInterpretation == "YBR_RCT"
        # as_rgb will be ignored if YBR_RCT or YBR_ICT
        decompress(ds, decoding_plugin="pylibjpeg", as_rgb=False)

        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
        elem = ds["PixelData"]
        assert len(elem.value) == ds.Rows * ds.Columns * (ds.BitsAllocated // 8) * 3
        assert elem.is_undefined_length is False
        assert elem.VR == "OB"
        assert "NumberOfFrames" not in ds
        assert ds.PlanarConfiguration == 0
        assert ds.PhotometricInterpretation == "RGB"
        assert ds._pixel_array is None
        assert ds._pixel_id == {}

        assert np.array_equal(ds.pixel_array, ref)

    @pytest.mark.skipif(SKIP_JPG, reason="JPEG plugins unavailable")
    def test_as_rgb(self):
        """Test decoding J2K - 1 frame, 3 sample (YBR_RCT)"""
        ds = dcmread(JPGB_08_08_3_1F_YBR_FULL.path)
        ds.pixel_array_options(decoding_plugin="pylibjpeg")
        ref = ds.pixel_array  # YBR -> RGB

        assert ds.BitsAllocated == 8
        assert ds.PhotometricInterpretation == "YBR_FULL"
        decompress(ds, decoding_plugin="pylibjpeg", as_rgb=True)

        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
        elem = ds["PixelData"]
        assert len(elem.value) == ds.Rows * ds.Columns * (ds.BitsAllocated // 8) * 3
        assert elem.is_undefined_length is False
        assert elem.VR == "OB"
        assert "NumberOfFrames" not in ds
        assert ds.PlanarConfiguration == 0
        assert ds.PhotometricInterpretation == "RGB"
        assert ds._pixel_array is None
        assert ds._pixel_id == {}
        assert np.array_equal(ds.pixel_array, ref)

        ds = dcmread(JPGB_08_08_3_1F_YBR_FULL.path)
        decompress(ds, decoding_plugin="pylibjpeg", as_rgb=False)
        assert ds.PhotometricInterpretation == "YBR_FULL"
        ds.pixel_array_options(as_rgb=False)
        rgb = convert_color_space(ds.pixel_array, "YBR_FULL", "RGB")
        assert np.array_equal(rgb, ref)

    @pytest.mark.skipif(SKIP_RLE, reason="RLE plugins unavailable")
    def test_instance_uid(self):
        """Test generating new SOP Instance UID."""
        ds = dcmread(RLE_8_3_1F.path)
        original = ds.SOPInstanceUID

        decompress(ds, decoding_plugin="pydicom", generate_instance_uid=True)
        assert ds.SOPInstanceUID != original
        assert ds.SOPInstanceUID == ds.file_meta.MediaStorageSOPInstanceUID

        ds = dcmread(RLE_8_3_1F.path)
        decompress(ds, decoding_plugin="pydicom", generate_instance_uid=False)
        assert ds.SOPInstanceUID == original
        assert ds.SOPInstanceUID == ds.file_meta.MediaStorageSOPInstanceUID


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestSetPixelData:
    """Tests for set_pixel_data()"""

    def test_float_pixel_data_raises(self):
        """Test exception raised if float pixel data elements present"""
        ds = Dataset()
        ds.FloatPixelData = b"\x00\x00"
        arr = np.zeros((10, 10), dtype="uint8")

        msg = (
            r"The dataset has an existing \(7FE0,0008\) 'Float Pixel Data' element "
            r"which indicates the \(0008,0016\) 'SOP Class UID' value is not suitable "
            "for a dataset with 'Pixel Data'. The 'Float Pixel Data' element should "
            "be deleted and the 'SOP Class UID' changed."
        )
        with pytest.raises(AttributeError, match=msg):
            set_pixel_data(ds, arr, "MONOCHROME1", 8)

        del ds.FloatPixelData
        ds.DoubleFloatPixelData = b"\x00\x00"

        msg = r"The dataset has an existing \(7FE0,0009\) 'Double Float Pixel Data'"
        with pytest.raises(AttributeError, match=msg):
            set_pixel_data(ds, arr, "MONOCHROME1", 8)

    def test_unsupported_dtype_raises(self):
        """Test exception raised if dtype is unsupported"""

        msg = (
            r"Unsupported ndarray dtype 'uint32', must be int8, int16, uint8 or uint16"
        )
        with pytest.raises(ValueError, match=msg):
            set_pixel_data(
                Dataset(), np.zeros((10, 10), dtype="uint32"), "MONOCHROME1", 8
            )

        msg = (
            r"Unsupported ndarray dtype 'float32', must be int8, int16, uint8 or uint16"
        )
        with pytest.raises(ValueError, match=msg):
            set_pixel_data(
                Dataset(), np.zeros((10, 10), dtype="float32"), "MONOCHROME1", 8
            )

    def test_unsupported_photometric_interpretation_raises(self):
        """Test exception raised if dtype is unsupported"""

        msg = "Unsupported 'photometric_interpretation' value 'YBR_RCT'"
        with pytest.raises(ValueError, match=msg):
            set_pixel_data(Dataset(), np.zeros((10, 10), dtype="int8"), "YBR_RCT", 8)

    def test_unsupported_dimension_raises(self):
        """Test exception raised if array dimensions are unsupported"""

        msg = "An ndarray with 'MONOCHROME1' data must have 2 or 3 dimensions, not 4"
        with pytest.raises(ValueError, match=msg):
            set_pixel_data(
                Dataset(), np.zeros((2, 10, 10, 3), dtype="int8"), "MONOCHROME1", 8
            )

        msg = "An ndarray with 'RGB' data must have 3 or 4 dimensions, not 2"
        with pytest.raises(ValueError, match=msg):
            set_pixel_data(Dataset(), np.zeros((10, 10), dtype="int8"), "RGB", 8)

    def test_invalid_samples_raises(self):
        """Test mismatch between array shape and photometric interpretation raises"""
        msg = (
            r"An ndarray with 'RGB' data must have shape \(rows, columns, 3\) or "
            r"\(frames, rows, columns, 3\), not \(10, 10, 10\)"
        )
        with pytest.raises(ValueError, match=msg):
            set_pixel_data(Dataset(), np.zeros((10, 10, 10), dtype="int8"), "RGB", 8)

    def test_invalid_bits_stored_raises(self):
        """Test bits_stored outside [1, 16] raises an exception"""
        msg = (
            "Invalid 'bits_stored' value '0', must be greater than 0 and "
            "less than or equal to the number of bits for the ndarray's itemsize "
            "'8'"
        )
        with pytest.raises(ValueError, match=msg):
            set_pixel_data(Dataset(), np.ones((3, 3), dtype="u1"), "MONOCHROME1", 0)

        msg = (
            "Invalid 'bits_stored' value '9', must be greater than 0 and "
            "less than or equal to the number of bits for the ndarray's itemsize "
            "'8'"
        )
        with pytest.raises(ValueError, match=msg):
            set_pixel_data(Dataset(), np.ones((3, 3), dtype="u1"), "MONOCHROME1", 9)

        msg = (
            "Invalid 'bits_stored' value '0', must be greater than 0 and "
            "less than or equal to the number of bits for the ndarray's itemsize "
            "'16'"
        )
        with pytest.raises(ValueError, match=msg):
            set_pixel_data(Dataset(), np.ones((3, 3), dtype="u2"), "MONOCHROME1", 0)

        msg = (
            "Invalid 'bits_stored' value '17', must be greater than 0 and "
            "less than or equal to the number of bits for the ndarray's itemsize "
            "'16'"
        )
        with pytest.raises(ValueError, match=msg):
            set_pixel_data(Dataset(), np.ones((3, 3), dtype="u2"), "MONOCHROME1", 17)

    def test_invalid_arr_range_raises(self):
        """Test the range of values in the array matches bits_stored"""
        arr = np.zeros((10, 10), dtype="uint8")
        # The array will overflow 256 -> 0 if bits_stored 8
        for bits_stored in range(1, 8):
            amin, amax = 0, 2**bits_stored - 1
            arr[0, 0] = amax + 1

            msg = (
                rf"The range of values in the ndarray \[0, {amax + 1}\] is "
                r"greater than that allowed by the 'bits_stored' value \[0, "
                rf"{amax}\]"
            )
            with pytest.raises(ValueError, match=msg):
                set_pixel_data(Dataset(), arr, "MONOCHROME1", bits_stored)

        arr = np.zeros((10, 10), dtype="uint16")
        for bits_stored in range(1, 16):
            amin, amax = 0, 2**bits_stored - 1
            arr[0, 0] = amax + 1

            msg = (
                rf"The range of values in the ndarray \[0, {amax + 1}\] is "
                r"greater than that allowed by the 'bits_stored' value \[0, "
                rf"{amax}\]"
            )
            with pytest.raises(ValueError, match=msg):
                set_pixel_data(Dataset(), arr, "MONOCHROME1", bits_stored)

        arr = np.zeros((10, 10), dtype="int8")
        for bits_stored in range(1, 8):
            amin, amax = -(2 ** (bits_stored - 1)), 2 ** (bits_stored - 1) - 1
            arr[0, 0] = amax + 1
            arr[0, 1] = amin - 1

            msg = (
                rf"The range of values in the ndarray \[{amin - 1}, {amax + 1}\] is "
                rf"greater than that allowed by the 'bits_stored' value \[{amin}, "
                rf"{amax}\]"
            )
            with pytest.raises(ValueError, match=msg):
                set_pixel_data(Dataset(), arr, "MONOCHROME1", bits_stored)

        arr = np.zeros((10, 10), dtype="int16")
        for bits_stored in range(1, 16):
            amin, amax = -(2 ** (bits_stored - 1)), 2 ** (bits_stored - 1) - 1
            arr[0, 0] = amax + 1
            arr[0, 1] = amin - 1

            msg = (
                rf"The range of values in the ndarray \[{amin - 1}, {amax + 1}\] is "
                rf"greater than that allowed by the 'bits_stored' value \[{amin}, "
                rf"{amax}\]"
            )
            with pytest.raises(ValueError, match=msg):
                set_pixel_data(Dataset(), arr, "MONOCHROME1", bits_stored)

    def test_big_endian_raises(self):
        """Test exception raised if big endian transfer syntax"""
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRBigEndian
        arr = np.zeros((10, 10), dtype="uint8")

        msg = (
            "The dataset's transfer syntax 'Explicit VR Big Endian' is big-endian, "
            "which is not supported"
        )
        with pytest.raises(NotImplementedError, match=msg):
            set_pixel_data(ds, arr, "MONOCHROME1", 8)

    def test_grayscale_8bit_unsigned(self):
        """Test setting unsigned 8-bit grayscale pixel data"""
        ds = Dataset()
        ds.PlanarConfiguration = 1
        ds.NumberOfFrames = 2

        arr = np.zeros((3, 5), dtype="u1")
        arr[0, 0] = 127
        set_pixel_data(ds, arr, "MONOCHROME1", 7)

        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
        assert ds.Rows == 3
        assert ds.Columns == 5
        assert ds.SamplesPerPixel == 1
        assert ds.PhotometricInterpretation == "MONOCHROME1"
        assert ds.PixelRepresentation == 0
        assert ds.BitsAllocated == 8
        assert ds.BitsStored == 7
        assert ds.HighBit == 6
        assert "NumberOfFrames" not in ds
        assert "PlanarConfiguration" not in ds

        elem = ds["PixelData"]
        assert elem.VR == "OB"
        assert len(elem.value) == 16
        assert elem.is_undefined_length is False
        assert ds._pixel_array is None
        assert ds._pixel_id == {}

        assert np.array_equal(ds.pixel_array, arr)

    def test_grayscale_8bit_signed(self):
        """Test setting signed 8-bit grayscale pixel data"""
        ds = Dataset()
        ds.PlanarConfiguration = 1
        ds.NumberOfFrames = 2

        arr = np.zeros((3, 5), dtype="i1")
        arr[0, 0] = 127
        arr[0, 1] = -128
        set_pixel_data(ds, arr, "MONOCHROME1", 8)

        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
        assert ds.Rows == 3
        assert ds.Columns == 5
        assert ds.SamplesPerPixel == 1
        assert ds.PhotometricInterpretation == "MONOCHROME1"
        assert ds.PixelRepresentation == 1
        assert ds.BitsAllocated == 8
        assert ds.BitsStored == 8
        assert ds.HighBit == 7

        elem = ds["PixelData"]
        assert elem.VR == "OB"
        assert len(elem.value) == 16

        assert np.array_equal(ds.pixel_array, arr)

    def test_grayscale_16bit_unsigned(self):
        """Test setting unsigned 16-bit grayscale pixel data"""
        ds = Dataset()
        ds.PlanarConfiguration = 1
        ds.NumberOfFrames = 2

        arr = np.zeros((3, 5), dtype="u2")
        arr[0, 0] = 65535
        set_pixel_data(ds, arr, "MONOCHROME1", 16)

        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
        assert ds.Rows == 3
        assert ds.Columns == 5
        assert ds.SamplesPerPixel == 1
        assert ds.PhotometricInterpretation == "MONOCHROME1"
        assert ds.PixelRepresentation == 0
        assert ds.BitsAllocated == 16
        assert ds.BitsStored == 16
        assert ds.HighBit == 15

        elem = ds["PixelData"]
        assert elem.VR == "OW"
        assert len(elem.value) == 30

        assert np.array_equal(ds.pixel_array, arr)

    def test_grayscale_16bit_signed(self):
        """Test setting signed 16-bit grayscale pixel data"""
        ds = Dataset()
        ds.PlanarConfiguration = 1
        ds.NumberOfFrames = 2

        arr = np.zeros((3, 5), dtype="i2")
        arr[0, 0] = 32767
        arr[0, 1] = -32768
        set_pixel_data(ds, arr, "MONOCHROME1", 16)

        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
        assert ds.Rows == 3
        assert ds.Columns == 5
        assert ds.SamplesPerPixel == 1
        assert ds.PhotometricInterpretation == "MONOCHROME1"
        assert ds.PixelRepresentation == 1
        assert ds.BitsAllocated == 16
        assert ds.BitsStored == 16
        assert ds.HighBit == 15

        elem = ds["PixelData"]
        assert elem.VR == "OW"
        assert len(elem.value) == 30

        assert np.array_equal(ds.pixel_array, arr)

    def test_grayscale_multiframe(self):
        """Test setting multiframe pixel data"""
        ds = Dataset()

        arr = np.zeros((10, 3, 5), dtype="u1")
        arr[0, 0, 0] = 127
        arr[9, 0, 0] = 255
        set_pixel_data(ds, arr, "MONOCHROME1", 8)

        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
        assert ds.Rows == 3
        assert ds.Columns == 5
        assert ds.SamplesPerPixel == 1
        assert ds.PhotometricInterpretation == "MONOCHROME1"
        assert ds.PixelRepresentation == 0
        assert ds.BitsAllocated == 8
        assert ds.BitsStored == 8
        assert ds.HighBit == 7
        assert ds.NumberOfFrames == 10
        assert "PlanarConfiguration" not in ds

        elem = ds["PixelData"]
        assert elem.VR == "OB"
        assert len(elem.value) == 150
        assert elem.is_undefined_length is False

        assert np.array_equal(ds.pixel_array, arr)

    def test_rgb_8bit_unsigned(self):
        """Test setting unsigned 8-bit RGB pixel data"""
        ds = Dataset()
        ds.NumberOfFrames = 2

        arr = np.zeros((3, 5, 3), dtype="u1")
        arr[0, 0] = [127, 255, 0]
        set_pixel_data(ds, arr, "RGB", 8)

        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
        assert ds.Rows == 3
        assert ds.Columns == 5
        assert ds.SamplesPerPixel == 3
        assert ds.PhotometricInterpretation == "RGB"
        assert ds.PixelRepresentation == 0
        assert ds.BitsAllocated == 8
        assert ds.BitsStored == 8
        assert ds.HighBit == 7
        assert ds.PlanarConfiguration == 0
        assert "NumberOfFrames" not in ds

        elem = ds["PixelData"]
        assert elem.VR == "OB"
        assert len(elem.value) == 46

        assert np.array_equal(ds.pixel_array, arr)

    def test_rgb_YBR_FULL_422(self):
        """Test setting multiframe pixel data"""
        ref = dcmread(EXPL_8_3_1F_YBR422.path)
        arr = pixel_array(ref, raw=True)

        ds = Dataset()
        set_pixel_data(ds, arr, "YBR_FULL_422", 8)

        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
        assert ds.Rows == ref.Rows
        assert ds.Columns == ref.Columns
        assert ds.SamplesPerPixel == ref.SamplesPerPixel
        assert ds.PhotometricInterpretation == "YBR_FULL_422"
        assert ds.PixelRepresentation == ref.PixelRepresentation
        assert ds.BitsAllocated == ref.BitsAllocated
        assert ds.BitsStored == ref.BitsStored
        assert ds.HighBit == ref.HighBit
        assert ds.PlanarConfiguration == ref.PlanarConfiguration

        elem = ds["PixelData"]
        assert elem.VR == "OB"
        assert len(elem.value) == (
            ds.Rows * ds.Columns * ds.BitsAllocated // 8 * ds.SamplesPerPixel // 3 * 2
        )
        assert elem.is_undefined_length is False

        assert np.array_equal(pixel_array(ds, raw=True), arr)

    def test_transfer_syntax(self):
        """Test setting the transfer syntax"""
        ds = Dataset()

        set_pixel_data(ds, np.zeros((3, 5, 3), dtype="u1"), "RGB", 8)
        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian

        del ds.file_meta.TransferSyntaxUID

        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        set_pixel_data(ds, np.zeros((3, 5, 3), dtype="u1"), "RGB", 8)
        assert ds.file_meta.TransferSyntaxUID == ImplicitVRLittleEndian

        ds.file_meta.TransferSyntaxUID = JPEG2000Lossless
        set_pixel_data(ds, np.zeros((3, 5, 3), dtype="u1"), "RGB", 8)
        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian

    def test_dataset_set_pixel_data(self):
        """Functionality test for Dataset.set_pixel_data()"""
        ref = dcmread(EXPL_8_3_1F_YBR422.path)
        arr = ref.pixel_array

        ds = Dataset()
        ds.set_pixel_data(arr, "RGB", 8)

        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
        assert ds.Rows == ref.Rows
        assert ds.Columns == ref.Columns
        assert ds.SamplesPerPixel == ref.SamplesPerPixel
        assert ds.PhotometricInterpretation == "RGB"
        assert ds.PixelRepresentation == ref.PixelRepresentation
        assert ds.BitsAllocated == ref.BitsAllocated
        assert ds.BitsStored == ref.BitsStored
        assert ds.HighBit == ref.HighBit
        assert ds.PlanarConfiguration == ref.PlanarConfiguration

        assert np.array_equal(ds.pixel_array, arr)

    def test_sop_instance(self):
        """Test generate_instance_uid kwarg"""
        ds = Dataset()
        ds.SOPInstanceUID = "1.2.3.4"

        set_pixel_data(ds, np.zeros((3, 5, 3), dtype="u1"), "RGB", 8)
        uid = ds.SOPInstanceUID
        assert uid != "1.2.3.4"
        set_pixel_data(
            ds, np.zeros((3, 5, 3), dtype="u1"), "RGB", 8, generate_instance_uid=False
        )
        assert ds.SOPInstanceUID == uid
