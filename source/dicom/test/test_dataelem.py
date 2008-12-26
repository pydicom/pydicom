# test_dataelem.py
"""unittest cases for dicom.dataelem module"""
# Copyright 2008, Darcy Mason
# This file is part of pydicom.
#
# pydicom is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# pydicom is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License (license.txt) for more details


# Many tests of DataElement class are implied in test_dataset also

import unittest
from dicom.dataelem import DataElement
from dicom.dataset import Dataset

class DataElementTests(unittest.TestCase):
    def setUp(self):
        self.data_elementSH= DataElement((1,2), "SH", "hello")
        self.data_elementIS = DataElement((1,2), "IS", "42")
        self.data_elementDS = DataElement((1,2), "DS", "42.00001")
        self.data_elementMulti = DataElement((1,2), "DS", ['42.1', '42.2', '42.3'])

    def testVM1(self):
        """DataElement: return correct value multiplicity for VM > 1........"""
        VM = self.data_elementMulti.VM
        self.assertEqual(VM, 3, "Wrong Value Multiplicity, expected 3, got %i" % VM)

    def testVM2(self):
        """DataElement: return correct value multiplicity for VM = 1........"""
        VM = self.data_elementIS.VM
        self.assertEqual(VM, 1, "Wrong Value Multiplicity, expected 1, got %i" % VM)
    
    def testBackslash(self):
        """DataElement: Passing string with '\\' sets multi-valued data_element."""
        data_element = DataElement((1,2), "DS", r"42.1\42.2\42.3") # note r" to avoid \ as escape chr
        self.assertEqual(data_element.VM, 3, "Did not get a mult-valued value")
    
if __name__ == "__main__":
    unittest.main()