# test_UID.py
"""Test suite for UID.py"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import unittest
from dicom.UID import UID, generate_uid, pydicom_root_UID, InvalidUID


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

    def testCompareNotEqualByName(self):
        """UID: comparing not equal by name......................."""
        # from Issue 121
        ct_image_storage = UID('1.2.840.10008.5.1.4.1.1.2')
        msg = "UID not equal comparison by name was not correct"
        self.assertFalse(ct_image_storage != 'CT Image Storage', msg)

    def testCompareNone(self):
        """UID: comparing against None give False................."""
        # From issue 96
        uid = UID('1.2.3')
        self.assertNotEqual(uid, None, "Comparison to a number returned True")

    def testTransferSyntaxes(self):
        pass

    def testGenerateUID(self):
        '''
        Test UID generator
        '''
        # Test standard UID generation with pydicom prefix
        uid = generate_uid()
        self.assertEqual(uid[:26], pydicom_root_UID)

        # Test standard UID generation with no prefix
        uid = generate_uid(None)
        self.assertEqual(uid[:5], '2.25.')

        # Test invalid UID truncation (trailing dot)
        invalid_prefix = \
            '1.2.33333333333333333333333333333333333333333333333333333333333.333.'
        self.assertRaises(InvalidUID,
                          lambda: generate_uid(prefix=invalid_prefix, truncate=True))

        # Test standard UID with truncate=True
        prefix = '1.2.3.444444'
        uid = generate_uid(prefix=prefix, truncate=True)
        self.assertEqual(uid[:12], prefix)

if __name__ == "__main__":
    unittest.main()
