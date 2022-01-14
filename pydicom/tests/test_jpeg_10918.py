"""Unit tests for the pydicom.jpeg.jpeg10918 module."""

import pytest

from pydicom.jpeg.jpeg10918 import (
    _get_bit,
    _split_byte,
    _find_marker,
    parse_jpeg,
    debug_jpeg,
)


def test_get_bit():
    """Test jpeg10918._get_bit()"""
    b = bytes([0b10110101])
    assert _get_bit(b, 0) == 1
    assert _get_bit(b, 1) == 0
    assert _get_bit(b, 2) == 1
    assert _get_bit(b, 3) == 1
    assert _get_bit(b, 4) == 0
    assert _get_bit(b, 5) == 1
    assert _get_bit(b, 6) == 0
    assert _get_bit(b, 7) == 1


def test_split_byte():
    """Test jpeg10918._split_byte()"""
    assert _split_byte(bytes([0b10110101])) == (0b00001011, 0b00000101)


class TestFindMarker:
    """Tests for jpeg10918._find_marker()"""
    def test_missing_marker_raises(self):
        """Test exception raised if no 0xFF byte found at start of search."""
        msg = r"No JPEG marker found at offset 0"
        with pytest.raises(ValueError, match=msg):
            _find_marker(b"\x00\xFF\x00")

    def test_fill_bytes(self):
        """Test marker search will fill bytes"""
        result = _find_marker(b"\xFF\xFF\xFF\xFF\x01\x00\x90")
        assert result == (b"\xFF\x01", 3)

    def test_no_marker_raises(self):
        """Test marker search raises if marker not found before EOF"""
        msg = r"No JPEG markers found after offset 3"
        with pytest.raises(ValueError, match=msg):
            _find_marker(b"\xFF" * 10, idx=3)

    def test_search_end(self):
        """Test marker search raises if marker not found before EOF"""
        result = _find_marker(b"\xFF\xD8")
        assert result == (b"\xFF\xD8", 0)


_SOF_MONO = b"\xFF\xC0\x00\x0C\x08\x00\x64\x00\x65\x01\x00\x11\x00"
_SOF_YBR = (
    b"\xFF\xC3\x00\x12\x08\x00\x64\x00\x64"
    b"\x03\x00\x11\x00\x01\x11\x00\x02\x11\x00"
)
_SOF_RGB = (
    b"\xFF\xCF\x00\x12\x08\x00\x64\x00\x64"
    b"\x03R\x11\x00G\x11\x00B\x11\x00"
)


class TestParseJPEG:
    """Tests for jpeg10918.parse_jpeg()"""
    def test_missing_marker(self):
        """Test missing SOI marker"""
        assert parse_jpeg(b"") == {}
        assert parse_jpeg(b"\xFF\xD7") == {}

    def test_APP_markers(self):
        """Test APPn markers are found."""
        b = b"\xFF\xD8" + b"\xFF\xE0\x00\x06\x00\x01\x02\x03" + _SOF_MONO
        d = parse_jpeg(b)
        assert d["APPn"][b"\xFF\xE0"] == b"\x00\x01\x02\x03"

    def test_COM_marker(self):
        """Test COM marker is found."""
        b = b"\xFF\xD8" + b"\xFF\xFE\x00\x06\x00\x01\x02\x03" + _SOF_MONO
        d = parse_jpeg(b)
        assert d["COM"] == b"\x00\x01\x02\x03"

    def test_SOF_marker(self):
        """Test SOF markers is found."""
        d = parse_jpeg(b"\xFF\xD8" + _SOF_MONO)
        sof = d["SOF"]
        assert sof["SOFn"] == b"\xFF\xC0"
        assert sof["P"] == 8
        assert sof["Y"] == 100
        assert sof["X"] == 101
        assert sof["Nf"] == 1
        assert sof["Components"] == [(b"\x00", 1, 1)]

        d = parse_jpeg(b"\xFF\xD8" + _SOF_YBR)
        sof = d["SOF"]
        assert sof["Components"] == [
            (b"\x00", 1, 1), (b"\x01", 1, 1), (b"\x02", 1, 1)
        ]

        d = parse_jpeg(b"\xFF\xD8" + _SOF_RGB)
        sof = d["SOF"]
        assert sof["Components"] == [
            (b"R", 1, 1), (b"G", 1, 1), (b"B", 1, 1)
        ]


class TestDebugJPEG:
    """Tests for jpeg10918.debug_jpeg()"""
    def test_debug_missing_SOI(self):
        """Test debug output if SOI missing"""
        s = debug_jpeg(b"")
        assert s[0] == "Insufficient data for JPEG codestream"

        s = debug_jpeg(b"\x00" * 40)
        assert "No SOI (FF D8) marker found at the start" in s[0]
        assert "00 00 00 00 ..." in s[1]

    def test_debug_APP(self):
        """Test debug output if SOI missing"""
        b = b"\xFF\xD8" + b"\xFF\xE0\x00\x06\x00\x01\x02\x03" + _SOF_MONO
        s = debug_jpeg(b)
        assert "SOI (FF D8) marker found" in s[0]
        assert "APP segment(s) found" in s[1]
        assert "APP0: 00 01 02 03" in s[2]

    def test_debug_COM(self):
        """Test debug output if SOI missing"""
        b = b"\xFF\xD8" + b"\xFF\xFE\x00\x06\x00\x01\x02\x03" + _SOF_MONO
        s = debug_jpeg(b)
        assert "SOI (FF D8) marker found" in s[0]
        assert "COM (FF FE) segment found" in s[1]
        assert "00 01 02 03" in s[2]

    def test_debug_SOF(self):
        """Test normal debug output"""
        s = debug_jpeg(b"\xFF\xD8" + _SOF_MONO)
        assert "SOI (FF D8) marker found" in s[0]
        assert "SOF (FF C0) segment found" in s[1]
        assert "Precision: 8" in s[2]
        assert "Rows: 100" in s[3]
        assert "Columns: 101" in s[4]
        assert "ID: 0x00, subsampling h1 v1" in s[6]

    def test_debug_SOF_missing(self):
        """Test normal debug output"""
        s = debug_jpeg(b"\xFF\xD8")
        assert "SOI (FF D8) marker found" in s[0]
        assert "No SOF marker found in the JPEG codestream" in s[1]
