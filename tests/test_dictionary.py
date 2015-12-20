# test_dictionary.py
"""Test suite for dicom_dictionary.py"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

import unittest
from pydicom.tag import Tag
from pydicom.dataset import Dataset
from pydicom.datadict import keyword_for_tag
from pydicom.datadict import dictionary_description
from pydicom.datadict import add_dict_entry, add_dict_entries


class DictTests(unittest.TestCase):
    def testTagNotFound(self):
        """dicom_dictionary: keyword_for_tag returns a blank string for unknown tag"""
        self.assertTrue(keyword_for_tag(0x99991111) == "")

    def testRepeaters(self):
        """dicom_dictionary: Tags with "x" return correct dict info........"""
        self.assertEqual(dictionary_description(0x280400), 'Transform Label')
        self.assertEqual(dictionary_description(0x280410), 'Rows For Nth Order Coefficients')

    def testAddEntry(self):
        """dicom_dictionary: Can add and use a single dictionary entry....."""
        add_dict_entry(0x10011001, "UL", "TestOne", "Test One")
        add_dict_entry(0x10011002, "DS", "TestTwo", "Test Two", VM='3')
        ds = Dataset()
        ds.TestOne = 'test'
        ds.TestTwo = ['1', '2', '3']

    def testAddEntries(self):
        """dicom_dictionary: Can add and use a dict of new dictionary entries..."""
        new_dict_items = {
            0x10011001: ('UL', '1', "Test One", '', 'TestOne'),
            0x10011002: ('DS', '3', "Test Two", '', 'TestTwo'),
            }
        add_dict_entries(new_dict_items)
        ds = Dataset()
        ds.TestOne = 'test'
        ds.TestTwo = ['1', '2', '3']


if __name__ == "__main__":
    unittest.main()
