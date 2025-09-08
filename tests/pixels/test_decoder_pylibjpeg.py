"""Test the pylibjpeg decoder."""

import importlib

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom import dcmread
from pydicom.encaps import get_frame, encapsulate
from pydicom.pixels import get_decoder
from pydicom.pixels.utils import unpack_bits
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
    HTJ2KLossless,
    HTJ2KLosslessRPCL,
    HTJ2K,
    RLELossless,
)
from pydicom.pixels.utils import get_j2k_parameters

from .pixels_reference import (
    PIXEL_REFERENCE,
    JPGE_BAD,
    J2KR_1_1_3F,
    J2KR_1_1_3F_NONALIGNED,
    J2KR_16_13_1_1_1F_M2_MISMATCH,
    JLSN_08_01_1_0_1F,
    JPGB_08_08_3_0_1F_RGB,  # has RGB component IDs
    JPGB_08_08_3_0_1F_YBR_FULL,  # has JFIF APP marker
    JLSL_08_07_1_0_1F,
    JLSL_16_15_1_1_1F,
    JLSL_16_12_1_0_10F,
    JPGB_08_08_3_0_120F_YBR_FULL_422,
    RLE_1_1_3F,
    EXPL_16_1_10F,
)


HAVE_PYLJ = bool(importlib.util.find_spec("pylibjpeg"))
HAVE_LJ = bool(importlib.util.find_spec("libjpeg"))
HAVE_OJ = bool(importlib.util.find_spec("openjpeg"))
HAVE_RLE = bool(importlib.util.find_spec("rle"))

SKIP_LJ = not (HAVE_NP and HAVE_PYLJ and HAVE_LJ)
SKIP_OJ = not (HAVE_NP and HAVE_PYLJ and HAVE_OJ)
SKIP_RLE = not (HAVE_NP and HAVE_PYLJ and HAVE_RLE)


def name(ref):
    return f"{ref.name}"


def test_is_available_unknown_uid():
    """Test is_available() for an unknown UID"""
    assert is_available("1.2.3.4") is False


@pytest.mark.skipif(SKIP_LJ, reason="Test is missing dependencies")
class TestLibJpegDecoder:
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGBaseline8Bit], ids=name)
    def test_jpg_baseline(self, reference):
        """Test the decoder with JPEGBaseline8Bit."""
        decoder = get_decoder(JPEGBaseline8Bit)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr, plugin="pylibjpeg")
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGExtended12Bit], ids=name)
    def test_jpg_extended(self, reference):
        """Test the decoder with JPEGExtended12Bit."""
        # Invalid spectrum end value, decode fails
        if reference.name == "JPEG-lossy.dcm":
            return

        decoder = get_decoder(JPEGExtended12Bit)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLossless], ids=name)
    def test_jpg_lossless(self, reference):
        """Test the decoder with JPEGLossless."""
        decoder = get_decoder(JPEGLossless)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLosslessSV1], ids=name)
    def test_jpg_lossless_sv1(self, reference):
        """Test the decoder with JPEGLosslessSV1."""
        decoder = get_decoder(JPEGLosslessSV1)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLSLossless], ids=name)
    def test_jls_lossless(self, reference):
        """Test the decoder with JPEGLSLossless."""
        decoder = get_decoder(JPEGLSLossless)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEGLSNearLossless], ids=name)
    def test_jls_lossy(self, reference):
        """Test the decoder with JPEGLSNearLossless."""
        decoder = get_decoder(JPEGLSNearLossless)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    def test_jpg_extended_invalid_se_raises(self):
        """Test invalid scan stop raises an exception."""
        decoder = get_decoder(JPEGExtended12Bit)
        msg = (
            "Unable to decode as exceptions were raised by all available "
            "plugins:\n  pylibjpeg: libjpeg error code '-1038' returned "
            r"from Decode\(\): A misplaced marker segment was found - scan "
            "start must be zero and scan stop must be 63 for the sequential "
            "operating modes"
        )
        with pytest.raises(RuntimeError, match=msg):
            decoder.as_array(JPGE_BAD.ds, decoding_plugin="pylibjpeg")

    def test_bits_allocated_mismatch(self):
        """Test the result when bits stored <= 8 and bits allocated 16"""
        # The JPEG-LS codestream uses a precision of 8, so it will return
        #   8-bit values, however the decoding process nominally expects 16-bit
        decoder = get_decoder(JPEGLSNearLossless)
        arr, meta = decoder.as_array(
            JLSN_08_01_1_0_1F.ds,
            raw=True,
            decoding_plugin="pylibjpeg",
            bits_allocated=16,
        )
        JLSN_08_01_1_0_1F.test(arr)
        assert arr.shape == JLSN_08_01_1_0_1F.shape
        assert arr.dtype != JLSN_08_01_1_0_1F.dtype
        assert arr.dtype == "<u2"
        assert arr.flags.writeable
        assert meta["bits_allocated"] == 16
        assert meta["bits_stored"] == 8

    def test_bits_allocated_mismatch_as_buffer(self):
        """Test the result when bits stored <= 8 and bits allocated 16"""
        decoder = get_decoder(JPEGLSNearLossless)
        ds = JLSN_08_01_1_0_1F.ds
        buffer, meta = decoder.as_buffer(
            ds,
            raw=True,
            decoding_plugin="pylibjpeg",
            bits_allocated=16,
        )
        assert ds.BitsStored == 8
        assert len(buffer) == ds.Rows * ds.Columns * ds.SamplesPerPixel
        arr = np.frombuffer(buffer, dtype="u1")
        arr = arr.reshape((ds.Rows, ds.Columns))
        JLSN_08_01_1_0_1F.test(arr)
        assert arr.shape == JLSN_08_01_1_0_1F.shape
        assert meta[0]["bits_allocated"] == 8
        assert meta[0]["bits_stored"] == 8

    def test_rgb_component_ids(self):
        """Test decoding an incorrect photometric interpretation using cIDs."""
        decoder = get_decoder(JPEGBaseline8Bit)
        reference = JPGB_08_08_3_0_1F_RGB
        msg = (
            r"The \(0028,0004\) 'Photometric Interpretation' value is "
            "'YBR_FULL_422' however the encoded image codestream for frame 0 uses "
            "component IDs that indicate it may be 'RGB'"
        )
        ds = dcmread(reference.path)
        ds.PhotometricInterpretation = "YBR_FULL_422"
        with pytest.warns(UserWarning, match=msg):
            arr, meta = decoder.as_array(ds, raw=True, decoding_plugin="pylibjpeg")

        reference.test(arr, plugin="pylibjpeg")
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable
        assert meta["photometric_interpretation"] == "RGB"

    def test_jfif(self):
        """Test decoding an incorrect photometric interpretation using JFIF."""
        decoder = get_decoder(JPEGBaseline8Bit)
        reference = JPGB_08_08_3_0_1F_YBR_FULL
        msg = (
            r"The \(0028,0004\) 'Photometric Interpretation' value is "
            "'RGB' however the encoded image codestream for frame 0 contains a JFIF "
            "APP marker which indicates it may be 'YBR_FULL_422'"
        )
        ds = dcmread(reference.path)
        ds.PhotometricInterpretation = "RGB"
        with pytest.warns(UserWarning, match=msg):
            arr, meta = decoder.as_array(ds, raw=True, decoding_plugin="pylibjpeg")

        reference.test(arr, plugin="pylibjpeg")
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable
        assert meta["photometric_interpretation"] == "YBR_FULL_422"

    def test_mixed_container_sizes(self):
        """Test mixed decoded pixel container sizes get upscaled."""
        d8 = get_frame(JLSL_08_07_1_0_1F.ds.PixelData, 0)
        d16 = get_frame(JLSL_16_15_1_1_1F.ds.PixelData, 0)

        ds = dcmread(JLSL_08_07_1_0_1F.path)
        ds.PixelData = encapsulate([d8, d16])
        ds.NumberOfFrames = 2
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 1

        decoder = get_decoder(JPEGLSLossless)
        buffer, meta = decoder.as_buffer(ds, decoding_plugin="pylibjpeg")
        assert meta[0]["bits_allocated"] == 16
        arr = np.frombuffer(buffer, dtype="<u2")
        arr = arr.reshape(2, ds.Rows, ds.Columns)
        JLSL_08_07_1_0_1F.test(arr[0], plugin="pylibjpeg")

        arr = arr.astype("<i2")
        # Needs bit-shifting to convert values to signed
        np.left_shift(arr, 1, out=arr)
        np.right_shift(arr, 1, out=arr)
        JLSL_16_15_1_1_1F.test(arr[1], plugin="pylibjpeg")

    def test_iter_array_ybr_to_rgb(self):
        """Test conversion from YBR to RGB for multi-framed data."""
        ds = JPGB_08_08_3_0_120F_YBR_FULL_422.ds
        assert ds.PhotometricInterpretation == "YBR_FULL_422"

        indices = [0, 60, -1]
        decoder = get_decoder(ds.file_meta.TransferSyntaxUID)
        func = decoder.iter_array(ds, decoding_plugin="pylibjpeg", indices=indices)
        for index, (arr, meta) in zip(indices, func):
            assert meta["photometric_interpretation"] == "RGB"
            JPGB_08_08_3_0_120F_YBR_FULL_422.test(
                arr, as_rgb=True, plugin="pylibjpeg", index=index
            )

    def test_iter_planar_configuration(self):
        """Test iter_pixels() with planar configuration."""
        ds = dcmread(JPGB_08_08_3_0_120F_YBR_FULL_422.path)
        decoder = get_decoder(ds.file_meta.TransferSyntaxUID)
        ds.PlanarConfiguration = 1

        # Always 0 when converting to an ndarray
        for _, meta in decoder.iter_array(ds, decoding_plugin="pylibjpeg"):
            assert meta["planar_configuration"] == 0

    def test_jls_shift_correction(self):
        """Regression test for #2260"""
        reference = JLSL_16_12_1_0_10F
        ds = dcmread(reference.path)
        ds.BitsStored = 8
        assert reference.ds.PixelRepresentation == 0
        decoder = get_decoder(JPEGLSLossless)

        arr, _ = decoder.as_array(ds, raw=True, decoding_plugin="pylibjpeg")
        # Would be [192 309 362 219 135] if no shift
        assert [192, 53, 106, 219, 135] == arr[0, -1, -5:].tolist()

        iterator = decoder.iter_array(ds, decoding_plugin="pylibjpeg")
        arr, _ = next(iterator)
        assert [192, 53, 106, 219, 135] == arr[-1, -5:].tolist()

    def test_jls_sign_correction_iter(self):
        """Test the JLS sign correction works with iter_array(..., indices=[...])"""
        reference = JLSL_16_15_1_1_1F
        assert reference.ds.PixelRepresentation == 1
        decoder = get_decoder(JPEGLSLossless)
        iterator = decoder.iter_array(
            reference.ds, indices=[0], decoding_plugin="pylibjpeg"
        )

        arr, _ = next(iterator)
        reference.test(arr)


@pytest.mark.skipif(SKIP_OJ, reason="Test is missing dependencies")
class TestOpenJpegDecoder:
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEG2000Lossless], ids=name)
    def test_j2k_lossless(self, reference):
        """Test the decoder with JPEG2000Lossless."""
        decoder = get_decoder(JPEG2000Lossless)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[JPEG2000], ids=name)
    def test_j2k(self, reference):
        """Test the decoder with JPEG2000."""
        decoder = get_decoder(JPEG2000)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[HTJ2KLossless], ids=name)
    def test_htj2k_lossless(self, reference):
        """Test the decoder with HTJ2KLossless."""
        decoder = get_decoder(HTJ2KLossless)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[HTJ2KLosslessRPCL], ids=name)
    def test_htj2k_lossless_rpcl(self, reference):
        """Test the decoder with HTJ2KLosslessRPCL."""
        decoder = get_decoder(HTJ2KLosslessRPCL)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[HTJ2K], ids=name)
    def test_htj2k(self, reference):
        """Test the decoder with HTJ2K."""
        decoder = get_decoder(HTJ2K)
        arr, _ = decoder.as_array(reference.ds, raw=True, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    def test_iter_array(self):
        """Test J2k corrections are applied when using iter_array()"""
        reference = J2KR_16_13_1_1_1F_M2_MISMATCH
        decoder = get_decoder(JPEG2000Lossless)
        # Using all frames
        frame_gen = decoder.iter_array(
            reference.ds, raw=True, decoding_plugin="pylibjpeg"
        )
        for arr, _ in frame_gen:
            reference.test(arr)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

        # Using indices
        frame_gen = decoder.iter_array(
            reference.ds, raw=True, decoding_plugin="pylibjpeg", indices=[0]
        )
        for arr, _ in frame_gen:
            reference.test(arr)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

    def test_j2k_sign_correction_indexed(self):
        """Test that sign correction works as expected with `index`"""
        reference = J2KR_16_13_1_1_1F_M2_MISMATCH
        decoder = get_decoder(JPEG2000Lossless)
        arr, meta = decoder.as_array(reference.ds, index=0, decoding_plugin="pylibjpeg")
        reference.test(arr)
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

    def test_j2k_sign_correction_iter(self):
        """Test that sign correction works as expected with iter_array()"""
        reference = J2KR_16_13_1_1_1F_M2_MISMATCH
        decoder = get_decoder(JPEG2000Lossless)
        for arr, _ in decoder.iter_array(reference.ds, decoding_plugin="pylibjpeg"):
            reference.test(arr)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

    @pytest.mark.parametrize("path", [J2KR_1_1_3F.path, J2KR_1_1_3F_NONALIGNED.path])
    def test_j2k_singlebit_as_buffer(self, path):
        """Test retrieving buffers from single bit J2K."""
        ds = dcmread(path)
        arr = ds.pixel_array
        n_pixels_per_frame = ds.Rows * ds.Columns
        n_pixels = n_pixels_per_frame * ds.NumberOfFrames

        decoder = get_decoder(JPEG2000Lossless)
        buffer, meta = decoder.as_buffer(ds, decoding_plugin="pylibjpeg")
        unpacked_buffer = unpack_bits(buffer)[:n_pixels]
        assert np.array_equal(unpacked_buffer, arr.flatten())

        for index in range(ds.NumberOfFrames):
            buffer, meta = decoder.as_buffer(
                ds, decoding_plugin="pylibjpeg", index=index
            )
            unpacked_buffer = unpack_bits(buffer)[:n_pixels_per_frame]
            assert np.array_equal(unpacked_buffer, arr[index].flatten())

    @pytest.mark.parametrize("path", [J2KR_1_1_3F.path, J2KR_1_1_3F_NONALIGNED.path])
    def test_j2k_singlebit_iter_buffer(self, path):
        """Test retrieving buffers from single bit J2K."""
        ds = dcmread(path)
        arr = ds.pixel_array
        nr_pixels = ds.Rows * ds.Columns

        decoder = get_decoder(JPEG2000Lossless)
        generator = decoder.iter_buffer(ds, decoding_plugin="pylibjpeg")
        for idx, (buffer, meta) in enumerate(generator):
            unpacked_buffer = unpack_bits(buffer)[:nr_pixels]
            assert np.array_equal(unpacked_buffer, arr[idx].flatten())

    def test_j2k_singlebit_excess(self):
        """Test retrieving buffers from single bit J2K with excess frames."""
        ds = dcmread(J2KR_1_1_3F.path)
        ds.NumberOfFrames = 2
        decoder = get_decoder(JPEG2000Lossless)
        msg = (
            "3 frames have been found in the encapsulated pixel data, which is "
            r"larger than the given \(0028,0008\) 'Number of Frames' value of 2. "
            "The returned data will include these extra frames and if it's correct "
            "then you should update 'Number of Frames' accordingly, otherwise pass "
            "'allow_excess_frames=False' to return only the first 2 frames."
        )
        with pytest.warns(UserWarning, match=msg):
            buffer, meta = decoder.as_buffer(ds, decoding_plugin="pylibjpeg")

        assert len(buffer) == (3 * 512 * 512) // 8
        assert len(meta) == 3

        buffer, meta = decoder.as_buffer(
            ds, allow_excess_frames=False, decoding_plugin="pylibjpeg"
        )
        assert len(buffer) == (2 * 512 * 512) // 8
        assert len(meta) == 2

    def test_j2k_shift_correction(self):
        """Regression test for #2260"""
        reference = J2KR_16_13_1_1_1F_M2_MISMATCH
        ds = dcmread(reference.path)
        ds.PixelRepresentation = 0
        ds.BitsStored = 12

        decoder = get_decoder(JPEG2000Lossless)
        arr, _ = decoder.as_array(ds, index=0, decoding_plugin="pylibjpeg")
        assert arr.dtype.kind == "u"
        assert arr.dtype.itemsize == 2

        # Without a shift this would be 6192
        assert 2096 == arr[0, 0]
        assert [621, 412, 138, 3903, 3576, 3329, 3189, 3130, 3108, 3101] == (
            arr[47:57, 279].tolist()
        )
        assert [3719, 3975, 141, 383, 633, 910, 1198, 1455, 1638, 1732] == (
            arr[328:338, 106].tolist()
        )

        iterator = decoder.iter_array(ds, decoding_plugin="pylibjpeg")
        arr, _ = next(iterator)
        assert 2096 == arr[0, 0]
        assert [621, 412, 138, 3903, 3576, 3329, 3189, 3130, 3108, 3101] == (
            arr[47:57, 279].tolist()
        )
        assert [3719, 3975, 141, 383, 633, 910, 1198, 1455, 1638, 1732] == (
            arr[328:338, 106].tolist()
        )

        iterator = decoder.iter_array(ds, indices=[0], decoding_plugin="pylibjpeg")
        arr, _ = next(iterator)
        assert 2096 == arr[0, 0]
        assert [621, 412, 138, 3903, 3576, 3329, 3189, 3130, 3108, 3101] == (
            arr[47:57, 279].tolist()
        )
        assert [3719, 3975, 141, 383, 633, 910, 1198, 1455, 1638, 1732] == (
            arr[328:338, 106].tolist()
        )


@pytest.mark.skipif(SKIP_RLE, reason="Test is missing dependencies")
class TestRleDecoder:
    @pytest.mark.parametrize("reference", PIXEL_REFERENCE[RLELossless], ids=name)
    def test_rle(self, reference):
        """Test the decoder with RLELossless."""
        decoder = get_decoder(RLELossless)
        arr, meta = decoder.as_array(
            reference.ds, raw=True, decoding_plugin="pylibjpeg"
        )
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        if meta["samples_per_pixel"] > 1:
            assert meta["planar_configuration"] == 0

        buffer, meta = decoder.as_buffer(
            reference.ds, raw=True, decoding_plugin="pylibjpeg"
        )
        for idx in meta:
            if meta[idx]["samples_per_pixel"] > 1:
                assert meta[idx]["planar_configuration"] == 1

    def test_singlebit_raises(self):
        """Currently single bit is not supported, check error raised."""
        reference = RLE_1_1_3F
        decoder = get_decoder(RLELossless)
        msg = (
            "Unable to decode as exceptions were raised by all "
            "available plugins:\n  pylibjpeg: pylibjpeg cannot "
            r"decompress RLE Lossless encoded data with \(0028,0100\) 'Bits "
            "Allocated' = 1"
        )
        with pytest.raises(RuntimeError, match=msg):
            decoder.as_array(reference.ds, decoding_plugin="pylibjpeg")
