# test_dictionary.py
"""Test suite for dicom_dictionary.py"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

import unittest
from pydicom.dataset import Dataset
from pydicom.tag import Tag
from pydicom.datadict import (keyword_for_tag, dictionary_description,
                              dictionary_has_tag, repeater_has_tag,
                              repeater_has_keyword)
from pydicom.datadict import add_dict_entry, add_dict_entries


class DictTests(unittest.TestCase):
    def testTagNotFound(self):
        """dicom_dictionary: keyword_for_tag returns a blank string for unknown tag"""
        self.assertTrue(keyword_for_tag(0x99991111) == "")

    def testRepeaters(self):
        """dicom_dictionary: Tags with "x" return correct dict info........"""
        self.assertEqual(dictionary_description(0x280400), 'Transform Label')
        self.assertEqual(dictionary_description(0x280410), 'Rows For Nth Order Coefficients')

    def test_dict_has_tag(self):
        """Test dictionary_has_tag"""
        self.assertTrue(dictionary_has_tag(0x00100010))
        self.assertFalse(dictionary_has_tag(0x11110010))
        
    def test_repeater_has_tag(self):
        """Test repeater_has_tag"""
        self.assertTrue(repeater_has_tag(0x60000010))
        self.assertTrue(repeater_has_tag(0x60020010))
        self.assertFalse(repeater_has_tag(0x00100010))

    def test_repeater_has_keyword(self):
        """Test repeater_has_keyword"""
        self.assertTrue(repeater_has_keyword('OverlayData'))
        self.assertFalse(repeater_has_keyword('PixelData'))

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
