# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Test for filebase.py"""

from io import BytesIO

import pytest

from pydicom.data import get_testdata_file
from pydicom.filebase import DicomIO, DicomFileLike, DicomFile, DicomBytesIO
from pydicom.tag import Tag


TEST_FILE = get_testdata_file("CT_small.dcm")


class TestDicomIO:
    """Test filebase.DicomIO class"""

    def test_init(self):
        """Test __init__"""
        fp = DicomIO(BytesIO())
        assert not hasattr(fp, "is_implicit_VR")
        assert not hasattr(fp, "is_little_endian")

    def test_parent(self):
        """Test DicomIO.parent"""
        buffer = BytesIO()
        fp = DicomIO(buffer)
        assert fp.parent is buffer

    def test_read_tag(self):
        """Test DicomIO.read_tag indirectly"""
        # Tags are 2 + 2 = 4 bytes
        bytestream = b"\x01\x02\x03\x04\x05\x06"
        # Little endian
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert Tag(fp.read_tag()) == 0x02010403

        # Big endian
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = False
        assert Tag(fp.read_tag()) == 0x01020304

    def test_write_tag(self):
        """Test DicomIO.write_tag indirectly"""
        tag = Tag(0x01020304)

        # Little endian
        fp = DicomBytesIO()
        fp.is_little_endian = True
        fp.write_tag(tag)
        assert fp.getvalue() == b"\x02\x01\x04\x03"

        # Big endian
        fp = DicomBytesIO()
        fp.is_little_endian = False
        fp.write_tag(tag)
        assert fp.getvalue() == b"\x01\x02\x03\x04"

    def test_read_us(self):
        """Test DicomIO.read_US"""
        # US are 2 bytes fixed
        bytestream = b"\x00\x00\xFF\x00\xFE\xFF"
        # Little endian
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert fp.read_US() == 0
        assert fp.read_US() == 255
        assert fp.read_US() == 65534

        # Big endian
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert fp.read_US() == 0
        assert fp.read_US() == 255
        assert fp.read_US() == 0xFFFE

    def test_write_us(self):
        """Test DicomIO.write_US"""
        # Little endian
        fp = DicomBytesIO()
        fp.is_little_endian = True
        assert fp.getvalue() == b""
        fp.write_US(0)
        assert fp.getvalue() == b"\x00\x00"
        fp.write_US(255)
        assert fp.getvalue() == b"\x00\x00\xFF\x00"
        fp.write_US(65534)
        assert fp.getvalue() == b"\x00\x00\xFF\x00\xFE\xFF"

        # Big endian
        fp = DicomBytesIO()
        fp.is_little_endian = False
        assert fp.getvalue() == b""
        fp.write_US(0)
        assert fp.getvalue() == b"\x00\x00"
        fp.write_US(255)
        assert fp.getvalue() == b"\x00\x00\x00\xFF"
        fp.write_US(65534)
        assert fp.getvalue() == b"\x00\x00\x00\xFF\xFF\xFE"

    def test_read_ul(self):
        """Test DicomIO.read_UL"""
        # UL are 4 bytes fixed
        bytestream = b"\x00\x00\x00\x00\xFF\xFF\x00\x00\xFE\xFF\xFF\xFF"
        # Little endian
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert fp.read_UL() == 0
        assert fp.read_UL() == 0xFFFF
        assert fp.read_UL() == 0xFFFFFFFE

        # Big endian
        bytestream = b"\x00\x00\x00\x00\x00\x00\xFF\xFF\xFF\xFF\xFF\xFE"
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = False
        assert fp.read_UL() == 0
        assert fp.read_UL() == 0xFFFF
        assert fp.read_UL() == 0xFFFFFFFE

    def test_write_ul(self):
        """Test DicomIO.write_UL indirectly"""
        # Little endian
        fp = DicomBytesIO()
        fp.is_little_endian = True
        assert fp.getvalue() == b""
        fp.write_UL(0)
        assert fp.getvalue() == b"\x00\x00\x00\x00"
        fp.write_UL(65535)
        assert fp.getvalue() == b"\x00\x00\x00\x00\xFF\xFF\x00\x00"
        fp.write_UL(4294967294)
        assert fp.getvalue() == (b"\x00\x00\x00\x00\xFF\xFF\x00\x00\xFE\xFF\xFF\xFF")

        # Big endian
        fp = DicomBytesIO()
        fp.is_little_endian = False
        assert fp.getvalue() == b""
        fp.write_UL(0)
        assert fp.getvalue() == b"\x00\x00\x00\x00"
        fp.write_UL(65535)
        assert fp.getvalue() == b"\x00\x00\x00\x00\x00\x00\xFF\xFF"
        fp.write_UL(4294967294)
        assert fp.getvalue() == (b"\x00\x00\x00\x00\x00\x00\xFF\xFF\xFF\xFF\xFF\xFE")

    def test_read(self):
        """Test DicomIO.read entire length"""
        fp = DicomBytesIO(b"\x00\x01\x03")
        bytestream = fp.read()
        assert bytestream == b"\x00\x01\x03"

    def test_read_length(self):
        """Test DicomIO.read specific length"""
        fp = DicomBytesIO(b"\x00\x01\x03")
        bytestream = fp.read(2)
        assert bytestream == b"\x00\x01"

    def test_read_exact(self):
        """Test DicomIO.read exact length"""
        fp = DicomBytesIO(b"\x00\x01\x03\x04")
        bytestream = fp.read_exact(length=4)
        assert bytestream == b"\x00\x01\x03\x04"

    def test_read_exact_retry(self):
        """Test DicomIO.read exact length success after retry"""

        class Foo:
            idx = 0
            seek = None
            tell = None

            def read(self, length):
                if self.idx == 0:
                    self.idx += 1
                    return b"\x00"

                return b"\x01\x03\x04"

        fp = DicomIO(Foo())
        bytestream = fp.read_exact(length=4)
        assert bytestream == b"\x00\x01\x03\x04"

    def test_read_exact_length_raises(self):
        """Test DicomIO.read exact length raises if short"""
        fp = DicomBytesIO(b"\x00\x01\x03")
        with pytest.raises(
            EOFError,
            match="Unexpected end of file. Read 3 bytes of 4 "
            "expected starting at position 0x0",
        ):
            fp.read_exact(length=4)

    def test_getter_is_little_endian(self):
        """Test DicomIO.is_little_endian getter"""
        fp = DicomIO(BytesIO())
        fp.is_little_endian = True
        assert fp.is_little_endian
        fp.is_little_endian = False
        assert not fp.is_little_endian

    def test_setter_is_little_endian(self):
        """Test DicomIO.is_little_endian setter"""
        fp = DicomIO(BytesIO())
        for is_little in (True, False):
            fp.is_little_endian = is_little
            assert hasattr(fp, "_us_packer")
            assert hasattr(fp, "_us_unpacker")
            assert hasattr(fp, "_ul_packer")
            assert hasattr(fp, "_ul_unpacker")
            assert hasattr(fp, "_us_packer")
            assert hasattr(fp, "_tag_packer")
            assert hasattr(fp, "_tag_unpacker")

        msg = "'DicomIO.is_little_endian' must be bool"
        with pytest.raises(TypeError, match=msg):
            fp.is_little_endian = None

    def test_is_implicit_vr(self):
        """Test DicomIO.is_implicit_VR"""
        fp = DicomIO(BytesIO())
        fp.is_implicit_VR = True
        assert fp.is_implicit_VR
        fp.is_implicit_VR = False
        assert not fp.is_implicit_VR

        msg = "'DicomIO.is_implicit_VR' must be bool"
        with pytest.raises(TypeError, match=msg):
            fp.is_implicit_VR = None

    def test_methods_raise(self):
        """Test various DicomIO methods raise exceptions."""

        class Reader:
            def read(self):
                pass

            def seek(self):
                pass

            def tell(self):
                pass

        class Writer:
            def write(self, b):
                pass

            def seek(self):
                pass

            def tell(self):
                pass

        with pytest.raises(TypeError, match=r"object has no read\(\) method"):
            DicomIO(Writer()).read(2)
        with pytest.raises(TypeError, match=r"object has no write\(\) method"):
            DicomIO(Reader()).write(b"")

        fp = DicomIO(Reader())
        assert fp.name is None
        fp.name = "foo"
        assert fp.name == "foo"
        fp.close()  # no exceptions

    def test_init_good_buffer(self):
        """Test methods are set OK if buffer is good"""
        buffer = BytesIO()
        fp = DicomFileLike(buffer)
        assert fp._buffer == buffer
        assert fp.write == buffer.write
        assert fp.seek == buffer.seek
        assert fp.read == buffer.read
        assert fp.tell == buffer.tell
        assert fp.close == buffer.close

    def test_context(self):
        """Test using DicomFileLike as a context"""
        with DicomIO(BytesIO(b"\x00\x01")) as fp:
            assert fp.read(2) == b"\x00\x01"


class TestDicomBytesIO:
    """Test filebase.DicomBytesIO class"""

    def test_getvalue(self):
        """Test DicomBytesIO.getvalue"""
        fp = DicomBytesIO(b"\x00\x01\x00\x02")
        assert fp.getvalue() == b"\x00\x01\x00\x02"


class TestDicomFile:
    """Test filebase.DicomFile() function"""

    def test_read(self):
        """Test the function"""
        with DicomFile(TEST_FILE, "rb") as fp:
            assert not fp._buffer.closed
            # Weird issue with Python 3.6 sometimes returning
            #   lowercase file path on Windows
            assert "ct_small.dcm" in fp.name.lower()
            assert fp.read(2) == b"\x49\x49"
