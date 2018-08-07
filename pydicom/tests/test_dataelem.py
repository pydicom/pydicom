# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""unittest cases for pydicom.dataelem module"""

# Many tests of DataElement class are implied in test_dataset also

import sys
import unittest

import pytest

from pydicom.charset import default_encoding
from pydicom.dataelem import (
    DataElement,
    RawDataElement,
    DataElement_from_raw,
    isStringOrStringList,
    DeferredDataElement
)
from pydicom.dataset import Dataset
from pydicom.filebase import DicomBytesIO
from pydicom.tag import Tag
from pydicom.uid import UID
from pydicom.valuerep import DSfloat


def test_is_string_like():
    """Test isStringOrStringList"""
    assert isStringOrStringList('some str')
    assert not isStringOrStringList(1234)
    assert isStringOrStringList(['some str', 'list'])
    assert not isStringOrStringList(['some str', 1234])


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

    def testDSFloatConversion(self):
        """Test that strings are correctly converted if changing the value."""
        self.assertTrue(isinstance(self.data_elementDS.value, DSfloat))
        self.assertTrue(isinstance(self.data_elementMulti.value[0], DSfloat))
        self.assertEqual(DSfloat('42.1'), self.data_elementMulti.value[0])

        # multi-value append/insert
        self.data_elementMulti.value.append('42.4')
        self.assertTrue(isinstance(self.data_elementMulti.value[3], DSfloat))
        self.assertEqual(DSfloat('42.4'), self.data_elementMulti.value[3])

        self.data_elementMulti.value.insert(0, '42.0')
        self.assertTrue(isinstance(self.data_elementMulti.value[0], DSfloat))
        self.assertEqual(DSfloat('42.0'), self.data_elementMulti.value[0])

        # change single value of multi-value
        self.data_elementMulti.value[3] = '123.4'
        self.assertTrue(isinstance(self.data_elementMulti.value[3], DSfloat))
        self.assertEqual(DSfloat('123.4'), self.data_elementMulti.value[3])

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
        self.assertEqual(self.data_elementCommand.keyword,
                         'CommandGroupLength')

        self.assertEqual(self.data_elementPrivate.keyword,
                         '')

    def testRetired(self):
        """DataElement: return correct is_retired"""
        self.assertEqual(self.data_elementCommand.is_retired, False)
        self.assertEqual(self.data_elementRetired.is_retired, True)
        self.assertEqual(self.data_elementPrivate.is_retired, False)

    def test_description_group_length(self):
        """Test DataElement.description for Group Length element"""
        elem = DataElement(0x00100000, 'LO', 12345)
        assert elem.description() == 'Group Length'

    def test_description_unknown_private(self):
        """Test DataElement.description with an unknown private element"""
        elem = DataElement(0x00110010, 'LO', 12345)
        elem.private_creator = 'TEST'
        assert elem.description() == 'Private tag data'
        elem = DataElement(0x00110F00, 'LO', 12345)
        assert elem.tag.is_private
        assert not hasattr(elem, 'private_creator')
        assert elem.description() == 'Private tag data'

    def test_description_unknown(self):
        """Test DataElement.description with an unknown element"""
        elem = DataElement(0x00000004, 'LO', 12345)
        assert elem.description() == ''

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
        ee = {'0x00100010': 'ANON'}
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

    def test_inequality_standard(self):
        """Test DataElement.__ne__ for standard element"""
        dd = DataElement(0x00100010, 'PN', 'ANON')
        assert not dd != dd
        ee = DataElement(0x00100010, 'PN', 'ANONA')
        assert dd != ee

        # Check tag
        ee = DataElement(0x00100011, 'PN', 'ANON')
        assert dd != ee

        # Check VR
        ee = DataElement(0x00100010, 'SH', 'ANON')
        assert dd != ee

    def test_inequality_sequence(self):
        """Test DataElement.__ne__ for sequence element"""
        dd = DataElement(0x300A00B0, 'SQ', [])
        assert not dd != dd
        ee = DataElement(0x300A00B0, 'SQ', [])
        assert not dd != ee
        ee = DataElement(0x300A00B0, 'SQ', [Dataset()])
        assert dd != ee

        # Check value
        dd.value = [Dataset()]
        dd[0].PatientName = 'ANON'
        ee[0].PatientName = 'ANON'
        assert not dd != ee
        ee[0].PatientName = 'ANONA'
        assert dd != ee

    def testHash(self):
        """DataElement: hash returns TypeErrpr"""
        dd = DataElement(0x00100010, 'PN', 'ANON')

        def test_hash():
            hash(dd)

        self.assertRaises(TypeError, test_hash)

    def test_repeater_str(self):
        """Test a repeater group element displays the element name."""
        elem = DataElement(0x60023000, 'OB', b'\x00')
        self.assertTrue('Overlay Data' in elem.__str__())

    def test_str_no_vr(self):
        """Test DataElement.__str__ output with no VR"""
        elem = DataElement(0x00100010, 'PN', 'ANON')
        assert "(0010, 0010) Patient's Name" in str(elem)
        assert "PN: 'ANON'" in str(elem)
        elem.showVR = False
        assert "(0010, 0010) Patient's Name" in str(elem)
        assert 'PN' not in str(elem)

    def test_repr_seq(self):
        """Test DataElement.__repr__ with a sequence"""
        elem = DataElement(0x300A00B0, 'SQ', [Dataset()])
        elem[0].PatientID = '1234'
        assert repr(elem) == repr(elem.value)

    @unittest.skipIf(sys.version_info >= (3, ), 'Testing Python 2 behavior')
    def test_unicode(self):
        """Test unicode representation of the DataElement"""
        elem = DataElement(0x00100010, 'PN', u'ANON')
        # Make sure elem.value is actually unicode
        assert isinstance(elem.value, unicode)
        assert unicode(elem) == (
            u"(0010, 0010) Patient's Name                      PN: ANON"
        )
        assert isinstance(unicode(elem), unicode)
        assert not isinstance(unicode(elem), str)
        # Make sure elem.value is still unicode
        assert isinstance(elem.value, unicode)

        # When value is not in compat.text_type
        elem = DataElement(0x00100010, 'LO', 12345)
        assert isinstance(unicode(elem), unicode)
        assert unicode(elem) == (
            u"(0010, 0010) Patient's Name                      LO: 12345"
        )

    def test_getitem_raises(self):
        """Test DataElement.__getitem__ raise if value not indexable"""
        elem = DataElement(0x00100010, 'LO', 12345)
        with pytest.raises(TypeError):
            elem[0]

    def test_private_tag_in_repeater_range(self):
        """Test that an unknown private tag (e.g. a tag not in the private
        dictionary) in the repeater range is not handled as a repeater tag
        if using Implicit Little Endian transfer syntax."""
        # regression test for #689
        ds = Dataset()
        ds[0x50f10010] = RawDataElement(
            Tag(0x50f10010), None, 8, b'FDMS 1.0', 0, True, True)
        ds[0x50f1100a] = RawDataElement(
            Tag(0x50f1100a), None, 6, b'ACC0.6', 0, True, True)
        private_creator_data_elem = ds[0x50f10010]
        assert 'Private Creator' == private_creator_data_elem.name
        assert 'LO' == private_creator_data_elem.VR

        private_data_elem = ds[0x50f1100a]
        assert '[FNC Parameters]' == private_data_elem.name
        assert 'UN' == private_data_elem.VR

    def test_private_repeater_tag(self):
        """Test that a known private tag in the repeater range is correctly
        handled using Implicit Little Endian transfer syntax."""
        ds = Dataset()
        ds[0x60210012] = RawDataElement(
            Tag(0x60210012), None, 12, b'PAPYRUS 3.0 ', 0, True, True)
        ds[0x60211200] = RawDataElement(
            Tag(0x60211200), None, 6, b'123456', 0, True, True)
        private_creator_data_elem = ds[0x60210012]
        assert 'Private Creator' == private_creator_data_elem.name
        assert 'LO' == private_creator_data_elem.VR

        private_data_elem = ds[0x60211200]
        assert '[Overlay ID]' == private_data_elem.name
        assert 'UN' == private_data_elem.VR


class RawDataElementTests(unittest.TestCase):
    def testKeyError(self):
        """RawDataElement: conversion of unknown tag throws KeyError..."""
        # raw data element -> tag VR length value
        #                       value_tell is_implicit_VR is_little_endian'
        # Unknown (not in DICOM dict), non-private, non-group 0 for this test
        raw = RawDataElement(Tag(0x88880002), None, 4, 0x1111,
                             0, True, True)
        self.assertRaises(KeyError, DataElement_from_raw, raw)

    def testValidTag(self):
        """RawDataElement: conversion of known tag succeeds..."""
        raw = RawDataElement(Tag(0x00080020), 'DA', 8, b'20170101',
                             0, False, True)
        element = DataElement_from_raw(raw, default_encoding)
        self.assertEqual(element.name, 'Study Date')
        self.assertEqual(element.VR, 'DA')
        self.assertEqual(element.value, '20170101')

        raw = RawDataElement(Tag(0x00080000), None, 4, b'\x02\x00\x00\x00',
                             0, True, True)
        elem = DataElement_from_raw(raw, default_encoding)
        assert elem.VR == 'UL'

    @unittest.skipIf(sys.version_info >= (3, ), 'Testing Python 2 behavior')
    def testTagWithoutEncodingPython2(self):
        """RawDataElement: no encoding needed in Python 2."""
        raw = RawDataElement(Tag(0x00104000), 'LT', 23,
                             b'comment\\comment2\\comment3',
                             0, False, True)
        element = DataElement_from_raw(raw)
        self.assertEqual(element.name, 'Patient Comments')

    @unittest.skipIf(sys.version_info < (3, ), 'Testing Python 3 behavior')
    def testTagWithoutEncodingPython3(self):
        """RawDataElement: raises if no encoding given in Python 3."""
        self.assertRaises(TypeError, RawDataElement(Tag(0x00104000), 'LT', 14,
                                                    b'comment1\\comment2',
                                                    0, False, True))

    def test_unknown_vr(self):
        """Test converting a raw element with unknown VR"""
        raw = RawDataElement(Tag(0x00080000), 'AA', 8, b'20170101',
                             0, False, True)
        with pytest.raises(NotImplementedError):
            DataElement_from_raw(raw, default_encoding)


def test_deferred_data_element_deprecated():
    """Test the deprecation warning is working"""
    fp = DicomBytesIO()
    fp.is_little_endian = True
    fp.is_implicit_VR = True
    with pytest.deprecated_call():
        elem = DeferredDataElement(0x00000000, 'UL', fp, 0, 0, 4)
