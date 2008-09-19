# test_dataset.py
"""unittest cases for dicom.dataset module"""

import unittest
from dicom.dataset import Dataset
from dicom.attribute import Attribute

class DatasetTests(unittest.TestCase):
    def dummy_dataset(self):
        # This dataset is used by many of the tests
        ds = Dataset()
        ds.AddNew((0x300a, 0x00b2), "SH", "unit001") # TreatmentMachineName
        return ds
        
    def testSetNewAttributeByName(self):
        """Dataset: set new attribute by name............................."""
        ds = Dataset()
        ds.TreatmentMachineName = "unit #1"
        attribute = ds[0x300a, 0x00b2]
        self.assertEqual(attribute.value, "unit #1", "Unable to set attribute by name")
        self.assertEqual(attribute.VR, "SH", "attribute not the expected VR")
    def testSetExistingAttributeByName(self):
        """Dataset: set existing attribute by name........................"""
        ds = self.dummy_dataset()
        ds.TreatmentMachineName = "unit999" # change existing value
        self.assertEqual(ds[0x300a, 0x00b2].value, "unit999")
    def testSetNonDicom(self):
        """Dataset: can set class instance property (non-dicom)..........."""
        ds = Dataset()
        ds.SomeVariableName = 42
        has_it = hasattr(ds, 'SomeVariableName')
        self.assert_(has_it, "Variable did not get created")
        if has_it:
            self.assertEqual(ds.SomeVariableName, 42, "There, but wrong value")
    def testMembership(self):
        """Dataset: can test if item present by 'if <name> in dataset'...."""
        ds = self.dummy_dataset()
        self.assert_('TreatmentMachineName' in ds, "membership test failed")
        self.assert_(not 'Dummyname' in ds, "non-member tested as member")
    def testContains(self):
        """Dataset: can test if item present by 'if <tag> in dataset'....."""
        ds = self.dummy_dataset()
        self.assert_((0x300a, 0xb2) in ds, "membership test failed")
        self.assert_(0x300a00b2 in ds, "membership test failed")
        self.assert_(not (0x10,0x5f) in ds, "non-member tested as member")        
    def testGet(self):
        """Dataset: can use dataset.get() to return item or default......."""
        ds = self.dummy_dataset()
        unit = ds.get('TreatmentMachineName', None)
        self.assertEqual(unit, 'unit001', "dataset.get() did not return existing member")
        not_there = ds.get('NotAMember', "not-there")
        self.assertEqual(not_there, "not-there",
                    "dataset.get() did not return default value for non-member")
    def test__setitem__(self):
        """Dataset: if set an item, it must be an Attribute instance......"""
        def callSet():
            ds[0x300a, 0xb2]="unit1" # common error - set attribute instead of attr.value
            
        ds = Dataset()
        self.assertRaises(TypeError, callSet)
    def test_matching_tags(self):
        """Dataset: key and attribute.tag mismatch raises ValueError......"""
        def set_wrong_tag():
            ds[0x10,0x10] = attribute
        ds = Dataset()
        attribute = Attribute((0x300a, 0x00b2), "SH", "unit001")
        self.assertRaises(ValueError, set_wrong_tag)
    def test_NamedMemberUpdated(self):
        """Dataset: if set attribute by tag, name also reflects change...."""
        ds = self.dummy_dataset()
        ds[0x300a,0xb2].value = "moon_unit"
        self.assertEqual(ds.TreatmentMachineName, 'moon_unit', "Member not updated")
    def testUpdate(self):
        """Dataset: update() method works with tag or name................"""
        ds = self.dummy_dataset()
        pat_attr = Attribute((0x10,0x12), 'PN', 'Johnny')
        ds.update({'PatientsName': 'John', (0x10,0x12): pat_attr})
        self.assertEqual(ds[0x10,0x10].value, 'John', "named attribute not set")
        self.assertEqual(ds[0x10,0x12].value, 'Johnny', "set by tag failed")
    def testDir(self):
        """Dataset: dir() returns sorted list of named attributes........."""
        ds = self.dummy_dataset()
        ds.PatientsName = "name"
        ds.PatientID = "id"
        ds.NonDicomVariable = "junk"
        ds.AddNew((0x18,0x1151), "IS", 150) # X-ray Tube Current
        ds.AddNew((0x1111, 0x123), "DS", "42.0") # private tag - no name in dir()
        expected = ['PatientID', 'PatientsName', 'TreatmentMachineName', 'XRayTubeCurrent']
        self.assertEqual(ds.dir(), expected, "dir() returned %s, expected %s" % (str(ds.dir()), str(expected)))
        
if __name__ == "__main__":
    unittest.main()