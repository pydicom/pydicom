"""Test the miscellaneous functions."""

import unittest
import os.path as osp

from pydicom.misc import is_dicom

test_file = osp.join(osp.dirname(osp.abspath(__file__)), 'test_files', 'CT_small.dcm')

class Test_Misc(unittest.TestCase):

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
