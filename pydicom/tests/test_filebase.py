# Copyright 2008-2017 pydicom authors. See LICENSE file for details.
"""Test for filebase.py"""

import pytest

from pydicom.data import get_testdata_files
from pydicom.filebase import DicomIO, DicomFileLike, DicomFile, DicomBytesIO
from pydicom.tag import Tag
from .testing import assert_raises_regex


TEST_FILE = get_testdata_files('CT_small.dcm')[0]


class TestDicomIO(object):
    """Test filebase.DicomIO class"""
    def test_init(self):
        """Test __init__"""
        # All the subclasses override this anyway
        fp = DicomIO()
        assert fp.is_implicit_VR

    def test_read_le_tag(self):
        """Test DicomIO.read_le_tag indirectly"""
        # Tags are 2 + 2 = 4 bytes
        bytestream = b'\x01\x02\x03\x04\x05\x06'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert Tag(fp.read_le_tag()) == 0x02010403

    def test_read_be_tag(self):
        """Test DicomIO.read_be_tag indirectly"""
        # Tags are 2 + 2 = 4 bytes
        bytestream = b'\x01\x02\x03\x04\x05\x06'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = False
        assert Tag(fp.read_be_tag()) == 0x01020304

    def test_write_tag(self):
        """Test DicomIO.write_tag indirectly"""
        tag = Tag(0x01020304)

        # Little endian
        fp = DicomBytesIO()
        fp.is_little_endian = True
        fp.write_tag(tag)
        assert fp.getvalue() == b'\x02\x01\x04\x03'

        # Big endian
        fp = DicomBytesIO()
        fp.is_little_endian = False
        fp.write_tag(tag)
        assert fp.getvalue() == b'\x01\x02\x03\x04'

    def test_read_le_us(self):
        """Test DicomIO.read_leUS indirectly"""
        # US are 2 bytes fixed
        bytestream = b'\x00\x00\xFF\x00\xFE\xFF'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert fp.read_leUS() == 0
        assert fp.read_leUS() == 255
        assert fp.read_leUS() == 65534

    def test_read_be_us(self):
        """Test DicomIO.read_beUS indirectly"""
        # US are 2 bytes fixed
        bytestream = b'\x00\x00\x00\xFF\xFF\xFE'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert fp.read_beUS() == 0
        assert fp.read_beUS() == 255
        assert fp.read_beUS() == 65534

    def test_write_le_us(self):
        """Test DicomIO.write_leUS indirectly"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        assert fp.getvalue() == b''
        fp.write_leUS(0)
        assert fp.getvalue() == b'\x00\x00'
        fp.write_leUS(255)
        assert fp.getvalue() == b'\x00\x00\xFF\x00'
        fp.write_leUS(65534)
        assert fp.getvalue() == b'\x00\x00\xFF\x00\xFE\xFF'

    def test_write_be_us(self):
        """Test DicomIO.write_beUS indirectly"""
        fp = DicomBytesIO()
        fp.is_little_endian = False
        assert fp.getvalue() == b''
        fp.write_beUS(0)
        assert fp.getvalue() == b'\x00\x00'
        fp.write_beUS(255)
        assert fp.getvalue() == b'\x00\x00\x00\xFF'
        fp.write_beUS(65534)
        assert fp.getvalue() == b'\x00\x00\x00\xFF\xFF\xFE'

    def test_read_le_ul(self):
        """Test DicomIO.read_leUL indirectly"""
        # UL are 4 bytes fixed
        bytestream = b'\x00\x00\x00\x00\xFF\xFF\x00\x00\xFE\xFF\xFF\xFF'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = True
        assert fp.read_leUL() == 0
        assert fp.read_leUL() == 65535
        assert fp.read_leUL() == 4294967294

    def test_read_be_ul(self):
        """Test DicomIO.read_beUL indirectly"""
        # UL are 4 bytes fixed
        bytestream = b'\x00\x00\x00\x00\x00\x00\xFF\xFF\xFF\xFF\xFF\xFE'
        fp = DicomBytesIO(bytestream)
        fp.is_little_endian = False
        assert fp.read_beUL() == 0
        assert fp.read_beUL() == 65535
        assert fp.read_beUL() == 4294967294

    def test_write_le_ul(self):
        """Test DicomIO.write_leUL indirectly"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        assert fp.getvalue() == b''
        fp.write_leUL(0)
        assert fp.getvalue() == b'\x00\x00\x00\x00'
        fp.write_leUL(65535)
        assert fp.getvalue() == b'\x00\x00\x00\x00\xFF\xFF\x00\x00'
        fp.write_leUL(4294967294)
        assert fp.getvalue() == (
            b'\x00\x00\x00\x00\xFF\xFF\x00\x00\xFE\xFF\xFF\xFF')

    def test_write_be_ul(self):
        """Test DicomIO.write_beUL indirectly"""
        fp = DicomBytesIO()
        fp.is_little_endian = False
        assert fp.getvalue() == b''
        fp.write_beUL(0)
        assert fp.getvalue() == b'\x00\x00\x00\x00'
        fp.write_beUL(65535)
        assert fp.getvalue() == b'\x00\x00\x00\x00\x00\x00\xFF\xFF'
        fp.write_beUL(4294967294)
        assert fp.getvalue() == (
            b'\x00\x00\x00\x00\x00\x00\xFF\xFF\xFF\xFF\xFF\xFE')

    def test_read(self):
        """Test DicomIO.read entire length"""
        fp = DicomBytesIO(b'\x00\x01\x03')
        fp.is_little_endian = True
        bytestream = fp.read(length=None, need_exact_length=False)
        assert bytestream == b'\x00\x01\x03'

    def test_read_length(self):
        """Test DicomIO.read specific length"""
        fp = DicomBytesIO(b'\x00\x01\x03')
        fp.is_little_endian = True
        bytestream = fp.read(length=2, need_exact_length=False)
        assert bytestream == b'\x00\x01'

    def test_read_exact_length(self):
        """Test DicomIO.read exact length"""
        fp = DicomBytesIO(b'\x00\x01\x03\x04')
        fp.is_little_endian = True
        bytestream = fp.read(length=4, need_exact_length=True)
        assert bytestream == b'\x00\x01\x03\x04'

    def test_read_exact_length_raises(self):
        """Test DicomIO.read exact length raises if short"""
        fp = DicomBytesIO(b'\x00\x01\x03')
        fp.is_little_endian = True
        assert_raises_regex(EOFError,
                            "Unexpected end of file. Read 3 bytes of 4 "
                            "expected starting at position 0x0",
                            fp.read,
                            length=4,
                            need_exact_length=True)

    def test_getter_is_little_endian(self):
        """Test DicomIO.is_little_endian getter"""
        fp = DicomIO()
        fp.is_little_endian = True
        assert fp.is_little_endian
        fp.is_little_endian = False
        assert not fp.is_little_endian

    def test_setter_is_little_endian(self):
        """Test DicomIO.is_little_endian setter"""
        fp = DicomIO()
        fp.is_little_endian = True
        assert fp.read_US == fp.read_leUS
        assert fp.read_UL == fp.read_leUL
        assert fp.write_US == fp.write_leUS
        assert fp.write_UL == fp.write_leUL
        assert fp.read_tag == fp.read_le_tag

        fp.is_little_endian = False
        assert fp.read_US == fp.read_beUS
        assert fp.read_UL == fp.read_beUL
        assert fp.write_US == fp.write_beUS
        assert fp.write_UL == fp.write_beUL
        assert fp.read_tag == fp.read_be_tag

    def test_is_implicit_vr(self):
        """Test DicomIO.is_implicit_VR"""
        fp = DicomIO()
        fp.is_implicit_VR = True
        assert fp.is_implicit_VR
        fp.is_implicit_VR = False
        assert not fp.is_implicit_VR


class TestDicomFileLike(object):
    """Test filebase.DicomFileLike class"""
    pass


class TestDicomBytesIO(object):
    """Test filebase.DicomBytesIO class"""
    pass


class TestDicomFile(object):
    """Test filebase.DicomFile function"""
    pass
