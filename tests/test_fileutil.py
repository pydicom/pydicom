# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Test suite for util functions"""
from io import BytesIO, RawIOBase
from pathlib import Path
import platform
import tempfile

import pytest

from pydicom.config import settings
from pydicom.fileutil import (
    path_from_pathlike,
    check_buffer,
    reset_buffer_position,
    read_buffer,
    buffer_remaining,
    buffer_length,
    buffer_equality,
)


IS_WINDOWS = platform.system() == "Windows"


class PathLike:
    """Minimal example for path-like object"""

    def __init__(self, path: str):
        self.path = path

    def __fspath__(self):
        return self.path


class TestPathFromPathLike:
    """Test the fileutil module"""

    def test_non_pathlike_is_returned_unaltered(self):
        assert "test.dcm" == path_from_pathlike("test.dcm")
        assert path_from_pathlike(None) is None
        file_like = BytesIO()
        assert file_like == path_from_pathlike(file_like)
        assert 42 == path_from_pathlike(42)

    def test_pathlib_path(self):
        assert "test.dcm" == path_from_pathlike(Path("test.dcm"))

    def test_path_like(self):
        assert "test.dcm" == path_from_pathlike(PathLike("test.dcm"))


@pytest.fixture
def reset_buffered_read_size():
    original = settings.buffered_read_size
    yield
    settings.buffered_read_size = original


class TestBufferFunctions:
    """Test for the buffer functions"""

    @pytest.mark.skipif(IS_WINDOWS, reason="Running on Windows")
    def test_check_buffer(self):
        """Test check_buffer()"""
        # Invalid type
        msg = "the buffer must inherit from 'io.BufferedIOBase'"
        with pytest.raises(TypeError, match=msg):
            check_buffer(None)

        b = BytesIO()
        assert b.readable()
        assert b.seekable()
        assert not b.closed
        check_buffer(b)

        # Buffer has been closed
        b.close()
        assert b.closed

        msg = "the buffer has been closed"
        with pytest.raises(ValueError, match=msg):
            check_buffer(b)

        # Buffer is not readable
        msg = "the buffer must be readable and seekable"
        with pytest.raises(ValueError, match=msg):
            with tempfile.TemporaryFile(mode="wb") as t:
                check_buffer(t)

    def test_buffer_remaining(self):
        """Test buffer_remaining()"""
        assert buffer_remaining(BytesIO()) == 0
        assert buffer_remaining(BytesIO(b"\x00")) == 1
        assert buffer_remaining(BytesIO(b"\x00" * 100)) == 100

        b = BytesIO(b"\x00" * 100)
        b.seek(100)
        assert buffer_remaining(b) == 0
        assert b.tell() == 100
        b.seek(0)
        assert buffer_remaining(b) == 100
        assert b.tell() == 0
        b.seek(13)
        assert buffer_remaining(b) == 87
        assert b.tell() == 13

    def test_reset_buffer_position(self):
        """Test reset_buffer_position()"""
        b = BytesIO(b"\x00" * 100)
        b.seek(100)

        with reset_buffer_position(b) as idx:
            assert idx == 100
            b.seek(0)

        assert b.tell() == 100

        b.seek(13)
        with reset_buffer_position(b) as idx:
            assert idx == 13
            b.seek(57)

        assert b.tell() == 13

        b.seek(0)
        with reset_buffer_position(b) as idx:
            assert idx == 0
            b.seek(47)

        assert b.tell() == 0

        b.close()
        msg = "the buffer has been closed"
        with pytest.raises(ValueError, match=msg):
            with reset_buffer_position(b) as idx:
                assert idx == 100
                b.seek(0)

    def test_read_buffer(self):
        """Test read_buffer()"""
        b = BytesIO()
        assert [d for d in read_buffer(b)] == []

        b = BytesIO(b"\x01" * 100 + b"\x02\x03")
        out = bytearray()
        for data in read_buffer(b, chunk_size=12):
            out.extend(data)

        assert len(out) == 102
        assert out == b.getvalue()

        msg = "Invalid 'chunk_size' value '-12', must be greater than 0"
        with pytest.raises(ValueError, match=msg):
            next(read_buffer(b, chunk_size=-12))

        b.close()
        msg = "the buffer has been closed"
        with pytest.raises(ValueError, match=msg):
            next(read_buffer(b))

    def test_read_buffer_chunk_size(self):
        """Test the chunk size for read_buffer()"""
        b = BytesIO(b"\x01\x02" * 6)
        settings.buffered_read_size = 2

        for idx, data in enumerate(read_buffer(b)):
            assert data == b"\x01\x02"

        assert idx == 5

        b.seek(0)
        for idx, data in enumerate(read_buffer(b, chunk_size=4)):
            assert data == b"\x01\x02\x01\x02"

        assert idx == 2

        msg = "The read size must be greater than 0"
        with pytest.raises(ValueError, match=msg):
            settings.buffered_read_size = -1

    def test_buffer_length(self):
        """Test buffer_length()"""
        assert buffer_length(BytesIO()) == 0
        assert buffer_length(BytesIO(b"\x00")) == 1
        assert buffer_length(BytesIO(b"\x00" * 100)) == 100

        b = BytesIO(b"\x00" * 100)
        b.seek(100)
        assert buffer_length(b) == 100
        b.seek(50)
        assert buffer_length(b) == 100

    def test_equality_not_buffer(self):
        """Test equality if 'other' is not a buffer or bytes"""
        assert buffer_equality(b"", None) is False
