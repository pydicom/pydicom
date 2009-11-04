# test_dataset.py
"""unittest cases for dicom.dataset module"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import unittest
from dicom.dataset import Dataset, haveNumpy, PropertyError
from dicom.dataelem import DataElement

class DatasetTests(unittest.TestCase):
    def failUnlessRaises(self, excClass, callableObj, *args, **kwargs):
        """Redefine unittest Exception test to return the exception object"""
        # from http://stackoverflow.com/questions/88325/how-do-i-unit-test-an-init-method-of-a-python-class-with-assertraises
        try:
            callableObj(*args, **kwargs)
        except excClass, excObj:
            return excObj # Actually return the exception object
        else:
            if hasattr(excClass,'__name__'): excName = excClass.__name__
            else: excName = str(excClass)
            raise self.failureException, "%s not raised" % excName

    def failUnlessExceptionArgs(self, start_args, excClass, callableObj):
        """Check the expected args were returned from an exception
        start_args -- a string with the start of the expected message
        """
        # based on same link as failUnlessRaises override above
        excObj = self.failUnlessRaises(excClass, callableObj)
        msg = "\nExpected Exception message:\n" + start_args + "\nGot:\n" + excObj[0]
        self.failUnless(excObj[0].startswith(start_args), msg)

    def testAttributeErrorInProperty(self):
        """Dataset: AttributeError in property raises actual error message..."""
        # This comes from bug fix for issue 42
        # First, fake enough to try the pixel_array property
        ds = Dataset()
        ds.PixelData = 'xyzlmnop'
        ds.isLittleEndian = True
#        save_Numpy = haveNumpy
#        haveNumpy = False
        attribute_error_msg = "AttributeError in pixel_array property: " + \
                           "Dataset does not have attribute 'TransferSyntaxUID'"
        self.failUnlessExceptionArgs(attribute_error_msg,
                        PropertyError, ds._get_pixel_array)
        
        
    def dummy_dataset(self):
        # This dataset is used by many of the tests
        ds = Dataset()
        ds.AddNew((0x300a, 0x00b2), "SH", "unit001") # TreatmentMachineName
        return ds
        
    def testSetNewDataElementByName(self):
        """Dataset: set new data_element by name............................."""
        ds = Dataset()
        ds.TreatmentMachineName = "unit #1"
        data_element = ds[0x300a, 0x00b2]
        self.assertEqual(data_element.value, "unit #1", "Unable to set data_element by name")
        self.assertEqual(data_element.VR, "SH", "data_element not the expected VR")
    def testSetExistingDataElementByName(self):
        """Dataset: set existing data_element by name........................"""
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
        """Dataset: if set an item, it must be an DataElement instance......"""
        def callSet():
            ds[0x300a, 0xb2]="unit1" # common error - set data_element instead of data_element.value
            
        ds = Dataset()
        self.assertRaises(TypeError, callSet)
    def test_matching_tags(self):
        """Dataset: key and data_element.tag mismatch raises ValueError......"""
        def set_wrong_tag():
            ds[0x10,0x10] = data_element
        ds = Dataset()
        data_element = DataElement((0x300a, 0x00b2), "SH", "unit001")
        self.assertRaises(ValueError, set_wrong_tag)
    def test_NamedMemberUpdated(self):
        """Dataset: if set data_element by tag, name also reflects change...."""
        ds = self.dummy_dataset()
        ds[0x300a,0xb2].value = "moon_unit"
        self.assertEqual(ds.TreatmentMachineName, 'moon_unit', "Member not updated")
    def testUpdate(self):
        """Dataset: update() method works with tag or name................"""
        ds = self.dummy_dataset()
        pat_data_element = DataElement((0x10,0x12), 'PN', 'Johnny')
        ds.update({'PatientsName': 'John', (0x10,0x12): pat_data_element})
        self.assertEqual(ds[0x10,0x10].value, 'John', "named data_element not set")
        self.assertEqual(ds[0x10,0x12].value, 'Johnny', "set by tag failed")
    def testDir(self):
        """Dataset: dir() returns sorted list of named data_elements........."""
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