"""Test decoding native transfer syntaxes."""

import pytest

from pydicom import dcmread
from pydicom.data import get_testdata_file
from pydicom.pixels import (
    get_decoder,
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

from .pixels_reference import PIXEL_REFERENCE, EXPL_16_1_1F_PAD


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
                arr = decoder.as_array(reference.ds, raw=True)
        else:
            arr = decoder.as_array(reference.ds, raw=True)
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRLittleEndian], ids=name
    )
    def test_reference_expl_index(self, reference):
        """Test by index against the reference data for explicit little."""
        decoder = get_decoder(ExplicitVRLittleEndian)
        for index in range(reference.number_of_frames):
            if reference == EXPL_16_1_1F_PAD:
                msg = (
                    "The pixel data is 8320 bytes long, which indicates it contains "
                    "128 bytes of excess padding to be removed"
                )
                with pytest.warns(UserWarning, match=msg):
                    arr = decoder.as_array(reference.ds, raw=True)
            else:
                arr = decoder.as_array(reference.ds, raw=True, index=index)
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

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
        arr = decoder.as_array(reference.ds, raw=True)
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ImplicitVRLittleEndian], ids=name
    )
    def test_reference_impl_index(self, reference):
        """Test by index against the reference data for implicit little."""
        decoder = get_decoder(ImplicitVRLittleEndian)
        for index in range(reference.number_of_frames):
            arr = decoder.as_array(reference.ds, raw=True, index=index)
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
        arr = decoder.as_array(reference.ds, raw=True)
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[DeflatedExplicitVRLittleEndian], ids=name
    )
    def test_reference_defl_index(self, reference):
        """Test by index against the reference data for deflated little."""
        decoder = get_decoder(DeflatedExplicitVRLittleEndian)
        for index in range(reference.number_of_frames):
            arr = decoder.as_array(reference.ds, raw=True, index=index)
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
        arr = decoder.as_array(reference.ds, raw=True)
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ExplicitVRBigEndian], ids=name
    )
    def test_reference_expb_index(self, reference):
        """Test by index against the reference data for explicit big."""
        decoder = get_decoder(ExplicitVRBigEndian)
        for index in range(reference.number_of_frames):
            arr = decoder.as_array(reference.ds, raw=True, index=index)
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]


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
                arr = next(frame_generator)
        else:
            arr = next(frame_generator)

        reference.test(arr, index=0)
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        if reference.number_of_frames == 1:
            assert arr.shape == reference.shape
        else:
            assert arr.shape == reference.shape[1:]

        for index, arr in enumerate(frame_generator):
            reference.test(arr, index=index + 1)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

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
        for index, arr in enumerate(decoder.iter_array(reference.ds, raw=True)):
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
        for index, arr in enumerate(decoder.iter_array(reference.ds, raw=True)):
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
        for index, arr in enumerate(decoder.iter_array(reference.ds, raw=True)):
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]


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
                arr = decoder.as_array(reference.ds, raw=True)
                buffer = decoder.as_buffer(reference.ds)
        else:
            arr = decoder.as_array(reference.ds, raw=True)
            buffer = decoder.as_buffer(reference.ds)

        assert arr.tobytes() == buffer

        for index in range(reference.number_of_frames):
            if reference == EXPL_16_1_1F_PAD:
                msg = (
                    "The pixel data is 8320 bytes long, which indicates it contains "
                    "128 bytes of excess padding to be removed"
                )
                with pytest.warns(UserWarning, match=msg):
                    arr = decoder.as_array(reference.ds, raw=True)
                    buffer = decoder.as_buffer(reference.ds)
            else:
                arr = decoder.as_array(reference.ds, raw=True, index=index)
                buffer = decoder.as_buffer(reference.ds, index=index)

            assert arr.tobytes() == buffer

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[ImplicitVRLittleEndian], ids=name
    )
    def test_reference_impl(self, reference):
        """Test against the reference data for implicit little."""
        decoder = get_decoder(ImplicitVRLittleEndian)
        arr = decoder.as_array(reference.ds, raw=True)
        buffer = decoder.as_buffer(reference.ds)
        assert arr.tobytes() == buffer

        for index in range(reference.number_of_frames):
            arr = decoder.as_array(reference.ds, raw=True, index=index)
            buffer = decoder.as_buffer(reference.ds, index=index)
            assert arr.tobytes() == buffer

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[DeflatedExplicitVRLittleEndian], ids=name
    )
    def test_reference_defl(self, reference):
        """Test against the reference data for deflated little."""
        decoder = get_decoder(DeflatedExplicitVRLittleEndian)
        arr = decoder.as_array(reference.ds, raw=True)
        buffer = decoder.as_buffer(reference.ds)
        assert arr.tobytes() == buffer

        for index in range(reference.number_of_frames):
            arr = decoder.as_array(reference.ds, raw=True, index=index)
            buffer = decoder.as_buffer(reference.ds, index=index)
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
        arr = decoder.as_array(ds, raw=True)
        buffer = decoder.as_buffer(ds)

        for index in range(reference.number_of_frames):
            arr = decoder.as_array(ds, raw=True, index=index)
            buffer = decoder.as_buffer(ds, index=index)
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
            arr = decoder.as_array(reference.ds, raw=True)
            buffer = decoder.as_buffer(reference.ds)
            if idx in (0, 1):
                # Even length - can just byteswap after re-viewing
                assert arr.view(">u2").byteswap().tobytes() == buffer
            else:
                # Odd length: need to pad + 1 pixel to be able to byteswap
                out = np.zeros((28), dtype=arr.dtype)
                out[:27] = arr.ravel()
                assert out.view(">u2").byteswap().tobytes() == buffer


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
                arr = next(arr_gen)
                buffer = next(buf_gen)
        else:
            arr = next(arr_gen)
            buffer = next(buf_gen)

        assert arr.tobytes() == buffer

        for arr, buffer in zip(arr_gen, buf_gen):
            assert arr.tobytes() == buffer

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[ImplicitVRLittleEndian])
    def test_reference_impl(self, reference):
        """Test against the reference data for implicit little."""
        decoder = get_decoder(ImplicitVRLittleEndian)
        arr_gen = decoder.iter_array(reference.ds, raw=True)
        buf_gen = decoder.iter_buffer(reference.ds)
        for arr, buffer in zip(arr_gen, buf_gen):
            assert arr.tobytes() == buffer

    @pytest.mark.parametrize(
        "reference", PIXEL_REFERENCE[DeflatedExplicitVRLittleEndian], ids=name
    )
    def test_reference_defl(self, reference):
        """Test against the reference data for deflated little."""
        decoder = get_decoder(DeflatedExplicitVRLittleEndian)
        arr_gen = decoder.iter_array(reference.ds, raw=True)
        buf_gen = decoder.iter_buffer(reference.ds)
        for arr, buffer in zip(arr_gen, buf_gen):
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
        for arr, buffer in zip(arr_gen, buf_gen):
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
            for arr, buffer in zip(arr_gen, buf_gen):
                if idx in (0, 1):
                    # Even length - can just byteswap after re-viewing
                    assert arr.view(">u2").byteswap().tobytes() == buffer
                else:
                    # Odd length: need to pad + 1 pixel to be able to byteswap
                    out = np.zeros((28), dtype=arr.dtype)
                    out[:27] = arr.ravel()
                    assert out.view(">u2").byteswap().tobytes() == buffer
