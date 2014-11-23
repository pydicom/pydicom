# test_dictionary.py
"""Test suite for dicom_dictionary.py"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import unittest
from dicom.tag import Tag
from dicom.datadict import CleanName, all_names_for_tag, dictionary_description


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


class PrivateDictTests(unittest.TestCase):
    def testPrivate1(self):
        """private dict: """
        self.assertTrue(CleanName(0x00100010) == "PatientsName")
        self.assertTrue(CleanName(Tag((0x0010, 0x0010))) == "PatientsName")


if __name__ == "__main__":
    unittest.main()
