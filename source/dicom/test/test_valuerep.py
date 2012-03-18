# test_valuerep.py
"""Test suite for valuerep.py"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import unittest
from dicom.valuerep import PersonName, PersonNameUnicode

default_encoding = 'iso8859'

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
        from sys import version_info
        if version_info >= (2,4):
            pn = PersonNameUnicode(
               """Hong^Gildong=\033$)C\373\363^\033$)C\321\316\324\327=\033$)C\310\253^\033$)C\261\346\265\277""",
               [default_encoding,'euc_kr'])
            expected = ("Hong", "Gildong")
            got = (pn.family_name, pn.given_name)
            self.assertEqual(got, expected, "PN: Expected single_byte name '{0!s}', got '{1!s}'" .format(expected, got))
    def testUnicodeJp(self):
        """PN: 3component in unicode works (Japanese)............................"""
        # Example name from PS3.5-2008 section H  p. 98
        from sys import version_info
        if version_info >= (2,4):
            pn = PersonNameUnicode(
               """Yamada^Tarou=\033$B;3ED\033(B^\033$BB@O:\033(B=\033$B$d$^$@\033(B^\033$B$?$m$&\033(B""",
               [default_encoding,'iso2022_jp'])
            expected = ("Yamada", "Tarou")
            got = (pn.family_name, pn.given_name)
            self.assertEqual(got, expected, "PN: Expected single_byte name '{0!s}', got '{1!s}'".format (expected, got))
        
if __name__ == "__main__":
    unittest.main()
