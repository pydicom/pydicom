# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Unit tests for the pydicom.dataset module."""

import pytest

import pydicom
from pydicom import compat
from pydicom.data import get_testdata_files
from pydicom.dataelem import DataElement, RawDataElement
from pydicom.dataset import Dataset, FileDataset, validate_file_meta
from pydicom import dcmread
from pydicom.filebase import DicomBytesIO
from pydicom.overlay_data_handlers import numpy_handler as NP_HANDLER
from pydicom.sequence import Sequence
from pydicom.tag import Tag
from pydicom.uid import (
    ImplicitVRLittleEndian,
    ExplicitVRBigEndian,
    PYDICOM_IMPLEMENTATION_UID
)


class BadRepr(object):
    def __repr__(self):
        raise ValueError("bad repr")


class TestDataset(object):
    """Tests for dataset.Dataset."""
    def setup(self):
        self.ds = Dataset()
        self.ds.TreatmentMachineName = "unit001"

    def test_attribute_error_in_property(self):
        """Dataset: AttributeError in property raises actual error message."""
        # This comes from bug fix for issue 42
        # First, fake enough to try the pixel_array property
        ds = Dataset()
        ds.file_meta = Dataset()
        ds.PixelData = 'xyzlmnop'
        msg_from_gdcm = r"'Dataset' object has no attribute 'filename'"
        msg_from_numpy = (r"'Dataset' object has no attribute "
                          "'TransferSyntaxUID'")
        msg_from_pillow = (r"'Dataset' object has no attribute "
                           "'PixelRepresentation'")
        msg = "(" + "|".join(
            [msg_from_gdcm, msg_from_numpy, msg_from_pillow]) + ")"
        with pytest.raises(AttributeError, match=msg):
            ds.pixel_array

    def test_for_stray_raw_data_element(self):
        dataset = Dataset()
        dataset.PatientName = 'MacDonald^George'
        sub_ds = Dataset()
        sub_ds.BeamNumber = '1'
        dataset.BeamSequence = Sequence([sub_ds])
        fp = DicomBytesIO()
        pydicom.write_file(fp, dataset)

        def _reset():
            fp.seek(0)
            ds1 = pydicom.dcmread(fp, force=True)
            fp.seek(0)
            ds2 = pydicom.dcmread(fp, force=True)
            return ds1, ds2

        ds1, ds2 = _reset()
        assert ds1 == ds2

        ds1, ds2 = _reset()
        ds1.PatientName  # convert from raw
        assert ds1 == ds2

        ds1, ds2 = _reset()
        ds2.PatientName
        assert ds1 == ds2

        ds1, ds2 = _reset()
        ds2.PatientName
        assert ds2 == ds1  # compare in other order

        ds1, ds2 = _reset()
        ds2.BeamSequence[0].BeamNumber
        assert ds1 == ds2

        # add a new element to one ds sequence item
        ds1, ds2 = _reset()
        ds2.BeamSequence[0].BeamName = '1'
        assert ds1 != ds2

        # change a value in a sequence item
        ds1, ds2 = _reset()
        ds2.BeamSequence[0].BeamNumber = '2'
        assert ds2 != ds1

        fp.close()

    def test_attribute_error_in_property_correct_debug(self):
        """Test AttributeError in property raises correctly."""
        class Foo(Dataset):
            @property
            def bar(self):
                return self._barr()

            def _bar(self):
                return 'OK'

        def test():
            ds = Foo()
            ds.bar

        msg = r"'Foo' object has no attribute '_barr'"
        with pytest.raises(AttributeError, match=msg):
            test()

    def test_tag_exception_print(self):
        """Test that tag appears in exception messages."""
        ds = Dataset()
        ds.PatientID = "123456"  # Valid value
        ds.SmallestImagePixelValue = BadRepr()  # Invalid value

        msg = r"With tag \(0028, 0106\) got exception: bad repr"
        with pytest.raises(ValueError, match=msg):
            str(ds)

    def test_tag_exception_walk(self):
        """Test that tag appears in exceptions raised during recursion."""
        ds = Dataset()
        ds.PatientID = "123456"  # Valid value
        ds.SmallestImagePixelValue = BadRepr()  # Invalid value

        def callback(dataset, data_element):
            return str(data_element)

        def func(dataset=ds):
            return dataset.walk(callback)

        msg = r"With tag \(0028, 0106\) got exception: bad repr"
        with pytest.raises(ValueError, match=msg):
            func()

    def test_set_new_data_element_by_name(self):
        """Dataset: set new data_element by name."""
        ds = Dataset()
        ds.TreatmentMachineName = "unit #1"
        data_element = ds[0x300a, 0x00b2]
        assert "unit #1" == data_element.value
        assert "SH" == data_element.VR

    def test_set_existing_data_element_by_name(self):
        """Dataset: set existing data_element by name."""
        self.ds.TreatmentMachineName = "unit999"  # change existing value
        assert "unit999" == self.ds[0x300a, 0x00b2].value

    def test_set_non_dicom(self):
        """Dataset: can set class instance property (non-dicom)."""
        ds = Dataset()
        ds.SomeVariableName = 42
        assert hasattr(ds, 'SomeVariableName')
        assert 42 == ds.SomeVariableName

    def test_membership(self):
        """Dataset: can test if item present by 'if <name> in dataset'."""
        assert 'TreatmentMachineName' in self.ds
        assert 'Dummyname' not in self.ds

    def test_contains(self):
        """Dataset: can test if item present by 'if <tag> in dataset'."""
        self.ds.CommandGroupLength = 100  # (0000,0000)
        assert (0x300a, 0xb2) in self.ds
        assert [0x300a, 0xb2] in self.ds
        assert 0x300a00b2 in self.ds
        assert (0x10, 0x5f) not in self.ds
        assert 'CommandGroupLength' in self.ds
        # Use a negative tag to cause an exception
        assert (-0x0010, 0x0010) not in self.ds
        # Random non-existent property
        assert 'random name' not in self.ds

    def test_clear(self):
        assert 1 == len(self.ds)
        self.ds.clear()
        assert 0 == len(self.ds)

    def test_pop(self):
        with pytest.raises(KeyError):
            self.ds.pop(0x300a00b244)
        assert 'default' == self.ds.pop('dummy', 'default')
        elem = self.ds.pop(0x300a00b2)
        assert 'unit001' == elem.value
        with pytest.raises(KeyError):
            self.ds.pop(0x300a00b2)

    def test_pop_using_tuple(self):
        elem = self.ds.pop((0x300a, 0x00b2))
        assert 'unit001' == elem.value
        with pytest.raises(KeyError):
            self.ds.pop((0x300a, 0x00b2))

    def test_pop_using_keyword(self):
        with pytest.raises(KeyError):
            self.ds.pop('InvalidName')
        elem = self.ds.pop('TreatmentMachineName')
        assert 'unit001' == elem.value
        with pytest.raises(KeyError):
            self.ds.pop('TreatmentMachineName')

    def test_popitem(self):
        elem = self.ds.popitem()
        assert 0x300a00b2 == elem[0]
        assert 'unit001' == elem[1].value
        with pytest.raises(KeyError):
            self.ds.popitem()

    def test_setdefault(self):
        elem = self.ds.setdefault(0x300a00b2, 'foo')
        assert 'unit001' == elem.value
        elem = self.ds.setdefault(
            0x00100010, DataElement(0x00100010, 'PN', "Test")
        )
        assert 'Test' == elem.value
        assert 2 == len(self.ds)

    def test_setdefault_tuple(self):
        elem = self.ds.setdefault((0x300a, 0x00b2), 'foo')
        assert 'unit001' == elem.value
        elem = self.ds.setdefault(
            (0x0010, 0x0010), DataElement(0x00100010, 'PN', "Test")
        )
        assert 'Test' == elem.value
        assert 2 == len(self.ds)

    def test_setdefault_use_value(self):
        elem = self.ds.setdefault((0x0010, 0x0010), "Test")
        assert 'Test' == elem.value
        assert 2 == len(self.ds)
        with pytest.raises(KeyError, match=r'Tag \(0011, 0010\) not found '
                                           r'in DICOM dictionary'):
            self.ds.setdefault((0x0011, 0x0010), "Test")

    def test_setdefault_keyword(self):
        elem = self.ds.setdefault('TreatmentMachineName', 'foo')
        assert 'unit001' == elem.value
        elem = self.ds.setdefault(
            'PatientName', DataElement(0x00100010, 'PN', "Test")
        )
        assert 'Test' == elem.value
        assert 2 == len(self.ds)

    def test_get_exists1(self):
        """Dataset: dataset.get() returns an existing item by name."""
        assert 'unit001' == self.ds.get('TreatmentMachineName', None)

    def test_get_exists2(self):
        """Dataset: dataset.get() returns an existing item by long tag."""
        assert 'unit001' == self.ds.get(0x300A00B2, None).value

    def test_get_exists3(self):
        """Dataset: dataset.get() returns an existing item by tuple tag."""
        assert 'unit001' == self.ds.get((0x300A, 0x00B2), None).value

    def test_get_exists4(self):
        """Dataset: dataset.get() returns an existing item by Tag."""
        assert 'unit001' == self.ds.get(Tag(0x300A00B2), None).value

    def test_get_default1(self):
        """Dataset: dataset.get() returns default for non-existing name."""
        assert "not-there" == self.ds.get('NotAMember', "not-there")

    def test_get_default2(self):
        """Dataset: dataset.get() returns default for non-existing tuple tag"""
        assert "not-there" == self.ds.get((0x9999, 0x9999), "not-there")

    def test_get_default3(self):
        """Dataset: dataset.get() returns default for non-existing long tag."""
        assert "not-there" == self.ds.get(0x99999999, "not-there")

    def test_get_default4(self):
        """Dataset: dataset.get() returns default for non-existing Tag."""
        assert "not-there" == self.ds.get(Tag(0x99999999), "not-there")

    def test_get_raises(self):
        """Test Dataset.get() raises exception when invalid Tag"""
        with pytest.raises(TypeError,
                           match=r'Dataset.get key must be a string or tag'):
            self.ds.get(-0x0010, 0x0010)

    def test_get_from_raw(self):
        """Dataset: get(tag) returns same object as ds[tag] for raw element."""
        # This came from issue 88, where get(tag#) returned a RawDataElement,
        #     while get(name) converted to a true DataElement
        test_tag = 0x100010
        test_elem = RawDataElement(Tag(test_tag), 'PN', 4, b'test',
                                   0, True, True)
        ds = Dataset({Tag(test_tag): test_elem})
        assert ds[test_tag] == ds.get(test_tag)

    def test__setitem__(self):
        """Dataset: if set an item, it must be a DataElement instance."""
        ds = Dataset()
        with pytest.raises(TypeError):
            ds[0x300a, 0xb2] = "unit1"

    def test_matching_tags(self):
        """Dataset: key and data_element.tag mismatch raises ValueError."""
        ds = Dataset()
        data_element = DataElement((0x300a, 0x00b2), "SH", "unit001")
        with pytest.raises(ValueError):
            ds[0x10, 0x10] = data_element

    def test_named_member_updated(self):
        """Dataset: if set data_element by tag, name also reflects change."""
        self.ds[0x300a, 0xb2].value = "moon_unit"
        assert 'moon_unit' == self.ds.TreatmentMachineName

    def test_update(self):
        """Dataset: update() method works with tag or name."""
        pat_data_element = DataElement((0x10, 0x12), 'PN', 'Johnny')
        self.ds.update({'PatientName': 'John', (0x10, 0x12): pat_data_element})
        assert 'John' == self.ds[0x10, 0x10].value
        assert 'Johnny' == self.ds[0x10, 0x12].value

    def test_dir_subclass(self):
        """Dataset.__dir__ returns class specific dir"""
        class DSP(Dataset):
            def test_func(self):
                pass

        ds = DSP()
        assert hasattr(ds, 'test_func')
        assert callable(ds.test_func)
        assert 'test_func' in dir(ds)

        ds = Dataset()
        assert hasattr(ds, 'group_dataset')
        assert callable(ds.group_dataset)
        assert 'group_dataset' in dir(ds)

    def test_dir(self):
        """Dataset.dir() returns sorted list of named data_elements."""
        ds = self.ds
        ds.PatientName = "name"
        ds.PatientID = "id"
        ds.NonDicomVariable = "junk"
        ds.add_new((0x18, 0x1151), "IS", 150)  # X-ray Tube Current
        ds.add_new((0x1111, 0x123), "DS", "42.0")  # private - no name in dir()
        expected = ['PatientID',
                    'PatientName',
                    'TreatmentMachineName',
                    'XRayTubeCurrent']
        assert expected == ds.dir()

    def test_dir_filter(self):
        """Test Dataset.dir(*filters) works OK."""
        ds = self.ds
        ds.PatientName = "name"
        ds.PatientID = "id"
        ds.NonDicomVariable = "junk"
        ds.add_new((0x18, 0x1151), "IS", 150)  # X-ray Tube Current
        ds.add_new((0x1111, 0x123), "DS", "42.0")  # private - no name in dir()
        assert 'PatientID' in ds
        assert 'XRayTubeCurrent' in ds
        assert 'TreatmentMachineName' in ds
        assert 'PatientName' in ds
        assert 'PatientBirthDate' not in ds
        assert ['PatientID', 'PatientName'] == ds.dir('Patient')
        assert ['PatientName', 'TreatmentMachineName'] == ds.dir('Name')
        expected = ['PatientID', 'PatientName', 'TreatmentMachineName']
        assert expected == ds.dir('Name', 'Patient')

    def test_delete_dicom_attr(self):
        """Dataset: delete DICOM attribute by name."""
        del self.ds.TreatmentMachineName
        with pytest.raises(AttributeError):
            self.ds.TreatmentMachineName

    def test_delete_dicom_command_group_length(self):
        """Dataset: delete CommandGroupLength doesn't raise AttributeError."""
        self.ds.CommandGroupLength = 100  # (0x0000, 0x0000)
        del self.ds.CommandGroupLength
        with pytest.raises(AttributeError):
            self.ds.CommandGroupLength

    def test_delete_other_attr(self):
        """Dataset: delete non-DICOM attribute by name."""
        self.ds.meaningoflife = 42
        assert hasattr(self.ds, 'meaningoflife')
        del self.ds.meaningoflife
        assert not hasattr(self.ds, 'meaningoflife')

    def test_delete_dicom_attr_we_dont_have(self):
        """Dataset: try delete of missing DICOM attribute."""
        with pytest.raises(AttributeError):
            del self.ds.PatientName

    def test_delete_item_long(self):
        """Dataset: delete item by tag number (long)."""
        del self.ds[0x300a00b2]

    def test_delete_item_tuple(self):
        """Dataset: delete item by tag number (tuple)."""
        del self.ds[0x300a, 0x00b2]

    def test_delete_non_existing_item(self):
        """Dataset: raise KeyError for non-existing item delete."""
        with pytest.raises(KeyError):
            del self.ds[0x10, 0x10]

    def test_equality_no_sequence(self):
        """Dataset: equality returns correct value with simple dataset"""
        # Test empty dataset
        assert Dataset() == Dataset()

        d = Dataset()
        d.SOPInstanceUID = '1.2.3.4'
        d.PatientName = 'Test'
        assert d == d

        e = Dataset()
        e.PatientName = 'Test'
        e.SOPInstanceUID = '1.2.3.4'
        assert d == e

        e.SOPInstanceUID = '1.2.3.5'
        assert not d == e

        # Check VR
        del e.SOPInstanceUID
        e.add(DataElement(0x00080018, 'PN', '1.2.3.4'))
        assert not d == e

        # Check Tag
        del e.SOPInstanceUID
        e.StudyInstanceUID = '1.2.3.4'
        assert not d == e

        # Check missing Element in self
        e.SOPInstanceUID = '1.2.3.4'
        assert not d == e

        # Check missing Element in other
        d = Dataset()
        d.SOPInstanceUID = '1.2.3.4'
        d.StudyInstanceUID = '1.2.3.4.5'

        e = Dataset()
        e.SOPInstanceUID = '1.2.3.4'
        assert not d == e

    def test_equality_private(self):
        """Dataset: equality returns correct value"""
        """when dataset has private elements"""
        d = Dataset()
        d_elem = DataElement(0x01110001, 'PN', 'Private')
        assert d == d
        d.add(d_elem)

        e = Dataset()
        e_elem = DataElement(0x01110001, 'PN', 'Private')
        e.add(e_elem)
        assert e == d

        e[0x01110001].value = 'Public'
        assert not e == d

    def test_equality_sequence(self):
        """Equality returns correct value with sequences"""
        # Test even sequences
        d = Dataset()
        d.SOPInstanceUID = '1.2.3.4'
        d.BeamSequence = []
        beam_seq = Dataset()
        beam_seq.PatientID = '1234'
        beam_seq.PatientName = 'ANON'
        d.BeamSequence.append(beam_seq)
        assert d == d

        e = Dataset()
        e.SOPInstanceUID = '1.2.3.4'
        e.BeamSequence = []
        beam_seq = Dataset()
        beam_seq.PatientName = 'ANON'
        beam_seq.PatientID = '1234'
        e.BeamSequence.append(beam_seq)
        assert d == e

        e.BeamSequence[0].PatientName = 'ANONY'
        assert not d == e

        # Test uneven sequences
        e.BeamSequence[0].PatientName = 'ANON'
        assert d == e

        e.BeamSequence.append(beam_seq)
        assert not d == e

        d.BeamSequence.append(beam_seq)
        assert d == e
        d.BeamSequence.append(beam_seq)
        assert not d == e

    def test_equality_not_dataset(self):
        """Dataset: equality returns correct value when not the same class"""
        d = Dataset()
        d.SOPInstanceUID = '1.2.3.4'
        # Make sure Dataset.__eq__() is being used, not dict__eq__()
        assert not d == {'SOPInstanceUID': '1.2.3.4'}

    def test_equality_unknown(self):
        """Dataset: equality returns correct value with extra members """
        # Non-element class members are ignored in equality testing
        d = Dataset()
        d.SOPEustaceUID = '1.2.3.4'
        assert d == d

        e = Dataset()
        e.SOPEustaceUID = '1.2.3.5'
        assert d == e

    def test_equality_inheritance(self):
        """Dataset: equality returns correct value for subclass """

        class DatasetPlus(Dataset):
            pass

        d = Dataset()
        d.PatientName = 'ANON'
        e = DatasetPlus()
        e.PatientName = 'ANON'
        assert d == e
        assert e == d
        assert e == e

        e.PatientName = 'ANONY'
        assert not d == e
        assert not e == d

    def test_equality_elements(self):
        """Test that Dataset equality only checks DataElements."""
        d = Dataset()
        d.SOPInstanceUID = '1.2.3.4'
        d.PatientName = 'Test'
        d.foo = 'foo'
        assert d == d

        e = Dataset()
        e.PatientName = 'Test'
        e.SOPInstanceUID = '1.2.3.4'
        assert d == e

    def test_inequality(self):
        """Test inequality operator"""
        d = Dataset()
        d.SOPInstanceUID = '1.2.3.4'
        assert not d != d

        e = Dataset()
        e.SOPInstanceUID = '1.2.3.5'
        assert d != e

    def test_hash(self):
        """DataElement: hash returns TypeError"""
        ds = Dataset()
        ds.PatientName = 'ANON'
        with pytest.raises(TypeError):
            hash(ds)

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
        assert 'ABCD' == dsp.test

    def test_add_repeater_elem_by_keyword(self):
        """Repeater using keyword to add repeater group elements raises."""
        ds = Dataset()
        with pytest.raises(ValueError):
            ds.OverlayData = b'\x00'

    def test_setitem_slice_raises(self):
        """Test Dataset.__setitem__ raises if slicing used."""
        ds = Dataset()
        with pytest.raises(NotImplementedError):
            ds.__setitem__(slice(None), Dataset())

    def test_getitem_slice_raises(self):
        """Test Dataset.__getitem__ raises if slice Tags invalid."""
        ds = Dataset()
        with pytest.raises(ValueError):
            ds.__getitem__(slice(None, -1))
        with pytest.raises(ValueError):
            ds.__getitem__(slice(-1, -1))
        with pytest.raises(ValueError):
            ds.__getitem__(slice(-1))

    def test_empty_slice(self):
        """Test Dataset slicing with empty Dataset."""
        ds = Dataset()
        assert ds[:] == Dataset()
        with pytest.raises(ValueError):
            ds.__getitem__(slice(None, -1))
        with pytest.raises(ValueError):
            ds.__getitem__(slice(-1, -1))
        with pytest.raises(ValueError):
            ds.__getitem__(slice(-1))
        with pytest.raises(NotImplementedError):
            ds.__setitem__(slice(None), Dataset())

    def test_getitem_slice(self):
        """Test Dataset.__getitem__ using slices."""
        ds = Dataset()
        ds.CommandGroupLength = 120  # 0000,0000
        ds.CommandLengthToEnd = 111  # 0000,0001
        ds.Overlays = 12  # 0000,51B0
        ds.LengthToEnd = 12  # 0008,0001
        ds.SOPInstanceUID = '1.2.3.4'  # 0008,0018
        ds.SkipFrameRangeFlag = 'TEST'  # 0008,9460
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
        ds.PatientName = 'CITIZEN^Jan'  # 0010,0010
        ds.PatientID = '12345'  # 0010,0010
        ds.ExaminedBodyThickness = 1.223  # 0010,9431
        ds.BeamSequence = [Dataset()]  # 300A,00B0
        ds.BeamSequence[0].PatientName = 'ANON'

        # Slice all items - should return original dataset
        assert ds[:] == ds

        # Slice starting from and including (0008,0001)
        test_ds = ds[0x00080001:]
        assert 'CommandGroupLength' not in test_ds
        assert 'CommandLengthToEnd' not in test_ds
        assert 'Overlays' not in test_ds
        assert 'LengthToEnd' in test_ds
        assert 'BeamSequence' in test_ds

        # Slice ending at and not including (0009,0002)
        test_ds = ds[:0x00090002]
        assert 'CommandGroupLength' in test_ds
        assert 'CommandLengthToEnd' in test_ds
        assert 'Overlays' in test_ds
        assert 'LengthToEnd' in test_ds
        assert 0x00090001 in test_ds
        assert 0x00090002 not in test_ds
        assert 'BeamSequence' not in test_ds

        # Slice with a step - every second tag
        # Should return zeroth tag, then second, fourth, etc...
        test_ds = ds[::2]
        assert 'CommandGroupLength' in test_ds
        assert 'CommandLengthToEnd' not in test_ds
        assert 0x00090001 in test_ds
        assert 0x00090002 not in test_ds

        # Slice starting at and including (0008,0018) and ending at and not
        #   including (0009,0008)
        test_ds = ds[0x00080018:0x00090008]
        assert 'SOPInstanceUID' in test_ds
        assert 0x00090007 in test_ds
        assert 0x00090008 not in test_ds

        # Slice starting at and including (0008,0018) and ending at and not
        #   including (0009,0008), every third element
        test_ds = ds[0x00080018:0x00090008:3]
        assert 'SOPInstanceUID' in test_ds
        assert 0x00090001 not in test_ds
        assert 0x00090002 in test_ds
        assert 0x00090003 not in test_ds
        assert 0x00090004 not in test_ds
        assert 0x00090005 in test_ds
        assert 0x00090006 not in test_ds
        assert 0x00090008 not in test_ds

        # Slice starting and ending (and not including) (0008,0018)
        assert ds[(0x0008, 0x0018):(0x0008, 0x0018)] == Dataset()

        # Test slicing using other acceptable Tag initialisations
        assert 'SOPInstanceUID' in ds[(0x00080018):(0x00080019)]
        assert 'SOPInstanceUID' in ds[(0x0008, 0x0018):(0x0008, 0x0019)]
        assert 'SOPInstanceUID' in ds['0x00080018':'0x00080019']

    def test_getitem_slice_ffff(self):
        """Test slicing with (FFFF,FFFF)"""
        # Issue #92
        ds = Dataset()
        ds.CommandGroupLength = 120  # 0000,0000
        ds.CommandLengthToEnd = 111  # 0000,0001
        ds.Overlays = 12  # 0000,51B0
        ds.LengthToEnd = 12  # 0008,0001
        ds.SOPInstanceUID = '1.2.3.4'  # 0008,0018
        ds.SkipFrameRangeFlag = 'TEST'  # 0008,9460
        ds.add_new(0xFFFF0001, 'PN', 'CITIZEN^1')
        ds.add_new(0xFFFF0002, 'PN', 'CITIZEN^2')
        ds.add_new(0xFFFF0003, 'PN', 'CITIZEN^3')
        ds.add_new(0xFFFFFFFE, 'PN', 'CITIZEN^4')
        ds.add_new(0xFFFFFFFF, 'PN', 'CITIZEN^5')

        assert 'CITIZEN^5' == ds[:][0xFFFFFFFF].value
        assert 0xFFFFFFFF not in ds[0x1000:0xFFFFFFFF]
        assert 0xFFFFFFFF not in ds[(0x1000):(0xFFFF, 0xFFFF)]

    def test_delitem_slice(self):
        """Test Dataset.__delitem__ using slices."""
        ds = Dataset()
        ds.CommandGroupLength = 120  # 0000,0000
        ds.CommandLengthToEnd = 111  # 0000,0001
        ds.Overlays = 12  # 0000,51B0
        ds.LengthToEnd = 12  # 0008,0001
        ds.SOPInstanceUID = '1.2.3.4'  # 0008,0018
        ds.SkipFrameRangeFlag = 'TEST'  # 0008,9460
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
        ds.PatientName = 'CITIZEN^Jan'  # 0010,0010
        ds.PatientID = '12345'  # 0010,0010
        ds.ExaminedBodyThickness = 1.223  # 0010,9431
        ds.BeamSequence = [Dataset()]  # 300A,00B0
        ds.BeamSequence[0].PatientName = 'ANON'

        # Delete the 0x0009 group
        del ds[0x00090000:0x00100000]
        assert 'SkipFrameRangeFlag' in ds
        assert 0x00090001 not in ds
        assert 0x00090010 not in ds
        assert 'PatientName' in ds

    @pytest.mark.skipif(not compat.in_py2, reason='Python 2 only iterators')
    def test_iteritems(self):
        ds = Dataset()
        ds.Overlays = 12  # 0000,51B0
        ds.LengthToEnd = 12  # 0008,0001
        ds.SOPInstanceUID = '1.2.3.4'  # 0008,0018
        ds.SkipFrameRangeFlag = 'TEST'  # 0008,9460

        keys = []
        for key in ds.iterkeys():
            keys.append(key)
        assert 4 == len(keys)
        assert 0x000051B0 in keys
        assert 0x00089460 in keys

        values = []
        for value in ds.itervalues():
            values.append(value)

        assert 4 == len(values)
        assert DataElement(0x00080018, 'UI', '1.2.3.4') in values
        assert DataElement(0x00089460, 'CS', 'TEST') in values

        items = {}
        for key, value in ds.iteritems():
            items[key] = value

        assert 4 == len(items)
        assert 0x000051B0 in items
        assert 0x00080018 in items
        assert '1.2.3.4' == items[0x00080018].value
        assert 12 == items[0x00080001].value

    def test_group_dataset(self):
        """Test Dataset.group_dataset"""
        ds = Dataset()
        ds.CommandGroupLength = 120  # 0000,0000
        ds.CommandLengthToEnd = 111  # 0000,0001
        ds.Overlays = 12  # 0000,51B0
        ds.LengthToEnd = 12  # 0008,0001
        ds.SOPInstanceUID = '1.2.3.4'  # 0008,0018
        ds.SkipFrameRangeFlag = 'TEST'  # 0008,9460

        # Test getting group 0x0000
        group0000 = ds.group_dataset(0x0000)
        assert 'CommandGroupLength' in group0000
        assert 'CommandLengthToEnd' in group0000
        assert 'Overlays' in group0000
        assert 'LengthToEnd' not in group0000
        assert 'SOPInstanceUID' not in group0000
        assert 'SkipFrameRangeFlag' not in group0000

        # Test getting group 0x0008
        group0000 = ds.group_dataset(0x0008)
        assert 'CommandGroupLength' not in group0000
        assert 'CommandLengthToEnd' not in group0000
        assert 'Overlays' not in group0000
        assert 'LengthToEnd' in group0000
        assert 'SOPInstanceUID' in group0000
        assert 'SkipFrameRangeFlag' in group0000

    def test_get_item(self):
        """Test Dataset.get_item"""
        ds = Dataset()
        ds.CommandGroupLength = 120  # 0000,0000
        ds.SOPInstanceUID = '1.2.3.4'  # 0008,0018

        # Test non-deferred read
        assert ds[0x00000000] == ds.get_item(0x00000000)
        assert 120 == ds.get_item(0x00000000).value
        assert ds[0x00080018] == ds.get_item(0x00080018)
        assert '1.2.3.4' == ds.get_item(0x00080018).value

        # Test deferred read
        test_file = get_testdata_files('MR_small.dcm')[0]
        ds = dcmread(test_file, force=True, defer_size='0.8 kB')
        ds_ref = dcmread(test_file, force=True)
        # get_item will follow the deferred read branch
        assert ds_ref.PixelData == ds.get_item((0x7fe00010)).value

    def test_get_item_slice(self):
        """Test Dataset.get_item with slice argument"""
        # adapted from test_getitem_slice
        ds = Dataset()
        ds.CommandGroupLength = 120  # 0000,0000
        ds.CommandLengthToEnd = 111  # 0000,0001
        ds.Overlays = 12  # 0000,51B0
        ds.LengthToEnd = 12  # 0008,0001
        ds.SOPInstanceUID = '1.2.3.4'  # 0008,0018
        ds.SkipFrameRangeFlag = 'TEST'  # 0008,9460
        ds.add_new(0x00090001, 'PN', 'CITIZEN^1')
        ds.add_new(0x00090002, 'PN', 'CITIZEN^2')
        ds.add_new(0x00090003, 'PN', 'CITIZEN^3')
        elem = RawDataElement(0x00090004, 'PN', 9, b'CITIZEN^4', 0, True, True)
        ds.__setitem__(0x00090004, elem)
        elem = RawDataElement(0x00090005, 'PN', 9, b'CITIZEN^5', 0, True, True)
        ds.__setitem__(0x00090005, elem)
        elem = RawDataElement(0x00090006, 'PN', 9, b'CITIZEN^6', 0, True, True)
        ds.__setitem__(0x00090006, elem)
        ds.PatientName = 'CITIZEN^Jan'  # 0010,0010
        elem = RawDataElement(0x00100020, 'LO', 5, b'12345', 0, True, True)
        ds.__setitem__(0x00100020, elem)  # Patient ID
        ds.ExaminedBodyThickness = 1.223  # 0010,9431
        ds.BeamSequence = [Dataset()]  # 300A,00B0
        ds.BeamSequence[0].PatientName = 'ANON'

        # Slice starting from and including (0008,0001)
        test_ds = ds.get_item(slice(0x00080001, None))
        assert 'CommandGroupLength' not in test_ds
        assert 'CommandLengthToEnd' not in test_ds
        assert 'Overlays' not in test_ds
        assert 'LengthToEnd' in test_ds
        assert 'BeamSequence' in test_ds

        # Slice ending at and not including (0009,0002)
        test_ds = ds.get_item(slice(None, 0x00090002))
        assert 'CommandGroupLength' in test_ds
        assert 'CommandLengthToEnd' in test_ds
        assert 'Overlays' in test_ds
        assert 'LengthToEnd' in test_ds
        assert 0x00090001 in test_ds
        assert 0x00090002 not in test_ds
        assert 'BeamSequence' not in test_ds

        # Slice with a step - every second tag
        # Should return zeroth tag, then second, fourth, etc...
        test_ds = ds.get_item(slice(None, None, 2))
        assert 'CommandGroupLength' in test_ds
        assert 'CommandLengthToEnd' not in test_ds
        assert 0x00090001 in test_ds
        assert 0x00090002 not in test_ds

        # Slice starting at and including (0008,0018) and ending at and not
        #   including (0009,0008)
        test_ds = ds.get_item(slice(0x00080018, 0x00090006))
        assert 'SOPInstanceUID' in test_ds
        assert 0x00090005 in test_ds
        assert 0x00090006 not in test_ds

        # Slice starting at and including (0008,0018) and ending at and not
        #   including (0009,0006), every third element
        test_ds = ds.get_item(slice(0x00080018, 0x00090008, 3))
        assert 'SOPInstanceUID' in test_ds
        assert 0x00090001 not in test_ds
        assert 0x00090002 in test_ds
        assert not test_ds.get_item(0x00090002).is_raw
        assert 0x00090003 not in test_ds
        assert 0x00090004 not in test_ds
        assert 0x00090005 in test_ds
        assert test_ds.get_item(0x00090005).is_raw
        assert 0x00090006 not in test_ds

        # Slice starting and ending (and not including) (0008,0018)
        assert Dataset() == ds.get_item(slice((0x0008, 0x0018),
                                              (0x0008, 0x0018)))

        # Test slicing using other acceptable Tag initialisations
        assert 'SOPInstanceUID' in ds.get_item(slice(0x00080018, 0x00080019))
        assert 'SOPInstanceUID' in ds.get_item(slice((0x0008, 0x0018),
                                                     (0x0008, 0x0019)))
        assert 'SOPInstanceUID' in ds.get_item(slice('0x00080018',
                                                     '0x00080019'))

        # Slice all items - should return original dataset
        assert ds == ds.get_item(slice(None, None))

    def test_get_private_item(self):
        ds = Dataset()
        ds.add_new(0x00080005, 'CS', 'ISO_IR 100')
        ds.add_new(0x00090010, 'LO', 'Creator 1.0')
        ds.add_new(0x00091001, 'SH', 'Version1')
        ds.add_new(0x00090011, 'LO', 'Creator 2.0')
        ds.add_new(0x00091101, 'SH', 'Version2')
        ds.add_new(0x00091102, 'US', 2)

        with pytest.raises(ValueError, match='Tag must be private'):
            ds.get_private_item(0x0008, 0x05, 'Creator 1.0')
        with pytest.raises(ValueError,
                           match='Private creator must have a value'):
            ds.get_private_item(0x0009, 0x10, '')
        with pytest.raises(KeyError,
                           match="Private creator 'Creator 3.0' not found"):
            ds.get_private_item(0x0009, 0x10, 'Creator 3.0')
        item = ds.get_private_item(0x0009, 0x01, 'Creator 1.0')
        assert 'Version1' == item.value
        item = ds.get_private_item(0x0009, 0x01, 'Creator 2.0')
        assert 'Version2' == item.value

        with pytest.raises(KeyError):
            ds.get_private_item(0x0009, 0x02, 'Creator 1.0')
        item = ds.get_private_item(0x0009, 0x02, 'Creator 2.0')
        assert 2 == item.value

    def test_private_block(self):
        ds = Dataset()
        ds.add_new(0x00080005, 'CS', 'ISO_IR 100')
        ds.add_new(0x00090010, 'LO', 'Creator 1.0')
        ds.add_new(0x00091001, 'SH', 'Version1')
        ds.add_new(0x00090011, 'LO', 'Creator 2.0')
        ds.add_new(0x00091101, 'SH', 'Version2')
        ds.add_new(0x00091102, 'US', 2)

        # Dataset.private_block
        with pytest.raises(ValueError, match='Tag must be private'):
            ds.private_block(0x0008, 'Creator 1.0')
        with pytest.raises(ValueError,
                           match='Private creator must have a value'):
            ds.private_block(0x0009, '')
        with pytest.raises(KeyError,
                           match="Private creator 'Creator 3.0' not found"):
            ds.private_block(0x0009, 'Creator 3.0')

        block = ds.private_block(0x0009, 'Creator 1.0')

        # test for containment
        assert 1 in block
        assert 2 not in block

        # get item from private block
        item = block[0x01]
        assert 'Version1' == item.value
        block = ds.private_block(0x0009, 'Creator 2.0')
        with pytest.raises(ValueError,
                           match='Element offset must be less than 256'):
            block[0x0101]

        item = block[0x01]
        assert 'Version2' == item.value

        # Dataset.get_private_item
        with pytest.raises(KeyError):
            ds.get_private_item(0x0009, 0x02, 'Creator 1.0')

        item = ds.get_private_item(0x0009, 0x02, 'Creator 2.0')
        assert 2 == item.value

    def test_add_new_private_tag(self):
        ds = Dataset()
        ds.add_new(0x00080005, 'CS', 'ISO_IR 100')
        ds.add_new(0x00090010, 'LO', 'Creator 1.0')
        ds.add_new(0x00090011, 'LO', 'Creator 2.0')

        with pytest.raises(ValueError, match='Tag must be private'):
            ds.private_block(0x0008, 'Creator 1.0')
        block = ds.private_block(0x0009, 'Creator 2.0', create=True)
        block.add_new(0x01, 'SH', 'Version2')
        assert 'Version2' == ds[0x00091101].value
        block = ds.private_block(0x0009, 'Creator 3.0', create=True)
        block.add_new(0x01, 'SH', 'Version3')
        assert 'Creator 3.0' == ds[0x00090012].value
        assert 'Version3' == ds[0x00091201].value

    def test_delete_private_tag(self):
        ds = Dataset()
        ds.add_new(0x00080005, 'CS', 'ISO_IR 100')
        ds.add_new(0x00090010, 'LO', 'Creator 1.0')
        ds.add_new(0x00090011, 'LO', 'Creator 2.0')
        ds.add_new(0x00091101, 'SH', 'Version2')

        block = ds.private_block(0x0009, 'Creator 2.0')
        with pytest.raises(ValueError,
                           match='Element offset must be less than 256'):
            del block[0x1001]
        assert 1 in block
        del block[0x01]
        assert 1 not in block
        with pytest.raises(KeyError):
            del block[0x01]

    def test_private_creators(self):
        ds = Dataset()
        ds.add_new(0x00080005, 'CS', 'ISO_IR 100')
        ds.add_new(0x00090010, 'LO', 'Creator 1.0')
        ds.add_new(0x00090011, 'LO', 'Creator 2.0')

        with pytest.raises(ValueError, match='Group must be an odd number'):
            ds.private_creators(0x0008)
        assert ['Creator 1.0', 'Creator 2.0'] == ds.private_creators(0x0009)
        assert not ds.private_creators(0x0011)

    def test_is_original_encoding(self):
        """Test Dataset.write_like_original"""
        ds = Dataset()
        assert not ds.is_original_encoding

        # simulate reading
        ds.SpecificCharacterSet = 'ISO_IR 100'
        ds.set_original_encoding(True, True, ['latin_1'])
        assert not ds.is_original_encoding

        ds.is_little_endian = True
        ds.is_implicit_VR = True
        assert ds.is_original_encoding
        # changed character set
        ds.SpecificCharacterSet = 'ISO_IR 192'
        assert not ds.is_original_encoding
        # back to original character set
        ds.SpecificCharacterSet = 'ISO_IR 100'
        assert ds.is_original_encoding
        ds.is_little_endian = False
        assert not ds.is_original_encoding
        ds.is_little_endian = True
        ds.is_implicit_VR = False
        assert not ds.is_original_encoding

    def test_remove_private_tags(self):
        """Test Dataset.remove_private_tags"""
        ds = Dataset()
        ds.CommandGroupLength = 120  # 0000,0000
        ds.SkipFrameRangeFlag = 'TEST'  # 0008,9460
        ds.add_new(0x00090001, 'PN', 'CITIZEN^1')
        ds.add_new(0x00090010, 'PN', 'CITIZEN^10')
        ds.PatientName = 'CITIZEN^Jan'  # 0010,0010

        ds.remove_private_tags()
        assert Dataset() == ds[0x00090000:0x00100000]
        assert 'CommandGroupLength' in ds
        assert 'SkipFrameRangeFlag' in ds
        assert 'PatientName' in ds

    def test_data_element(self):
        """Test Dataset.data_element."""
        ds = Dataset()
        ds.CommandGroupLength = 120
        ds.SkipFrameRangeFlag = 'TEST'
        ds.add_new(0x00090001, 'PN', 'CITIZEN^1')
        ds.BeamSequence = [Dataset()]
        ds.BeamSequence[0].PatientName = 'ANON'
        assert ds[0x00000000] == ds.data_element('CommandGroupLength')
        assert ds[0x300A00B0] == ds.data_element('BeamSequence')
        assert ds.data_element('not an element keyword') is None

    def test_iterall(self):
        """Test Dataset.iterall"""
        ds = Dataset()
        ds.CommandGroupLength = 120
        ds.SkipFrameRangeFlag = 'TEST'
        ds.add_new(0x00090001, 'PN', 'CITIZEN^1')
        ds.BeamSequence = [Dataset()]
        ds.BeamSequence[0].PatientName = 'ANON'
        elem_gen = ds.iterall()
        assert ds.data_element('CommandGroupLength') == next(elem_gen)
        assert ds.data_element('SkipFrameRangeFlag') == next(elem_gen)
        assert ds[0x00090001] == next(elem_gen)
        assert ds.data_element('BeamSequence') == next(elem_gen)
        assert ds.BeamSequence[0].data_element('PatientName') == next(elem_gen)

    def test_save_as(self):
        """Test Dataset.save_as"""
        fp = DicomBytesIO()
        ds = Dataset()
        ds.PatientName = 'CITIZEN'
        # Raise AttributeError if is_implicit_VR or is_little_endian missing
        with pytest.raises(AttributeError):
            ds.save_as(fp, write_like_original=False)

        ds.is_implicit_VR = True
        with pytest.raises(AttributeError):
            ds.save_as(fp, write_like_original=False)

        ds.is_little_endian = True
        del ds.is_implicit_VR
        with pytest.raises(AttributeError):
            ds.save_as(fp, write_like_original=False)

        ds.is_implicit_VR = True
        ds.file_meta = Dataset()
        ds.file_meta.MediaStorageSOPClassUID = '1.1'
        ds.file_meta.MediaStorageSOPInstanceUID = '1.2'
        ds.file_meta.TransferSyntaxUID = '1.3'
        ds.file_meta.ImplementationClassUID = '1.4'
        ds.save_as(fp, write_like_original=False)

    def test_with(self):
        """Test Dataset.__enter__ and __exit__."""
        test_file = get_testdata_files('CT_small.dcm')[0]
        with dcmread(test_file) as ds:
            assert 'CompressedSamples^CT1' == ds.PatientName

    def test_exit_exception(self):
        """Test Dataset.__exit__ when an exception is raised."""
        class DSException(Dataset):
            @property
            def test(self):
                raise ValueError("Random ex message!")

        with pytest.raises(ValueError, match="Random ex message!"):
            getattr(DSException(), 'test')

    def test_pixel_array_already_have(self):
        """Test Dataset._get_pixel_array when we already have the array"""
        # Test that _pixel_array is returned unchanged unless required
        fpath = get_testdata_files("CT_small.dcm")[0]
        ds = dcmread(fpath)
        ds._pixel_id = id(ds.PixelData)
        ds._pixel_array = 'Test Value'
        ds.convert_pixel_data()
        assert id(ds.PixelData) == ds._pixel_id
        assert 'Test Value' == ds._pixel_array

    def test_pixel_array_id_changed(self):
        """Test that we try to get new pixel data if the id has changed."""
        fpath = get_testdata_files("CT_small.dcm")[0]
        ds = dcmread(fpath)
        ds.file_meta.TransferSyntaxUID = '1.2.3.4'
        ds._pixel_id = 1234
        assert id(ds.PixelData) != ds._pixel_id
        ds._pixel_array = 'Test Value'
        # If _pixel_id doesn't match then attempt to get new pixel data
        orig_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = []
        with pytest.raises(NotImplementedError):
            ds.convert_pixel_data()

        pydicom.config.pixel_data_handlers = orig_handlers

    def test_pixel_array_unknown_syntax(self):
        """Test that pixel_array for an unknown syntax raises exception."""
        ds = dcmread(get_testdata_files("CT_small.dcm")[0])
        ds.file_meta.TransferSyntaxUID = '1.2.3.4'
        msg = (
            r"Unable to decode pixel data with a transfer syntax UID of "
            r"'1.2.3.4' \(1.2.3.4\) as there are no pixel data handlers "
            r"available that support it"
        )
        with pytest.raises(NotImplementedError, match=msg):
            ds.pixel_array

    def test_formatted_lines(self):
        """Test Dataset.formatted_lines"""
        ds = Dataset()
        with pytest.raises(StopIteration):
            next(ds.formatted_lines())
        ds.PatientName = 'CITIZEN^Jan'
        ds.BeamSequence = [Dataset()]
        ds.BeamSequence[0].PatientID = 'JAN^Citizen'
        elem_format = "%(tag)s"
        seq_format = "%(name)s %(tag)s"
        indent_format = ">>>"  # placeholder for future functionality

        line_generator = ds.formatted_lines(element_format=elem_format,
                                            sequence_element_format=seq_format,
                                            indent_format=indent_format)
        assert "(0010, 0010)" == next(line_generator)
        assert "Beam Sequence (300a, 00b0)" == next(line_generator)
        assert "(0010, 0020)" == next(line_generator)
        with pytest.raises(StopIteration):
            next(line_generator)

    def test_formatted_lines_known_uid(self):
        """Test that the UID name is output when known."""
        ds = Dataset()
        ds.TransferSyntaxUID = '1.2.840.10008.1.2'
        assert 'Implicit VR Little Endian' in str(ds)

    def test_set_convert_private_elem_from_raw(self):
        """Test Dataset.__setitem__ with a raw private element"""
        test_file = get_testdata_files('CT_small.dcm')[0]
        ds = dcmread(test_file, force=True)
        # 'tag VR length value value_tell is_implicit_VR is_little_endian'
        elem = RawDataElement((0x0043, 0x1029), 'OB', 2, b'\x00\x01', 0,
                              True, True)
        ds.__setitem__((0x0043, 0x1029), elem)

        assert b'\x00\x01' == ds[(0x0043, 0x1029)].value
        assert isinstance(ds[(0x0043, 0x1029)], DataElement)

    def test_top(self):
        """Test Dataset.top returns only top level str"""
        ds = Dataset()
        ds.PatientName = 'CITIZEN^Jan'
        ds.BeamSequence = [Dataset()]
        ds.BeamSequence[0].PatientID = 'JAN^Citizen'
        assert "Patient's Name" in ds.top()
        assert "Patient ID" not in ds.top()

    def test_trait_names(self):
        """Test Dataset.trait_names contains element keywords"""
        test_file = get_testdata_files('CT_small.dcm')[0]
        ds = dcmread(test_file, force=True)
        names = ds.trait_names()
        assert 'PatientName' in names
        assert 'save_as' in names
        assert 'PixelData' in names

    def test_walk(self):
        """Test Dataset.walk iterates through sequences"""
        def test_callback(dataset, elem):
            if elem.keyword is 'PatientID':
                dataset.PatientID = 'FIXED'

        ds = Dataset()
        ds.PatientName = 'CITIZEN^Jan'
        ds.BeamSequence = [Dataset(), Dataset()]
        ds.BeamSequence[0].PatientID = 'JAN^Citizen^Snr'
        ds.BeamSequence[0].PatientName = 'Some^Name'
        ds.BeamSequence[1].PatientID = 'JAN^Citizen^Jr'
        ds.BeamSequence[1].PatientName = 'Other^Name'
        ds.walk(test_callback, recursive=True)

        assert 'CITIZEN^Jan' == ds.PatientName
        assert 'FIXED' == ds.BeamSequence[0].PatientID
        assert 'Some^Name' == ds.BeamSequence[0].PatientName
        assert 'FIXED' == ds.BeamSequence[1].PatientID
        assert 'Other^Name' == ds.BeamSequence[1].PatientName

    def test_update_with_dataset(self):
        """Regression test for #779"""
        ds = Dataset()
        ds.PatientName = "Test"
        ds2 = Dataset()
        ds2.update(ds)
        assert 'Test' == ds2.PatientName

        # Test sequences
        ds2 = Dataset()
        ds.BeamSequence = [Dataset(), Dataset()]
        ds.BeamSequence[0].PatientName = 'TestA'
        ds.BeamSequence[1].PatientName = 'TestB'

        ds2.update(ds)
        assert 'TestA' == ds2.BeamSequence[0].PatientName
        assert 'TestB' == ds2.BeamSequence[1].PatientName

        # Test overwrite
        ds.PatientName = 'TestC'
        ds2.update(ds)
        assert 'TestC' == ds2.PatientName

    def test_convert_pixel_data_no_px(self):
        """Test convert_pixel_data() with no pixel data elements."""
        ds = Dataset()
        msg = (
            r"Unable to convert the pixel data: one of Pixel Data, Float "
            r"Pixel Data or Double Float Pixel Data must be present in "
            r"the dataset"
        )
        with pytest.raises(AttributeError, match=msg):
            ds.convert_pixel_data()


class TestDatasetElements(object):
    """Test valid assignments of data elements"""
    def setup(self):
        self.ds = Dataset()
        self.sub_ds1 = Dataset()
        self.sub_ds2 = Dataset()

    def test_sequence_assignment(self):
        """Assignment to SQ works only if valid Sequence assigned."""
        msg = r"Sequence contents must be Dataset instances"
        with pytest.raises(TypeError, match=msg):
            self.ds.ConceptCodeSequence = [1, 2, 3]

        # check also that assigning proper sequence *does* work
        self.ds.ConceptCodeSequence = [self.sub_ds1, self.sub_ds2]
        assert isinstance(self.ds.ConceptCodeSequence, Sequence)

    def test_ensure_file_meta(self):
        assert not hasattr(self.ds, 'file_meta')
        self.ds.ensure_file_meta()
        assert hasattr(self.ds, 'file_meta')
        assert not self.ds.file_meta

    def test_fix_meta_info(self):
        self.ds.is_little_endian = True
        self.ds.is_implicit_VR = True
        self.ds.fix_meta_info(enforce_standard=False)
        assert ImplicitVRLittleEndian == self.ds.file_meta.TransferSyntaxUID

        self.ds.is_implicit_VR = False
        self.ds.fix_meta_info(enforce_standard=False)
        # transfer syntax does not change because of ambiguity
        assert ImplicitVRLittleEndian == self.ds.file_meta.TransferSyntaxUID

        self.ds.is_little_endian = False
        self.ds.is_implicit_VR = True
        with pytest.raises(NotImplementedError):
            self.ds.fix_meta_info()

        self.ds.is_implicit_VR = False
        self.ds.fix_meta_info(enforce_standard=False)
        assert ExplicitVRBigEndian == self.ds.file_meta.TransferSyntaxUID

        assert 'MediaStorageSOPClassUID' not in self.ds.file_meta
        assert 'MediaStorageSOPInstanceUID ' not in self.ds.file_meta
        with pytest.raises(ValueError,
                           match='Missing required File Meta .*'):
            self.ds.fix_meta_info(enforce_standard=True)

        self.ds.SOPClassUID = '1.2.3'
        self.ds.SOPInstanceUID = '4.5.6'
        self.ds.fix_meta_info(enforce_standard=False)
        assert '1.2.3' == self.ds.file_meta.MediaStorageSOPClassUID
        assert '4.5.6' == self.ds.file_meta.MediaStorageSOPInstanceUID
        self.ds.fix_meta_info(enforce_standard=True)

        self.ds.file_meta.PatientID = 'PatientID'
        with pytest.raises(ValueError,
                           match=r'Only File Meta Information Group '
                                 r'\(0002,eeee\) elements must be present .*'):
            self.ds.fix_meta_info(enforce_standard=True)

    def test_validate_and_correct_file_meta(self):
        file_meta = Dataset()
        validate_file_meta(file_meta, enforce_standard=False)
        with pytest.raises(ValueError):
            validate_file_meta(file_meta, enforce_standard=True)

        file_meta.PatientID = 'PatientID'
        for enforce_standard in (True, False):
            with pytest.raises(
                    ValueError,
                    match=r'Only File Meta Information Group '
                          r'\(0002,eeee\) elements must be present .*'):
                validate_file_meta(
                    file_meta, enforce_standard=enforce_standard)

        file_meta = Dataset()
        file_meta.MediaStorageSOPClassUID = '1.2.3'
        file_meta.MediaStorageSOPInstanceUID = '1.2.4'
        # still missing TransferSyntaxUID
        with pytest.raises(ValueError):
            validate_file_meta(file_meta, enforce_standard=True)

        file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        validate_file_meta(file_meta, enforce_standard=True)

        # check the default created values
        assert b'\x00\x01' == file_meta.FileMetaInformationVersion
        assert PYDICOM_IMPLEMENTATION_UID == file_meta.ImplementationClassUID
        assert file_meta.ImplementationVersionName.startswith('PYDICOM ')

        file_meta.ImplementationClassUID = '1.2.3.4'
        file_meta.ImplementationVersionName = 'ACME LTD'
        validate_file_meta(file_meta, enforce_standard=True)
        # check that existing values are left alone
        assert '1.2.3.4' == file_meta.ImplementationClassUID
        assert 'ACME LTD' == file_meta.ImplementationVersionName


class TestFileDataset(object):
    def setup(self):
        self.test_file = get_testdata_files('CT_small.dcm')[0]

    def test_pickle(self):
        ds = pydicom.dcmread(self.test_file)
        import pickle
        s = pickle.dumps({'ds': ds})
        ds1 = pickle.loads(s)['ds']
        assert ds == ds1
        assert ds1.Modality == 'CT'

    def test_pickle_modified(self):
        """Test pickling a modified dataset."""
        ds = pydicom.dcmread(self.test_file)
        ds.PixelSpacing = [1.0, 1.0]
        import pickle
        s = pickle.dumps({'ds': ds})
        ds1 = pickle.loads(s)['ds']
        assert ds == ds1
        assert ds1.PixelSpacing == [1.0, 1.0]

        # Test workaround for python 2
        if compat.in_py2:
            ds1.PixelSpacing = ds1.PixelSpacing

        ds1.PixelSpacing.insert(1, 2)
        assert [1, 2, 1] == ds1.PixelSpacing

    def test_equality_file_meta(self):
        """Dataset: equality returns correct value if with metadata"""
        d = dcmread(self.test_file)
        e = dcmread(self.test_file)
        assert d == e

        e.is_implicit_VR = not e.is_implicit_VR
        assert not d == e

        e.is_implicit_VR = not e.is_implicit_VR
        assert d == e
        e.is_little_endian = not e.is_little_endian
        assert not d == e

        e.is_little_endian = not e.is_little_endian
        assert d == e
        e.filename = 'test_filename.dcm'
        assert not d == e

    def test_creation_with_container(self):
        """FileDataset.__init__ works OK with a container such as gzip"""
        class Dummy(object):
            filename = '/some/path/to/test'

        ds = Dataset()
        ds.PatientName = "CITIZEN^Jan"
        fds = FileDataset(Dummy(), ds)
        assert '/some/path/to/test' == fds.filename

    def test_works_as_expected_within_numpy_array(self):
        """Test Dataset within a numpy array"""
        try:
            import numpy as np
        except ImportError:
            np = None

        if np is None:
            pytest.skip('No numpy installed')

        # see PR #836
        dataset = Dataset()
        patient_name = 'MacDonald^George'
        dataset.PatientName = patient_name
        array_of_datasets = np.array([dataset])
        assert patient_name == array_of_datasets[0].PatientName

    def test_dataset_overrides_all_dict_attributes(self):
        """Ensure that we don't use inherited dict functionality"""
        ds = Dataset()
        di = dict()
        expected_diff = {'__class__', '__doc__', '__hash__'}
        assert expected_diff == set(dir(di)) - set(dir(ds))


class TestDatasetOverlayArray(object):
    """Tests for Dataset.overlay_array()."""
    def setup(self):
        """Setup the test datasets and the environment."""
        self.original_handlers = pydicom.config.overlay_data_handlers
        pydicom.config.overlay_data_handlers = [NP_HANDLER]

        self.ds = dcmread(
            get_testdata_files("MR-SIEMENS-DICOM-WithOverlays.dcm")[0]
        )

        class DummyHandler(object):
            def __init__(self):
                self.raise_exc = False
                self.has_dependencies = True
                self.DEPENDENCIES = {
                    'numpy': ('http://www.numpy.org/', 'NumPy'),
                }
                self.HANDLER_NAME = 'Dummy'

            def supports_transfer_syntax(self, syntax):
                return True

            def is_available(self):
                return self.has_dependencies

            def get_overlay_array(self, ds, group):
                if self.raise_exc:
                    raise ValueError("Dummy error message")

                return 'Success'

        self.dummy = DummyHandler()

    def teardown(self):
        """Restore the environment."""
        pydicom.config.overlay_data_handlers = self.original_handlers

    def test_no_possible(self):
        """Test with no possible handlers available."""
        pydicom.config.overlay_data_handlers = []
        with pytest.raises((NotImplementedError, RuntimeError)):
            self.ds.overlay_array(0x6000)

    def test_possible_not_available(self):
        """Test with possible but not available handlers."""
        self.dummy.has_dependencies = False
        pydicom.config.overlay_data_handlers = [self.dummy]
        msg = (
            r"The following handlers are available to decode the overlay "
            r"data however they are missing required dependencies: "
        )
        with pytest.raises(RuntimeError, match=msg):
            self.ds.overlay_array(0x6000)

    def test_possible_available(self):
        """Test with possible and available handlers."""
        pydicom.config.overlay_data_handlers = [self.dummy]
        assert 'Success' == self.ds.overlay_array(0x6000)

    def test_handler_raises(self):
        """Test the handler raising an exception."""
        self.dummy.raise_exc = True
        pydicom.config.overlay_data_handlers = [self.dummy]
        with pytest.raises(ValueError, match=r"Dummy error message"):
            self.ds.overlay_array(0x6000)
