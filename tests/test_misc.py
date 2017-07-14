"""Test the miscellaneous functions."""

import unittest
import os.path as osp

from pydicom.misc import is_dicom, size_in_bytes

test_file = osp.join(osp.dirname(osp.abspath(__file__)), 'test_files', 'CT_small.dcm')


class TestMisc(unittest.TestCase):
    def test_is_dicom(self):
        """Test the is_dicom function."""
        invalid_file = test_file.replace('CT_', 'CT')  # invalid file
        notdicom_file = osp.abspath(__file__)  # use own file

        # valid file returns True
        self.assertTrue(is_dicom(test_file))

        # return false for real file but not dicom
        self.assertFalse(is_dicom(notdicom_file))

        # test invalid path
        self.assertRaises(IOError, is_dicom, invalid_file)

    def test_size_in_bytes(self):
        """Test convenience function size_in_bytes()."""
        # None or numbers shall be returned unchanged
        self.assertIsNone(size_in_bytes(None))
        self.assertEqual(1234, size_in_bytes(1234))

        # string shall be parsed
        self.assertEqual(1234, size_in_bytes('1234'))
        self.assertEqual(4096, size_in_bytes('4 kb'))
        self.assertEqual(0x4000, size_in_bytes('16 KB'))
        self.assertEqual(0x300000, size_in_bytes('3  MB'))
        self.assertEqual(0x80000000, size_in_bytes('2gB'))

        self.assertRaises(ValueError, size_in_bytes, '2 TB')
        self.assertRaises(ValueError, size_in_bytes, 'KB 2')
