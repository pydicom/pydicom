# test_dictionary.py
"""Test suite for dicom_dictionary.py"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

import unittest
from pydicom.tag import Tag
from pydicom.datadict import (CleanName, all_names_for_tag,
                              dictionary_description, dictionary_has_tag,
                              repeater_has_tag, repeater_has_keyword)


class DictTests(unittest.TestCase):
    def testCleanName(self):
        """dicom_dictionary: CleanName returns correct strings............."""
        self.assertTrue(CleanName(0x00100010) == "PatientsName")
        self.assertTrue(CleanName(Tag((0x0010, 0x0010))) == "PatientsName")

    def testTagNotFound(self):
        """dicom_dictionary: CleanName returns blank string for unknown tag"""
        self.assertTrue(CleanName(0x99991111) == "")

    def testNameFinding(self):
        """dicom_dictionary: get long and short names for a data_element name"""
        names = all_names_for_tag(Tag(0x300a00b2))  # Treatment Machine Name
        expected = ['TreatmentMachineName']
        self.assertEqual(names, expected, "Expected %s, got %s" % (expected, names))
        names = all_names_for_tag(Tag(0x300A0120))
        expected = ['BeamLimitingDeviceAngle', 'BLDAngle']
        self.assertEqual(names, expected, "Expected %s, got %s" % (expected, names))

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


class PrivateDictTests(unittest.TestCase):
    def testPrivate1(self):
        """private dict: """
        self.assertTrue(CleanName(0x00100010) == "PatientsName")
        self.assertTrue(CleanName(Tag((0x0010, 0x0010))) == "PatientsName")


if __name__ == "__main__":
    unittest.main()
