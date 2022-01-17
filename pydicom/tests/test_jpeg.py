"""Unit tests for the pydicom.jpeg module."""

import pytest

from pydicom.jpeg.jpeg10918 import (
    _get_bit,
    _split_byte,
    _find_marker,
    parse_jpeg,
    debug_jpeg,
)
from pydicom.jpeg.jpeg15444 import debug_jpeg2k, parse_jpeg2k


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
    b"\xFF\xCF\x00\x12\x08\x00\x64\x00\x64\x03R\x11\x00G\x11\x00B\x11\x00"
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
    def test_missing_SOI(self):
        """Test debug output if SOI missing"""
        s = debug_jpeg(b"")
        assert len(s) == 1
        assert s[0] == "Insufficient data for JPEG codestream"

        s = debug_jpeg(b"\x00" * 40)
        assert len(s) == 2
        assert "No SOI (FF D8) marker found at the start" in s[0]
        assert "00 00 00 00 ..." in s[1]

        s = debug_jpeg(b"\xFF\xC0" * 10)
        assert len(s) == 2
        assert "No SOI (FF D8) marker found at the start" in s[0]
        assert "FF C0 FF C0 ..." in s[1]

    def test_APP(self):
        """Test debug output if SOI missing"""
        b = b"\xFF\xD8" + b"\xFF\xE0\x00\x06\x00\x01\x02\x03" + _SOF_MONO
        s = debug_jpeg(b)
        assert len(s) == 9
        assert "SOI (FF D8) marker found" in s[0]
        assert "APP segment(s) found" in s[1]
        assert "APP0: 00 01 02 03" in s[2]

    def test_COM(self):
        """Test debug output if SOI missing"""
        b = b"\xFF\xD8" + b"\xFF\xFE\x00\x06\x00\x01\x02\x03" + _SOF_MONO
        s = debug_jpeg(b)
        assert len(s) == 10
        assert "SOI (FF D8) marker found" in s[0]
        assert "COM (FF FE) segment found" in s[1]
        assert "00 01 02 03" in s[2]

    def test_SOF(self):
        """Test normal debug output"""
        s = debug_jpeg(b"\xFF\xD8" + _SOF_MONO)
        assert len(s) == 7
        assert "SOI (FF D8) marker found" in s[0]
        assert "SOF (FF C0) segment found" in s[1]
        assert "Precision: 8" in s[2]
        assert "Rows: 100" in s[3]
        assert "Columns: 101" in s[4]
        assert "ID: 0x00, subsampling h1 v1" in s[6]

    def test_SOF_missing(self):
        """Test normal debug output"""
        s = debug_jpeg(b"\xFF\xD8")
        assert len(s) == 2
        assert "SOI (FF D8) marker found" in s[0]
        assert "Unable to parse the JPEG codestream" in s[1]


class TestParseJPEG2K:
    """Tests for parse_jpeg2k."""
    def test_precision(self):
        """Test getting the precision for a JPEG2K bytestream."""
        base = b'\xff\x4f\xff\x51' + b'\x00' * 38
        # Signed
        for ii in range(135, 144):
            params = parse_jpeg2k(base + bytes([ii]))
            assert ii - 127 == params["precision"]
            assert params["is_signed"]

        # Unsigned
        for ii in range(7, 16):
            params = parse_jpeg2k(base + bytes([ii]))
            assert ii + 1 == params["precision"]
            assert not params["is_signed"]

    def test_not_j2k(self):
        """Test result when no JPEG2K SOF marker present"""
        base = b'\xff\x4e\xff\x51' + b'\x00' * 38
        assert {} == parse_jpeg2k(base + b'\x8F')

    def test_no_siz(self):
        """Test result when no SIZ box present"""
        base = b'\xff\x4f\xff\x52' + b'\x00' * 38
        assert {} == parse_jpeg2k(base + b'\x8F')

    def test_short_bytestream(self):
        """Test result when no SIZ box present"""
        assert {} == parse_jpeg2k(b'')
        assert {} == parse_jpeg2k(b'\xff\x4f\xff\x51' + b'\x00' * 20)


_SIZ_SIGNED = (
    #                         |  nr cols      |  nr rows      |
    b"\xff\x51\x00\x00\x00\x00\x00\x00\x00\x64\x00\x00\x00\x65"
    # XOsiz, YOSiz, XTsiz, YTSiz, XTOsiz, YTOSiz
    + b"\x00" * 6 * 4
    #  csiz   |     ssiz: 1-bit signed    XRsiz, YRSiz
    + b"\x00\x01" + bytes([0b10000000]) + b"\x00\x00"
)
_SIZ_UNSIGNED = (
    #                         |  nr cols      |  nr rows      |
    b"\xff\x51\x00\x00\x00\x00\x00\x00\x00\x64\x00\x00\x00\x65"
    # XOsiz, YOSiz, XTsiz, YTSiz, XTOsiz, YTOSiz
    + b"\x00" * 6 * 4
    #  csiz   |     ssiz: 38-bit unsigned
    + b"\x00\x03"
    + bytes([0b00100101]) + b"\x00\x00"
    + bytes([0b00001101]) + b"\x00\x00"
    + bytes([0b00100000]) + b"\x00\x00"
)


class TestDebugJPEG2K:
    """Tests for jpeg15444.debug_jpeg2k()"""
    def test_missing_SOI(self):
        """Test debug output if SOI missing"""
        s = debug_jpeg2k(b"")
        assert len(s) == 1
        assert "No SOI (FF 4F) marker found @ offset 0" in s[0]

        s = debug_jpeg2k(b"\x00" * 100)
        assert len(s) == 2
        assert "No SOI (FF 4F) marker found @ offset 0" in s[0]
        assert "00 00 00 00 ..." in s[1]

    def test_missing_SIZ(self):
        """Test debug output if SIZ missing"""
        s = debug_jpeg2k(b"\xff\x4f")
        assert len(s) == 2
        assert "SOI (FF 4F) marker found @ offset 0" in s[0]
        assert "No SIZ (FF 51) marker found @ offset 2" in s[1]

        s = debug_jpeg2k(b"\xff\x4f" + b"\x00" * 20)
        assert len(s) == 3
        assert "SOI (FF 4F) marker found @ offset 0" in s[0]
        assert "No SIZ (FF 51) marker found @ offset 2" in s[1]
        assert "00 00 00 00 ..." in s[2]

    def test_bad_SIZ(self):
        """Test debug output if SIZ bad"""
        s = debug_jpeg2k(b"\xff\x4f\xff\x51")
        assert len(s) == 3
        assert "SOI (FF 4F) marker found @ offset 0" in s[0]
        assert "SIZ (FF 51) segment found @ offset 2" in s[1]
        assert "Insufficient data for JPEG 2000 codestream" in s[2]

    def test_SIZ(self):
        """Test SIZ debug output"""
        s = debug_jpeg2k(b"\xff\x4f" + _SIZ_SIGNED)
        assert len(s) == 7
        assert "SOI (FF 4F) marker found @ offset 0" in s[0]
        assert "SIZ (FF 51) segment found @ offset 2" in s[1]
        assert "Rows: 101" in s[2]
        assert "Columns: 100" in s[3]
        assert "0: signed, precision 1" in s[5]
        assert "No COD (FF 52) marker found @ offset 45" in s[6]

        s = debug_jpeg2k(b"\xff\x4f" + _SIZ_UNSIGNED + b"\xff\xbb")
        assert len(s) == 10
        assert "SOI (FF 4F) marker found @ offset 0" in s[0]
        assert "SIZ (FF 51) segment found @ offset 2" in s[1]
        assert "Rows: 101" in s[2]
        assert "Columns: 100" in s[3]
        assert "0: unsigned, precision 38" in s[5]
        assert "1: unsigned, precision 14" in s[6]
        assert "2: unsigned, precision 33" in s[7]
        assert "No COD (FF 52) marker found @ offset 51" in s[8]
        assert "FF BB" in s[9]

    def test_bad_COD(self):
        """Test COD debug output"""
        s = debug_jpeg2k(b"\xff\x4f" + _SIZ_SIGNED + b"\xFF\x52")
        assert len(s) == 8
        assert "SOI (FF 4F) marker found @ offset 0" in s[0]
        assert "SIZ (FF 51) segment found @ offset 2" in s[1]
        assert "Rows: 101" in s[2]
        assert "Columns: 100" in s[3]
        assert "0: signed, precision 1" in s[5]
        assert "COD (FF 52) segment found @ offset 45" in s[6]
        assert "Insufficient data for JPEG 2000 codestream" in s[7]

    def test_COD(self):
        """Test COD debug output"""
        # MCT non, irreversible wavelet
        #               | Lcod  | Scod    | SGcod     mct \ SPcod         xform
        cod = b"\xFF\x52\x00\x00\x00" + b"\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        s = debug_jpeg2k(b"\xff\x4f" + _SIZ_SIGNED + cod)
        assert len(s) == 9
        assert "SOI (FF 4F) marker found @ offset 0" in s[0]
        assert "SIZ (FF 51) segment found @ offset 2" in s[1]
        assert "Rows: 101" in s[2]
        assert "Columns: 100" in s[3]
        assert "0: signed, precision 1" in s[5]
        assert "COD (FF 52) segment found @ offset 45" in s[6]
        assert "Multiple component transform: none" in s[7]
        assert "Wavelet transform: 9-7 irreversible" in s[8]

        # MCT applied, reversible wavelet
        cod = b"\xFF\x52\x00\x00\x00" + b"\x00\x00\x00\x01\x00\x00\x00\x00\x01"
        s = debug_jpeg2k(b"\xff\x4f" + _SIZ_SIGNED + cod)
        assert len(s) == 9
        assert "Multiple component transform: applied" in s[7]
        assert "Wavelet transform: 5-3 reversible" in s[8]

        # Weird MCT and wavelet values
        cod = b"\xFF\x52\x00\x00\x00" + b"\x00\x00\x00\x08\x00\x00\x00\x00\x07"
        s = debug_jpeg2k(b"\xff\x4f" + _SIZ_SIGNED + cod)
        assert "Multiple component transform: 0b00001000" in s[7]
        assert "Wavelet transform: 0b00000111" in s[8]
