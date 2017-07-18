# test_dataset.py
"""unittest cases for pydicom.dataset module"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

import os
import unittest

from pydicom.dataset import Dataset, PropertyError
from pydicom.dataelem import DataElement, RawDataElement
from pydicom.dicomio import read_file
from pydicom.filebase import DicomBytesIO
from pydicom.tag import Tag
from pydicom.sequence import Sequence
from pydicom import compat


class DatasetTests(unittest.TestCase):
    def failUnlessRaises(self, excClass, callableObj, *args, **kwargs):
        """Redefine unittest Exception test to return the exception object"""
        # from http://stackoverflow.com/questions/88325/
        # how-do-i-unit-test-an-init-method-of-a-python-class-with-assertraises
        try:
            callableObj(*args, **kwargs)
        except excClass as excObj:
            return excObj  # Actually return the exception object
        else:
            if hasattr(excClass, '__name__'):
                excName = excClass.__name__
            else:
                excName = str(excClass)
            raise self.failureException("{0:s} not raised".format(excName))

    def failUnlessExceptionArgs(self, start_args, excClass, callableObj):
        """Check the expected args were returned from an exception
        start_args -- a string with the start of the expected message
        """
        if not compat.in_py2:
            with self.assertRaises(excClass) as cm:
                callableObj()

            excObj = cm.exception
        else:
            excObj = self.failUnlessRaises(excClass, callableObj)

        msg = "\nExpected Exception message:\n" + start_args
        msg += "\nGot:\n" + excObj.args[0]
        self.assertTrue(excObj.args[0].startswith(start_args), msg)

    def testAttributeErrorInProperty(self):
        """Dataset: AttributeError in property raises actual error message.."""
        # This comes from bug fix for issue 42
        # First, fake enough to try the pixel_array property
        ds = Dataset()
        ds.file_meta = Dataset()
        ds.PixelData = 'xyzlmnop'

        def callable_pixel_array():
            ds.pixel_array

        msg = "'Dataset' object has no attribute 'TransferSyntaxUID'"
        self.failUnlessExceptionArgs(msg, AttributeError, callable_pixel_array)

    def test_attribute_error_in_property_correct_debug(self):
        """Test AttributeError in property raises correctly."""
        class Foo(Dataset):
            @property
            def bar(self): return self._barr()

            def _bar(self): return 'OK'

        def test():
            ds = Foo()
            ds.bar

        self.assertRaises(AttributeError, test)
        msg = "'Foo' object has no attribute '_barr'"
        self.failUnlessExceptionArgs(msg, AttributeError, test)

    def testTagExceptionPrint(self):
        # When printing datasets, a tag number should appear in error
        # messages
        ds = Dataset()
        ds.PatientID = "123456" # Valid value
        ds.SmallestImagePixelValue = 0 # Invalid value

        if compat.in_PyPy:
            expected_msg = "Invalid tag (0028, 0106): 'int' has no length"
        else:
            expected_msg = ("Invalid tag (0028, 0106): object of type 'int' "
                            "has no len()")

        self.failUnlessExceptionArgs(expected_msg, TypeError, lambda: str(ds))

    def testTagExceptionWalk(self):
        # When recursing through dataset, a tag number should appear in
        # error messages
        ds = Dataset()
        ds.PatientID = "123456" # Valid value
        ds.SmallestImagePixelValue = 0 # Invalid value

        if compat.in_PyPy:
            expected_msg = "Invalid tag (0028, 0106): 'int' has no length"
        else:
            expected_msg = ("Invalid tag (0028, 0106): object of type 'int' "
                            "has no len()")

        callback = lambda dataset, data_element: str(data_element)
        func = lambda: ds.walk(callback)

        self.failUnlessExceptionArgs(expected_msg, TypeError, func)

    def dummy_dataset(self):
        # This dataset is used by many of the tests
        ds = Dataset()
        ds.add_new((0x300a, 0x00b2), "SH", "unit001")  # TreatmentMachineName
        return ds

    def testSetNewDataElementByName(self):
        """Dataset: set new data_element by name............................"""
        ds = Dataset()
        ds.TreatmentMachineName = "unit #1"
        data_element = ds[0x300a, 0x00b2]
        self.assertEqual(data_element.value, "unit #1",
                         "Unable to set data_element by name")
        self.assertEqual(data_element.VR, "SH",
                         "data_element not the expected VR")

    def testSetExistingDataElementByName(self):
        """Dataset: set existing data_element by name......................."""
        ds = self.dummy_dataset()
        ds.TreatmentMachineName = "unit999"  # change existing value
        self.assertEqual(ds[0x300a, 0x00b2].value, "unit999")

    def testSetNonDicom(self):
        """Dataset: can set class instance property (non-dicom)............."""
        ds = Dataset()
        ds.SomeVariableName = 42
        has_it = hasattr(ds, 'SomeVariableName')
        self.assertTrue(has_it, "Variable did not get created")
        if has_it:
            self.assertEqual(ds.SomeVariableName, 42, "There, but wrong value")

    def testMembership(self):
        """Dataset: can test if item present by 'if <name> in dataset'......"""
        ds = self.dummy_dataset()
        self.assertTrue('TreatmentMachineName' in ds, "membership test failed")
        self.assertTrue('Dummyname' not in ds, "non-member tested as member")

    def testContains(self):
        """Dataset: can test if item present by 'if <tag> in dataset'......."""
        ds = self.dummy_dataset()
        ds.CommandGroupLength = 100 # (0000,0000)
        self.assertTrue((0x300a, 0xb2) in ds, "membership test failed")
        self.assertTrue([0x300a, 0xb2] in ds,
                        "membership test failed when list used")
        self.assertTrue(0x300a00b2 in ds, "membership test failed")
        self.assertTrue(not (0x10, 0x5f) in ds, "non-member tested as member")
        self.assertTrue('CommandGroupLength' in ds)

    def testGetExists1(self):
        """Dataset: dataset.get() returns an existing item by name.........."""
        ds = self.dummy_dataset()
        unit = ds.get('TreatmentMachineName', None)
        self.assertEqual(unit, 'unit001',
                         "dataset.get() did not return existing member by name")

    def testGetExists2(self):
        """Dataset: dataset.get() returns an existing item by long tag......"""
        ds = self.dummy_dataset()
        unit = ds.get(0x300A00B2, None).value
        self.assertEqual(unit, 'unit001',
                         "dataset.get() did not return existing member by long tag")

    def testGetExists3(self):
        """Dataset: dataset.get() returns an existing item by tuple tag....."""
        ds = self.dummy_dataset()
        unit = ds.get((0x300A, 0x00B2), None).value
        self.assertEqual(unit, 'unit001',
                         "dataset.get() did not return existing member by tuple tag")

    def testGetExists4(self):
        """Dataset: dataset.get() returns an existing item by Tag..........."""
        ds = self.dummy_dataset()
        unit = ds.get(Tag(0x300A00B2), None).value
        self.assertEqual(unit, 'unit001',
                         "dataset.get() did not return existing member by tuple tag")

    def testGetDefault1(self):
        """Dataset: dataset.get() returns default for non-existing name ...."""
        ds = self.dummy_dataset()
        not_there = ds.get('NotAMember', "not-there")
        msg = ("dataset.get() did not return default value "
               "for non-member by name")

        self.assertEqual(not_there, "not-there", msg)

    def testGetDefault2(self):
        """Dataset: dataset.get() returns default for non-existing tuple tag"""
        ds = self.dummy_dataset()
        not_there = ds.get((0x9999, 0x9999), "not-there")
        msg = ("dataset.get() did not return default value"
               " for non-member by tuple tag")
        self.assertEqual(not_there, "not-there", msg)

    def testGetDefault3(self):
        """Dataset: dataset.get() returns default for non-existing long tag."""
        ds = self.dummy_dataset()
        not_there = ds.get(0x99999999, "not-there")
        msg = ("dataset.get() did not return default value"
               " for non-member by long tag")
        self.assertEqual(not_there, "not-there", msg)

    def testGetDefault4(self):
        """Dataset: dataset.get() returns default for non-existing Tag......"""
        ds = self.dummy_dataset()
        not_there = ds.get(Tag(0x99999999), "not-there")
        msg = ("dataset.get() did not return default value"
               " for non-member by Tag")
        self.assertEqual(not_there, "not-there", msg)

    def testGetFromRaw(self):
        """Dataset: get(tag) returns same object as ds[tag] for raw element."""
        # This came from issue 88, where get(tag#) returned a RawDataElement,
        #     while get(name) converted to a true DataElement
        test_tag = 0x100010
        test_elem = RawDataElement(Tag(test_tag), 'PN', 4, b'test',
                                   0, True, True)
        ds = Dataset({Tag(test_tag): test_elem})
        by_get = ds.get(test_tag)
        by_item = ds[test_tag]

        msg = ("Dataset.get() returned different objects for ds.get(tag) "
               "and ds[tag]:\nBy get():%r\nBy ds[tag]:%r\n")
        self.assertEqual(by_get, by_item, msg % (by_get, by_item))

    def test__setitem__(self):
        """Dataset: if set an item, it must be a DataElement instance......."""
        def callSet():
            # common error - set data_element instead of data_element.value
            ds[0x300a, 0xb2] = "unit1"

        ds = Dataset()
        self.assertRaises(TypeError, callSet)

    def test_matching_tags(self):
        """Dataset: key and data_element.tag mismatch raises ValueError....."""
        def set_wrong_tag():
            ds[0x10, 0x10] = data_element
        ds = Dataset()
        data_element = DataElement((0x300a, 0x00b2), "SH", "unit001")
        self.assertRaises(ValueError, set_wrong_tag)

    def test_NamedMemberUpdated(self):
        """Dataset: if set data_element by tag, name also reflects change..."""
        ds = self.dummy_dataset()
        ds[0x300a, 0xb2].value = "moon_unit"
        self.assertEqual(ds.TreatmentMachineName, 'moon_unit',
                         "Member not updated")

    def testUpdate(self):
        """Dataset: update() method works with tag or name.................."""
        ds = self.dummy_dataset()
        pat_data_element = DataElement((0x10, 0x12), 'PN', 'Johnny')
        ds.update({'PatientName': 'John', (0x10, 0x12): pat_data_element})
        self.assertEqual(ds[0x10, 0x10].value, 'John',
                         "named data_element not set")
        self.assertEqual(ds[0x10, 0x12].value, 'Johnny', "set by tag failed")

    def testDir(self):
        """Dataset: dir() returns sorted list of named data_elements........"""
        ds = self.dummy_dataset()
        ds.PatientName = "name"
        ds.PatientID = "id"
        ds.NonDicomVariable = "junk"
        ds.add_new((0x18, 0x1151), "IS", 150)  # X-ray Tube Current
        ds.add_new((0x1111, 0x123), "DS", "42.0")  # private - no name in dir()
        expected = ['PatientID', 'PatientName', 'TreatmentMachineName',
                    'XRayTubeCurrent']
        self.assertEqual(ds.dir(), expected,
                         "dir() returned %s, expected %s" % (str(ds.dir()), str(expected)))

    def testDeleteDicomAttr(self):
        """Dataset: delete DICOM attribute by name.........................."""
        def testAttribute():
            ds.TreatmentMachineName

        ds = self.dummy_dataset()
        del ds.TreatmentMachineName
        self.assertRaises(AttributeError, testAttribute)

    def testDeleteDicomCommandGroupLength(self):
        """Dataset: delete CommandGroupLength doesn't raise AttributeError.."""
        def testAttribute():
            ds.CommandGroupLength

        ds = self.dummy_dataset()
        ds.CommandGroupLength = 100 # (0x0000, 0x0000)
        del ds.CommandGroupLength
        self.assertRaises(AttributeError, testAttribute)

    def testDeleteOtherAttr(self):
        """Dataset: delete non-DICOM attribute by name......................"""
        ds = self.dummy_dataset()
        ds.meaningoflife = 42
        del ds.meaningoflife

    def testDeleteDicomAttrWeDontHave(self):
        """Dataset: try delete of missing DICOM attribute..................."""
        def try_delete():
            del ds.PatientName
        ds = self.dummy_dataset()
        self.assertRaises(AttributeError, try_delete)

    def testDeleteItemLong(self):
        """Dataset: delete item by tag number (long)..................."""
        ds = self.dummy_dataset()
        del ds[0x300a00b2]

    def testDeleteItemTuple(self):
        """Dataset: delete item by tag number (tuple).................."""
        ds = self.dummy_dataset()
        del ds[0x300a, 0x00b2]

    def testDeleteNonExistingItem(self):
        """Dataset: raise KeyError for non-existing item delete........"""
        ds = self.dummy_dataset()

        def try_delete():
            del ds[0x10, 0x10]
        self.assertRaises(KeyError, try_delete)

    def testEqualityNoSequence(self):
        """Dataset: equality returns correct value with simple dataset"""
        d = Dataset()
        d.SOPInstanceUID = '1.2.3.4'
        self.assertTrue(d == d)

        e = Dataset()
        e.SOPInstanceUID = '1.2.3.4'
        self.assertTrue(d == e)

        e.SOPInstanceUID = '1.2.3.5'
        self.assertFalse(d == e)

        # Check VR
        del e.SOPInstanceUID
        e.add(DataElement(0x00080018, 'PN', '1.2.3.4'))
        self.assertFalse(d == e)

        # Check Tag
        del e.SOPInstanceUID
        e.StudyInstanceUID = '1.2.3.4'
        self.assertFalse(d == e)

        # Check missing Element in self
        e.SOPInstanceUID = '1.2.3.4'
        self.assertFalse(d == e)

        # Check missing Element in other
        d = Dataset()
        d.SOPInstanceUID = '1.2.3.4'
        d.StudyInstanceUID = '1.2.3.4.5'

        e = Dataset()
        e.SOPInstanceUID = '1.2.3.4'
        self.assertFalse(d == e)

    def testEqualityPrivate(self):
        """Dataset: equality returns correct value when dataset has private elements"""
        d = Dataset()
        d_elem = DataElement(0x01110001, 'PN', 'Private')
        self.assertTrue(d == d)
        d.add(d_elem)

        e = Dataset()
        e_elem = DataElement(0x01110001, 'PN', 'Private')
        e.add(e_elem)
        self.assertTrue(d == e)

        e[0x01110001].value = 'Public'
        self.assertFalse(d == e)

    def testEqualitySequence(self):
        """Dataset: equality returns correct value when dataset has sequences"""
        # Test even sequences
        d = Dataset()
        d.SOPInstanceUID = '1.2.3.4'
        d.BeamSequence = []
        beam_seq = Dataset()
        beam_seq.PatientName = 'ANON'
        d.BeamSequence.append(beam_seq)
        self.assertTrue(d == d)

        e = Dataset()
        e.SOPInstanceUID = '1.2.3.4'
        e.BeamSequence = []
        beam_seq = Dataset()
        beam_seq.PatientName = 'ANON'
        e.BeamSequence.append(beam_seq)
        self.assertTrue(d == e)

        e.BeamSequence[0].PatientName = 'ANONY'
        self.assertFalse(d == e)

        # Test uneven sequences
        e.BeamSequence[0].PatientName = 'ANON'
        self.assertTrue(d == e)

        e.BeamSequence.append(beam_seq)
        self.assertFalse(d == e)

        d.BeamSequence.append(beam_seq)
        self.assertTrue(d == e)
        d.BeamSequence.append(beam_seq)
        self.assertFalse(d == e)

    def testEqualityNotDataset(self):
        """Dataset: equality returns correct value when not the same class"""
        d = Dataset()
        d.SOPInstanceUID = '1.2.3.4'
        self.assertFalse(d == {'SOPInstanceUID' : '1.2.3.4'})

    def testEqualityUnknown(self):
        """Dataset: equality returns correct value with extra members """
        d = Dataset()
        d.SOPEustaceUID = '1.2.3.4'
        self.assertTrue(d == d)

        e = Dataset()
        e.SOPEustaceUID = '1.2.3.4'
        self.assertTrue(d == e)

        e.SOPEustaceUID = '1.2.3.5'
        self.assertFalse(d == e)

    def testEqualityInheritance(self):
        """Dataset: equality returns correct value for subclass """

        class DatasetPlus(Dataset):
            pass

        d = Dataset()
        d.PatientName = 'ANON'
        e = DatasetPlus()
        e.PatientName = 'ANON'
        self.assertTrue(d == e)
        self.assertTrue(e == d)
        self.assertTrue(e == e)

        e.PatientName = 'ANONY'
        self.assertFalse(d == e)
        self.assertFalse(e == d)

    def test_inequality(self):
        """Test inequality operator"""
        d = Dataset()
        d.SOPInstanceUID = '1.2.3.4'
        self.assertFalse(d != d)

        e = Dataset()
        e.SOPInstanceUID = '1.2.3.5'
        self.assertTrue(d != e)

    def testHash(self):
        """DataElement: hash returns TypeError"""

        def test_hash():
            d = Dataset()
            d.PatientName = 'ANON'
            hash(d)

        self.assertRaises(TypeError, test_hash)

    def test_property(self):
        """Test properties work OK."""
        class DSPlus(Dataset):
            @property
            def test(self):
                return self._test

            @test.setter
            def test(self, value):
                self._test = value

        dsp = DSPlus()
        dsp.test = 'ABCD'
        self.assertEqual(dsp.test, 'ABCD')

    def test_add_repeater_elem_by_keyword(self):
        """Repeater using keyword to add repeater group elements raises ValueError."""
        ds = Dataset()
        def test():
            ds.OverlayData = b'\x00'
        self.assertRaises(ValueError, test)

    def test_setitem_slice_raises(self):
        """Test Dataset.__setitem__ raises if slicing used."""
        ds = Dataset()
        self.assertRaises(NotImplementedError, ds.__setitem__,
                          slice(None), Dataset())

    def test_getitem_slice_raises(self):
        """Test Dataset.__getitem__ raises if slice Tags invalid."""
        ds = Dataset()
        self.assertRaises(ValueError, ds.__getitem__, slice(None,-1))
        self.assertRaises(ValueError, ds.__getitem__, slice(-1, -1))
        self.assertRaises(ValueError, ds.__getitem__, slice(-1))

    def test_empty_slice(self):
        """Test Dataset slicing with empty Dataset."""
        ds = Dataset()
        self.assertEqual(ds[:], Dataset())
        self.assertRaises(ValueError, ds.__getitem__, slice(None,-1))
        self.assertRaises(ValueError, ds.__getitem__, slice(-1, -1))
        self.assertRaises(ValueError, ds.__getitem__, slice(-1))
        self.assertRaises(NotImplementedError, ds.__setitem__,
                          slice(None), Dataset())

    def test_getitem_slice(self):
        """Test Dataset.__getitem__ using slices."""
        ds = Dataset()
        ds.CommandGroupLength = 120 # 0000,0000
        ds.CommandLengthToEnd = 111 # 0000,0001
        ds.Overlays = 12 # 0000,51B0
        ds.LengthToEnd = 12 # 0008,0001
        ds.SOPInstanceUID = '1.2.3.4' # 0008,0018
        ds.SkipFrameRangeFlag = 'TEST' # 0008,9460
        ds.add_new(0x00090001, 'PN', 'CITIZEN^1')
        ds.add_new(0x00090002, 'PN', 'CITIZEN^2')
        ds.add_new(0x00090003, 'PN', 'CITIZEN^3')
        ds.add_new(0x00090004, 'PN', 'CITIZEN^4')
        ds.add_new(0x00090005, 'PN', 'CITIZEN^5')
        ds.add_new(0x00090006, 'PN', 'CITIZEN^6')
        ds.add_new(0x00090007, 'PN', 'CITIZEN^7')
        ds.add_new(0x00090008, 'PN', 'CITIZEN^8')
        ds.add_new(0x00090009, 'PN', 'CITIZEN^9')
        ds.add_new(0x00090010, 'PN', 'CITIZEN^10')
        ds.PatientName = 'CITIZEN^Jan' # 0010,0010
        ds.PatientID = '12345' # 0010,0010
        ds.ExaminedBodyThickness = 1.223 # 0010,9431
        ds.BeamSequence = [Dataset()] # 300A,00B0
        ds.BeamSequence[0].PatientName = 'ANON'

        # Slice all items - should return original dataset
        self.assertEqual(ds[:], ds)

        # Slice starting from and including (0008,0001)
        test_ds = ds[0x00080001:]
        self.assertFalse('CommandGroupLength' in test_ds)
        self.assertFalse('CommandLengthToEnd' in test_ds)
        self.assertFalse('Overlays' in test_ds)
        self.assertTrue('LengthToEnd' in test_ds)
        self.assertTrue('BeamSequence' in test_ds)

        # Slice ending at and not including (0009,0002)
        test_ds = ds[:0x00090002]
        self.assertTrue('CommandGroupLength' in test_ds)
        self.assertTrue('CommandLengthToEnd' in test_ds)
        self.assertTrue('Overlays' in test_ds)
        self.assertTrue('LengthToEnd' in test_ds)
        self.assertTrue(0x00090001 in test_ds)
        self.assertFalse(0x00090002 in test_ds)
        self.assertFalse('BeamSequence' in test_ds)

        # Slice with a step - every second tag
        # Should return zeroth tag, then second, fourth, etc...
        test_ds = ds[::2]
        self.assertTrue('CommandGroupLength' in test_ds)
        self.assertFalse('CommandLengthToEnd' in test_ds)
        self.assertTrue(0x00090001 in test_ds)
        self.assertFalse(0x00090002 in test_ds)

        # Slice starting at and including (0008,0018) and ending at and not
        #   including (0009,0008)
        test_ds = ds[0x00080018:0x00090008]
        self.assertTrue('SOPInstanceUID' in test_ds)
        self.assertTrue(0x00090007 in test_ds)
        self.assertFalse(0x00090008 in test_ds)

        # Slice starting at and including (0008,0018) and ending at and not
        #   including (0009,0008), every third element
        test_ds = ds[0x00080018:0x00090008:3]
        self.assertTrue('SOPInstanceUID' in test_ds)
        self.assertFalse(0x00090001 in test_ds)
        self.assertTrue(0x00090002 in test_ds)
        self.assertFalse(0x00090003 in test_ds)
        self.assertFalse(0x00090004 in test_ds)
        self.assertTrue(0x00090005 in test_ds)
        self.assertFalse(0x00090006 in test_ds)
        self.assertFalse(0x00090008 in test_ds)

        # Slice starting and ending (and not including) (0008,0018)
        self.assertEqual(ds[(0x0008,0x0018):(0x0008,0x0018)], Dataset())

        # Test slicing using other acceptable Tag initialisations
        self.assertTrue('SOPInstanceUID' in ds[(0x00080018):(0x00080019)])
        self.assertTrue('SOPInstanceUID' in ds[(0x0008,0x0018):(0x0008,0x0019)])
        self.assertTrue('SOPInstanceUID' in ds['0x00080018':'0x00080019'])

    def test_delitem_slice(self):
        """Test Dataset.__delitem__ using slices."""
        ds = Dataset()
        ds.CommandGroupLength = 120 # 0000,0000
        ds.CommandLengthToEnd = 111 # 0000,0001
        ds.Overlays = 12 # 0000,51B0
        ds.LengthToEnd = 12 # 0008,0001
        ds.SOPInstanceUID = '1.2.3.4' # 0008,0018
        ds.SkipFrameRangeFlag = 'TEST' # 0008,9460
        ds.add_new(0x00090001, 'PN', 'CITIZEN^1')
        ds.add_new(0x00090002, 'PN', 'CITIZEN^2')
        ds.add_new(0x00090003, 'PN', 'CITIZEN^3')
        ds.add_new(0x00090004, 'PN', 'CITIZEN^4')
        ds.add_new(0x00090005, 'PN', 'CITIZEN^5')
        ds.add_new(0x00090006, 'PN', 'CITIZEN^6')
        ds.add_new(0x00090007, 'PN', 'CITIZEN^7')
        ds.add_new(0x00090008, 'PN', 'CITIZEN^8')
        ds.add_new(0x00090009, 'PN', 'CITIZEN^9')
        ds.add_new(0x00090010, 'PN', 'CITIZEN^10')
        ds.PatientName = 'CITIZEN^Jan' # 0010,0010
        ds.PatientID = '12345' # 0010,0010
        ds.ExaminedBodyThickness = 1.223 # 0010,9431
        ds.BeamSequence = [Dataset()] # 300A,00B0
        ds.BeamSequence[0].PatientName = 'ANON'

        # Delete the 0x0009 group
        del ds[0x00090000:0x00100000]
        self.assertTrue('SkipFrameRangeFlag' in ds)
        self.assertFalse(0x00090001 in ds)
        self.assertFalse(0x00090010 in ds)
        self.assertTrue('PatientName' in ds)

    def test_group_dataset(self):
        """Test Dataset.group_dataset"""
        ds = Dataset()
        ds.CommandGroupLength = 120 # 0000,0000
        ds.CommandLengthToEnd = 111 # 0000,0001
        ds.Overlays = 12 # 0000,51B0
        ds.LengthToEnd = 12 # 0008,0001
        ds.SOPInstanceUID = '1.2.3.4' # 0008,0018
        ds.SkipFrameRangeFlag = 'TEST' # 0008,9460

        # Test getting group 0x0000
        group0000 = ds.group_dataset(0x0000)
        self.assertTrue('CommandGroupLength' in group0000)
        self.assertTrue('CommandLengthToEnd' in group0000)
        self.assertTrue('Overlays' in group0000)
        self.assertFalse('LengthToEnd' in group0000)
        self.assertFalse('SOPInstanceUID' in group0000)
        self.assertFalse('SkipFrameRangeFlag' in group0000)

        # Test getting group 0x0008
        group0000 = ds.group_dataset(0x0008)
        self.assertFalse('CommandGroupLength' in group0000)
        self.assertFalse('CommandLengthToEnd' in group0000)
        self.assertFalse('Overlays' in group0000)
        self.assertTrue('LengthToEnd' in group0000)
        self.assertTrue('SOPInstanceUID' in group0000)
        self.assertTrue('SkipFrameRangeFlag' in group0000)

    def test_get_item(self):
        """Test Dataset.get_item"""
        # TODO: Add test for deferred read
        ds = Dataset()
        ds.CommandGroupLength = 120 # 0000,0000
        ds.SOPInstanceUID = '1.2.3.4' # 0008,0018

        # Test non-deferred read
        self.assertEqual(ds.get_item(0x00000000), ds[0x00000000])
        self.assertEqual(ds.get_item(0x00000000).value, 120)
        self.assertEqual(ds.get_item(0x00080018), ds[0x00080018])
        self.assertEqual(ds.get_item(0x00080018).value, '1.2.3.4')

    def test_remove_private_tags(self):
        """Test Dataset.remove_private_tags"""
        ds = Dataset()
        ds.CommandGroupLength = 120 # 0000,0000
        ds.SkipFrameRangeFlag = 'TEST' # 0008,9460
        ds.add_new(0x00090001, 'PN', 'CITIZEN^1')
        ds.add_new(0x00090010, 'PN', 'CITIZEN^10')
        ds.PatientName = 'CITIZEN^Jan' # 0010,0010

        ds.remove_private_tags()
        self.assertEqual(ds[0x00090000:0x00100000], Dataset())
        self.assertTrue('CommandGroupLength' in ds)
        self.assertTrue('SkipFrameRangeFlag' in ds)
        self.assertTrue('PatientName' in ds)

    def test_data_element(self):
        """Test Dataset.data_element."""
        ds = Dataset()
        ds.CommandGroupLength = 120
        ds.SkipFrameRangeFlag = 'TEST'
        ds.add_new(0x00090001, 'PN', 'CITIZEN^1')
        ds.BeamSequence = [Dataset()]
        ds.BeamSequence[0].PatientName = 'ANON'
        self.assertEqual(ds.data_element('CommandGroupLength'), ds[0x00000000])
        self.assertEqual(ds.data_element('BeamSequence'), ds[0x300A00B0])

    def test_iterall(self):
        """Test Dataset.iterall"""
        ds = Dataset()
        ds.CommandGroupLength = 120
        ds.SkipFrameRangeFlag = 'TEST'
        ds.add_new(0x00090001, 'PN', 'CITIZEN^1')
        ds.BeamSequence = [Dataset()]
        ds.BeamSequence[0].PatientName = 'ANON'
        elem_gen = ds.iterall()
        self.assertEqual(ds.data_element('CommandGroupLength'), next(elem_gen))
        self.assertEqual(ds.data_element('SkipFrameRangeFlag'), next(elem_gen))
        self.assertEqual(ds[0x00090001], next(elem_gen))
        self.assertEqual(ds.data_element('BeamSequence'), next(elem_gen))
        self.assertEqual(ds.BeamSequence[0].data_element('PatientName'), next(elem_gen))

    def test_save_as(self):
        """Test Dataset.save_as"""
        fp = DicomBytesIO()
        ds = Dataset()
        ds.PatientName = 'CITIZEN'
        # Raise AttributeError if is_implicit_VR or is_little_endian missing
        self.assertRaises(AttributeError, ds.save_as, fp, write_like_original=False)
        ds.is_implicit_VR = True
        self.assertRaises(AttributeError, ds.save_as, fp, write_like_original=False)
        ds.is_little_endian = True
        del ds.is_implicit_VR
        self.assertRaises(AttributeError, ds.save_as, fp, write_like_original=False)
        ds.is_implicit_VR = True
        ds.file_meta = Dataset()
        ds.file_meta.MediaStorageSOPClassUID = '1.1'
        ds.file_meta.MediaStorageSOPInstanceUID = '1.2'
        ds.file_meta.TransferSyntaxUID = '1.3'
        ds.file_meta.ImplementationClassUID = '1.4'
        ds.save_as(fp, write_like_original=False)


class DatasetElementsTests(unittest.TestCase):
    """Test valid assignments of data elements"""
    def setUp(self):
        self.ds = Dataset()
        self.sub_ds1 = Dataset()
        self.sub_ds2 = Dataset()

    def testSequenceAssignment(self):
        """Assignment to SQ works only if valid Sequence assigned......"""
        def try_non_Sequence():
            self.ds.ConceptCodeSequence = [1, 2, 3]
        msg = "Assigning non-sequence to SQ data element did not raise error"
        self.assertRaises(TypeError, try_non_Sequence, msg=msg)
        # check also that assigning proper sequence *does* work
        self.ds.ConceptCodeSequence = [self.sub_ds1, self.sub_ds2]
        self.assertTrue(isinstance(self.ds.ConceptCodeSequence, Sequence),
                        "Sequence assignment did not result in Sequence type")


class FileDatasetTests(unittest.TestCase):
    def setUp(self):
        test_dir = os.path.dirname(__file__)
        self.test_file = os.path.join(test_dir, 'test_files', 'CT_small.dcm')

    def testEqualityFileMeta(self):
        """Dataset: equality returns correct value if with metadata"""
        d = read_file(self.test_file)
        e = read_file(self.test_file)
        self.assertTrue(d == e)

        e.is_implicit_VR = not e.is_implicit_VR
        self.assertFalse(d == e)

        e.is_implicit_VR = not e.is_implicit_VR
        self.assertTrue(d == e)
        e.is_little_endian = not e.is_little_endian
        self.assertFalse(d == e)

        e.is_little_endian = not e.is_little_endian
        self.assertTrue(d == e)
        e.filename = 'test_filename.dcm'
        self.assertFalse(d == e)


if __name__ == "__main__":
    unittest.main()
