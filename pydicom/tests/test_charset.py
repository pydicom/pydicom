# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""unittest cases for pydicom.charset module"""

import unittest

import pytest

from pydicom.data import get_charset_files
from pydicom.data import get_testdata_files
import pydicom.charset
from pydicom.dataelem import DataElement, RawDataElement, DataElement_from_raw
from pydicom import dcmread, Dataset

latin1_file = get_charset_files("chrFren.dcm")[0]
jp_file = get_charset_files("chrH31.dcm")[0]
multiPN_file = get_charset_files("chrFrenMulti.dcm")[0]
sq_encoding_file = get_charset_files("chrSQEncoding.dcm")[0]
sq_encoding1_file = get_charset_files("chrSQEncoding1.dcm")[0]
explicit_ir6_file = get_charset_files("chrJapMultiExplicitIR6.dcm")[0]
normal_file = get_testdata_files("CT_small.dcm")[0]


class CharsetTests(unittest.TestCase):
    def test_latin1(self):
        """charset: can read and decode latin_1 file........................"""
        ds = dcmread(latin1_file)
        ds.decode()
        # Make sure don't get unicode encode error on converting to string
        expected = u'Buc^J\xe9r\xf4me'
        got = ds.PatientName
        self.assertEqual(expected, got,
                         "Expected %r, got %r" % (expected, got))

    def test_encodings(self):
        test_string = u'Hello World'
        for x in pydicom.charset.python_encoding.items():
            try:
                test_string.encode(x[1])
            except LookupError:
                found = "(was '%s')" % x[1]
                term = "Term '%s'" % x[0]
                message = "%s has invalid python encoding %s" % (found, term)
                self.fail(msg=message)

    def test_nested_character_sets(self):
        """charset: can read and decode SQ with different encodings........."""
        ds = dcmread(sq_encoding_file)
        ds.decode()

        # These datasets inside of the SQ cannot be decoded with
        # default_encoding OR UTF-8 (the parent dataset's encoding).
        # Instead, we make sure that it is decoded using the
        # (0008,0005) tag of the dataset

        expected = (u'\uff94\uff8f\uff80\uff9e^\uff80\uff9b\uff73='
                    u'\u5c71\u7530^\u592a\u90ce='
                    u'\u3084\u307e\u3060^\u305f\u308d\u3046')

        sequence = ds[0x32, 0x1064][0]
        assert sequence._character_set == [
            'shift_jis', 'iso2022_jp', 'iso2022_jp']
        assert expected == sequence.PatientName

    def test_inherited_character_set_in_sequence(self):
        """charset: can read and decode SQ with parent encoding............."""
        ds = dcmread(sq_encoding1_file)
        ds.decode()

        # These datasets inside of the SQ shall be decoded with the parent
        # dataset's encoding
        expected = (u'\uff94\uff8f\uff80\uff9e^\uff80\uff9b\uff73='
                    u'\u5c71\u7530^\u592a\u90ce='
                    u'\u3084\u307e\u3060^\u305f\u308d\u3046')

        sequence = ds[0x32, 0x1064][0]
        assert sequence._character_set == [
            'shift_jis', 'iso2022_jp', 'iso2022_jp']
        assert expected == sequence.PatientName

    def test_standard_file(self):
        """charset: can read and decode standard file without special char.."""
        ds = dcmread(normal_file)
        ds.decode()

    def test_explicit_iso2022_ir6(self):
        """charset: can decode file with multi-valued data elements........."""
        ds = dcmread(explicit_ir6_file)
        ds.decode()

    def test_multi_PN(self):
        """charset: can decode file with multi-valued data elements........."""
        ds = dcmread(multiPN_file)
        ds.decode()

    def test_encoding_with_specific_tags(self):
        """Encoding is correctly applied even if  Specific Character Set
        is not in specific tags..."""
        ds = dcmread(jp_file, specific_tags=['PatientName'])
        ds.decode()
        self.assertEqual(1, len(ds))
        expected = ('Yamada^Tarou='
                    '\033$B;3ED\033(B^\033$BB@O:\033(B='
                    '\033$B$d$^$@\033(B^\033$B$?$m$&\033(B')
        self.assertEqual(expected, ds.PatientName)

    def test_bad_charset(self):
        """Test bad charset defaults to ISO IR 6"""
        # Python 3: elem.value is PersonName3, Python 2: elem.value is str
        elem = DataElement(0x00100010, 'PN', 'CITIZEN')
        pydicom.charset.decode(elem, ['ISO 2022 IR 126'])
        # After decode Python 2: elem.value is PersonNameUnicode
        assert 'iso_ir_126' in elem.value.encodings
        assert 'iso8859' not in elem.value.encodings
        # default encoding is iso8859
        pydicom.charset.decode(elem, [])
        assert 'iso8859' in elem.value.encodings

    def test_patched_charset(self):
        """Test some commonly misspelled charset values"""
        elem = DataElement(0x00100010, 'PN', b'Buc^J\xc3\xa9r\xc3\xb4me')
        pydicom.charset.decode(elem, ['ISO_IR 192'])
        # correct encoding
        assert u'Buc^J\xe9r\xf4me' == elem.value

        # patched encoding shall behave correctly, but a warning is issued
        elem = DataElement(0x00100010, 'PN', b'Buc^J\xc3\xa9r\xc3\xb4me')
        with pytest.warns(UserWarning,
                          match='Incorrect value for Specific Character Set '
                                "'ISO IR 192' - assuming 'ISO_IR 192'"):
            pydicom.charset.decode(elem, ['ISO IR 192'])
            assert u'Buc^J\xe9r\xf4me' == elem.value

        elem = DataElement(0x00100010, 'PN', b'Buc^J\xc3\xa9r\xc3\xb4me')
        with pytest.warns(UserWarning,
                          match='Incorrect value for Specific Character Set '
                                "'ISO-IR 192' - assuming 'ISO_IR 192'"):
            pydicom.charset.decode(elem, ['ISO-IR 192'])
            assert u'Buc^J\xe9r\xf4me' == elem.value

        # not patched incorrect encoding raises
        elem = DataElement(0x00100010, 'PN', b'Buc^J\xc3\xa9r\xc3\xb4me')
        with pytest.raises(LookupError):
            pydicom.charset.decode(elem, ['ISOIR 192'])

        # Python encoding also can be used directly
        elem = DataElement(0x00100010, 'PN', b'Buc^J\xc3\xa9r\xc3\xb4me')
        pydicom.charset.decode(elem, ['utf8'])
        assert u'Buc^J\xe9r\xf4me' == elem.value


if __name__ == "__main__":
    # This is called if run alone, but not if loaded through run_tests.py
    # If not run from the directory where the sample images are,
    #   then need to switch there
    unittest.main()
