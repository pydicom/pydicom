# test_dictionary.py
"""Test suite for dicom_dictionary.py"""


import unittest
from dicom.tag import Tag
from dicom.dicom_dictionary import DicomDictionary, CleanName, AllNamesForTag

class DictTests(unittest.TestCase):
    def testCleanName(self):
        """dicom_dictionary: CleanName returns correct strings............."""
        self.assert_(CleanName(0x00100010) == "PatientsName")
        self.assert_(CleanName(Tag((0x0010, 0x0010))) == "PatientsName")
    def testTagNotFound(self):
        """dicom_dictionary: CleanName returns blank string for unknown tag"""
        self.assert_(CleanName(0x99991111)=="")
    def testNameFinding(self):
        """dicom_dictionary: get long and short names for an attribute name"""
        names = AllNamesForTag(Tag(0x300a00b2)) # Treatment Machine Name
        expected = ['TreatmentMachineName']
        self.assertEqual(names, expected, "Expected %s, got %s" % (expected, names))
        names = AllNamesForTag(Tag(0x300A0120))
        expected = ['BeamLimitingDeviceAngle', 'BLDAngle']
        self.assertEqual(names, expected, "Expected %s, got %s" % (expected, names))

        

if __name__ == "__main__":
    unittest.main()
