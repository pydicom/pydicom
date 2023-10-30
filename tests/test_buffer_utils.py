from io import BytesIO
import pytest

from pydicom.util.buffers import buffer_length, read_bytes, reset_buffer_position


class TestBufferUtils:
    @pytest.mark.parametrize(
        "buffer_data",
        (
            b"\x00\x01\x02\x03",
            b"",
            # big value
            bytes(("0" * 10_000), encoding="utf-8"),
        ),
    )
    @pytest.mark.parametrize("chunk_size", (None, 1, 100_000_000))
    def test_reading_data_from_a_buffer(self, buffer_data, chunk_size):
        buffer = BytesIO(buffer_data)
        data = b""

        kwargs = {}
        if chunk_size:
            # used for testing the default value
            kwargs["chunk_size"] = chunk_size

        for chunk in read_bytes(buffer, **kwargs):
            data += chunk

        assert data == buffer_data

    def test_reading_data_from_a_buffer_from_middle_of_buffer(self):
        buffer = BytesIO(b"\x00\x01\x02\x03")
        buffer.seek(2)

        data = b""
        for chunk in read_bytes(buffer):
            data += chunk

        assert data == b"\x02\x03"

    @pytest.mark.parametrize(
        "chunk_size",
        (
            0,
            -1,
        ),
    )
    def test_invalid_inputs_to_read_bytes(self, chunk_size):
        with pytest.raises(AssertionError, match="chunk_size must be > 0"):
            next(read_bytes(BytesIO(), chunk_size=chunk_size))

    def test_reading_bytes_from_buffer_does_not_reset_buffer_position(self):
        buffer = BytesIO(b"\x00\x01\x02\x03")
        for _ in read_bytes(buffer):
            pass

        assert buffer.tell() == 4

    def test_reading_length_of_buffer(self):
        buffer = BytesIO(b"\x00\x01\x02\x03")
        assert buffer_length(buffer) == 4

        # reset back to position
        assert buffer.tell() == 0

    def test_reading_length_of_buffer_from_last_position(self):
        buffer = BytesIO(b"\x00\x01\x02\x03")
        buffer.seek(2)

        assert buffer_length(buffer) == 2

        # reset back to position
        assert buffer.tell() == 2

    def test_reset_buffer_position(self):
        buffer = BytesIO(b"\x00\x01\x02\x03")
        with reset_buffer_position(buffer):
            buffer.read()

        assert buffer.tell() == 0

    def test_reset_buffer_position_from_last_position(self):
        buffer = BytesIO(b"\x00\x01\x02\x03")
        buffer.seek(2)
        with reset_buffer_position(buffer):
            buffer.read()

        assert buffer.tell() == 2

    def test_reset_buffer_position_yields_starting_position(self):
        buffer = BytesIO(b"\x00\x01\x02\x03")
        buffer.seek(2)
        with reset_buffer_position(buffer) as start_position:
            assert start_position == 2
            buffer.read()

        assert buffer.tell() == 2
