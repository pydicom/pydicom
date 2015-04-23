# test_uid.py
"""Test suite for uid.py"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

import unittest
from pydicom.uid import UID, generate_uid, pydicom_root_UID, InvalidUID


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
        self.assertTrue(len(uid) <= 64)

        # Test standard UID generation with no prefix
        uid = generate_uid(None)
        self.assertEqual(uid[:5], '2.25.')
        self.assertTrue(len(uid) <= 64)

        # Test invalid UID prefixes
        for invalid_prefix in (('1' * 63) + '.',
                               '',
                               '.',
                               '1',
                               '1.2',
                               '1.2..3.',
                               '1.a.2.',
                               '1.01.1.',
                              ):
            self.assertRaises(ValueError,
                              lambda: generate_uid(prefix=invalid_prefix))

        # Test some valid prefixes and make sure they survive
        for valid_prefix in ('0.',
                             '1.',
                             '1.23.',
                             '1.0.23.',
                             ('1' * 62) + '.',
                             '1.2.3.444444.',
                            ):
            uid = generate_uid(prefix=valid_prefix)
            self.assertEqual(uid[:len(valid_prefix)], valid_prefix)
            self.assertTrue(len(uid) <= 64)

    def testIsValid(self):
        for invalid_uid in ('1' * 65,
                            '1.' + ('2' * 63),
                            '',
                            '.',
                            '1.',
                            '1.01',
                            '1.a.2',
                           ):
            self.assertRaises(InvalidUID,
                              lambda: UID(invalid_uid).is_valid())

        for valid_uid in ('0',
                          '1',
                          '0.1',
                          '1' * 64,
                          '1.' + ('2' * 62),
                          '1.0.23',
                         ):
            UID(valid_uid).is_valid() # Shouldn't raise


if __name__ == "__main__":
    unittest.main()
