# test_UID.py
"""Test suite for UID.py"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import unittest
from dicom.UID import UID


class UIDtests(unittest.TestCase):
    def testKnownUID(self):
        """UID: Known UID properties accessed....................."""

        msg = "UID: expected '{1:s}', got '{2:s}' for UID {0:s}"

        uid = UID('1.2.840.10008.1.2')  # Implicit VR Little Endian
        expected = 'Implicit VR Little Endian'
        got = uid.name
        self.assertEqual(got, expected, msg.format("name", expected, got))

        expected = 'Transfer Syntax'
        got = uid.type
        self.assertEqual(got, expected, msg.format("type", expected, got))

        expected = 'Default Transfer Syntax for DICOM'
        got = uid.info
        self.assertEqual(got, expected, msg.format("info", expected, got))

        expected = False
        got = uid.is_retired
        self.assertEqual(got, expected,
                     msg.format("is_retired", str(expected), str(got)))

    def testComparison(self):
        """UID: can compare by number or by name.................."""
        uid = UID('1.2.840.10008.1.2')
        self.assertEqual(uid, 'Implicit VR Little Endian',
                                    "UID equality failed on name")
        self.assertEqual(uid, '1.2.840.10008.1.2',
                                    "UID equality failed on number string")

    def testCompareNumber(self):
        """UID: comparing against a number give False............."""
        # From issue 96
        uid = UID('1.2.3')
        self.assertNotEqual(uid, 3, "Comparison to a number returned True")

    def testCompareNone(self):
        """UID: comparing against None give False................."""
        # From issue 96
        uid = UID('1.2.3')
        self.assertNotEqual(uid, None, "Comparison to a number returned True")

    def testTransferSyntaxes(self):
        pass


if __name__ == "__main__":
    unittest.main()
