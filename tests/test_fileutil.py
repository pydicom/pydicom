# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Test suite for util functions"""
from io import BytesIO, RawIOBase
from pathlib import Path

import pytest

from pydicom.fileutil import (
    path_from_pathlike,
    check_buffer,
    reset_buffer_position,
    read_buffer,
    buffer_remaining,
    buffer_length,
)


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


class TestBufferFunctions:
    """Test for the buffer functions"""

    def test_check_buffer(self):
        """Test check_buffer()"""
        b = BytesIO()
        assert check_buffer(b) is None

        b.close()
        assert b.closed

        msg = "Unable to use the buffer object as it has been closed"
        with pytest.raises(ValueError, match=msg):
            check_buffer(b)

        class Foo:
            closed = False

        def _bar(self):
            pass

        foo = Foo()
        msg = (
            r"Invalid buffer object type 'Foo', the object must have read\(\), "
            r"seek\(\) and tell\(\) methods"
        )
        with pytest.raises(TypeError, match=msg):
            check_buffer(foo)

        foo.read = _bar
        with pytest.raises(TypeError, match=msg):
            check_buffer(foo)

        foo.seek = _bar
        with pytest.raises(TypeError, match=msg):
            check_buffer(foo)

        foo.tell = _bar
        assert check_buffer(foo) is None

        foo.closed = True
        msg = "Unable to use the buffer object as it has been closed"
        with pytest.raises(ValueError, match=msg):
            check_buffer(foo)

        foo.closed = False
        assert check_buffer(foo) is None

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
        msg = "Unable to use the buffer object as it has been closed"
        with pytest.raises(ValueError, match=msg):
            with reset_buffer_position(b) as idx:
                assert idx == 100
                b.seek(0)

    def test_read_buffer(self):
        """Test read_buffer()"""
        b = BytesIO()
        d = []
        for data in read_buffer(b):
            d.append(data)

        assert d == []

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
        msg = "Unable to use the buffer object as it has been closed"
        with pytest.raises(ValueError, match=msg):
            next(read_buffer(b))

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
