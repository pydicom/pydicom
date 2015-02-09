# test_valuerep.py
"""Test suite for valuerep.py"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import unittest
from dicom import in_py3
import dicom.config
import os
import dicom
import cPickle as pickle


if in_py3:
    from dicom.valuerep import PersonName3 as PersonNameUnicode
    PersonName = PersonNameUnicode
else:
    from dicom.valuerep import PersonName, PersonNameUnicode

from pkg_resources import Requirement, resource_filename
test_dir = resource_filename(Requirement.parse("pydicom"), "dicom/testfiles")
badvr_name = os.path.join(test_dir, "badVR.dcm")
default_encoding = 'iso8859'

class DSfloatPickleTest(unittest.TestCase):
    """Unit tests unique to the use of DS class derived from python Decimal"""

    def testPickling(self):
        # Check that a pickled DSFloat is read back properly
        x = dicom.valuerep.DSfloat(9.0)
        x.original_string = 'hello'
        data1_string = pickle.dumps(x)
        x2 = pickle.loads(data1_string)        
        self.assertTrue(x.real == x2.real)
        self.assertTrue(x.original_string == x2.original_string)


class DSdecimalPickleTest(unittest.TestCase):
    """Unit tests unique to the use of DS class derived from python Decimal"""

    def testPickling(self):
        # Check that a pickled DSdecimal is read back properly
        # DSdecimal actually prefers original_string when 
        # reading back
        x = dicom.valuerep.DSdecimal(19)
        x.original_string = '19'
        data1_string = pickle.dumps(x)
        x2 = pickle.loads(data1_string)        
        self.assertTrue(x.real == x2.real)
        self.assertTrue(x.original_string == x2.original_string)


class ISPickleTest(unittest.TestCase):
    """Unit tests unique to the use of DS class derived from python Decimal"""

    def testPickling(self):
        # Check that a pickled IS is read back properly
        x = dicom.valuerep.IS(921)
        x.original_string = 'hello'
        data1_string = pickle.dumps(x)
        x2 = pickle.loads(data1_string)        
        self.assertTrue(x.real == x2.real)
        self.assertTrue(x.original_string == x2.original_string)


class BadValueReadtests(unittest.TestCase):
    """Unit tests unique to the use of DS class derived from python Decimal"""

    def testReadBadValueInVR(self):
        # Check that invalid values are read
        # and converted to some semi-useful type

        dataset = dicom.read_file(badvr_name)
        self.assertTrue(dataset.NumberOfFrames == '1A')


class DecimalStringtests(unittest.TestCase):
    """Unit tests unique to the use of DS class derived from python Decimal"""

    def setUp(self):
        dicom.config.DS_decimal(True)

    def tearDown(self):
        dicom.config.DS_decimal(False)

    def testValidDecimalStrings(self):
        # Ensures that decimal.Decimal doesn't cause a valid string to become
        # invalid
        valid_str = '-9.81338674e-006'
        ds = dicom.valuerep.DS(valid_str)
        L = len(str(ds))
        self.assertTrue(L <= 16, "DS: expected a string of length 16 but got %d" % (L,))

        # Now the input string is too long but decimal.Decimal can convert it
        # to a valid 16-character string
        long_str = '-0.000000981338674'
        ds = dicom.valuerep.DS(long_str)
        L = len(str(ds))
        self.assertTrue(L <= 16, "DS: expected a string of length 16 but got %d" % (L,))

    def testInvalidDecimalStrings(self):
        # Now the input string truly is invalid
        invalid_string = '-9.813386743e-006'
        self.assertRaises(OverflowError, dicom.valuerep.DS, invalid_string)


class PersonNametests(unittest.TestCase):
    def testLastFirst(self):
        """PN: Simple Family-name^Given-name works..............................."""
        pn = PersonName("Family^Given")
        expected = "Family"
        got = pn.family_name
        self.assertEqual(got, expected, "PN: expected '%s', got '%s' for family name" % (expected, got))

        expected = 'Given'
        got = pn.given_name
        self.assertEqual(got, expected, "PN: expected '%s', got '%s' for given name" % (expected, got))

        expected = ''
        got = pn.name_suffix
        self.assertEqual(got, expected, "PN: expected '%s', got '%s' for name_suffix" % (expected, got))

        expected = ''
        got = pn.phonetic
        self.assertEqual(got, expected, "PN: expected '%s', got '%s' for phonetic component" % (expected, got))

    def testThreeComponent(self):
        """PN: 3component (single-byte, ideographic, phonetic characters) works.."""
        # Example name from PS3.5-2008 section I.2 p. 108
        pn = PersonName("""Hong^Gildong=\033$)C\373\363^\033$)C\321\316\324\327=\033$)C\310\253^\033$)C\261\346\265\277""")
        expected = ("Hong", "Gildong")
        got = (pn.family_name, pn.given_name)
        self.assertEqual(got, expected, "PN: Expected single_byte name '%s', got '%s'" % (expected, got))

    def testFormatting(self):
        """PN: Formatting works.................................................."""
        pn = PersonName("Family^Given")
        expected = "Family, Given"
        got = pn.family_comma_given()
        self.assertEqual(got, expected, "PN: expected '%s', got '%s' for formatted Family, Given" % (expected, got))

    def testUnicodeKr(self):
        """PN: 3component in unicode works (Korean).............................."""
        # Example name from PS3.5-2008 section I.2 p. 101
        pn = PersonNameUnicode(
            """Hong^Gildong=\033$)C\373\363^\033$)C\321\316\324\327=\033$)C\310\253^\033$)C\261\346\265\277""",
            [default_encoding, 'euc_kr'])
        expected = ("Hong", "Gildong")
        got = (pn.family_name, pn.given_name)
        self.assertEqual(got, expected, "PN: Expected single_byte name '{0!s}', got '{1!s}'".format(expected, got))

    def testUnicodeJp(self):
        """PN: 3component in unicode works (Japanese)............................"""
        # Example name from PS3.5-2008 section H  p. 98
        pn = PersonNameUnicode(
            """Yamada^Tarou=\033$B;3ED\033(B^\033$BB@O:\033(B=\033$B$d$^$@\033(B^\033$B$?$m$&\033(B""",
            [default_encoding, 'iso2022_jp'])
        expected = ("Yamada", "Tarou")
        got = (pn.family_name, pn.given_name)
        self.assertEqual(got, expected, "PN: Expected single_byte name '{0!s}', got '{1!s}'".format(expected, got))

    def testNotEqual(self):
        """PN3: Not equal works correctly (issue 121)..........................."""
        # Meant to only be used in python 3 but doing simple check here
        from dicom.valuerep import PersonName3
        pn = PersonName3("John^Doe")
        msg = "PersonName3 not equal comparison did not work correctly"
        self.assertFalse(pn != "John^Doe", msg)


if __name__ == "__main__":
    unittest.main()
