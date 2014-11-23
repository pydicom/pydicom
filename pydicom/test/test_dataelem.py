# test_dataelem.py
"""unittest cases for dicom.dataelem module"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

# Many tests of DataElement class are implied in test_dataset also

import unittest
from dicom.dataelem import DataElement
from dicom.dataelem import RawDataElement, DataElement_from_raw
from dicom.tag import Tag
from dicom.dataset import Dataset
from dicom.UID import UID


class DataElementTests(unittest.TestCase):
    def setUp(self):
        self.data_elementSH = DataElement((1, 2), "SH", "hello")
        self.data_elementIS = DataElement((1, 2), "IS", "42")
        self.data_elementDS = DataElement((1, 2), "DS", "42.00001")
        self.data_elementMulti = DataElement((1, 2), "DS",
                                             ['42.1', '42.2', '42.3'])

    def testVM1(self):
        """DataElement: return correct value multiplicity for VM > 1........"""
        VM = self.data_elementMulti.VM
        self.assertEqual(VM, 3,
                         "Wrong Value Multiplicity, expected 3, got %i" % VM)

    def testVM2(self):
        """DataElement: return correct value multiplicity for VM = 1........"""
        VM = self.data_elementIS.VM
        self.assertEqual(VM, 1,
                         "Wrong Value Multiplicity, expected 1, got %i" % VM)

    def testBackslash(self):
        """DataElement: String with '\\' sets multi-valued data_element."""
        data_element = DataElement((1, 2), "DS", r"42.1\42.2\42.3")
        self.assertEqual(data_element.VM, 3, "Did not get a mult-valued value")

    def testUID(self):
        """DataElement: setting or changing UID results in UID type........."""
        ds = Dataset()
        ds.TransferSyntaxUID = "1.2.3"
        self.assertTrue(isinstance(ds.TransferSyntaxUID, UID),
                        "Assignment to UID did not create UID class")
        ds.TransferSyntaxUID += ".4.5.6"
        self.assertTrue(isinstance(ds.TransferSyntaxUID, UID),
                        "+= to UID did not keep as UID class")


class RawDataElementTests(unittest.TestCase):
    def setUp(self):
        # raw data element -> tag VR length value
        #                       value_tell is_implicit_VR is_little_endian'
        # Unknown (not in DICOM dict), non-private, non-group 0 for this test
        self.raw1 = RawDataElement(Tag(0x88880002), None, 4, 0x1111,
                                   0, True, True)

    def testKeyError(self):
        """RawDataElement: conversion of unknown tag throws KeyError........"""
        self.assertRaises(KeyError, DataElement_from_raw, self.raw1)


if __name__ == "__main__":
    unittest.main()
