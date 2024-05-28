"""Tests for the RLELosslessDecoder and the pydicom RLE plugin."""

from io import BytesIO
from struct import pack, unpack

import pytest

from pydicom import dcmread
from pydicom.config import debug
from pydicom.encaps import get_frame, generate_frames, encapsulate
from pydicom.pixels import get_decoder
from pydicom.pixels.decoders import RLELosslessDecoder
from pydicom.pixels.decoders.rle import (
    _rle_parse_header,
    _rle_decode_segment,
    _rle_decode_frame,
)
from pydicom.uid import RLELossless, ExplicitVRLittleEndian

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False


from .pixels_reference import PIXEL_REFERENCE, RLE_16_1_1F, RLE_16_1_10F

RLE_REFERENCE = PIXEL_REFERENCE[RLELossless]


def name(ref):
    return f"{ref.name}"


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
class TestAsArray:
    """Tests for as_array() with RLE lossless"""

    def setup_method(self):
        self.decoder = get_decoder(RLELossless)

    @pytest.mark.parametrize("reference", RLE_REFERENCE, ids=name)
    def test_reference(self, reference):
        """Test against the reference data for RLE lossless using dataset."""
        arr, _ = self.decoder.as_array(
            reference.ds, raw=True, decoding_plugin="pydicom"
        )
        reference.test(arr)
        assert arr.shape == reference.shape
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable

        for index in range(reference.number_of_frames):
            arr, meta = self.decoder.as_array(
                reference.ds, raw=True, index=index, decoding_plugin="pydicom"
            )
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

            if reference.ds.SamplesPerPixel > 1:
                # The returned array is always planar configuration 0
                assert meta["planar_configuration"] == 0

    @pytest.mark.parametrize("reference", RLE_REFERENCE, ids=name)
    def test_reference_binary(self, reference):
        """Test against the reference data for RLE lossless using binary IO."""
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
            arr, _ = self.decoder.as_array(
                f, raw=True, decoding_plugin="pydicom", **opts
            )
            reference.test(arr)
            assert arr.shape == reference.shape
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            for index in range(reference.number_of_frames):
                arr, _ = self.decoder.as_array(
                    f, raw=True, index=index, decoding_plugin="pydicom", **opts
                )
                reference.test(arr, index=index)
                assert arr.dtype == reference.dtype
                assert arr.flags.writeable

                if reference.number_of_frames == 1:
                    assert arr.shape == reference.shape
                else:
                    assert arr.shape == reference.shape[1:]

                assert f.tell() == file_offset

    def test_little_endian_segment_order(self):
        """Test interpreting segment order as little endian."""
        ds = RLE_16_1_1F.ds

        arr, _ = self.decoder.as_array(
            ds, rle_segment_order="<", decoding_plugin="pydicom"
        )
        assert arr.dtype == RLE_16_1_1F.dtype
        assert arr.shape == RLE_16_1_1F.shape
        assert tuple(arr[0, 31:34]) == (-23039, 16129, 26881)
        assert tuple(arr[31, :3]) == (28161, 27393, 16897)
        assert tuple(arr[-1, -3:]) == (22789, 26884, 24067)

        assert not np.array_equal(self.decoder.as_array(ds, rle_segment_order=">"), arr)

    def test_index_greater_than_frames(self):
        """Test being able to index an extra frame."""
        # Issue 1666
        reference = RLE_16_1_10F
        # Override NumberOfFrames to 9 and try and get the 10th frame
        arr, _ = self.decoder.as_array(
            reference.ds, number_of_frames=9, index=9, decoding_plugin="pydicom"
        )
        reference.test(arr, index=9)
        assert arr.dtype == reference.dtype
        assert arr.flags.writeable
        assert arr.shape == reference.shape[1:]


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
class TestIterArray:
    """Tests for iter_array() with RLE lossless"""

    def setup_method(self):
        self.decoder = get_decoder(RLELossless)

    @pytest.mark.parametrize("reference", RLE_REFERENCE, ids=name)
    def test_reference(self, reference):
        """Test against the reference data for RLE lossless."""
        func = self.decoder.iter_array(
            reference.ds, raw=True, decoding_plugin="pydicom"
        )
        for index, (arr, meta) in enumerate(func):
            reference.test(arr, index=index)
            assert arr.dtype == reference.dtype
            assert arr.flags.writeable

            if reference.number_of_frames == 1:
                assert arr.shape == reference.shape
            else:
                assert arr.shape == reference.shape[1:]

            if reference.ds.SamplesPerPixel > 1:
                # The returned array is always planar configuration 0
                assert meta["planar_configuration"] == 0

    @pytest.mark.parametrize("reference", RLE_REFERENCE, ids=name)
    def test_reference_binary(self, reference):
        """Test against the reference data for RLE lossless for binary IO."""
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
            func = self.decoder.iter_array(
                f, raw=True, decoding_plugin="pydicom", **opts
            )
            for index, (arr, _) in enumerate(func):
                reference.test(arr, index=index)
                assert arr.dtype == reference.dtype
                assert arr.flags.writeable

                if reference.number_of_frames == 1:
                    assert arr.shape == reference.shape
                else:
                    assert arr.shape == reference.shape[1:]

            assert f.tell() == file_offset

    def test_indices(self):
        """Test the `indices` argument."""
        indices = [0, 4, 9]
        func = self.decoder.iter_array(
            RLE_16_1_10F.ds, raw=True, indices=indices, decoding_plugin="pydicom"
        )
        for idx, (arr, _) in enumerate(func):
            RLE_16_1_10F.test(arr, index=indices[idx])
            assert arr.dtype == RLE_16_1_10F.dtype
            assert arr.flags.writeable
            assert arr.shape == RLE_16_1_10F.shape[1:]

        assert idx == 2


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
class TestAsBuffer:
    """Tests for as_buffer() with RLELossless."""

    def setup_method(self):
        self.decoder = get_decoder(RLELossless)

    @pytest.mark.parametrize("reference", RLE_REFERENCE, ids=name)
    def test_reference(self, reference):
        """Test against the reference data for RLE lossless."""
        ds = reference.ds
        arr, _ = self.decoder.as_array(
            reference.ds, raw=True, decoding_plugin="pydicom"
        )
        buffer, meta = self.decoder.as_buffer(reference.ds)

        frame_len = ds.Rows * ds.Columns * ds.SamplesPerPixel * ds.BitsAllocated // 8

        for index in range(reference.number_of_frames):
            if reference.number_of_frames == 1:
                arr_frame = arr
                buffer_frame = buffer
            else:
                arr_frame = arr[index, ...]
                start = index * frame_len
                buffer_frame = buffer[start : start + frame_len]

            if ds.SamplesPerPixel == 1:
                assert arr_frame.tobytes() == buffer_frame
            else:
                assert meta["planar_configuration"] == 1
                # Red
                arr_plane = arr_frame[..., 0].tobytes()
                plane_length = len(arr_plane)
                buf_plane = buffer_frame[:plane_length]
                assert arr_plane == buf_plane
                # Green
                arr_plane = arr_frame[..., 1].tobytes()
                buf_plane = buffer_frame[plane_length : 2 * plane_length]
                assert arr_plane == buf_plane
                # Blue
                arr_plane = arr_frame[..., 2].tobytes()
                buf_plane = buffer_frame[2 * plane_length :]
                assert arr_plane == buf_plane

    @pytest.mark.parametrize("reference", RLE_REFERENCE, ids=name)
    def test_reference_binary(self, reference):
        """Test against the reference data for RLE lossless for binary IO."""
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
            arr, _ = self.decoder.as_array(
                f, raw=True, decoding_plugin="pydicom", **opts
            )
            assert f.tell() == file_offset
            buffer, _ = self.decoder.as_buffer(f, **opts)
            assert f.tell() == file_offset

            frame_len = (
                ds.Rows * ds.Columns * ds.SamplesPerPixel * ds.BitsAllocated // 8
            )

            for index in range(reference.number_of_frames):
                if reference.number_of_frames == 1:
                    arr_frame = arr
                    buffer_frame = buffer
                else:
                    arr_frame = arr[index, ...]
                    start = index * frame_len
                    buffer_frame = buffer[start : start + frame_len]

                if ds.SamplesPerPixel == 1:
                    assert arr_frame.tobytes() == buffer_frame
                else:
                    # Red
                    arr_plane = arr_frame[..., 0].tobytes()
                    plane_length = len(arr_plane)
                    buf_plane = buffer_frame[:plane_length]
                    assert arr_plane == buf_plane
                    # Green
                    arr_plane = arr_frame[..., 1].tobytes()
                    buf_plane = buffer_frame[plane_length : 2 * plane_length]
                    assert arr_plane == buf_plane
                    # Blue
                    arr_plane = arr_frame[..., 2].tobytes()
                    buf_plane = buffer_frame[2 * plane_length :]
                    assert arr_plane == buf_plane

    @pytest.mark.parametrize("reference", RLE_REFERENCE, ids=name)
    def test_reference_index(self, reference):
        """Test by `index` for RLE lossless"""
        ds = reference.ds
        for index in range(reference.number_of_frames):
            arr, _ = self.decoder.as_array(
                reference.ds, raw=True, index=index, decoding_plugin="pydicom"
            )
            buffer, _ = self.decoder.as_buffer(
                reference.ds, index=index, decoding_plugin="pydicom"
            )

            if ds.SamplesPerPixel == 1:
                assert arr.tobytes() == buffer
            else:
                # Red
                arr_plane = arr[..., 0].tobytes()
                plane_length = len(arr_plane)
                buf_plane = buffer[:plane_length]
                assert arr_plane == buf_plane
                # Green
                arr_plane = arr[..., 1].tobytes()
                buf_plane = buffer[plane_length : 2 * plane_length]
                assert arr_plane == buf_plane
                # Blue
                arr_plane = arr[..., 2].tobytes()
                buf_plane = buffer[2 * plane_length :]
                assert arr_plane == buf_plane

    @pytest.mark.parametrize("reference", RLE_REFERENCE, ids=name)
    def test_reference_index_binary(self, reference):
        """Test by `index` for RLE lossless for binary IO"""
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
            for index in range(reference.number_of_frames):
                arr, _ = self.decoder.as_array(
                    f, raw=True, index=index, decoding_plugin="pydicom", **opts
                )
                assert f.tell() == file_offset
                buffer, _ = self.decoder.as_buffer(
                    f, index=index, decoding_plugin="pydicom", **opts
                )
                assert f.tell() == file_offset

                if ds.SamplesPerPixel == 1:
                    assert arr.tobytes() == buffer
                else:
                    # Red
                    arr_plane = arr[..., 0].tobytes()
                    plane_length = len(arr_plane)
                    buf_plane = buffer[:plane_length]
                    assert arr_plane == buf_plane
                    # Green
                    arr_plane = arr[..., 1].tobytes()
                    buf_plane = buffer[plane_length : 2 * plane_length]
                    assert arr_plane == buf_plane
                    # Blue
                    arr_plane = arr[..., 2].tobytes()
                    buf_plane = buffer[2 * plane_length :]
                    assert arr_plane == buf_plane


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
class TestIterBuffer:
    """Tests for iter_buffer() with RLELossless."""

    def setup_method(self):
        self.decoder = get_decoder(RLELossless)

    @pytest.mark.parametrize("reference", RLE_REFERENCE, ids=name)
    def test_reference(self, reference):
        """Test against the reference data for RLE lossless."""
        arr_func = self.decoder.iter_array(
            reference.ds, raw=True, decoding_plugin="pydicom"
        )
        buf_func = self.decoder.iter_buffer(
            reference.ds, raw=True, decoding_plugin="pydicom"
        )

        for (arr, _), (buf, meta) in zip(arr_func, buf_func):
            if reference.ds.SamplesPerPixel == 3:
                # If samples per pixel is 3 then bytes are planar configuration 1
                assert meta["planar_configuration"] == 1
                # Red
                arr_frame = arr[..., 0].tobytes()
                frame_len = len(arr_frame)
                buf_frame = buf[:frame_len]
                assert arr_frame == buf_frame
                # Green
                arr_frame = arr[..., 1].tobytes()
                buf_frame = buf[frame_len : 2 * frame_len]
                assert arr_frame == buf_frame
                # Blue
                arr_frame = arr[..., 2].tobytes()
                buf_frame = buf[2 * frame_len :]
                assert arr_frame == buf_frame
            else:
                assert arr.tobytes() == buf

    @pytest.mark.parametrize("reference", RLE_REFERENCE, ids=name)
    def test_reference_binary(self, reference):
        """Test against the reference data for RLE lossless for binary IO."""
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

            # Can't do two encapsulated iters at once with binary IO...
            arr_func = self.decoder.iter_array(
                f, raw=True, decoding_plugin="pydicom", **opts
            )
            arrays = [arr for arr in arr_func]
            assert f.tell() == file_offset
            buf_func = self.decoder.iter_buffer(
                f, raw=True, decoding_plugin="pydicom", **opts
            )
            for (arr, _), (buf, _) in zip(arrays, buf_func):
                if reference.ds.SamplesPerPixel == 3:
                    # If samples per pixel is 3 then bytes are planar configuration 1
                    # Red
                    arr_frame = arr[..., 0].tobytes()
                    frame_len = len(arr_frame)
                    buf_frame = buf[:frame_len]
                    assert arr_frame == buf_frame
                    # Green
                    arr_frame = arr[..., 1].tobytes()
                    buf_frame = buf[frame_len : 2 * frame_len]
                    assert arr_frame == buf_frame
                    # Blue
                    arr_frame = arr[..., 2].tobytes()
                    buf_frame = buf[2 * frame_len :]
                    assert arr_frame == buf_frame
                else:
                    assert arr.tobytes() == buf

            pytest.raises(StopIteration, next, buf_func)
            assert f.tell() == file_offset

    def test_indices(self):
        """Test the `indices` argument."""
        indices = [0, 4, 9]
        arr_func = self.decoder.iter_array(
            RLE_16_1_10F.ds, raw=True, indices=indices, decoding_plugin="pydicom"
        )
        buf_func = self.decoder.iter_buffer(
            RLE_16_1_10F.ds, raw=True, indices=indices, decoding_plugin="pydicom"
        )
        for idx, ((arr, _), (buf, _)) in enumerate(zip(arr_func, buf_func)):
            assert arr.tobytes() == buf

        assert idx == 2


# RLE encodes data by first splitting a frame into 8-bit segments
BAD_SEGMENT_DATA = [
    # (RLE header, ds.SamplesPerPixel, ds.BitsAllocated)
    (b"\x00\x00\x00\x00", 1, 8),  # 0 segments, 1 expected
    (b"\x02\x00\x00\x00", 1, 8),  # 2 segments, 1 expected
    (b"\x02\x00\x00\x00", 3, 8),  # 2 segments, 3 expected
    (b"\x04\x00\x00\x00", 3, 8),  # 4 segments, 3 expected
    (b"\x01\x00\x00\x00", 1, 16),  # 1 segment, 2 expected
    (b"\x03\x00\x00\x00", 1, 16),  # 3 segments, 2 expected
    (b"\x05\x00\x00\x00", 3, 16),  # 5 segments, 6 expected
    (b"\x07\x00\x00\x00", 3, 16),  # 7 segments, 6 expected
    (b"\x03\x00\x00\x00", 1, 32),  # 3 segments, 4 expected
    (b"\x05\x00\x00\x00", 1, 32),  # 5 segments, 4 expected
    (b"\x0B\x00\x00\x00", 3, 32),  # 11 segments, 12 expected
    (b"\x0D\x00\x00\x00", 3, 32),  # 13 segments, 12 expected
    (b"\x07\x00\x00\x00", 1, 64),  # 7 segments, 8 expected
    (b"\x09\x00\x00\x00", 1, 64),  # 9 segments, 8 expected
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


class TestParseHeader:
    """Tests for _rle_parse_header()."""

    def test_invalid_header_length(self):
        """Test exception raised if header is not 64 bytes long."""
        for length in [0, 1, 63, 65]:
            msg = r"RLE header can only be 64 bytes long"
            with pytest.raises(ValueError, match=msg):
                _rle_parse_header(b"\x00" * length)

    def test_invalid_nr_segments_raises(self):
        """Test that more than 15 segments raises exception."""
        with pytest.raises(ValueError, match="invalid number of segments"):
            _rle_parse_header(b"\x10" + b"\x00" * 63)

    @pytest.mark.parametrize("nr_segments, offsets", HEADER_DATA)
    def test_parse_header(self, nr_segments, offsets):
        """Test parsing header data."""
        # Encode the header
        header = bytearray()
        header.extend(pack("<L", nr_segments))
        header.extend(pack(f"<{len(offsets)}L", *offsets))
        # Add padding
        header.extend(b"\x00" * (64 - len(header)))

        assert len(header) == 64
        assert _rle_parse_header(header) == offsets


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
class TestDecodeFrame:
    """Tests for _rle_decode_frame()."""

    def test_unsupported_bits_allocated_raises(self):
        """Test exception raised for BitsAllocated not a multiple of 8."""
        msg = r"Unable to decode RLE encoded pixel data with 12 bits allocated"
        with pytest.raises(NotImplementedError, match=msg):
            _rle_decode_frame(b"\x00\x00\x00\x00", 1, 1, 1, 12)

    @pytest.mark.parametrize("header,samples,bits", BAD_SEGMENT_DATA)
    def test_invalid_nr_segments_raises(self, header, samples, bits):
        """Test having too many segments in the data raises exception."""
        # This should probably be ValueError
        expected = samples * bits // 8
        actual = unpack("<L", header)[0]
        header += b"\x00" * (64 - len(header))
        msg = rf"expected amount \({actual} vs. {expected} segments\)"
        with pytest.raises(ValueError, match=msg):
            _rle_decode_frame(
                header, rows=1, columns=1, nr_samples=samples, nr_bits=bits
            )

    def test_invalid_segment_data_raises(self):
        """Test invalid segment data raises exception"""
        ds = RLE_16_1_1F.ds
        pixel_data = get_frame(ds.PixelData, 0)
        msg = r"amount \(4095 vs. 4096 bytes\)"
        with pytest.raises(ValueError, match=msg):
            _rle_decode_frame(
                pixel_data[:-1],
                ds.Rows,
                ds.Columns,
                ds.SamplesPerPixel,
                ds.BitsAllocated,
            )

    def test_nonconf_segment_padding_warns(self):
        """Test non-conformant segment padding warns"""
        ds = RLE_16_1_1F.ds
        pixel_data = get_frame(ds.PixelData, 0)
        msg = (
            r"The decoded RLE segment contains non-conformant padding - 4097 "
            r"vs. 4096 bytes expected"
        )
        with pytest.warns(UserWarning, match=msg):
            _rle_decode_frame(
                pixel_data + b"\x00\x01", 4096, 1, ds.SamplesPerPixel, ds.BitsAllocated
            )

    def test_8bit_1sample(self):
        """Test decoding 8-bit, 1 sample/pixel."""
        header = b"\x01\x00\x00\x00\x40\x00\x00\x00"
        header += (64 - len(header)) * b"\x00"
        # 2 x 3 data
        # 0, 64, 128, 160, 192, 255
        data = b"\x05\x00\x40\x80\xA0\xC0\xFF"
        decoded = _rle_decode_frame(header + data, 2, 3, 1, 8)
        arr = np.frombuffer(decoded, np.dtype("|u1"))
        assert arr.tolist() == [0, 64, 128, 160, 192, 255]

    def test_8bit_3sample(self):
        """Test decoding 8-bit, 3 sample/pixel."""
        header = (
            b"\x03\x00\x00\x00"  # 3 segments
            b"\x40\x00\x00\x00"  # 64
            b"\x47\x00\x00\x00"  # 71
            b"\x4E\x00\x00\x00"  # 78
        )
        header += (64 - len(header)) * b"\x00"
        # 2 x 3 data
        # 0, 64, 128, 160, 192, 255
        data = (
            b"\x05\x00\x40\x80\xA0\xC0\xFF"  # R
            b"\x05\xFF\xC0\x80\x40\x00\xFF"  # B
            b"\x05\x01\x40\x80\xA0\xC0\xFE"  # G
        )
        decoded = _rle_decode_frame(header + data, 2, 3, 3, 8)
        arr = np.frombuffer(decoded, np.dtype("|u1"))
        # Ordered all R, all G, all B
        assert arr[:6].tolist() == [0, 64, 128, 160, 192, 255]
        assert arr[6:12].tolist() == [255, 192, 128, 64, 0, 255]
        assert arr[12:].tolist() == [1, 64, 128, 160, 192, 254]

    def test_16bit_1sample(self):
        """Test decoding 16-bit, 1 sample/pixel."""
        header = b"\x02\x00\x00\x00\x40\x00\x00\x00\x47\x00\x00\x00"
        header += (64 - len(header)) * b"\x00"
        # 2 x 3 data
        data = (
            # 0, 1, 256, 255, 65280, 65535
            b"\x05\x00\x00\x01\x00\xFF\xFF"  # MSB
            b"\x05\x00\x01\x00\xFF\x00\xFF"  # LSB
        )
        decoded = _rle_decode_frame(header + data, 2, 3, 1, 16)
        arr = np.frombuffer(decoded, np.dtype("<u2"))
        assert arr.tolist() == [0, 1, 256, 255, 65280, 65535]

    def test_16bit_3sample(self):
        """Test decoding 16-bit, 3 sample/pixel."""
        header = (
            b"\x06\x00\x00\x00"  # 6 segments
            b"\x40\x00\x00\x00"  # 64
            b"\x47\x00\x00\x00"  # 71
            b"\x4E\x00\x00\x00"  # 78
            b"\x55\x00\x00\x00"  # 85
            b"\x5C\x00\x00\x00"  # 92
            b"\x63\x00\x00\x00"  # 99
        )
        header += (64 - len(header)) * b"\x00"
        # 2 x 3 data
        data = (
            # 0, 1, 256, 255, 65280, 65535
            b"\x05\x00\x00\x01\x00\xFF\xFF"  # MSB
            b"\x05\x00\x01\x00\xFF\x00\xFF"  # LSB
            b"\x05\xFF\x00\x01\x00\xFF\x00"  # MSB
            b"\x05\xFF\x01\x00\xFF\x00\x00"  # LSB
            b"\x05\x00\x00\x01\x00\xFF\xFF"  # MSB
            b"\x05\x01\x01\x00\xFF\x00\xFE"  # LSB
        )
        decoded = _rle_decode_frame(header + data, 2, 3, 3, 16)
        arr = np.frombuffer(decoded, np.dtype("<u2"))
        assert arr[:6].tolist() == [0, 1, 256, 255, 65280, 65535]
        assert arr[6:12].tolist() == [65535, 1, 256, 255, 65280, 0]
        assert arr[12:].tolist() == [1, 1, 256, 255, 65280, 65534]

    def test_32bit_1sample(self):
        """Test decoding 32-bit, 1 sample/pixel."""
        header = (
            b"\x04\x00\x00\x00"  # 4 segments
            b"\x40\x00\x00\x00"  # 64 offset
            b"\x47\x00\x00\x00"  # 71 offset
            b"\x4E\x00\x00\x00"  # 78 offset
            b"\x55\x00\x00\x00"  # 85 offset
        )
        header += (64 - len(header)) * b"\x00"
        # 2 x 3 data
        data = (
            # 0, 16777216, 65536, 256, 4294967295
            b"\x05\x00\x01\x00\x00\x00\xFF"  # MSB
            b"\x05\x00\x00\x01\x00\x00\xFF"
            b"\x05\x00\x00\x00\x01\x00\xFF"
            b"\x05\x00\x00\x00\x00\x01\xFF"  # LSB
        )
        decoded = _rle_decode_frame(header + data, 2, 3, 1, 32)
        arr = np.frombuffer(decoded, np.dtype("<u4"))
        assert arr.tolist() == [0, 16777216, 65536, 256, 1, 4294967295]

    def test_32bit_3sample(self):
        """Test decoding 32-bit, 3 sample/pixel."""
        header = (
            b"\x0C\x00\x00\x00"  # 12 segments
            b"\x40\x00\x00\x00"  # 64
            b"\x47\x00\x00\x00"  # 71
            b"\x4E\x00\x00\x00"  # 78
            b"\x55\x00\x00\x00"  # 85
            b"\x5C\x00\x00\x00"  # 92
            b"\x63\x00\x00\x00"  # 99
            b"\x6A\x00\x00\x00"  # 106
            b"\x71\x00\x00\x00"  # 113
            b"\x78\x00\x00\x00"  # 120
            b"\x7F\x00\x00\x00"  # 127
            b"\x86\x00\x00\x00"  # 134
            b"\x8D\x00\x00\x00"  # 141
        )
        header += (64 - len(header)) * b"\x00"
        # 2 x 3 data
        data = (
            # 0, 16777216, 65536, 256, 4294967295
            b"\x05\x00\x01\x00\x00\x00\xFF"  # MSB
            b"\x05\x00\x00\x01\x00\x00\xFF"
            b"\x05\x00\x00\x00\x01\x00\xFF"
            b"\x05\x00\x00\x00\x00\x01\xFF"  # LSB
            b"\x05\xFF\x01\x00\x00\x00\x00"  # MSB
            b"\x05\xFF\x00\x01\x00\x00\x00"
            b"\x05\xFF\x00\x00\x01\x00\x00"
            b"\x05\xFF\x00\x00\x00\x01\x00"  # LSB
            b"\x05\x00\x01\x00\x00\x00\xFF"  # MSB
            b"\x05\x00\x00\x01\x00\x00\xFF"
            b"\x05\x00\x00\x00\x01\x00\xFF"
            b"\x05\x01\x00\x00\x00\x01\xFE"  # LSB
        )
        decoded = _rle_decode_frame(header + data, 2, 3, 3, 32)
        arr = np.frombuffer(decoded, np.dtype("<u4"))
        assert arr[:6].tolist() == [0, 16777216, 65536, 256, 1, 4294967295]
        assert arr[6:12].tolist() == [4294967295, 16777216, 65536, 256, 1, 0]
        assert arr[12:].tolist() == [1, 16777216, 65536, 256, 1, 4294967294]


class TestDecodeSegment:
    """Tests for _rle_decode_segment().

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
        data = b"\x80\x80\x80"
        assert bytes(_rle_decode_segment(data)) == b""

        # noop at start, data after
        data = (
            b"\x80\x80"  # No operation
            b"\x05\x01\x02\x03\x04\x05\x06"  # Literal
            b"\xFE\x01"  # Copy
            b"\x80"
        )
        assert bytes(_rle_decode_segment(data)) == (
            b"\x01\x02\x03\x04\x05\x06\x01\x01\x01"
        )

        # data at start, noop middle, data at end
        data = (
            b"\x05\x01\x02\x03\x04\x05\x06"  # Literal
            b"\x80"  # No operation
            b"\xFE\x01"  # Copy
            b"\x80"
        )
        assert bytes(_rle_decode_segment(data)) == (
            b"\x01\x02\x03\x04\x05\x06\x01\x01\x01"
        )

        # data at start, noop end
        # Copy 6 bytes literally, then 3 x 0x01
        data = b"\x05\x01\x02\x03\x04\x05\x06\xFE\x01\x80"
        assert bytes(_rle_decode_segment(data)) == (
            b"\x01\x02\x03\x04\x05\x06\x01\x01\x01"
        )

    def test_literal(self):
        """Test literal output."""
        # For n < 128, read the next (n + 1) bytes literally
        # n = 0 (0x80 is 128 -> no operation)
        data = b"\x00\x02\x80"
        assert bytes(_rle_decode_segment(data)) == b"\x02"
        # n = 1
        data = b"\x01\x02\x03\x80"
        assert bytes(_rle_decode_segment(data)) == b"\x02\x03"
        # n = 127
        data = b"\x7f" + b"\x40" * 128 + b"\x80"
        assert bytes(_rle_decode_segment(data)) == b"\x40" * 128

    def test_copy(self):
        """Test copy output."""
        # For n > 128, copy the next byte (257 - n) times
        # n = 255, copy x2 (0x80 is 128 -> no operation)
        data = b"\xFF\x02\x80"
        assert bytes(_rle_decode_segment(data)) == b"\x02\x02"
        # n = 254, copy x3
        data = b"\xFE\x02\x80"
        assert bytes(_rle_decode_segment(data)) == b"\x02\x02\x02"
        # n = 129, copy x128
        data = b"\x81\x02\x80"
        assert bytes(_rle_decode_segment(data)) == b"\x02" * 128


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
def test_dataset_decompress():
    """Test Dataset.decompress with RLE Lossless"""
    ds = dcmread(RLE_16_1_1F.path)
    ref = ds.pixel_array
    ds.decompress(decoding_plugin="pydicom")

    assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
    elem = ds["PixelData"]
    assert len(elem.value) == ds.Rows * ds.Columns * (ds.BitsAllocated // 8)
    assert elem.is_undefined_length is False
    assert elem.VR == "OW"
    assert "NumberOfFrames" not in ds
    assert ds._pixel_array is None
    assert ds._pixel_id == {}
    assert np.array_equal(ds.pixel_array, ref)
