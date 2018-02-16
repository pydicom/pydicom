# Copyright 2008-2017 pydicom authors. See LICENSE file for details.
"""Tests for dataset.py"""

import pytest

from pydicom.tag import Tag
from pydicom.values import (convert_value, converters, convert_tag,
                            convert_ATvalue, convert_DA_string)


class TestConvertTag(object):
    def test_big_endian(self):
        """Test convert_tag with a big endian byte string"""
        bytestring = b'\x00\x10\x00\x20'
        assert convert_tag(bytestring, False) == Tag(0x0010, 0x0020)

    def test_little_endian(self):
        """Test convert_tag with a little endian byte string"""
        bytestring = b'\x10\x00\x20\x00'
        assert convert_tag(bytestring, True) == Tag(0x0010, 0x0020)

    def test_offset(self):
        """Test convert_tag with an offset"""
        bytestring = b'\x12\x23\x10\x00\x20\x00\x34\x45'
        assert convert_tag(bytestring, True, 0) == Tag(0x2312, 0x0010)
        assert convert_tag(bytestring, True, 2) == Tag(0x0010, 0x0020)

    @pytest.mark.skip(reason='empty bytestring not handled properly')
    def test_empty_bytestring(self):
        """Test convert_tag with empty bytestring"""
        bytestring = b''
        assert convert_tag(bytestring, True) == ''

    @pytest.mark.skip(reason='bad bytestring not handled properly')
    def test_bad_bytestring(self):
        """Test convert_tag with a bad bytestring"""
        bytestring = b'\x10\x00'
        convert_tag(bytestring, True)


class TestConvertAT(object):
    def test_big_endian(self):
        """Test convert_ATvalue with a big endian byte string"""
        # VM 1
        bytestring = b'\x00\x10\x00\x20'
        assert convert_ATvalue(bytestring, False) == Tag(0x0010, 0x0020)

        # VM 3
        bytestring += b'\x00\x10\x00\x30\x00\x10\x00\x40'
        out = convert_ATvalue(bytestring, False)
        assert Tag(0x0010, 0x0020) in out
        assert Tag(0x0010, 0x0030) in out
        assert Tag(0x0010, 0x0040) in out

    def test_little_endian(self):
        """Test convert_ATvalue with a little endian byte string"""
        # VM 1
        bytestring = b'\x10\x00\x20\x00'
        assert convert_ATvalue(bytestring, True) == Tag(0x0010, 0x0020)

        # VM 3
        bytestring += b'\x10\x00\x30\x00\x10\x00\x40\x00'
        out = convert_ATvalue(bytestring, True)
        assert Tag(0x0010, 0x0020) in out
        assert Tag(0x0010, 0x0030) in out
        assert Tag(0x0010, 0x0040) in out

    def test_empty_bytestring(self):
        """Test convert_ATvalue with empty bytestring"""
        bytestring = b''
        assert convert_ATvalue(bytestring, True) == []

    @pytest.mark.skip(reason='bad bytestring not handled properly')
    def test_bad_length(self):
        """Test convert_ATvalue with bad length bytestring"""
        bytestring = b''
        assert convert_ATvalue(bytestring, True) == ''

        bytestring = b'\x10\x00\x20\x00\x10\x00\x30\x00\x10'
        convert_ATvalue(bytestring, True)


class TestConvertDA(object):
    def test_big_endian(self):
        """Test convert_DA_string with a big endian byte string"""
        # VM 1
        bytestring = b'\x32\x30\x30\x34\x30\x31\x31\x39'
        # byte ordering independent
        assert convert_DA_string(bytestring, False) == '20040119'

        # VM 2
        bytestring += b'\x5c\x31\x39\x39\x39\x31\x32\x31\x32'
        out = convert_DA_string(bytestring, False)
        assert out == ['20040119', '19991212']

    def test_little_endian(self):
        """Test convert_DA_string with a little endian byte string"""
        # VM 1
        bytestring = b'\x32\x30\x30\x34\x30\x31\x31\x39'
        # byte ordering independent
        assert convert_DA_string(bytestring, True) == '20040119'

        # VM 2
        bytestring += b'\x5c\x31\x39\x39\x39\x31\x32\x31\x32'
        out = convert_DA_string(bytestring, True)
        assert out == ['20040119', '19991212']

    def test_empty_bytestring(self):
        """Test convert_DA_string with empty bytestring"""
        bytestring = b''
        assert convert_DA_string(bytestring, True) == ''


class TestConvertValue(object):
    def test_convert_value_raises(self):
        """Test convert_value raises exception if unsupported VR"""
        converter_func = converters['PN']
        del converters['PN']

        with pytest.raises(NotImplementedError,
                           match="Unknown Value Representation 'PN'"):
            convert_value('PN', None)

        # Fix converters
        converters['PN'] = converter_func
        assert 'PN' in converters
