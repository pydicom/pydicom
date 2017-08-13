"""unittest cases for pydicom.charset module"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file LICENSE included with this distribution, also
#    available at https://github.com/pydicom/pydicom
import unittest

from pydicom.data import get_charset_files
from pydicom.data import get_testdata_files
from pydicom import dicomio
import pydicom.charset
from pydicom.compat import in_py2
from pydicom.dataelem import DataElement
import pytest

latin1_file = get_charset_files("chrFren.dcm")[0]
jp_file = get_charset_files("chrH31.dcm")[0]
multiPN_file = get_charset_files("chrFrenMulti.dcm")[0]
sq_encoding_file = get_charset_files("chrSQEncoding.dcm")[0]
explicit_ir6_file = get_charset_files("chrJapMultiExplicitIR6.dcm")[0]
normal_file = get_testdata_files("CT_small.dcm")[0]


class CharsetTests(unittest.TestCase):
    def testLatin1(self):
        """charset: can read and decode latin_1 file........................"""
        ds = dicomio.dcmread(latin1_file)
        ds.decode()
        # Make sure don't get unicode encode error on converting to string
        expected = u'Buc^J\xe9r\xf4me'
        got = ds.PatientName
        self.assertEqual(expected, got,
                         "Expected %r, got %r" % (expected, got))

    def testEncodings(self):
        test_string = u'Hello World'
        for x in pydicom.charset.python_encoding.items():
            try:
                test_string.encode(x[1])
            except LookupError:
                found = "(was '%s')" % x[1]
                term = "Term '%s'" % x[0]
                message = "%s has invalid python encoding %s" % (found, term)
                self.fail(msg=message)

    def testNestedCharacterSets(self):
        """charset: can read and decode SQ with different encodings........."""
        ds = dicomio.dcmread(sq_encoding_file)
        ds.decode()

        # These datasets inside of the SQ cannot be decoded with
        # default_encoding OR UTF-8 (the parent dataset's encoding).
        # Instead, we make sure that it is decoded using the
        # (0008,0005) tag of the dataset

        expected = (u'\uff94\uff8f\uff80\uff9e^\uff80\uff9b\uff73='
                    u'\u5c71\u7530^\u592a\u90ce='
                    u'\u3084\u307e\u3060^\u305f\u308d\u3046')

        got = ds[0x32, 0x1064][0].PatientName
        self.assertEqual(expected, got,
                         "Expected %r, got %r" % (expected, got))

    def testStandardFile(self):
        """charset: can read and decode standard file without special char.."""
        ds = dicomio.dcmread(normal_file)
        ds.decode()

    def testExplicitISO2022_IR6(self):
        """charset: can decode file with multi-valued data elements........."""
        ds = dicomio.dcmread(explicit_ir6_file)
        ds.decode()

    def testMultiPN(self):
        """charset: can decode file with multi-valued data elements........."""
        ds = dicomio.dcmread(multiPN_file)
        ds.decode()

    def testEncodingWithSpecificTags(self):
        """Encoding is correctly applied even if  Specific Character Set
        is not in specific tags..."""
        ds = dicomio.dcmread(jp_file, specific_tags=['PatientName'])
        ds.decode()
        self.assertEqual(1, len(ds))
        expected = ('Yamada^Tarou='
                    '\033$B;3ED\033(B^\033$BB@O:\033(B='
                    '\033$B$d$^$@\033(B^\033$B$?$m$&\033(B')
        self.assertEqual(expected, ds.PatientName)

    @pytest.mark.skipif(not in_py2, reason='Fails with python3 due to #466')
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


if __name__ == "__main__":
    # This is called if run alone, but not if loaded through run_tests.py
    # If not run from the directory where the sample images are,
    #   then need to switch there
    unittest.main()
