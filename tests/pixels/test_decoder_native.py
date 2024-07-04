"""Test decoding native transfer syntaxes."""

import pytest

from pydicom import dcmread
from pydicom.data import get_testdata_file
from pydicom.pixels import get_decoder
from pydicom.pixels.decoders import (
    ImplicitVRLittleEndianDecoder,
    ExplicitVRLittleEndianDecoder,
    ExplicitVRBigEndianDecoder,
    DeflatedExplicitVRLittleEndianDecoder,
)
from pydicom.uid import (
    ImplicitVRLittleEndian,
    ExplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian,
    ExplicitVRBigEndian,
)

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from .pixels_reference import PIXEL_REFERENCE, EXPL_16_1_1F_PAD, IMPL_32_1_1F


def name(ref):
    return f"{ref.name}"


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
class TestAsArray:
    """Tests for decoder.as_array() with native transfer syntaxes"""

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRLittleEndian], ids=name
    )
    def test_reference_expl(self, reference):
        """Test against the reference data for explicit little."""
        decoder = get_decoder(ExplicitVRLittleEndian)
        if reference == EXPL_16_1_1F_PAD:
            msg = (
                "The pixel data is 8320 bytes long, which indicates it contains "
                "128 bytes of excess padding to be removed"
            )
            with pytest.warns(UserWarning, match=msg):
                arr, _ = decoder.as_array(reference.ds, raw=True)
        else:
            arr, _ = decoder.as_array(reference.ds, raw=True)
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        for index in range(reference.number_of_frames):
            if reference == EXPL_16_1_1F_PAD:
                msg = (
                    "The pixel data is 8320 bytes long, which indicates it contains "
                    "128 bytes of excess padding to be removed"
                )
                with pytest.warns(UserWarning, match=msg):
                    arr, _ = decoder.as_array(reference.ds, raw=True)
            else:
                arr, _ = decoder.as_array(reference.ds, raw=True, index=index)
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRLittleEndian], ids=name
    )
    def test_reference_expl_binary(self, reference):
        """Test against the reference data for explicit little for binary IO."""
        decoder = get_decoder(ExplicitVRLittleEndian)
        ds = reference.ds
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": ds.PixelRepresentation,
            "bits_allocated": ds.BitsAllocated,
            "bits_stored": ds.BitsStored,
            "number_of_frames": ds.get("NumberOfFrames", 1),
            "planar_configuration": ds.get("PlanarConfiguration", 0),
            "pixel_keyword": "PixelData",
        }

        with open(reference.path, "rb") as f:
            file_offset = reference.ds["PixelData"].file_tell
            f.seek(file_offset)
            arr, _ = decoder.as_array(f, raw=True, **opts)
            assert f.tell() == file_offset
            reference.test(arr)
            assert arr.shape == reference.shape
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            for index in range(reference.number_of_frames):
                arr, _ = decoder.as_array(f, raw=True, index=index, **opts)
                reference.test(arr, index=index)
                assert arr.dtype == reference.dtype
                assert arr.flags.writeable
                assert f.tell() == file_offset

                if reference.number_of_frames == 1:
                    assert arr.shape == reference.shape
                else:
                    assert arr.shape == reference.shape[1:]

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ImplicitVRLittleEndian], ids=name
    )
    def test_reference_impl(self, reference):
        """Test against the reference data for implicit little."""
        decoder = get_decoder(ImplicitVRLittleEndian)
        arr, _ = decoder.as_array(reference.ds, raw=True)
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        for index in range(reference.number_of_frames):
            arr, _ = decoder.as_array(reference.ds, raw=True, index=index)
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[DeflatedExplicitVRLittleEndian], ids=name
    )
    def test_reference_defl(self, reference):
        """Test against the reference data for deflated little."""
        decoder = get_decoder(DeflatedExplicitVRLittleEndian)
        arr, _ = decoder.as_array(reference.ds, raw=True)
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        for index in range(reference.number_of_frames):
            arr, _ = decoder.as_array(reference.ds, raw=True, index=index)
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRBigEndian], ids=name
    )
    def test_reference_expb(self, reference):
        """Test against the reference data for explicit big."""
        decoder = get_decoder(ExplicitVRBigEndian)
        arr, _ = decoder.as_array(reference.ds, raw=True)
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        for index in range(reference.number_of_frames):
            arr, _ = decoder.as_array(reference.ds, raw=True, index=index)
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRBigEndian], ids=name
    )
    def test_reference_expb_binary(self, reference):
        """Test against the reference data for explicit big using binary IO."""
        decoder = get_decoder(ExplicitVRBigEndian)
        ds = reference.ds
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": ds.PixelRepresentation,
            "bits_allocated": ds.BitsAllocated,
            "bits_stored": ds.BitsStored,
            "number_of_frames": ds.get("NumberOfFrames", 1),
            "planar_configuration": ds.get("PlanarConfiguration", 0),
            "pixel_keyword": "PixelData",
            "pixel_vr": ds["PixelData"].VR,
        }

        with open(reference.path, "rb") as f:
            file_offset = reference.ds["PixelData"].file_tell
            f.seek(file_offset)
            arr, _ = decoder.as_array(f, raw=True, **opts)
            assert f.tell() == file_offset
            reference.test(arr)
            assert arr.shape == reference.shape
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            for index in range(reference.number_of_frames):
                arr, _ = decoder.as_array(f, raw=True, index=index, **opts)
                reference.test(arr, index=index)
                assert arr.dtype == reference.dtype
                assert arr.flags.writeable
                assert f.tell() == file_offset

                if reference.number_of_frames == 1:
                    assert arr.shape == reference.shape
                else:
                    assert arr.shape == reference.shape[1:]

    def test_float_pixel_data(self):
        """Test Float Pixel Data."""
        # Only 1 sample per pixel allowed
        ds = dcmread(IMPL_32_1_1F.path)
        ds.FloatPixelData = ds.PixelData
        del ds.PixelData
        assert 32 == ds.BitsAllocated
        decoder = get_decoder(ds.file_meta.TransferSyntaxUID)
        arr, _ = decoder.as_array(ds, raw=True)
        assert "float32" == arr.dtype

        ref, _ = decoder.as_array(IMPL_32_1_1F.ds, raw=True)
        assert np.array_equal(arr, ref.view("float32"))

    def test_double_float_pixel_data(self):
        """Test Double Float Pixel Data."""
        # Only 1 sample per pixel allowed
        ds = dcmread(IMPL_32_1_1F.path)
        ds.DoubleFloatPixelData = ds.PixelData + ds.PixelData
        del ds.PixelData
        ds.BitsAllocated = 64
        decoder = get_decoder(ds.file_meta.TransferSyntaxUID)
        arr, _ = decoder.as_array(ds, raw=True)
        assert "float64" == arr.dtype

        ref, _ = decoder.as_array(IMPL_32_1_1F.ds, raw=True)
        assert np.array_equal(arr.ravel()[:50], ref.view("float64").ravel())
        assert np.array_equal(arr.ravel()[50:], ref.view("float64").ravel())


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
class TestIterArray:
    """Tests for Decoder.iter_array() with native transfer syntaxes"""

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRLittleEndian], ids=name
    )
    def test_reference_expl(self, reference):
        """Test against the reference data for explicit little."""
        decoder = get_decoder(ExplicitVRLittleEndian)
        frame_generator = decoder.iter_array(reference.ds, raw=True)
        if reference == EXPL_16_1_1F_PAD:
            msg = (
                "The pixel data is 8320 bytes long, which indicates it contains "
                "128 bytes of excess padding to be removed"
            )
            with pytest.warns(UserWarning, match=msg):
                arr, _ = next(frame_generator)
        else:
            arr, _ = next(frame_generator)

        reference.test(arr, index=0)
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        if reference.number_of_frames == 1:
            assert arr.shape == reference.shape
        else:
            assert arr.shape == reference.shape[1:]

        for index, (arr, _) in enumerate(frame_generator):
            reference.test(arr, index=index + 1)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRLittleEndian], ids=name
    )
    def test_reference_expl_binary(self, reference):
        """Test against the reference data for explicit little for binary IO."""
        decoder = get_decoder(ExplicitVRLittleEndian)
        ds = reference.ds
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": ds.PixelRepresentation,
            "bits_allocated": ds.BitsAllocated,
            "bits_stored": ds.BitsStored,
            "number_of_frames": ds.get("NumberOfFrames", 1),
            "planar_configuration": ds.get("PlanarConfiguration", 0),
            "pixel_keyword": "PixelData",
        }

        with open(reference.path, "rb") as f:
            file_offset = reference.ds["PixelData"].file_tell
            f.seek(file_offset)

            frame_generator = decoder.iter_array(f, raw=True, **opts)
            arr, _ = next(frame_generator)

            reference.test(arr, index=0)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

            for index, (arr, _) in enumerate(frame_generator):
                reference.test(arr, index=index + 1)
                assert arr.dtype == reference.dtype
                assert arr.flags.writeable

                if reference.number_of_frames == 1:
                    assert arr.shape == reference.shape
                else:
                    assert arr.shape == reference.shape[1:]

            assert f.tell() == file_offset

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ImplicitVRLittleEndian], ids=name
    )
    def test_reference_impl(self, reference):
        """Test against the reference data for implicit little."""
        decoder = get_decoder(ImplicitVRLittleEndian)
        for index, (arr, _) in enumerate(decoder.iter_array(reference.ds, raw=True)):
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[DeflatedExplicitVRLittleEndian], ids=name
    )
    def test_reference_defl(self, reference):
        """Test against the reference data for deflated little."""
        decoder = get_decoder(DeflatedExplicitVRLittleEndian)
        for index, (arr, _) in enumerate(decoder.iter_array(reference.ds, raw=True)):
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRBigEndian], ids=name
    )
    def test_reference_expb(self, reference):
        """Test against the reference data for explicit big."""
        decoder = get_decoder(ExplicitVRBigEndian)
        for index, (arr, _) in enumerate(decoder.iter_array(reference.ds, raw=True)):
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRBigEndian], ids=name
    )
    def test_reference_expb_binary(self, reference):
        """Test against the reference data for explicit big for binary IO."""
        decoder = get_decoder(ExplicitVRBigEndian)
        ds = reference.ds
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": ds.PixelRepresentation,
            "bits_allocated": ds.BitsAllocated,
            "bits_stored": ds.BitsStored,
            "number_of_frames": ds.get("NumberOfFrames", 1),
            "planar_configuration": ds.get("PlanarConfiguration", 0),
            "pixel_keyword": "PixelData",
            "pixel_vr": ds["PixelData"].VR,
        }

        with open(reference.path, "rb") as f:
            file_offset = reference.ds["PixelData"].file_tell
            f.seek(file_offset)
            for index, (arr, _) in enumerate(decoder.iter_array(f, raw=True, **opts)):
                reference.test(arr, index=index)
                assert arr.dtype == reference.dtype
                assert arr.flags.writeable

                if reference.number_of_frames == 1:
                    assert arr.shape == reference.shape
                else:
                    assert arr.shape == reference.shape[1:]

            assert f.tell() == file_offset


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
class TestAsBuffer:
    """Tests for Decoder.as_buffer() with native transfer syntaxes"""

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRLittleEndian], ids=name
    )
    def test_reference_expl(self, reference):
        """Test against the reference data for explicit little."""
        decoder = get_decoder(ExplicitVRLittleEndian)
        # Exclude bit-packed and YBR_FULL_422
        if reference.ds.BitsAllocated == 1:
            return

        if reference.ds.PhotometricInterpretation == "YBR_FULL_422":
            return

        if reference == EXPL_16_1_1F_PAD:
            msg = (
                "The pixel data is 8320 bytes long, which indicates it contains "
                "128 bytes of excess padding to be removed"
            )
            with pytest.warns(UserWarning, match=msg):
                arr, _ = decoder.as_array(reference.ds, raw=True)
                buffer, _ = decoder.as_buffer(reference.ds)
        else:
            arr, _ = decoder.as_array(reference.ds, raw=True)
            buffer, _ = decoder.as_buffer(reference.ds)

        assert arr.tobytes() == buffer

        for index in range(reference.number_of_frames):
            if reference == EXPL_16_1_1F_PAD:
                msg = (
                    "The pixel data is 8320 bytes long, which indicates it contains "
                    "128 bytes of excess padding to be removed"
                )
                with pytest.warns(UserWarning, match=msg):
                    arr, _ = decoder.as_array(reference.ds, raw=True)
                    buffer, _ = decoder.as_buffer(reference.ds)
            else:
                arr, _ = decoder.as_array(reference.ds, raw=True, index=index)
                buffer, _ = decoder.as_buffer(reference.ds, index=index)

            assert arr.tobytes() == buffer

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRLittleEndian], ids=name
    )
    def test_reference_expl_binary(self, reference):
        """Test against the reference data for explicit little for binary IO."""
        decoder = get_decoder(ExplicitVRLittleEndian)
        # Exclude bit-packed and YBR_FULL_422
        if reference.ds.BitsAllocated == 1:
            return

        if reference.ds.PhotometricInterpretation == "YBR_FULL_422":
            return

        ds = reference.ds
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": ds.PixelRepresentation,
            "bits_allocated": ds.BitsAllocated,
            "bits_stored": ds.BitsStored,
            "number_of_frames": ds.get("NumberOfFrames", 1),
            "planar_configuration": ds.get("PlanarConfiguration", 0),
            "pixel_keyword": "PixelData",
        }

        with open(reference.path, "rb") as f:
            file_offset = reference.ds["PixelData"].file_tell
            f.seek(file_offset)
            arr, _ = decoder.as_array(f, raw=True, **opts)
            buffer, _ = decoder.as_buffer(f, **opts)
            assert arr.tobytes() == buffer
            assert f.tell() == file_offset

            for index in range(reference.number_of_frames):
                arr, _ = decoder.as_array(f, raw=True, index=index, **opts)
                buffer, _ = decoder.as_buffer(f, index=index, **opts)
                assert arr.tobytes() == buffer
                assert f.tell() == file_offset

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ImplicitVRLittleEndian], ids=name
    )
    def test_reference_impl(self, reference):
        """Test against the reference data for implicit little."""
        decoder = get_decoder(ImplicitVRLittleEndian)
        arr, _ = decoder.as_array(reference.ds, raw=True)
        buffer, _ = decoder.as_buffer(reference.ds)
        assert arr.tobytes() == buffer

        for index in range(reference.number_of_frames):
            arr, _ = decoder.as_array(reference.ds, raw=True, index=index)
            buffer, _ = decoder.as_buffer(reference.ds, index=index)
            assert arr.tobytes() == buffer

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[DeflatedExplicitVRLittleEndian], ids=name
    )
    def test_reference_defl(self, reference):
        """Test against the reference data for deflated little."""
        decoder = get_decoder(DeflatedExplicitVRLittleEndian)
        arr, _ = decoder.as_array(reference.ds, raw=True)
        buffer, _ = decoder.as_buffer(reference.ds)
        assert arr.tobytes() == buffer

        for index in range(reference.number_of_frames):
            arr, _ = decoder.as_array(reference.ds, raw=True, index=index)
            buffer, _ = decoder.as_buffer(reference.ds, index=index)
            assert arr.tobytes() == buffer

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRBigEndian], ids=name
    )
    def test_reference_expb(self, reference):
        """Test against the reference data for explicit big."""
        ds = reference.ds
        # Exclude bit-packed and YBR_FULL_422
        if ds.BitsAllocated == 1:
            return

        if ds.PhotometricInterpretation == "YBR_FULL_422":
            return

        if ds.BitsAllocated == 8 and ds["PixelData"].VR == "OW":
            return

        decoder = get_decoder(ExplicitVRBigEndian)
        arr, _ = decoder.as_array(ds, raw=True)
        buffer, _ = decoder.as_buffer(ds)
        if ds.SamplesPerPixel > 1 and ds.PlanarConfiguration == 1:
            # Transpose to match colour by plane
            arr = arr.transpose(2, 0, 1)

        assert arr.tobytes() == buffer

        for index in range(reference.number_of_frames):
            arr, _ = decoder.as_array(ds, raw=True, index=index)
            buffer, _ = decoder.as_buffer(ds, index=index)
            if ds.SamplesPerPixel > 1 and ds.PlanarConfiguration == 1:
                # Transpose to match colour by plane
                arr = arr.transpose(2, 0, 1)

            assert arr.tobytes() == buffer

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRBigEndian], ids=name
    )
    def test_reference_expb_binary(self, reference):
        """Test against the reference data for explicit big for binary IO."""
        ds = reference.ds
        # Exclude bit-packed and YBR_FULL_422
        if ds.BitsAllocated == 1:
            return

        if ds.PhotometricInterpretation == "YBR_FULL_422":
            return

        if ds.BitsAllocated == 8 and ds["PixelData"].VR == "OW":
            return

        decoder = get_decoder(ExplicitVRBigEndian)
        ds = reference.ds
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": ds.PixelRepresentation,
            "bits_allocated": ds.BitsAllocated,
            "bits_stored": ds.BitsStored,
            "number_of_frames": ds.get("NumberOfFrames", 1),
            "planar_configuration": ds.get("PlanarConfiguration", 0),
            "pixel_keyword": "PixelData",
            "pixel_vr": ds["PixelData"].VR,
        }

        with open(reference.path, "rb") as f:
            file_offset = reference.ds["PixelData"].file_tell
            f.seek(file_offset)
            arr, _ = decoder.as_array(f, raw=True, **opts)
            assert f.tell() == file_offset
            buffer, _ = decoder.as_buffer(f, **opts)
            assert f.tell() == file_offset
            if ds.SamplesPerPixel > 1 and ds.PlanarConfiguration == 1:
                # Transpose to match colour by plane
                arr = arr.transpose(2, 0, 1)

            assert arr.tobytes() == buffer

            for index in range(reference.number_of_frames):
                arr, _ = decoder.as_array(f, raw=True, index=index, **opts)
                assert f.tell() == file_offset
                buffer, _ = decoder.as_buffer(f, index=index, **opts)
                assert f.tell() == file_offset
                if ds.SamplesPerPixel > 1 and ds.PlanarConfiguration == 1:
                    # Transpose to match colour by plane
                    arr = arr.transpose(2, 0, 1)

                assert arr.tobytes() == buffer

    def test_expb_8bit_ow(self):
        """Test big endian 8-bit data written as OW"""
        decoder = get_decoder(ExplicitVRBigEndian)

        references = [
            PIXEL_REFERENCE[ExplicitVRBigEndian][2],
            PIXEL_REFERENCE[ExplicitVRBigEndian][3],
            PIXEL_REFERENCE[ExplicitVRBigEndian][5],
        ]
        for idx, reference in enumerate(references):
            ds = reference.ds
            assert ds.BitsAllocated == 8 and ds["PixelData"].VR == "OW"
            arr, _ = decoder.as_array(reference.ds, raw=True)
            buffer, _ = decoder.as_buffer(reference.ds)
            if arr.size % 2 == 0:
                # Even length - can just byteswap after re-viewing
                assert arr.view(">u2").byteswap().tobytes() == buffer
            else:
                # Odd length: need to pad + 1 pixel to be able to byteswap
                out = np.zeros((28), dtype=arr.dtype)
                out[:27] = arr.ravel()
                assert out.view(">u2").byteswap().tobytes() == buffer

    def test_expb_8bit_ow_binary(self):
        """Test big endian 8-bit data written as OW for binary IO"""
        decoder = get_decoder(ExplicitVRBigEndian)

        references = [
            PIXEL_REFERENCE[ExplicitVRBigEndian][2],
            PIXEL_REFERENCE[ExplicitVRBigEndian][3],
            PIXEL_REFERENCE[ExplicitVRBigEndian][5],
        ]

        for idx, reference in enumerate(references):
            ds = reference.ds
            opts = {
                "rows": ds.Rows,
                "columns": ds.Columns,
                "samples_per_pixel": ds.SamplesPerPixel,
                "photometric_interpretation": ds.PhotometricInterpretation,
                "pixel_representation": ds.PixelRepresentation,
                "bits_allocated": ds.BitsAllocated,
                "bits_stored": ds.BitsStored,
                "number_of_frames": ds.get("NumberOfFrames", 1),
                "planar_configuration": ds.get("PlanarConfiguration", 0),
                "pixel_keyword": "PixelData",
                "pixel_vr": ds["PixelData"].VR,
            }
            assert ds.BitsAllocated == 8 and ds["PixelData"].VR == "OW"

            with open(reference.path, "rb") as f:
                file_offset = reference.ds["PixelData"].file_tell
                f.seek(file_offset)
                arr, _ = decoder.as_array(f, raw=True, **opts)
                assert f.tell() == file_offset
                buffer, _ = decoder.as_buffer(f, **opts)
                assert f.tell() == file_offset
                if arr.size % 2 == 0:
                    # Even length - can just byteswap after re-viewing
                    assert arr.view(">u2").byteswap().tobytes() == buffer
                else:
                    # Odd length: need to pad + 1 pixel to be able to byteswap
                    out = np.zeros((28), dtype=arr.dtype)
                    out[:27] = arr.ravel()
                    assert out.view(">u2").byteswap().tobytes() == buffer

    def test_float_pixel_data(self):
        """Test Float Pixel Data."""
        ds = dcmread(IMPL_32_1_1F.path)
        ref = ds.PixelData
        ds.FloatPixelData = ref
        del ds.PixelData
        assert 32 == ds.BitsAllocated
        decoder = get_decoder(ds.file_meta.TransferSyntaxUID)
        buffer, _ = decoder.as_buffer(ds, raw=True)
        assert buffer == ref

    def test_double_float_pixel_data(self):
        """Test Double Float Pixel Data."""
        ds = dcmread(IMPL_32_1_1F.path)
        ref = ds.PixelData + ds.PixelData
        ds.DoubleFloatPixelData = ref
        del ds.PixelData
        ds.BitsAllocated = 64
        decoder = get_decoder(ds.file_meta.TransferSyntaxUID)
        buffer, _ = decoder.as_buffer(ds, raw=True)
        assert buffer == ref


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
class TestIterBuffer:
    """Tests for Decoder.iter_buffer() with native transfer syntaxes"""

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRLittleEndian], ids=name
    )
    def test_reference_expl(self, reference):
        """Test against the reference data for explicit little."""
        decoder = get_decoder(ExplicitVRLittleEndian)
        if reference.ds.BitsAllocated == 1:
            return

        if reference.ds.PhotometricInterpretation == "YBR_FULL_422":
            return

        arr_gen = decoder.iter_array(reference.ds, raw=True)
        buf_gen = decoder.iter_buffer(reference.ds)
        if reference == EXPL_16_1_1F_PAD:
            msg = (
                "The pixel data is 8320 bytes long, which indicates it contains "
                "128 bytes of excess padding to be removed"
            )
            with pytest.warns(UserWarning, match=msg):
                arr, _ = next(arr_gen)
                buffer, _ = next(buf_gen)
        else:
            arr, _ = next(arr_gen)
            buffer, _ = next(buf_gen)

        assert arr.tobytes() == buffer

        for (arr, _), (buffer, _) in zip(arr_gen, buf_gen):
            assert arr.tobytes() == buffer

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRLittleEndian], ids=name
    )
    def test_reference_expl_binary(self, reference):
        """Test against the reference data for explicit little for binary IO."""
        decoder = get_decoder(ExplicitVRLittleEndian)
        if reference.ds.BitsAllocated == 1:
            return

        if reference.ds.PhotometricInterpretation == "YBR_FULL_422":
            return

        ds = reference.ds
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": ds.PixelRepresentation,
            "bits_allocated": ds.BitsAllocated,
            "bits_stored": ds.BitsStored,
            "number_of_frames": ds.get("NumberOfFrames", 1),
            "planar_configuration": ds.get("PlanarConfiguration", 0),
            "pixel_keyword": "PixelData",
        }

        with open(reference.path, "rb") as f:
            file_offset = reference.ds["PixelData"].file_tell
            f.seek(file_offset)
            arr_gen = decoder.iter_array(f, raw=True, **opts)
            buf_gen = decoder.iter_buffer(f, **opts)
            arr, _ = next(arr_gen)
            assert f.tell() == file_offset
            buffer, _ = next(buf_gen)
            assert f.tell() == file_offset

            assert arr.tobytes() == buffer

            for (arr, _), (buffer, _) in zip(arr_gen, buf_gen):
                assert arr.tobytes() == buffer

            assert f.tell() == file_offset

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[ImplicitVRLittleEndian])
    def test_reference_impl(self, reference):
        """Test against the reference data for implicit little."""
        decoder = get_decoder(ImplicitVRLittleEndian)
        arr_gen = decoder.iter_array(reference.ds, raw=True)
        buf_gen = decoder.iter_buffer(reference.ds)
        for (arr, _), (buffer, _) in zip(arr_gen, buf_gen):
            assert arr.tobytes() == buffer

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[DeflatedExplicitVRLittleEndian], ids=name
    )
    def test_reference_defl(self, reference):
        """Test against the reference data for deflated little."""
        decoder = get_decoder(DeflatedExplicitVRLittleEndian)
        arr_gen = decoder.iter_array(reference.ds, raw=True)
        buf_gen = decoder.iter_buffer(reference.ds)
        for (arr, _), (buffer, _) in zip(arr_gen, buf_gen):
            assert arr.tobytes() == buffer

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRBigEndian], ids=name
    )
    def test_reference_expb(self, reference):
        """Test against the reference data for explicit big."""
        ds = reference.ds
        if ds.BitsAllocated == 1:
            return

        if ds.BitsAllocated == 8 and ds["PixelData"].VR == "OW":
            return

        decoder = get_decoder(ExplicitVRBigEndian)
        arr_gen = decoder.iter_array(ds, raw=True)
        buf_gen = decoder.iter_buffer(ds)
        for (arr, _), (buffer, _) in zip(arr_gen, buf_gen):
            if ds.SamplesPerPixel > 1 and ds.PlanarConfiguration == 1:
                # Transpose to match colour by plane
                arr = arr.transpose(2, 0, 1)

            assert arr.tobytes() == buffer

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRBigEndian], ids=name
    )
    def test_reference_expb_binary(self, reference):
        """Test against the reference data for explicit big for binary IO."""
        ds = reference.ds
        if ds.BitsAllocated == 1:
            return

        if ds.BitsAllocated == 8 and ds["PixelData"].VR == "OW":
            return

        decoder = get_decoder(ExplicitVRBigEndian)
        ds = reference.ds
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": ds.PixelRepresentation,
            "bits_allocated": ds.BitsAllocated,
            "bits_stored": ds.BitsStored,
            "number_of_frames": ds.get("NumberOfFrames", 1),
            "planar_configuration": ds.get("PlanarConfiguration", 0),
            "pixel_keyword": "PixelData",
        }

        with open(reference.path, "rb") as f:
            file_offset = reference.ds["PixelData"].file_tell
            f.seek(file_offset)
            arr_gen = decoder.iter_array(f, raw=True, **opts)
            buf_gen = decoder.iter_buffer(f, **opts)
            for (arr, _), (buffer, _) in zip(arr_gen, buf_gen):
                assert f.tell() == file_offset
                if ds.SamplesPerPixel > 1 and ds.PlanarConfiguration == 1:
                    # Transpose to match colour by plane
                    arr = arr.transpose(2, 0, 1)

                assert arr.tobytes() == buffer

    def test_expb_8bit_ow(self):
        """Test big endian 8-bit data written as OW"""
        decoder = get_decoder(ExplicitVRBigEndian)

        references = [
            PIXEL_REFERENCE[ExplicitVRBigEndian][2],
            PIXEL_REFERENCE[ExplicitVRBigEndian][3],
            PIXEL_REFERENCE[ExplicitVRBigEndian][5],
        ]
        for idx, reference in enumerate(references):
            ds = reference.ds
            assert ds.BitsAllocated == 8 and ds["PixelData"].VR == "OW"
            arr_gen = decoder.iter_array(reference.ds, raw=True)
            buf_gen = decoder.iter_buffer(reference.ds)
            for (arr, _), (buffer, _) in zip(arr_gen, buf_gen):
                if arr.size % 2 == 0:
                    # Even length - can just byteswap after re-viewing
                    assert arr.view(">u2").byteswap().tobytes() == buffer
                else:
                    # Odd length: need to pad + 1 pixel to be able to byteswap
                    out = np.zeros((arr.size + 1), dtype=arr.dtype)
                    out[: arr.size] = arr.ravel()
                    assert out.view(">u2").byteswap().tobytes() == buffer

    def test_expb_8bit_ow_binary(self):
        """Test big endian 8-bit data written as OW as binary IO"""
        decoder = get_decoder(ExplicitVRBigEndian)

        references = [
            PIXEL_REFERENCE[ExplicitVRBigEndian][2],
            PIXEL_REFERENCE[ExplicitVRBigEndian][3],
            PIXEL_REFERENCE[ExplicitVRBigEndian][5],
        ]
        for idx, reference in enumerate(references):
            ds = reference.ds
            opts = {
                "rows": ds.Rows,
                "columns": ds.Columns,
                "samples_per_pixel": ds.SamplesPerPixel,
                "photometric_interpretation": ds.PhotometricInterpretation,
                "pixel_representation": ds.PixelRepresentation,
                "bits_allocated": ds.BitsAllocated,
                "bits_stored": ds.BitsStored,
                "number_of_frames": ds.get("NumberOfFrames", 1),
                "planar_configuration": ds.get("PlanarConfiguration", 0),
                "pixel_keyword": "PixelData",
                "pixel_vr": ds["PixelData"].VR,
            }
            assert ds.BitsAllocated == 8 and ds["PixelData"].VR == "OW"

            with open(reference.path, "rb") as f:
                file_offset = reference.ds["PixelData"].file_tell
                f.seek(file_offset)
                arr_gen = decoder.iter_array(f, raw=True, **opts)
                buf_gen = decoder.iter_buffer(f, **opts)
                for (arr, _), (buffer, _) in zip(arr_gen, buf_gen):
                    assert f.tell() == file_offset
                    if arr.size % 2 == 0:
                        # Even length - can just byteswap after re-viewing
                        assert arr.view(">u2").byteswap().tobytes() == buffer
                    else:
                        # Odd length: need to pad + 1 pixel to be able to byteswap
                        out = np.zeros((arr.size + 1), dtype=arr.dtype)
                        out[: arr.size] = arr.ravel()
                        assert out.view(">u2").byteswap().tobytes() == buffer
