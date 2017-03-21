# test_dataelem.py
"""unittest cases for pydicom.dataelem module"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

# Many tests of DataElement class are implied in test_dataset also

import unittest

from pydicom.dataelem import DataElement
from pydicom.dataelem import RawDataElement, DataElement_from_raw
from pydicom.dataset import Dataset
from pydicom.tag import Tag
from pydicom.uid import UID


class DataElementTests(unittest.TestCase):
    def setUp(self):
        self.data_elementSH = DataElement((1, 2), "SH", "hello")
        self.data_elementIS = DataElement((1, 2), "IS", "42")
        self.data_elementDS = DataElement((1, 2), "DS", "42.00001")
        self.data_elementMulti = DataElement((1, 2), "DS",
                                             ['42.1', '42.2', '42.3'])
        self.data_elementCommand = DataElement(0x00000000, 'UL', 100)
        self.data_elementPrivate = DataElement(0x00090000, 'UL', 101)
        self.data_elementRetired = DataElement(0x00080010, 'SH', 102)

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

    def testKeyword(self):
        """DataElement: return correct keyword"""
        self.assertEqual(self.data_elementCommand.keyword, 'CommandGroupLength')
        self.assertEqual(self.data_elementPrivate.keyword, '')

    def testRetired(self):
        """DataElement: return correct is_retired"""
        self.assertEqual(self.data_elementCommand.is_retired, False)
        self.assertEqual(self.data_elementRetired.is_retired, True)
        self.assertEqual(self.data_elementPrivate.is_retired, False)

    def testEqualityStandardElement(self):
        """DataElement: equality returns correct value for simple elements"""
        dd = DataElement(0x00100010, 'PN', 'ANON')
        self.assertTrue(dd == dd)
        ee = DataElement(0x00100010, 'PN', 'ANON')
        self.assertTrue(dd == ee)

        # Check value
        ee.value = 'ANAN'
        self.assertFalse(dd == ee)

        # Check tag
        ee = DataElement(0x00100011, 'PN', 'ANON')
        self.assertFalse(dd == ee)

        # Check VR
        ee = DataElement(0x00100010, 'SH', 'ANON')
        self.assertFalse(dd == ee)

        dd = DataElement(0x00080018, 'UI', '1.2.3.4')
        ee = DataElement(0x00080018, 'UI', '1.2.3.4')
        self.assertTrue(dd == ee)

        ee = DataElement(0x00080018, 'PN', '1.2.3.4')
        self.assertFalse(dd == ee)

    def testEqualityPrivateElement(self):
        """DataElement: equality returns correct value for private elements"""
        dd = DataElement(0x01110001, 'PN', 'ANON')
        self.assertTrue(dd == dd)
        ee = DataElement(0x01110001, 'PN', 'ANON')
        self.assertTrue(dd == ee)

        # Check value
        ee.value = 'ANAN'
        self.assertFalse(dd == ee)

        # Check tag
        ee = DataElement(0x01110002, 'PN', 'ANON')
        self.assertFalse(dd == ee)

        # Check VR
        ee = DataElement(0x01110001, 'SH', 'ANON')
        self.assertFalse(dd == ee)

    def testEqualitySequenceElement(self):
        """DataElement: equality returns correct value for sequence elements"""
        dd = DataElement(0x300A00B0, 'SQ', [])
        self.assertTrue(dd == dd)
        ee = DataElement(0x300A00B0, 'SQ', [])
        self.assertTrue(dd == ee)

        # Check value
        e = Dataset()
        e.PatientName = 'ANON'
        ee.value = [e]
        self.assertFalse(dd == ee)

        # Check tag
        ee = DataElement(0x01110002, 'SQ', [])
        self.assertFalse(dd == ee)

        # Check VR
        ee = DataElement(0x300A00B0, 'SH', [])
        self.assertFalse(dd == ee)

        # Check with dataset
        dd = DataElement(0x300A00B0, 'SQ', [Dataset()])
        dd.value[0].PatientName = 'ANON'
        ee = DataElement(0x300A00B0, 'SQ', [Dataset()])
        ee.value[0].PatientName = 'ANON'
        self.assertTrue(dd == ee)

        # Check uneven sequences
        dd.value.append(Dataset())
        dd.value[1].PatientName = 'ANON'
        self.assertFalse(dd == ee)

        ee.value.append(Dataset())
        ee.value[1].PatientName = 'ANON'
        self.assertTrue(dd == ee)
        ee.value.append(Dataset())
        ee.value[2].PatientName = 'ANON'
        self.assertFalse(dd == ee)

    def testEqualityNotElement(self):
        """DataElement: equality returns correct value when not same class"""
        dd = DataElement(0x00100010, 'PN', 'ANON')
        ee = {'0x00100010' : 'ANON'}
        self.assertFalse(dd == ee)

    def testEqualityInheritance(self):
        """DataElement: equality returns correct value for subclasses"""

        class DataElementPlus(DataElement):
            pass

        dd = DataElement(0x00100010, 'PN', 'ANON')
        ee = DataElementPlus(0x00100010, 'PN', 'ANON')
        self.assertTrue(ee == ee)
        self.assertTrue(dd == ee)
        self.assertTrue(ee == dd)

        ee = DataElementPlus(0x00100010, 'PN', 'ANONY')
        self.assertFalse(dd == ee)
        self.assertFalse(ee == dd)

    def test_equality_class_members(self):
        """Test equality is correct when ignored class members differ."""
        dd = DataElement(0x00100010, 'PN', 'ANON')
        dd.showVR = False
        dd.file_tell = 10
        dd.maxBytesToDisplay = 0
        dd.descripWidth = 0
        ee = DataElement(0x00100010, 'PN', 'ANON')
        self.assertTrue(dd == ee)

    def testHash(self):
        """DataElement: hash returns TypeErrpr"""
        dd = DataElement(0x00100010, 'PN', 'ANON')

        def test_hash():
            hash(dd)

        self.assertRaises(TypeError, test_hash)


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
