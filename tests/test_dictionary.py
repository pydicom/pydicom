# test_dictionary.py
"""Test suite for dicom_dictionary.py"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

import unittest
from pydicom.tag import Tag
from pydicom.datadict import keyword_for_tag, dictionary_description


class DictTests(unittest.TestCase):
    def testTagNotFound(self):
        """dicom_dictionary: keyword_for_tag returns a blank string for unknown tag"""
        self.assertTrue(keyword_for_tag(0x99991111) == "")

    def testRepeaters(self):
        """dicom_dictionary: Tags with "x" return correct dict info........"""
        self.assertEqual(dictionary_description(0x280400), 'Transform Label')
        self.assertEqual(dictionary_description(0x280410), 'Rows For Nth Order Coefficients')


if __name__ == "__main__":
    unittest.main()
