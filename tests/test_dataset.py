# Copyright 2008-2023 pydicom authors. See LICENSE file for details.
"""Unit tests for the pydicom.dataset module."""

import copy
import io
import math
from pathlib import Path
import pickle
from platform import python_implementation
import sys
import weakref
import tempfile

import pytest

from pydicom.datadict import add_private_dict_entry
from .test_helpers import assert_no_warning

try:
    import numpy

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

import pydicom
from pydicom import config
from pydicom import dcmread
from pydicom.data import get_testdata_file
from pydicom.dataelem import DataElement, RawDataElement
from pydicom.dataset import Dataset, FileDataset, validate_file_meta, FileMetaDataset
from pydicom.encaps import encapsulate
from pydicom.filebase import DicomBytesIO
from pydicom.pixels.utils import get_image_pixel_ids
from pydicom.sequence import Sequence
from pydicom.tag import Tag
from pydicom.uid import (
    ImplicitVRLittleEndian,
    ExplicitVRLittleEndian,
    ExplicitVRBigEndian,
    JPEGBaseline8Bit,
    PYDICOM_IMPLEMENTATION_UID,
    CTImageStorage,
)
from pydicom.valuerep import DS, VR


class BadRepr:
    def __repr__(self):
        raise ValueError("bad repr")


@pytest.fixture()
def clear_pixel_data_handlers():
    orig_handlers = pydicom.config.pixel_data_handlers
    pydicom.config.pixel_data_handlers = []
    yield
    pydicom.config.pixel_data_handlers = orig_handlers


class TestDataset:
    """Tests for dataset.Dataset."""

    def setup_method(self):
        self.ds = Dataset()
        self.ds.TreatmentMachineName = "unit001"

    def test_attribute_error_in_property(self):
        """Dataset: AttributeError in property raises actual error message."""
        # This comes from bug fix for issue 42
        # First, fake enough to try the pixel_array property
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.PixelData = "xyzlmnop"
        msg = (
            "Unable to decode the pixel data as the dataset's 'file_meta' has "
            r"no \(0002,0010\) 'Transfer Syntax UID' element"
        )
        with pytest.raises(AttributeError, match=msg):
            ds.pixel_array

    def test_for_stray_raw_data_element(self):
        dataset = Dataset()
        dataset.PatientName = "MacDonald^George"
        sub_ds = Dataset()
        sub_ds.BeamNumber = "1"
        dataset.BeamSequence = Sequence([sub_ds])
        fp = DicomBytesIO()
        dataset.save_as(fp, implicit_vr=True)

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
        ds2.BeamSequence[0].BeamName = "1"
        assert ds1 != ds2

        # change a value in a sequence item
        ds1, ds2 = _reset()
        ds2.BeamSequence[0].BeamNumber = "2"
        assert ds2 != ds1

    def test_attribute_error_in_property_correct_debug(self):
        """Test AttributeError in property raises correctly."""

        class Foo(Dataset):
            @property
            def bar(self):
                return self._barr()

            def _bar(self):
                return "OK"

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

        msg = r"With tag \(0028,0106\) got exception: bad repr"
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

        msg = r"With tag \(0028,0106\) got exception: bad repr"
        with pytest.raises(ValueError, match=msg):
            func()

    def test_set_new_data_element_by_name(self):
        """Dataset: set new data_element by name."""
        ds = Dataset()
        ds.TreatmentMachineName = "unit #1"
        data_element = ds[0x300A, 0x00B2]
        assert "unit #1" == data_element.value
        assert "SH" == data_element.VR

    def test_set_existing_data_element_by_name(self):
        """Dataset: set existing data_element by name."""
        self.ds.TreatmentMachineName = "unit999"  # change existing value
        assert "unit999" == self.ds[0x300A, 0x00B2].value

    def test_set_non_dicom(self, setattr_warn):
        """Dataset: can set class instance property (non-dicom)."""
        ds = Dataset()
        msg = (
            r"Camel case attribute 'SomeVariableName' used which is not in "
            r"the element keyword data dictionary"
        )
        with pytest.warns(UserWarning, match=msg):
            ds.SomeVariableName = 42
        assert hasattr(ds, "SomeVariableName")
        assert 42 == ds.SomeVariableName

    def test_membership(self, contains_warn):
        """Dataset: can test if item present by 'if <name> in dataset'."""
        assert "TreatmentMachineName" in self.ds
        msg = (
            r"Invalid value 'Dummyname' used with the 'in' operator: must be "
            r"an element tag as a 2-tuple or int, or an element keyword"
        )
        with pytest.warns(UserWarning, match=msg):
            assert "Dummyname" not in self.ds

    def test_contains(self, contains_warn):
        """Dataset: can test if item present by 'if <tag> in dataset'."""
        self.ds.CommandGroupLength = 100  # (0000,0000)
        assert (0x300A, 0xB2) in self.ds
        assert [0x300A, 0xB2] in self.ds
        assert 0x300A00B2 in self.ds
        assert (0x10, 0x5F) not in self.ds
        assert "CommandGroupLength" in self.ds
        # Use a negative tag to cause an exception
        msg = (
            r"Invalid value '\(-16, 16\)' used with the 'in' operator: must "
            r"be an element tag as a 2-tuple or int, or an element keyword"
        )
        with pytest.warns(UserWarning, match=msg):
            assert (-0x0010, 0x0010) not in self.ds

        def foo():
            pass

        # Try a function
        msg = r"Invalid value '<function TestDataset"
        with pytest.warns(UserWarning, match=msg):
            assert foo not in self.ds

        # Random non-existent property
        msg = (
            r"Invalid value 'random name' used with the 'in' operator: must "
            r"be an element tag as a 2-tuple or int, or an element keyword"
        )
        with pytest.warns(UserWarning, match=msg):
            assert "random name" not in self.ds

        # Overflowing tag
        msg = (
            r"Invalid element tag value used with the 'in' operator: "
            r"tags have a maximum value of \(0xFFFF, 0xFFFF\)"
        )
        with pytest.warns(UserWarning, match=msg):
            assert 0x100100010 not in self.ds

    def test_contains_raises(self, contains_raise):
        """Test raising exception for invalid key."""
        msg = (
            r"Invalid value 'invalid' used with the 'in' operator: must "
            r"be an element tag as a 2-tuple or int, or an element keyword"
        )
        with pytest.raises(ValueError, match=msg):
            "invalid" in self.ds

    def test_contains_ignore(self, contains_ignore):
        """Test ignoring invalid keys."""
        with assert_no_warning():
            assert "invalid" not in self.ds

    def test_clear(self):
        assert 1 == len(self.ds)
        self.ds.clear()
        assert 0 == len(self.ds)

    def test_pop(self):
        with pytest.raises(KeyError):
            self.ds.pop(0x300A00B244)
        assert "default" == self.ds.pop("dummy", "default")
        elem = self.ds.pop(0x300A00B2)
        assert "unit001" == elem.value
        with pytest.raises(KeyError):
            self.ds.pop(0x300A00B2)

    def test_pop_using_tuple(self):
        elem = self.ds.pop((0x300A, 0x00B2))
        assert "unit001" == elem.value
        with pytest.raises(KeyError):
            self.ds.pop((0x300A, 0x00B2))

    def test_pop_using_keyword(self):
        with pytest.raises(KeyError):
            self.ds.pop("InvalidName")
        elem = self.ds.pop("TreatmentMachineName")
        assert "unit001" == elem.value
        with pytest.raises(KeyError):
            self.ds.pop("TreatmentMachineName")

    def test_popitem(self):
        elem = self.ds.popitem()
        assert 0x300A00B2 == elem[0]
        assert "unit001" == elem[1].value
        with pytest.raises(KeyError):
            self.ds.popitem()

    def test_setdefault(self):
        elem = self.ds.setdefault(0x300A00B2, "foo")
        assert "unit001" == elem.value
        elem = self.ds.setdefault(0x00100010, DataElement(0x00100010, "PN", "Test"))
        assert "Test" == elem.value
        assert 2 == len(self.ds)

    def test_setdefault_unknown_tag(self, dont_raise_on_writing_invalid_value):
        with pytest.warns(UserWarning, match=r"\(8888,0002\)"):
            elem = self.ds.setdefault(0x88880002, "foo")
        assert "foo" == elem.value
        assert "UN" == elem.VR
        assert 2 == len(self.ds)

    def test_setdefault_unknown_tag_strict(self, raise_on_writing_invalid_value):
        with pytest.raises(KeyError, match=r"\(8888,0004\)"):
            self.ds.setdefault(0x88880004, "foo")

    def test_setdefault_tuple(self):
        elem = self.ds.setdefault((0x300A, 0x00B2), "foo")
        assert "unit001" == elem.value
        elem = self.ds.setdefault(
            (0x0010, 0x0010), DataElement(0x00100010, "PN", "Test")
        )
        assert "Test" == elem.value
        assert 2 == len(self.ds)

    def test_setdefault_unknown_tuple(self, dont_raise_on_writing_invalid_value):
        with pytest.warns(UserWarning, match=r"\(8888,0002\)"):
            elem = self.ds.setdefault((0x8888, 0x0002), "foo")
        assert "foo" == elem.value
        assert "UN" == elem.VR
        assert 2 == len(self.ds)

    def test_setdefault_unknown_tuple_strict(self, raise_on_writing_invalid_value):
        with pytest.raises(KeyError, match=r"\(8888,0004\)"):
            self.ds.setdefault((0x8888, 0x0004), "foo")

    def test_setdefault_use_value(self, dont_raise_on_writing_invalid_value):
        elem = self.ds.setdefault((0x0010, 0x0010), "Test")
        assert "Test" == elem.value
        assert 2 == len(self.ds)

    def test_setdefault_keyword(self):
        """Test setdefault()."""
        assert "WindowWidth" not in self.ds
        elem = self.ds.setdefault("WindowWidth", None)
        assert elem.value is None
        assert self.ds.WindowWidth is None
        elem = self.ds.setdefault("WindowWidth", 1024)
        assert elem.value is None
        assert self.ds.WindowWidth is None

        assert "TreatmentMachineName" in self.ds
        assert "unit001" == self.ds.TreatmentMachineName
        elem = self.ds.setdefault("TreatmentMachineName", "foo")
        assert "unit001" == elem.value

        elem = self.ds.setdefault("PatientName", DataElement(0x00100010, "PN", "Test"))
        assert "Test" == elem.value
        assert 3 == len(self.ds)

    def test_setdefault_invalid_keyword(self):
        """Test setdefault() with an invalid keyword raises."""
        msg = (
            r"Unable to create an element tag from 'FooBar': unknown "
            r"DICOM element keyword"
        )
        with pytest.raises(ValueError, match=msg):
            self.ds.setdefault("FooBar", "foo")

    def test_setdefault_private(self):
        """Test setdefault() with a private tag."""
        elem = self.ds.setdefault(0x00090020, None)
        assert elem.is_private
        assert elem.value is None
        assert "UN" == elem.VR
        assert 0x00090020 in self.ds
        elem.VR = "PN"
        elem = self.ds.setdefault(0x00090020, "test")
        assert elem.is_private
        assert elem.value is None
        assert "PN" == elem.VR

    def test_get_exists1(self):
        """Dataset: dataset.get() returns an existing item by name."""
        assert "unit001" == self.ds.get("TreatmentMachineName", None)

    def test_get_exists2(self):
        """Dataset: dataset.get() returns an existing item by long tag."""
        assert "unit001" == self.ds.get(0x300A00B2, None).value

    def test_get_exists3(self):
        """Dataset: dataset.get() returns an existing item by tuple tag."""
        assert "unit001" == self.ds.get((0x300A, 0x00B2), None).value

    def test_get_exists4(self):
        """Dataset: dataset.get() returns an existing item by Tag."""
        assert "unit001" == self.ds.get(Tag(0x300A00B2), None).value

    def test_get_default1(self):
        """Dataset: dataset.get() returns default for non-existing name."""
        assert "not-there" == self.ds.get("NotAMember", "not-there")

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
        with pytest.raises(TypeError, match=r"Dataset.get key must be a string or tag"):
            self.ds.get(-0x0010, 0x0010)

    def test_get_from_raw(self):
        """Dataset: get(tag) returns same object as ds[tag] for raw element."""
        # This came from issue 88, where get(tag#) returned a RawDataElement,
        #     while get(name) converted to a true DataElement
        test_tag = 0x100010
        test_elem = RawDataElement(Tag(test_tag), "PN", 4, b"test", 0, True, True)
        ds = Dataset({Tag(test_tag): test_elem})
        assert ds[test_tag] == ds.get(test_tag)

    def test__setitem__(self):
        """Dataset: if set an item, it must be a DataElement instance."""
        ds = Dataset()
        with pytest.raises(TypeError):
            ds[0x300A, 0xB2] = "unit1"

    def test_matching_tags(self):
        """Dataset: key and data_element.tag mismatch raises ValueError."""
        ds = Dataset()
        data_element = DataElement((0x300A, 0x00B2), "SH", "unit001")
        with pytest.raises(ValueError):
            ds[0x10, 0x10] = data_element

    def test_named_member_updated(self):
        """Dataset: if set data_element by tag, name also reflects change."""
        self.ds[0x300A, 0xB2].value = "moon_unit"
        assert "moon_unit" == self.ds.TreatmentMachineName

    def test_update(self):
        """Dataset: update() method works with tag or name."""
        pat_data_element = DataElement((0x10, 0x12), "PN", "Johnny")
        self.ds.update({"PatientName": "John", (0x10, 0x12): pat_data_element})
        assert "John" == self.ds[0x10, 0x10].value
        assert "Johnny" == self.ds[0x10, 0x12].value

    def test_dir_attr(self):
        """Dataset.__dir__ returns class attributes"""
        ds = Dataset()
        assert hasattr(ds, "is_implicit_VR")
        assert "is_implicit_VR" in dir(ds)

    def test_dir_subclass(self):
        """Dataset.__dir__ returns class specific dir"""

        class DSP(Dataset):
            def test_func(self):
                pass

        ds = DSP()
        assert hasattr(ds, "test_func")
        assert callable(ds.test_func)
        assert "test_func" in dir(ds)

        ds = Dataset()
        assert hasattr(ds, "group_dataset")
        assert callable(ds.group_dataset)
        assert "group_dataset" in dir(ds)

    def test_dir(self, setattr_warn):
        """Dataset.dir() returns sorted list of named data_elements."""
        ds = self.ds
        ds.PatientName = "name"
        ds.PatientID = "id"
        msg = (
            r"Camel case attribute 'NonDicomVariable' used which is not in "
            r"the element keyword data dictionary"
        )
        with pytest.warns(UserWarning, match=msg):
            ds.NonDicomVariable = "junk"
        ds.add_new((0x18, 0x1151), "IS", 150)  # X-ray Tube Current
        ds.add_new((0x1111, 0x123), "DS", "42.0")  # private - no name in dir()
        expected = [
            "PatientID",
            "PatientName",
            "TreatmentMachineName",
            "XRayTubeCurrent",
        ]
        assert expected == ds.dir()

    def test_dir_filter(self, setattr_warn):
        """Test Dataset.dir(*filters) works OK."""
        ds = self.ds
        ds.PatientName = "name"
        ds.PatientID = "id"
        msg = (
            r"Camel case attribute 'NonDicomVariable' used which is not in "
            r"the element keyword data dictionary"
        )
        with pytest.warns(UserWarning, match=msg):
            ds.NonDicomVariable = "junk"
        ds.add_new((0x18, 0x1151), "IS", 150)  # X-ray Tube Current
        ds.add_new((0x1111, 0x123), "DS", "42.0")  # private - no name in dir()
        assert "PatientID" in ds
        assert "XRayTubeCurrent" in ds
        assert "TreatmentMachineName" in ds
        assert "PatientName" in ds
        assert "PatientBirthDate" not in ds
        assert ["PatientID", "PatientName"] == ds.dir("Patient")
        assert ["PatientName", "TreatmentMachineName"] == ds.dir("Name")
        expected = ["PatientID", "PatientName", "TreatmentMachineName"]
        assert expected == ds.dir("Name", "Patient")

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
        assert hasattr(self.ds, "meaningoflife")
        del self.ds.meaningoflife
        assert not hasattr(self.ds, "meaningoflife")

    def test_delete_dicom_attr_we_dont_have(self):
        """Dataset: try delete of missing DICOM attribute."""
        with pytest.raises(AttributeError):
            del self.ds.PatientName

    def test_delete_item_long(self):
        """Dataset: delete item by tag number (long)."""
        del self.ds[0x300A00B2]

    def test_delete_item_tuple(self):
        """Dataset: delete item by tag number (tuple)."""
        del self.ds[0x300A, 0x00B2]

    def test_delete_non_existing_item(self):
        """Dataset: raise KeyError for non-existing item delete."""
        with pytest.raises(KeyError):
            del self.ds[0x10, 0x10]

    def test_equality_no_sequence(self):
        """Dataset: equality returns correct value with simple dataset"""
        # Test empty dataset
        assert Dataset() == Dataset()

        d = Dataset()
        d.SOPInstanceUID = "1.2.3.4"
        d.PatientName = "Test"
        assert d == d  # noqa: PLR0124 Need to check equality with self

        e = Dataset()
        e.PatientName = "Test"
        e.SOPInstanceUID = "1.2.3.4"
        assert d == e

        e.SOPInstanceUID = "1.2.3.5"
        assert not d == e

        # Check VR
        del e.SOPInstanceUID
        e.add(DataElement(0x00080018, "PN", "1.2.3.4"))
        assert not d == e

        # Check Tag
        del e.SOPInstanceUID
        e.StudyInstanceUID = "1.2.3.4"
        assert not d == e

        # Check missing Element in self
        e.SOPInstanceUID = "1.2.3.4"
        assert not d == e

        # Check missing Element in other
        d = Dataset()
        d.SOPInstanceUID = "1.2.3.4"
        d.StudyInstanceUID = "1.2.3.4.5"

        e = Dataset()
        e.SOPInstanceUID = "1.2.3.4"
        assert not d == e

    def test_equality_private(self):
        """Dataset: equality returns correct value"""
        """when dataset has private elements"""
        d = Dataset()
        d_elem = DataElement(0x01110001, "PN", "Private")
        assert d == d  # noqa: PLR0124 Need to check equality with self
        d.add(d_elem)

        e = Dataset()
        e_elem = DataElement(0x01110001, "PN", "Private")
        e.add(e_elem)
        assert e == d

        e[0x01110001].value = "Public"
        assert not e == d

    def test_equality_sequence(self):
        """Equality returns correct value with sequences"""
        # Test even sequences
        d = Dataset()
        d.SOPInstanceUID = "1.2.3.4"
        d.BeamSequence = []
        beam_seq = Dataset()
        beam_seq.PatientID = "1234"
        beam_seq.PatientName = "ANON"
        d.BeamSequence.append(beam_seq)
        assert d == d  # noqa: PLR0124 Need to check equality with self

        e = Dataset()
        e.SOPInstanceUID = "1.2.3.4"
        e.BeamSequence = []
        beam_seq = Dataset()
        beam_seq.PatientName = "ANON"
        beam_seq.PatientID = "1234"
        e.BeamSequence.append(beam_seq)
        assert d == e

        e.BeamSequence[0].PatientName = "ANONY"
        assert not d == e

        # Test uneven sequences
        e.BeamSequence[0].PatientName = "ANON"
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
        d.SOPInstanceUID = "1.2.3.4"
        # Make sure Dataset.__eq__() is being used, not dict__eq__()
        assert not d == {"SOPInstanceUID": "1.2.3.4"}

    def test_equality_unknown(self, setattr_warn):
        """Dataset: equality returns correct value with extra members"""
        # Non-element class members are ignored in equality testing
        d = Dataset()
        msg = (
            r"Camel case attribute 'SOPEustaceUID' used which is not in "
            r"the element keyword data dictionary"
        )
        with pytest.warns(UserWarning, match=msg):
            d.SOPEustaceUID = "1.2.3.4"
        assert d == d  # noqa: PLR0124 Need to check equality with self

        e = Dataset()
        with pytest.warns(UserWarning, match=msg):
            e.SOPEustaceUID = "1.2.3.5"
        assert d == e

    def test_equality_inheritance(self):
        """Dataset: equality returns correct value for subclass"""

        class DatasetPlus(Dataset):
            pass

        d = Dataset()
        d.PatientName = "ANON"
        e = DatasetPlus()
        e.PatientName = "ANON"
        assert d == e
        assert e == d
        assert e == e  # noqa: PLR0124 Need to check equality with self

        e.PatientName = "ANONY"
        assert not d == e
        assert not e == d

    def test_equality_elements(self):
        """Test that Dataset equality only checks DataElements."""
        d = Dataset()
        d.SOPInstanceUID = "1.2.3.4"
        d.PatientName = "Test"
        d.foo = "foo"
        assert d == d  # noqa: PLR0124 Need to check equality with self

        e = Dataset()
        e.PatientName = "Test"
        e.SOPInstanceUID = "1.2.3.4"
        assert d == e

    def test_inequality(self):
        """Test inequality operator"""
        d = Dataset()
        d.SOPInstanceUID = "1.2.3.4"
        assert not d != d  # noqa: PLR0124 Need to check inequality with self

        e = Dataset()
        e.SOPInstanceUID = "1.2.3.5"
        assert d != e

    def test_hash(self):
        """DataElement: hash returns TypeError"""
        ds = Dataset()
        ds.PatientName = "ANON"
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
        dsp.test = "ABCD"
        assert "ABCD" == dsp.test

    def test_add_repeater_elem_by_keyword(self):
        """Repeater using keyword to add repeater group elements raises."""
        ds = Dataset()
        with pytest.raises(ValueError):
            ds.OverlayData = b"\x00"

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
        ds.SOPInstanceUID = "1.2.3.4"  # 0008,0018
        ds.SkipFrameRangeFlag = "TEST"  # 0008,9460
        ds.add_new(0x00090001, "PN", "CITIZEN^1")
        ds.add_new(0x00090002, "PN", "CITIZEN^2")
        ds.add_new(0x00090003, "PN", "CITIZEN^3")
        ds.add_new(0x00090004, "PN", "CITIZEN^4")
        ds.add_new(0x00090005, "PN", "CITIZEN^5")
        ds.add_new(0x00090006, "PN", "CITIZEN^6")
        ds.add_new(0x00090007, "PN", "CITIZEN^7")
        ds.add_new(0x00090008, "PN", "CITIZEN^8")
        ds.add_new(0x00090009, "PN", "CITIZEN^9")
        ds.add_new(0x00090010, "PN", "CITIZEN^10")
        ds.PatientName = "CITIZEN^Jan"  # 0010,0010
        ds.PatientID = "12345"  # 0010,0010
        ds.ExaminedBodyThickness = 1.223  # 0010,9431
        ds.BeamSequence = [Dataset()]  # 300A,00B0
        ds.BeamSequence[0].PatientName = "ANON"

        # Slice all items - should return original dataset
        assert ds[:] == ds

        # Slice starting from and including (0008,0001)
        test_ds = ds[0x00080001:]
        assert "CommandGroupLength" not in test_ds
        assert "CommandLengthToEnd" not in test_ds
        assert "Overlays" not in test_ds
        assert "LengthToEnd" in test_ds
        assert "BeamSequence" in test_ds

        # Slice ending at and not including (0009,0002)
        test_ds = ds[:0x00090002]
        assert "CommandGroupLength" in test_ds
        assert "CommandLengthToEnd" in test_ds
        assert "Overlays" in test_ds
        assert "LengthToEnd" in test_ds
        assert 0x00090001 in test_ds
        assert 0x00090002 not in test_ds
        assert "BeamSequence" not in test_ds

        # Slice with a step - every second tag
        # Should return zeroth tag, then second, fourth, etc...
        test_ds = ds[::2]
        assert "CommandGroupLength" in test_ds
        assert "CommandLengthToEnd" not in test_ds
        assert 0x00090001 in test_ds
        assert 0x00090002 not in test_ds

        # Slice starting at and including (0008,0018) and ending at and not
        #   including (0009,0008)
        test_ds = ds[0x00080018:0x00090008]
        assert "SOPInstanceUID" in test_ds
        assert 0x00090007 in test_ds
        assert 0x00090008 not in test_ds

        # Slice starting at and including (0008,0018) and ending at and not
        #   including (0009,0008), every third element
        test_ds = ds[0x00080018:0x00090008:3]
        assert "SOPInstanceUID" in test_ds
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
        assert "SOPInstanceUID" in ds[(0x00080018):(0x00080019)]
        assert "SOPInstanceUID" in ds[(0x0008, 0x0018):(0x0008, 0x0019)]
        assert "SOPInstanceUID" in ds["0x00080018":"0x00080019"]

    def test_getitem_slice_ffff(self):
        """Test slicing with (FFFF,FFFF)"""
        # Issue #92
        ds = Dataset()
        ds.CommandGroupLength = 120  # 0000,0000
        ds.CommandLengthToEnd = 111  # 0000,0001
        ds.Overlays = 12  # 0000,51B0
        ds.LengthToEnd = 12  # 0008,0001
        ds.SOPInstanceUID = "1.2.3.4"  # 0008,0018
        ds.SkipFrameRangeFlag = "TEST"  # 0008,9460
        ds.add_new(0xFFFF0001, "PN", "CITIZEN^1")
        ds.add_new(0xFFFF0002, "PN", "CITIZEN^2")
        ds.add_new(0xFFFF0003, "PN", "CITIZEN^3")
        ds.add_new(0xFFFFFFFE, "PN", "CITIZEN^4")
        ds.add_new(0xFFFFFFFF, "PN", "CITIZEN^5")

        assert "CITIZEN^5" == ds[:][0xFFFFFFFF].value
        assert 0xFFFFFFFF not in ds[0x1000:0xFFFFFFFF]
        assert 0xFFFFFFFF not in ds[(0x1000):(0xFFFF, 0xFFFF)]

    def test_delitem_slice(self):
        """Test Dataset.__delitem__ using slices."""
        ds = Dataset()
        ds.CommandGroupLength = 120  # 0000,0000
        ds.CommandLengthToEnd = 111  # 0000,0001
        ds.Overlays = 12  # 0000,51B0
        ds.LengthToEnd = 12  # 0008,0001
        ds.SOPInstanceUID = "1.2.3.4"  # 0008,0018
        ds.SkipFrameRangeFlag = "TEST"  # 0008,9460
        ds.add_new(0x00090001, "PN", "CITIZEN^1")
        ds.add_new(0x00090002, "PN", "CITIZEN^2")
        ds.add_new(0x00090003, "PN", "CITIZEN^3")
        ds.add_new(0x00090004, "PN", "CITIZEN^4")
        ds.add_new(0x00090005, "PN", "CITIZEN^5")
        ds.add_new(0x00090006, "PN", "CITIZEN^6")
        ds.add_new(0x00090007, "PN", "CITIZEN^7")
        ds.add_new(0x00090008, "PN", "CITIZEN^8")
        ds.add_new(0x00090009, "PN", "CITIZEN^9")
        ds.add_new(0x00090010, "PN", "CITIZEN^10")
        ds.PatientName = "CITIZEN^Jan"  # 0010,0010
        ds.PatientID = "12345"  # 0010,0010
        ds.ExaminedBodyThickness = 1.223  # 0010,9431
        ds.BeamSequence = [Dataset()]  # 300A,00B0
        ds.BeamSequence[0].PatientName = "ANON"

        # Delete the 0x0009 group
        del ds[0x00090000:0x00100000]
        assert "SkipFrameRangeFlag" in ds
        assert 0x00090001 not in ds
        assert 0x00090010 not in ds
        assert "PatientName" in ds

    def test_group_dataset(self):
        """Test Dataset.group_dataset"""
        ds = Dataset()
        ds.CommandGroupLength = 120  # 0000,0000
        ds.CommandLengthToEnd = 111  # 0000,0001
        ds.Overlays = 12  # 0000,51B0
        ds.LengthToEnd = 12  # 0008,0001
        ds.SOPInstanceUID = "1.2.3.4"  # 0008,0018
        ds.SkipFrameRangeFlag = "TEST"  # 0008,9460

        # Test getting group 0x0000
        group0000 = ds.group_dataset(0x0000)
        assert "CommandGroupLength" in group0000
        assert "CommandLengthToEnd" in group0000
        assert "Overlays" in group0000
        assert "LengthToEnd" not in group0000
        assert "SOPInstanceUID" not in group0000
        assert "SkipFrameRangeFlag" not in group0000

        # Test getting group 0x0008
        group0000 = ds.group_dataset(0x0008)
        assert "CommandGroupLength" not in group0000
        assert "CommandLengthToEnd" not in group0000
        assert "Overlays" not in group0000
        assert "LengthToEnd" in group0000
        assert "SOPInstanceUID" in group0000
        assert "SkipFrameRangeFlag" in group0000

    def test_get_item(self):
        """Test Dataset.get_item"""
        ds = Dataset()
        ds.CommandGroupLength = 120  # 0000,0000
        ds.SOPInstanceUID = "1.2.3.4"  # 0008,0018

        # Test non-deferred read
        assert ds[0x00000000] == ds.get_item(0x00000000)
        assert 120 == ds.get_item(0x00000000).value
        assert ds[0x00080018] == ds.get_item(0x00080018)
        assert "1.2.3.4" == ds.get_item(0x00080018).value

        # Test deferred read
        test_file = get_testdata_file("MR_small.dcm")
        ds = dcmread(test_file, force=True, defer_size="0.8 kB")
        ds_ref = dcmread(test_file, force=True)
        # get_item will follow the deferred read branch
        assert ds_ref.PixelData == ds.get_item(0x7FE00010).value

    def test_get_item_slice(self):
        """Test Dataset.get_item with slice argument"""
        # adapted from test_getitem_slice
        ds = Dataset()
        ds.CommandGroupLength = 120  # 0000,0000
        ds.CommandLengthToEnd = 111  # 0000,0001
        ds.Overlays = 12  # 0000,51B0
        ds.LengthToEnd = 12  # 0008,0001
        ds.SOPInstanceUID = "1.2.3.4"  # 0008,0018
        ds.SkipFrameRangeFlag = "TEST"  # 0008,9460
        ds.add_new(0x00090001, "PN", "CITIZEN^1")
        ds.add_new(0x00090002, "PN", "CITIZEN^2")
        ds.add_new(0x00090003, "PN", "CITIZEN^3")
        elem = RawDataElement(0x00090004, "PN", 9, b"CITIZEN^4", 0, True, True)
        ds.__setitem__(0x00090004, elem)
        elem = RawDataElement(0x00090005, "PN", 9, b"CITIZEN^5", 0, True, True)
        ds.__setitem__(0x00090005, elem)
        elem = RawDataElement(0x00090006, "PN", 9, b"CITIZEN^6", 0, True, True)
        ds.__setitem__(0x00090006, elem)
        ds.PatientName = "CITIZEN^Jan"  # 0010,0010
        elem = RawDataElement(0x00100020, "LO", 5, b"12345", 0, True, True)
        ds.__setitem__(0x00100020, elem)  # Patient ID
        ds.ExaminedBodyThickness = 1.223  # 0010,9431
        ds.BeamSequence = [Dataset()]  # 300A,00B0
        ds.BeamSequence[0].PatientName = "ANON"

        # Slice starting from and including (0008,0001)
        test_ds = ds.get_item(slice(0x00080001, None))
        assert "CommandGroupLength" not in test_ds
        assert "CommandLengthToEnd" not in test_ds
        assert "Overlays" not in test_ds
        assert "LengthToEnd" in test_ds
        assert "BeamSequence" in test_ds

        # Slice ending at and not including (0009,0002)
        test_ds = ds.get_item(slice(None, 0x00090002))
        assert "CommandGroupLength" in test_ds
        assert "CommandLengthToEnd" in test_ds
        assert "Overlays" in test_ds
        assert "LengthToEnd" in test_ds
        assert 0x00090001 in test_ds
        assert 0x00090002 not in test_ds
        assert "BeamSequence" not in test_ds

        # Slice with a step - every second tag
        # Should return zeroth tag, then second, fourth, etc...
        test_ds = ds.get_item(slice(None, None, 2))
        assert "CommandGroupLength" in test_ds
        assert "CommandLengthToEnd" not in test_ds
        assert 0x00090001 in test_ds
        assert 0x00090002 not in test_ds

        # Slice starting at and including (0008,0018) and ending at and not
        #   including (0009,0008)
        test_ds = ds.get_item(slice(0x00080018, 0x00090006))
        assert "SOPInstanceUID" in test_ds
        assert 0x00090005 in test_ds
        assert 0x00090006 not in test_ds

        # Slice starting at and including (0008,0018) and ending at and not
        #   including (0009,0006), every third element
        test_ds = ds.get_item(slice(0x00080018, 0x00090008, 3))
        assert "SOPInstanceUID" in test_ds
        assert 0x00090001 not in test_ds
        assert 0x00090002 in test_ds
        assert not test_ds.get_item(0x00090002).is_raw
        assert 0x00090003 not in test_ds
        assert 0x00090004 not in test_ds
        assert 0x00090005 in test_ds
        assert test_ds.get_item(0x00090005).is_raw
        assert 0x00090006 not in test_ds

        # Slice starting and ending (and not including) (0008,0018)
        assert Dataset() == ds.get_item(slice((0x0008, 0x0018), (0x0008, 0x0018)))

        # Test slicing using other acceptable Tag initialisations
        assert "SOPInstanceUID" in ds.get_item(slice(0x00080018, 0x00080019))
        assert "SOPInstanceUID" in ds.get_item(
            slice((0x0008, 0x0018), (0x0008, 0x0019))
        )
        assert "SOPInstanceUID" in ds.get_item(slice("0x00080018", "0x00080019"))

        # Slice all items - should return original dataset
        assert ds == ds.get_item(slice(None, None))

    def test_getitem_deferred(self):
        """Test get_item(..., keep_deferred)"""
        test_file = get_testdata_file("MR_small.dcm")
        ds = dcmread(test_file, force=True, defer_size="0.8 kB")
        elem = ds.get_item("PixelData", keep_deferred=True)
        assert isinstance(elem, RawDataElement)
        assert elem.value is None

        elem = ds.get_item("PixelData", keep_deferred=False)
        assert isinstance(elem, DataElement)
        assert elem.value is not None

    def test_get_private_item(self):
        ds = Dataset()
        ds.add_new(0x00080005, "CS", "ISO_IR 100")
        ds.add_new(0x00090010, "LO", "Creator 1.0")
        ds.add_new(0x00091001, "SH", "Version1")
        ds.add_new(0x00090011, "LO", "Creator 2.0")
        ds.add_new(0x00091101, "SH", "Version2")
        ds.add_new(0x00091102, "US", 2)

        with pytest.raises(ValueError, match="Tag must be private"):
            ds.get_private_item(0x0008, 0x05, "Creator 1.0")
        with pytest.raises(ValueError, match="Private creator must have a value"):
            ds.get_private_item(0x0009, 0x10, "")
        with pytest.raises(KeyError, match="Private creator 'Creator 3.0' not found"):
            ds.get_private_item(0x0009, 0x10, "Creator 3.0")
        item = ds.get_private_item(0x0009, 0x01, "Creator 1.0")
        assert "Version1" == item.value
        item = ds.get_private_item(0x0009, 0x01, "Creator 2.0")
        assert "Version2" == item.value

        with pytest.raises(KeyError):
            ds.get_private_item(0x0009, 0x02, "Creator 1.0")
        item = ds.get_private_item(0x0009, 0x02, "Creator 2.0")
        assert 2 == item.value

    def test_add_unknown_private_tag(self):
        ds = Dataset()
        with pytest.raises(ValueError, match="Tag must be private"):
            ds.add_new_private("Creator 1.0", 0x0010, 0x01, "VALUE", VR.SH)
        with pytest.raises(ValueError, match="Private creator must have a value"):
            ds.add_new_private("", 0x0011, 0x01, "VALUE", VR.SH)
        with pytest.raises(
            KeyError,
            match="Private creator 'Creator 1.0' not in the private dictionary",
        ):
            ds.add_new_private("Creator 1.0", 0x0011, 0x01, "VALUE")

        ds.add_new_private("Creator 1.0", 0x0011, 0x01, "VALUE", VR.SH)
        item = ds.get_private_item(0x0011, 0x01, "Creator 1.0")
        assert item.value == "VALUE"
        assert item.private_creator == "Creator 1.0"
        assert item.VR == VR.SH

    def test_add_known_private_tag(self):
        ds = Dataset()
        ds.add_new_private("GEMS_GENIE_1", 0x0009, 0x10, "Test Study")
        item = ds.get_private_item(0x0009, 0x10, "GEMS_GENIE_1")
        assert item.value == "Test Study"
        assert item.private_creator == "GEMS_GENIE_1"
        assert item.VR == VR.LO

        add_private_dict_entry("Creator 1.0", 0x00110001, VR.SH, "Some Value")
        ds.add_new_private("Creator 1.0", 0x0011, 0x01, "VALUE")
        item = ds.get_private_item(0x0011, 0x01, "Creator 1.0")
        assert item.value == "VALUE"
        assert item.private_creator == "Creator 1.0"
        assert item.VR == VR.SH

    def test_private_block(self):
        ds = Dataset()
        ds.add_new(0x00080005, "CS", "ISO_IR 100")
        ds.add_new(0x00090010, "LO", "Creator 1.0")
        ds.add_new(0x00091001, "SH", "Version1")
        # make sure it works with non-contiguous blocks
        ds.add_new(0x00090020, "LO", "Creator 2.0")
        ds.add_new(0x00092001, "SH", "Version2")
        ds.add_new(0x00092002, "US", 2)

        # Dataset.private_block
        with pytest.raises(ValueError, match="Tag must be private"):
            ds.private_block(0x0008, "Creator 1.0")
        with pytest.raises(ValueError, match="Private creator must have a value"):
            ds.private_block(0x0009, "")
        with pytest.raises(KeyError, match="Private creator 'Creator 3.0' not found"):
            ds.private_block(0x0009, "Creator 3.0")

        block = ds.private_block(0x0009, "Creator 1.0")

        # test for containment
        assert 1 in block
        assert 2 not in block

        # get item from private block
        item = block[0x01]
        assert "Version1" == item.value
        block = ds.private_block(0x0009, "Creator 2.0")
        with pytest.raises(ValueError, match="Element offset must be less than 256"):
            block[0x0101]

        item = block[0x01]
        assert "Version2" == item.value

        # Dataset.get_private_item
        with pytest.raises(KeyError):
            ds.get_private_item(0x0009, 0x02, "Creator 1.0")

        item = ds.get_private_item(0x0009, 0x02, "Creator 2.0")
        assert 2 == item.value

    def test_private_block_deepcopy(self):
        """Test deepcopying a private block."""
        ds = Dataset()
        ds.private_block(0x000B, "Foo", create=True)

        ds2 = copy.deepcopy(ds)
        assert ds2[0x000B0010].value == "Foo"

    def test_private_block_pickle(self):
        """Test pickling a private block."""
        ds = Dataset()
        ds.private_block(0x000B, "Foo", create=True)

        s = pickle.dumps({"ds": ds})
        ds2 = pickle.loads(s)["ds"]
        assert ds2[0x000B0010].value == "Foo"

    def test_private_creator_from_raw_ds(self):
        # regression test for #1078
        ct_filename = get_testdata_file("CT_small.dcm")
        ds = dcmread(ct_filename)
        ds.private_block(0x11, "GEMS_PATI_01", create=True)
        assert ["GEMS_PATI_01"] == ds.private_creators(0x11)

        assert [] == ds.private_creators(0x13)
        ds.private_block(0x13, "GEMS_PATI_01", create=True)
        assert ["GEMS_PATI_01"] == ds.private_creators(0x13)

    def test_add_known_private_tag2(self):
        # regression test for #1082
        ds = dcmread(get_testdata_file("CT_small.dcm"))
        assert "[Patient Status]" == ds[0x11, 0x1010].name

        block = ds.private_block(0x11, "GEMS_PATI_01")
        block.add_new(0x10, "SS", 1)
        assert "[Patient Status]" == ds[0x11, 0x1010].name

    def test_add_new_private_tag(self):
        ds = Dataset()
        ds.add_new(0x00080005, "CS", "ISO_IR 100")
        ds.add_new(0x00090010, "LO", "Creator 1.0")
        ds.add_new(0x00090011, "LO", "Creator 2.0")

        with pytest.raises(ValueError, match="Tag must be private"):
            ds.private_block(0x0008, "Creator 1.0")
        block = ds.private_block(0x0009, "Creator 2.0", create=True)
        block.add_new(0x01, "SH", "Version2")
        assert "Version2" == ds[0x00091101].value
        block = ds.private_block(0x0009, "Creator 3.0", create=True)
        block.add_new(0x01, "SH", "Version3")
        assert "Creator 3.0" == ds[0x00090012].value
        assert "Version3" == ds[0x00091201].value

    def test_delete_private_tag(self):
        ds = Dataset()
        ds.add_new(0x00080005, "CS", "ISO_IR 100")
        ds.add_new(0x00090010, "LO", "Creator 1.0")
        ds.add_new(0x00090011, "LO", "Creator 2.0")
        ds.add_new(0x00091101, "SH", "Version2")

        block = ds.private_block(0x0009, "Creator 2.0")
        with pytest.raises(ValueError, match="Element offset must be less than 256"):
            del block[0x1001]
        assert 1 in block
        del block[0x01]
        assert 1 not in block
        with pytest.raises(KeyError):
            del block[0x01]

    def test_private_creators(self):
        ds = Dataset()
        ds.add_new(0x00080005, "CS", "ISO_IR 100")
        ds.add_new(0x00090010, "LO", "Creator 1.0")
        ds.add_new(0x00090011, "LO", "Creator 2.0")

        with pytest.raises(ValueError, match="Group must be an odd number"):
            ds.private_creators(0x0008)
        assert ["Creator 1.0", "Creator 2.0"] == ds.private_creators(0x0009)
        assert not ds.private_creators(0x0011)

    def test_non_contiguous_private_creators(self):
        ds = Dataset()
        ds.add_new(0x00080005, "CS", "ISO_IR 100")
        ds.add_new(0x00090010, "LO", "Creator 1.0")
        ds.add_new(0x00090020, "LO", "Creator 2.0")
        ds.add_new(0x000900FF, "LO", "Creator 3.0")

        assert ["Creator 1.0", "Creator 2.0", "Creator 3.0"] == ds.private_creators(
            0x0009
        )

    def test_create_private_tag_after_removing_all(self):
        # regression test for #1097 - make sure private blocks are updated
        # after removing all private tags
        ds = Dataset()
        block = ds.private_block(0x000B, "dog^1", create=True)
        block.add_new(0x01, "SH", "Border Collie")
        block = ds.private_block(0x000B, "dog^2", create=True)
        block.add_new(0x01, "SH", "Poodle")

        ds.remove_private_tags()
        block = ds.private_block(0x000B, "dog^2", create=True)
        block.add_new(0x01, "SH", "Poodle")
        assert len(ds) == 2
        assert (0x000B0010) in ds
        assert ds[0x000B0010].value == "dog^2"

    def test_create_private_tag_after_removing_private_creator(self):
        ds = Dataset()
        block = ds.private_block(0x000B, "dog^1", create=True)
        block.add_new(0x01, "SH", "Border Collie")

        del ds[0x000B0010]
        block = ds.private_block(0x000B, "dog^1", create=True)
        block.add_new(0x02, "SH", "Poodle")
        assert len(ds) == 3
        assert ds[0x000B0010].value == "dog^1"

        del ds[Tag(0x000B, 0x0010)]
        block = ds.private_block(0x000B, "dog^1", create=True)
        block.add_new(0x01, "SH", "Pug")
        assert len(ds) == 3
        assert ds[0x000B0010].value == "dog^1"

        del ds["0x000b0010"]
        block = ds.private_block(0x000B, "dog^1", create=True)
        block.add_new(0x01, "SH", "Pug")
        assert len(ds) == 3
        assert ds[0x000B0010].value == "dog^1"

    def test_create_private_tag_after_removing_slice(self):
        ds = Dataset()
        block = ds.private_block(0x000B, "dog^1", create=True)
        block.add_new(0x01, "SH", "Border Collie")
        block = ds.private_block(0x000B, "dog^2", create=True)
        block.add_new(0x01, "SH", "Poodle")

        del ds[0x000B0010:0x000B1110]
        block = ds.private_block(0x000B, "dog^2", create=True)
        block.add_new(0x01, "SH", "Poodle")
        assert len(ds) == 2
        assert ds[0x000B0010].value == "dog^2"

    def test_read_invalid_private_tag_number_as_un(self):
        # regression test for #1347
        ds = Dataset()
        # not a valid private tag number nor a valid private creator
        tag1 = Tag(0x70050000)  # this one caused a recursion
        tag2 = Tag(0x70050005)
        ds[tag1] = RawDataElement(tag1, None, 2, b"\x01\x02", 0, True, True)
        ds[tag2] = RawDataElement(tag2, None, 2, b"\x03\x04", 0, True, True)
        assert ds[tag1].value == b"\x01\x02"
        assert ds[tag1].VR == "UN"
        assert ds[tag2].value == b"\x03\x04"
        assert ds[tag2].VR == "UN"

    def test_invalid_private_creator(self):
        # regression test for #1638
        ds = Dataset()
        ds.add_new(0x00250010, "SL", [13975, 13802])
        ds.add_new(0x00250011, "LO", "Valid Creator")
        ds.add_new(0x00251007, "UN", "foobar")
        ds.add_new(0x00251107, "UN", "foobaz")
        msg = r"\(0025,0010\) '\[13975, 13802]' is not a valid private creator"
        with pytest.warns(UserWarning, match=msg):
            assert (
                str(ds[0x00251007]) == "(0025,1007) Private tag data"
                "                    UN: 'foobar'"
            )
        assert (
            str(ds[0x00251107]) == "(0025,1107) Private tag data"
            "                    UN: 'foobaz'"
        )

    def test_is_original_encoding(self):
        """Test Dataset.is_original_encoding"""
        ds = Dataset()
        assert not ds.is_original_encoding

        # simulate reading
        ds.SpecificCharacterSet = "ISO_IR 100"
        ds.set_original_encoding(True, True, ["latin_1"])
        assert not ds.is_original_encoding

        ds._is_little_endian = True
        ds._is_implicit_VR = True
        assert ds.is_original_encoding
        # changed character set
        ds.SpecificCharacterSet = "ISO_IR 192"
        assert not ds.is_original_encoding
        # back to original character set
        ds.SpecificCharacterSet = "ISO_IR 100"
        assert ds.is_original_encoding
        ds._is_little_endian = False
        assert not ds.is_original_encoding
        ds._is_little_endian = True
        ds._is_implicit_VR = False
        assert not ds.is_original_encoding

        ds.set_original_encoding(True, True, None)
        assert ds.original_character_set == ["latin_1"]

    def test_original_charset_is_equal_to_charset_after_dcmread(self):
        default_encoding_test_file = get_testdata_file("liver_1frame.dcm")
        non_default_encoding_test_file = get_testdata_file("CT_small.dcm")

        default_encoding_ds = dcmread(default_encoding_test_file)
        non_default_encoding_ds = dcmread(non_default_encoding_test_file)

        assert default_encoding_ds.original_character_set == "iso8859"
        assert (
            default_encoding_ds.original_character_set
            == default_encoding_ds._character_set
        )
        assert (
            default_encoding_ds.ReferencedSeriesSequence[0].original_character_set
            == default_encoding_ds.ReferencedSeriesSequence[0]._character_set
        )
        assert (
            default_encoding_ds.file_meta.original_character_set
            == default_encoding_ds.file_meta._character_set
        )
        assert non_default_encoding_ds.original_character_set == ["latin_1"]
        assert (
            non_default_encoding_ds.original_character_set
            == non_default_encoding_ds._character_set
        )
        assert (
            non_default_encoding_ds.OtherPatientIDsSequence[0].original_character_set
            == non_default_encoding_ds.OtherPatientIDsSequence[0]._character_set
        )
        assert (
            non_default_encoding_ds.file_meta.original_character_set
            == non_default_encoding_ds.file_meta._character_set
        )

    def test_remove_private_tags(self):
        """Test Dataset.remove_private_tags"""
        ds = Dataset()
        ds.CommandGroupLength = 120  # 0000,0000
        ds.SkipFrameRangeFlag = "TEST"  # 0008,9460
        ds.add_new(0x00090001, "PN", "CITIZEN^1")
        ds.add_new(0x00090010, "PN", "CITIZEN^10")
        ds.PatientName = "CITIZEN^Jan"  # 0010,0010

        ds.remove_private_tags()
        assert Dataset() == ds[0x00090000:0x00100000]
        assert "CommandGroupLength" in ds
        assert "SkipFrameRangeFlag" in ds
        assert "PatientName" in ds

    def test_data_element(self):
        """Test Dataset.data_element."""
        ds = Dataset()
        ds.CommandGroupLength = 120
        ds.SkipFrameRangeFlag = "TEST"
        ds.add_new(0x00090001, "PN", "CITIZEN^1")
        ds.BeamSequence = [Dataset()]
        ds.BeamSequence[0].PatientName = "ANON"
        assert ds[0x00000000] == ds.data_element("CommandGroupLength")
        assert ds[0x300A00B0] == ds.data_element("BeamSequence")
        assert ds.data_element("not an element keyword") is None

    def test_iterall(self):
        """Test Dataset.iterall"""
        ds = Dataset()
        ds.CommandGroupLength = 120
        ds.SkipFrameRangeFlag = "TEST"
        ds.add_new(0x00090001, "PN", "CITIZEN^1")
        ds.BeamSequence = [Dataset()]
        ds.BeamSequence[0].PatientName = "ANON"
        elem_gen = ds.iterall()
        assert ds.data_element("CommandGroupLength") == next(elem_gen)
        assert ds.data_element("SkipFrameRangeFlag") == next(elem_gen)
        assert ds[0x00090001] == next(elem_gen)
        assert ds.data_element("BeamSequence") == next(elem_gen)
        assert ds.BeamSequence[0].data_element("PatientName") == next(elem_gen)

    def test_with(self):
        """Test Dataset.__enter__ and __exit__."""
        test_file = get_testdata_file("CT_small.dcm")
        with dcmread(test_file) as ds:
            assert "CompressedSamples^CT1" == ds.PatientName

    def test_exit_exception(self):
        """Test Dataset.__exit__ when an exception is raised."""

        class DSException(Dataset):
            @property
            def test(self):
                raise ValueError("Random ex message!")

        with pytest.raises(ValueError, match="Random ex message!"):
            getattr(DSException(), "test")

    def test_pixel_array_already_have(self):
        """Test Dataset._get_pixel_array when we already have the array"""
        # Test that _pixel_array is returned unchanged unless required
        fpath = get_testdata_file("CT_small.dcm")
        ds = dcmread(fpath)
        ds._pixel_id = get_image_pixel_ids(ds)
        ds._pixel_array = "Test Value"
        ds.convert_pixel_data()
        assert get_image_pixel_ids(ds) == ds._pixel_id
        assert "Test Value" == ds._pixel_array

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
    def test_invalid_nr_frames_warns(self):
        """Test an invalid Number of Frames value shows an warning."""
        fpath = get_testdata_file("CT_small.dcm")
        ds = dcmread(fpath)
        ds.NumberOfFrames = 0
        msg = r"A value of '0' for \(0028,0008\) 'Number of Frames' is invalid"
        with pytest.warns(UserWarning, match=msg):
            assert ds.pixel_array is not None

    def test_pixel_array_id_changed(self, clear_pixel_data_handlers):
        """Test that we try to get new pixel data if the id has changed."""
        fpath = get_testdata_file("CT_small.dcm")
        ds = dcmread(fpath)
        ds.file_meta.TransferSyntaxUID = "1.2.3.4"
        ds._pixel_id = 1234
        assert id(ds.PixelData) != ds._pixel_id
        ds._pixel_array = "Test Value"
        msg = (
            r"Unable to decode the pixel data as a \(0002,0010\) 'Transfer Syntax UID' "
            "value of '1.2.3.4' is not supported"
        )
        with pytest.raises(NotImplementedError, match=msg):
            ds.pixel_array

        ds.pixel_array_options(use_v2_backend=True)
        msg = "Unable to decode pixel data with a transfer syntax UID of '1.2.3.4'"
        with pytest.raises(NotImplementedError, match=msg):
            ds.convert_pixel_data()

    def test_pixel_array_id_reset_on_delete(self):
        """Test _pixel_array and _pixel_id reset when deleting pixel data"""
        fpath = get_testdata_file("CT_small.dcm")
        ds = dcmread(fpath)
        assert ds._pixel_id == {}
        assert ds._pixel_array is None
        ds._pixel_id = {"SamplesPerPixel": 3}
        ds._pixel_array = True

        del ds.PixelData
        assert ds._pixel_id == {}
        assert ds._pixel_array is None

        ds.PixelData = b"\x00\x01"
        ds._pixel_id = {"SamplesPerPixel": 3}
        ds._pixel_array = True

        del ds["PixelData"]
        assert ds._pixel_id == {}
        assert ds._pixel_array is None

        ds.PixelData = b"\x00\x01"
        ds._pixel_id = {"SamplesPerPixel": 3}
        ds._pixel_array = True

        del ds[Tag("PixelData")]
        assert ds._pixel_id == {}
        assert ds._pixel_array is None

        ds.PixelData = b"\x00\x01"
        ds._pixel_id = {"SamplesPerPixel": 3}
        ds._pixel_array = True

        del ds[0x7FE00010]
        assert ds._pixel_id == {}
        assert ds._pixel_array is None

        ds.PixelData = b"\x00\x01"
        ds._pixel_id = {"SamplesPerPixel": 3}
        ds._pixel_array = True

        del ds[0x7FE00000:0x7FE00012]
        assert ds._pixel_id == {}
        assert ds._pixel_array is None

    def test_pixel_array_unknown_syntax(self):
        """Test that pixel_array for an unknown syntax raises exception."""
        ds = dcmread(get_testdata_file("CT_small.dcm"))
        ds.file_meta.TransferSyntaxUID = "1.2.3.4"
        msg = (
            r"Unable to decode the pixel data as a \(0002,0010\) 'Transfer Syntax UID' "
            "value of '1.2.3.4' is not supported"
        )
        with pytest.raises(NotImplementedError, match=msg):
            ds.pixel_array

    def test_formatted_lines(self):
        """Test Dataset.formatted_lines"""
        ds = Dataset()
        with pytest.raises(StopIteration):
            next(ds.formatted_lines())
        ds.PatientName = "CITIZEN^Jan"
        ds.BeamSequence = [Dataset()]
        ds.BeamSequence[0].PatientID = "JAN^Citizen"
        elem_format = "%(tag)s"
        seq_format = "%(name)s %(tag)s"
        indent_format = ">>>"  # placeholder for future functionality

        line_generator = ds.formatted_lines(
            element_format=elem_format,
            sequence_element_format=seq_format,
            indent_format=indent_format,
        )
        assert "(0010,0010)" == next(line_generator)
        assert "Beam Sequence (300A,00B0)" == next(line_generator)
        assert "(0010,0020)" == next(line_generator)
        with pytest.raises(StopIteration):
            next(line_generator)

    def test_formatted_lines_known_uid(self):
        """Test that the UID name is output when known."""
        ds = Dataset()
        ds.TransferSyntaxUID = "1.2.840.10008.1.2"
        assert "Implicit VR Little Endian" in str(ds)

    def test_set_convert_private_elem_from_raw(self):
        """Test Dataset.__setitem__ with a raw private element"""
        test_file = get_testdata_file("CT_small.dcm")
        ds = dcmread(test_file, force=True)
        # 'tag VR length value value_tell is_implicit_VR is_little_endian'
        elem = RawDataElement((0x0043, 0x1029), "OB", 2, b"\x00\x01", 0, True, True)
        ds.__setitem__((0x0043, 0x1029), elem)

        assert b"\x00\x01" == ds[(0x0043, 0x1029)].value
        assert isinstance(ds[(0x0043, 0x1029)], DataElement)

    def test_top(self):
        """Test Dataset.top returns only top level str"""
        ds = Dataset()
        ds.PatientName = "CITIZEN^Jan"
        ds.BeamSequence = [Dataset()]
        ds.BeamSequence[0].PatientID = "JAN^Citizen"
        assert "Patient's Name" in ds.top()
        assert "Patient ID" not in ds.top()

    def test_trait_names(self):
        """Test Dataset.trait_names contains element keywords"""
        test_file = get_testdata_file("CT_small.dcm")
        ds = dcmread(test_file, force=True)
        names = ds.trait_names()
        assert "PatientName" in names
        assert "save_as" in names
        assert "PixelData" in names

    def test_walk(self):
        """Test Dataset.walk iterates through sequences"""

        def test_callback(dataset, elem):
            if elem.keyword == "PatientID":
                dataset.PatientID = "FIXED"

        ds = Dataset()
        ds.PatientName = "CITIZEN^Jan"
        ds.BeamSequence = [Dataset(), Dataset()]
        ds.BeamSequence[0].PatientID = "JAN^Citizen^Snr"
        ds.BeamSequence[0].PatientName = "Some^Name"
        ds.BeamSequence[1].PatientID = "JAN^Citizen^Jr"
        ds.BeamSequence[1].PatientName = "Other^Name"
        ds.walk(test_callback, recursive=True)

        assert "CITIZEN^Jan" == ds.PatientName
        assert "FIXED" == ds.BeamSequence[0].PatientID
        assert "Some^Name" == ds.BeamSequence[0].PatientName
        assert "FIXED" == ds.BeamSequence[1].PatientID
        assert "Other^Name" == ds.BeamSequence[1].PatientName

    def test_update_with_dataset(self):
        """Regression test for #779"""
        ds = Dataset()
        ds.PatientName = "Test"
        ds2 = Dataset()
        ds2.update(ds)
        assert "Test" == ds2.PatientName

        # Test sequences
        ds2 = Dataset()
        ds.BeamSequence = [Dataset(), Dataset()]
        ds.BeamSequence[0].PatientName = "TestA"
        ds.BeamSequence[1].PatientName = "TestB"

        ds2.update(ds)
        assert "TestA" == ds2.BeamSequence[0].PatientName
        assert "TestB" == ds2.BeamSequence[1].PatientName

        # Test overwrite
        ds.PatientName = "TestC"
        ds2.update(ds)
        assert "TestC" == ds2.PatientName

    def test_getitem_invalid_key_raises(self):
        """Test that __getitem__ raises KeyError on invalid key."""
        ds = Dataset()
        with pytest.raises(KeyError, match=r"'invalid'"):
            ds["invalid"]

    def test_setitem_invalid_key(self):
        """Test that __setitem__ behavior."""
        a = {}
        with pytest.raises(KeyError, match=r"'invalid'"):
            a["invalid"]

        ds = Dataset()
        ds.PatientName = "Citizen^Jan"
        msg = r"Unable to convert the key 'invalid' to an element tag"
        with pytest.raises(ValueError, match=msg):
            ds["invalid"] = ds["PatientName"]

    def test_values(self):
        """Test Dataset.values()."""
        ds = Dataset()
        ds.PatientName = "Foo"
        ds.BeamSequence = [Dataset()]
        ds.BeamSequence[0].PatientID = "Bar"

        values = list(ds.values())
        assert values[0] == ds["PatientName"]
        assert values[1] == ds["BeamSequence"]
        assert len(values) == 2

    def test_pixel_rep(self):
        """Tests for Dataset._pixel_rep"""
        ds = Dataset()
        ds.PixelRepresentation = None
        ds.BeamSequence = []

        fp = io.BytesIO()
        ds.save_as(fp, implicit_vr=True)
        ds = dcmread(fp, force=True)
        assert not hasattr(ds, "_pixel_rep")
        assert ds.PixelRepresentation is None
        assert ds.BeamSequence == []
        # Attribute not set if Pixel Representation is None
        assert not hasattr(ds, "_pixel_rep")

        ds = dcmread(fp, force=True)
        ds.PixelRepresentation = 0
        assert ds.BeamSequence == []
        assert ds._pixel_rep == 0

        ds = dcmread(fp, force=True)
        ds.PixelRepresentation = 1
        assert ds.BeamSequence == []
        assert ds._pixel_rep == 1

        ds = Dataset()
        ds.PixelRepresentation = 0
        ds._set_pixel_representation(ds["PixelRepresentation"])
        assert ds._pixel_rep == 0

    def test_update_raw(self):
        """Tests for Dataset.update_raw_element()"""
        ds = Dataset()

        msg = "Either or both of 'vr' and 'value' are required"
        with pytest.raises(ValueError, match=msg):
            ds.update_raw_element(None)

        msg = "Invalid VR value 'XX'"
        with pytest.raises(ValueError, match=msg):
            ds.update_raw_element(None, vr="XX")

        msg = "'value' must be bytes, not 'int'"
        with pytest.raises(TypeError, match=msg):
            ds.update_raw_element(None, value=1234)

        msg = r"No element with tag \(0010,0010\) was found"
        with pytest.raises(KeyError, match=msg):
            ds.update_raw_element(0x00100010, vr="US")

        ds.PatientName = "Foo"
        msg = (
            r"The element with tag \(0010,0010\) has already been converted to a "
            "'DataElement' instance, this method must be called earlier"
        )
        with pytest.raises(TypeError, match=msg):
            ds.update_raw_element(0x00100010, vr="US")

        raw = RawDataElement(0x00100010, "PN", 4, b"Fooo", 0, True, True)
        ds._dict[0x00100010] = raw
        ds.update_raw_element("PatientName", vr="US")
        assert ds.PatientName == [28486, 28527]
        assert isinstance(ds["PatientName"].VR, str)

        raw = RawDataElement(0x00100010, "PN", 4, b"Fooo", 0, True, True)
        ds._dict[0x00100010] = raw
        ds.update_raw_element(0x00100010, value=b"Bar")
        assert ds.PatientName == "Bar"


class TestDatasetSaveAs:
    def test_no_transfer_syntax(self):
        """Test basic use of Dataset.save_as()"""
        ds = Dataset()
        ds.PatientName = "CITIZEN"

        # Requires implicit_vr
        msg = (
            "Unable to determine the encoding to use for writing the dataset, "
            "please set the file meta's Transfer Syntax UID or use the "
            "'implicit_vr' and 'little_endian' arguments"
        )
        with pytest.raises(ValueError, match=msg):
            ds.save_as(DicomBytesIO())

        # OK
        ds.save_as(DicomBytesIO(), implicit_vr=True)

    def test_little_endian_default(self):
        """Test that the default uses little endian."""
        ds = Dataset()
        ds.PatientName = "CITIZEN"
        bs = io.BytesIO()
        ds.save_as(bs, implicit_vr=True, little_endian=None)
        assert ds["PatientName"].tag.group == 0x0010
        assert bs.getvalue()[:4] == b"\x10\x00\x10\x00"

    def test_mismatch(self):
        """Test mismatch between transfer syntax and args."""
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian

        msg = (
            "The 'implicit_vr' value is not consistent with the required "
            "VR encoding for the 'Implicit VR Little Endian' transfer syntax"
        )
        with pytest.raises(ValueError, match=msg):
            ds.save_as(DicomBytesIO(), implicit_vr=False, little_endian=False)

        msg = (
            "The 'little_endian' value is not consistent with the required "
            "endianness for the 'Implicit VR Little Endian' transfer syntax"
        )
        with pytest.raises(ValueError, match=msg):
            ds.save_as(DicomBytesIO(), implicit_vr=True, little_endian=False)

    def test_priority_syntax(self):
        """Test prefer transfer syntax over dataset attributes."""
        ds = get_testdata_file("CT_small.dcm", read=True)
        assert not ds.original_encoding[0]
        assert not ds._is_implicit_VR

        # Explicit -> implicit
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        fp = DicomBytesIO()
        ds.save_as(fp)
        fp.seek(0)
        ds = dcmread(fp)
        assert ds.original_encoding[0]
        assert ds._is_implicit_VR

        # Implicit -> explicit
        fp = DicomBytesIO()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds._is_implicit_VR = True
        ds.save_as(fp)
        fp.seek(0)
        ds = dcmread(fp)
        assert not ds.original_encoding[0]

        ds = Dataset()
        ds.preamble = b"\x00" * 128
        ds.PatientName = "Foo"
        ds._is_little_endian = True
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRBigEndian

        # Big endian
        fp = DicomBytesIO()
        ds.save_as(fp)
        fp.seek(0)
        ds = dcmread(fp)
        assert not ds.original_encoding[1]

        # Little endian
        ds._read_little = None
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        fp = DicomBytesIO()
        ds.save_as(fp)
        fp.seek(0)
        ds = dcmread(fp)
        assert ds.original_encoding[1]

    def test_priority_args(self):
        """Test prefer args over dataset attributes."""
        ds = get_testdata_file("CT_small.dcm", read=True)
        del ds.file_meta
        assert not ds.original_encoding[0]
        assert not ds._is_implicit_VR

        # Explicit -> implicit
        fp = DicomBytesIO()
        ds.save_as(fp, implicit_vr=True)
        fp.seek(0)
        ds = dcmread(fp)
        assert ds.original_encoding == (True, True)
        assert ds._is_implicit_VR

        # Implicit -> explicit
        fp = DicomBytesIO()
        ds.save_as(fp, implicit_vr=False)
        fp.seek(0)
        ds = dcmread(fp)
        assert ds.original_encoding == (False, True)

        ds = Dataset()
        ds.preamble = b"\x00" * 128
        ds.PatientName = "Foo"
        ds._is_little_endian = True

        # Big endian
        fp = DicomBytesIO()
        ds.save_as(fp, implicit_vr=False, little_endian=False)
        fp.seek(0)
        ds = dcmread(fp)
        assert not ds.original_encoding[1]

        # Little endian
        ds._read_little = None
        fp = DicomBytesIO()
        ds.save_as(fp, implicit_vr=False, little_endian=True)
        fp.seek(0)
        ds = dcmread(fp)
        assert ds.original_encoding[1]

    def test_priority_attr(self):
        """Test priority of dataset attrs over original."""
        ds = get_testdata_file("CT_small.dcm", read=True)
        del ds.file_meta
        assert not ds.original_encoding[0]

        # Explicit -> implicit
        fp = DicomBytesIO()
        ds._is_implicit_VR = True
        ds.save_as(fp)
        fp.seek(0)
        ds = dcmread(fp)
        assert ds.original_encoding == (True, True)

        # Implicit -> explicit
        fp = DicomBytesIO()
        ds._is_implicit_VR = False
        ds.save_as(fp)
        fp.seek(0)
        ds = dcmread(fp)
        assert ds.original_encoding == (False, True)

    def test_write_like_original(self):
        ds = Dataset()
        ds.SOPClassUID = "1.2.3"
        ds.SOPInstanceUID = "1.2.3.4"
        msg = (
            "'write_like_original' is deprecated and will be removed in v4.0, "
            "please use 'enforce_file_format' instead"
        )

        # Test kwarg - not enforce_file_format
        with pytest.warns(DeprecationWarning, match=msg):
            ds.save_as(DicomBytesIO(), write_like_original=False, implicit_vr=True)

        # Test default - not enforce_file_format
        ds.save_as(DicomBytesIO(), implicit_vr=True)

    def test_save_as_compressed_no_encaps(self):
        """Test saving a compressed dataset with no encapsulation."""
        fp = DicomBytesIO()
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = JPEGBaseline8Bit
        ds.PixelData = b"\x00\x01\x02\x03\x04\x05\x06"
        ds["PixelData"].VR = "OB"
        msg = (
            r"The \(7FE0,0010\) 'Pixel Data' element value hasn't been encapsulated "
            "as required for a compressed transfer syntax - see pydicom.encaps."
            r"encapsulate\(\) for more information"
        )
        with pytest.raises(ValueError, match=msg):
            ds.save_as(fp)

    def test_save_as_compressed_encaps(self):
        """Test saving a compressed dataset with encapsulation."""
        fp = DicomBytesIO()
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = JPEGBaseline8Bit
        ds.PixelData = encapsulate([b"\x00\x01\x02\x03\x04\x05\x06"])
        ds["PixelData"].VR = "OB"
        ds.save_as(fp)

    def test_save_as_no_pixel_data(self):
        """Test saving with no Pixel Data."""
        fp = DicomBytesIO()
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = JPEGBaseline8Bit
        ds.save_as(fp)

    def test_save_as_no_file_meta(self):
        """Test saving with no Transfer Syntax or file_meta."""
        fp = DicomBytesIO()
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.save_as(fp, implicit_vr=False)

        del ds.file_meta
        ds.save_as(fp, implicit_vr=False)

    def test_save_as_private_transfer_syntax(self):
        """Test saving with a private transfer syntax."""
        fp = DicomBytesIO()
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = "1.2.3.4.5.6"

        msg = (
            "The 'implicit_vr' and 'little_endian' arguments are required "
            "when using a private transfer syntax"
        )
        with pytest.raises(ValueError, match=msg):
            ds.save_as(fp)

        ds.save_as(fp, implicit_vr=False)

    def test_save_as_set_little_implicit_with_tsyntax(self):
        """Test setting is_implicit_VR and is_little_endian from tsyntax"""
        ds = Dataset()
        ds.PatientName = "CITIZEN"
        msg = (
            "Unable to determine the encoding to use for writing the dataset, "
            "please set the file meta's Transfer Syntax UID or use the "
            "'implicit_vr' and 'little_endian' arguments"
        )
        with pytest.raises(ValueError, match=msg):
            ds.save_as(DicomBytesIO())

        # Test public transfer syntax OK
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
        ds.save_as(DicomBytesIO())

    def test_save_as_undefined(self):
        """Test setting is_undefined_length correctly."""
        fp = DicomBytesIO()
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = JPEGBaseline8Bit
        ds.PixelData = encapsulate([b"\x00\x01\x02\x03\x04\x05\x06"])
        elem = ds["PixelData"]
        elem.VR = "OB"
        # Compressed
        # False to True
        assert not elem.is_undefined_length
        ds.save_as(fp)
        assert elem.is_undefined_length
        # True to True
        ds.save_as(fp)
        assert elem.is_undefined_length

        # Uncompressed
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        # True to False
        ds.save_as(fp)
        assert not elem.is_undefined_length
        # False to False
        ds.save_as(fp)
        assert not elem.is_undefined_length

    def test_save_as_undefined_private(self):
        """Test is_undefined_length unchanged with private tsyntax."""
        fp = DicomBytesIO()
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = "1.2.3.4.5"
        ds.PixelData = encapsulate([b"\x00\x01\x02\x03\x04\x05\x06"])
        elem = ds["PixelData"]
        elem.VR = "OB"
        # Unchanged - False
        assert not elem.is_undefined_length
        ds.save_as(fp, implicit_vr=True)
        assert not elem.is_undefined_length
        # Unchanged - True
        elem.is_undefined_length = True
        ds.save_as(fp, implicit_vr=True)
        assert elem.is_undefined_length

    def test_save_as_undefined_no_tsyntax(self):
        """Test is_undefined_length unchanged with no tsyntax."""
        fp = DicomBytesIO()
        ds = Dataset()
        ds.PixelData = encapsulate([b"\x00\x01\x02\x03\x04\x05\x06"])
        elem = ds["PixelData"]
        elem.VR = "OB"
        # Unchanged - False
        assert not elem.is_undefined_length
        ds.save_as(fp, implicit_vr=False)
        assert not elem.is_undefined_length
        # Unchanged - True
        elem.is_undefined_length = True
        ds.save_as(fp, implicit_vr=False)
        assert elem.is_undefined_length

    def test_convert_big_little_endian_raises(self):
        """Test conversion between big <-> little endian raises exception"""
        ds = Dataset()
        ds._read_implicit = True
        msg = (
            r"'Dataset.save_as\(\)' cannot be used to "
            r"convert between little and big endian encoding. Please "
            r"read the documentation for filewriter.dcmwrite\(\) "
            r"if this is what you really want to do"
        )

        # Test using is_little_endian
        ds._is_implicit_VR = True
        ds._is_little_endian = True
        ds._read_little = False
        with pytest.raises(ValueError, match=msg):
            ds.save_as(DicomBytesIO())

        ds._read_little = True
        ds._is_little_endian = False
        with pytest.raises(ValueError, match=msg):
            ds.save_as(DicomBytesIO())

        # Test using args
        with pytest.raises(ValueError, match=msg):
            ds.save_as(DicomBytesIO(), implicit_vr=True, little_endian=False)

        ds._read_little = False
        with pytest.raises(ValueError, match=msg):
            ds.save_as(DicomBytesIO(), implicit_vr=True, little_endian=True)

        # Test using transfer syntax
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        with pytest.raises(ValueError, match=msg):
            ds.save_as(DicomBytesIO())

        ds._read_little = True
        ds.file_meta.TransferSyntaxUID = ExplicitVRBigEndian
        with pytest.raises(ValueError, match=msg):
            ds.save_as(DicomBytesIO())

    def test_overwrite(self):
        """Test the overwrite argument"""
        ds = dcmread(get_testdata_file("MR_small.dcm"))
        patient_name = ds.PatientName

        with tempfile.TemporaryDirectory() as tdir:
            p = Path(tdir) / "foo.dcm"
            p.touch()

            assert p.exists()

            msg = r"File exists: '(.*)foo.dcm'"
            with pytest.raises(FileExistsError, match=msg):
                ds.save_as(p, overwrite=False)

            ds.save_as(p, overwrite=True)
            assert dcmread(p).PatientName == patient_name


class TestDatasetElements:
    """Test valid assignments of data elements"""

    def setup_method(self):
        self.ds = Dataset()
        self.sub_ds1 = Dataset()
        self.sub_ds2 = Dataset()

    def test_sequence_assignment(self):
        """Assignment to SQ works only if valid Sequence assigned."""
        msg = r"Sequence contents must be 'Dataset' instances"
        with pytest.raises(TypeError, match=msg):
            self.ds.ConceptCodeSequence = [1, 2, 3]

        # check also that assigning proper sequence *does* work
        self.ds.ConceptCodeSequence = [self.sub_ds1, self.sub_ds2]
        assert isinstance(self.ds.ConceptCodeSequence, Sequence)

    def test_formatted_DS_assignment(self):
        """Assigning an auto-formatted decimal string works as expected."""
        ds = pydicom.Dataset()
        ds.PatientWeight = DS(math.pi, auto_format=True)
        assert ds.PatientWeight.auto_format
        # Check correct 16-character string representation
        assert str(ds.PatientWeight) == "3.14159265358979"

    def test_ensure_file_meta(self):
        assert not hasattr(self.ds, "file_meta")
        self.ds.ensure_file_meta()
        assert hasattr(self.ds, "file_meta")
        assert not self.ds.file_meta

    def test_validate_and_correct_file_meta(self):
        file_meta = FileMetaDataset()
        validate_file_meta(file_meta, enforce_standard=False)
        with pytest.raises(AttributeError):
            validate_file_meta(file_meta, enforce_standard=True)

        file_meta = Dataset()  # not FileMetaDataset for bkwds-compat checks
        file_meta.PatientID = "PatientID"
        for enforce_standard in (True, False):
            with pytest.raises(
                ValueError,
                match=r"Only File Meta Information group "
                r"\(0002,eeee\) elements may be present .*",
            ):
                validate_file_meta(file_meta, enforce_standard=enforce_standard)

        file_meta = FileMetaDataset()
        file_meta.MediaStorageSOPClassUID = "1.2.3"
        file_meta.MediaStorageSOPInstanceUID = "1.2.4"
        # still missing TransferSyntaxUID
        with pytest.raises(AttributeError):
            validate_file_meta(file_meta, enforce_standard=True)

        file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        validate_file_meta(file_meta, enforce_standard=True)

        # check the default created values
        assert b"\x00\x01" == file_meta.FileMetaInformationVersion
        assert PYDICOM_IMPLEMENTATION_UID == file_meta.ImplementationClassUID
        assert file_meta.ImplementationVersionName.startswith("PYDICOM ")

        file_meta.ImplementationClassUID = "1.2.3.4"
        file_meta.ImplementationVersionName = "ACME LTD"
        validate_file_meta(file_meta, enforce_standard=True)
        # check that existing values are left alone
        assert "1.2.3.4" == file_meta.ImplementationClassUID
        assert "ACME LTD" == file_meta.ImplementationVersionName


class TestFileDataset:
    def setup_method(self):
        self.test_file = get_testdata_file("CT_small.dcm")

    def test_pickle_raw_data(self):
        ds = pydicom.dcmread(self.test_file)
        s = pickle.dumps({"ds": ds})
        ds1 = pickle.loads(s)["ds"]
        assert ds == ds1
        assert ds1.Modality == "CT"

    def test_pickle_data_elements(self):
        ds = pydicom.dcmread(self.test_file)
        for e in ds:
            # make sure all data elements have been loaded
            pass
        s = pickle.dumps({"ds": ds})
        ds1 = pickle.loads(s)["ds"]
        assert ds == ds1

    def test_pickle_nested_sequence(self):
        ds = pydicom.dcmread(get_testdata_file("nested_priv_SQ.dcm"))
        for e in ds:
            # make sure all data elements have been loaded
            pass
        s = pickle.dumps({"ds": ds})
        ds1 = pickle.loads(s)["ds"]
        assert ds == ds1

    def test_pickle_modified(self):
        """Test pickling a modified dataset."""
        ds = pydicom.dcmread(self.test_file)
        ds.PixelSpacing = [1.0, 1.0]
        s = pickle.dumps({"ds": ds})
        ds1 = pickle.loads(s)["ds"]
        assert ds == ds1
        assert ds1.PixelSpacing == [1.0, 1.0]

        ds1.PixelSpacing.insert(1, 2)
        assert [1, 2, 1] == ds1.PixelSpacing

    def test_equality_file_meta(self):
        """Dataset: equality ignores metadata"""
        d = dcmread(self.test_file)
        e = dcmread(self.test_file)
        assert d == e

        e._read_implicit = not e._read_implicit
        assert d == e

        e._read_implicit = not e._read_implicit
        assert d == e
        e._read_little = not e._read_little
        assert d == e

        e._read_little = not e._read_little
        assert d == e
        e.filename = "test_filename.dcm"
        assert d == e

    def test_creation_with_container(self):
        """FileDataset.__init__ works OK with a container such as gzip"""

        class Dummy:
            filename = "/some/path/to/test"

        ds = Dataset()
        ds.PatientName = "CITIZEN^Jan"
        fds = FileDataset(Dummy(), ds)
        assert "/some/path/to/test" == fds.filename

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_with_array(self):
        """Test Dataset within a numpy array"""
        ds = get_testdata_file("CT_small.dcm", read=True)
        arr = numpy.array([ds])
        assert arr[0].PatientName == ds.PatientName
        assert arr.dtype == object
        assert arr.shape == (1,)
        assert arr.flags.writeable

        arr[0].PatientName = "Citizen^Jan"
        assert arr[0].PatientName == "Citizen^Jan"
        assert "BeamSequence" not in arr[0]
        arr[0].BeamSequence = []
        assert arr[0].BeamSequence == []

        elem = arr[0]["PatientID"]
        assert isinstance(elem, DataElement)

        b = DicomBytesIO()
        arr[0].save_as(b)
        b.seek(0)

        out = dcmread(b)
        assert out == arr[0]

    def test_dataset_overrides_all_dict_attributes(self):
        """Ensure that we don't use inherited dict functionality"""
        ds = Dataset()
        di = dict()
        expected_diff = {
            "fromkeys",
            "__reversed__",
            "__ror__",
            "__ior__",
            "__or__",
            "__class_getitem__",
        }
        if "PyPy" in python_implementation():
            # __ror__ missing in <= 3.10.13
            if "__ror__" not in dir(dict):
                expected_diff.remove("__ror__")

        assert expected_diff == set(dir(di)) - set(dir(ds))

    def test_copy_filelike_open(self):
        f = open(get_testdata_file("CT_small.dcm"), "rb")
        ds = pydicom.dcmread(f)
        assert not f.closed

        ds_copy = copy.copy(ds)
        assert ds.PatientName == ds_copy.PatientName
        assert ds.filename.endswith("CT_small.dcm")
        assert ds.buffer is None
        assert ds_copy.filename.endswith("CT_small.dcm")
        assert ds_copy.buffer is None
        assert ds_copy == ds
        assert ds_copy.fileobj_type == ds.fileobj_type

        f.close()

    def test_copy_filelike_closed(self):
        f = open(get_testdata_file("CT_small.dcm"), "rb")
        ds = pydicom.dcmread(f)
        f.close()
        assert f.closed

        ds_copy = copy.copy(ds)
        assert ds.PatientName == ds_copy.PatientName
        assert ds.filename.endswith("CT_small.dcm")
        assert ds.buffer is None
        assert ds_copy.filename.endswith("CT_small.dcm")
        assert ds_copy.buffer is None
        assert ds_copy == ds
        assert ds_copy.fileobj_type == ds.fileobj_type

    def test_copy_buffer_open(self):
        with open(get_testdata_file("CT_small.dcm"), "rb") as fb:
            data = fb.read()
        buff = io.BytesIO(data)
        ds = pydicom.dcmread(buff)

        ds_copy = copy.copy(ds)
        assert ds.filename is None
        assert ds.buffer is buff
        assert ds_copy.filename is None
        assert ds_copy == ds
        # Shallow copy, the two buffers share the same object
        assert ds_copy.buffer is ds.buffer
        assert not ds.buffer.closed
        assert ds_copy.fileobj_type == ds.fileobj_type

    def test_copy_buffer_closed(self):
        with open(get_testdata_file("CT_small.dcm"), "rb") as fb:
            data = fb.read()
        buff = io.BytesIO(data)
        ds = pydicom.dcmread(buff)
        buff.close()
        assert buff.closed

        ds_copy = copy.copy(ds)
        assert ds_copy == ds

        assert ds.filename is None
        assert ds.buffer is buff
        assert ds.buffer.closed

        assert ds_copy.filename is None
        assert ds_copy.buffer is buff
        assert ds_copy.buffer.closed

        # Shallow copy, the two buffers share the same object
        assert ds_copy.buffer is ds.buffer
        assert ds_copy.fileobj_type == ds.fileobj_type

    def test_deepcopy_filelike_open(self):
        f = open(get_testdata_file("CT_small.dcm"), "rb")
        ds = pydicom.dcmread(f)
        assert not f.closed

        ds_copy = copy.deepcopy(ds)
        assert ds.PatientName == ds_copy.PatientName
        assert ds.filename.endswith("CT_small.dcm")
        assert ds.buffer is None
        assert ds_copy.filename.endswith("CT_small.dcm")
        assert ds_copy.buffer is None
        assert ds_copy == ds
        assert ds_copy.fileobj_type == ds.fileobj_type

        f.close()

    def test_deepcopy_filelike_closed(self):
        f = open(get_testdata_file("CT_small.dcm"), "rb")
        ds = pydicom.dcmread(f)
        f.close()
        assert f.closed

        ds_copy = copy.deepcopy(ds)
        assert ds.PatientName == ds_copy.PatientName
        assert ds.filename.endswith("CT_small.dcm")
        assert ds.buffer is None
        assert ds_copy.filename.endswith("CT_small.dcm")
        assert ds_copy.buffer is None
        assert ds_copy == ds
        assert ds_copy.fileobj_type == ds.fileobj_type

    def test_deepcopy_buffer_open(self):
        # regression test for #1147
        with open(get_testdata_file("CT_small.dcm"), "rb") as fb:
            data = fb.read()
        buff = io.BytesIO(data)
        ds = pydicom.dcmread(buff)
        assert not buff.closed

        ds_copy = copy.deepcopy(ds)
        assert ds_copy == ds

        assert ds.filename is None
        assert ds.buffer is buff
        assert not ds.buffer.closed

        assert ds_copy.filename is None
        assert isinstance(ds_copy.buffer, io.BytesIO)
        assert not ds_copy.buffer.closed

        # Deep copy, the two buffers should not be the same object, but equal otherwise
        assert ds.buffer is not ds_copy.buffer
        assert ds.buffer.getvalue() == ds_copy.buffer.getvalue()

    def test_deepcopy_buffer_closed(self):
        # regression test for #1147
        with open(get_testdata_file("CT_small.dcm"), "rb") as fb:
            data = fb.read()
        buff = io.BytesIO(data)
        ds = pydicom.dcmread(buff)
        buff.close()
        assert buff.closed
        msg = (
            r"The ValueError exception '(.*)' occurred trying to deepcopy the "
            "buffer-like the dataset was read from, the 'buffer' attribute will be "
            "set to 'None' in the copied object"
        )
        with pytest.warns(UserWarning, match=msg):
            ds_copy = copy.deepcopy(ds)

        assert ds_copy == ds

        # Deep copy, the two buffers should not be the same object but
        #   cannot copy a closed IOBase object
        assert ds.filename is None
        assert ds.buffer is buff
        assert ds.buffer.closed

        assert ds_copy.filename is None
        assert ds_copy.buffer is None

    def test_equality_with_different_metadata(self):
        ds = dcmread(get_testdata_file("CT_small.dcm"))
        ds2 = copy.deepcopy(ds)
        assert ds == ds2
        ds.filename = "foo.dcm"
        ds._read_implicit = not ds._read_implicit
        ds._read_little = not ds._read_little
        ds.file_meta = None
        ds.preamble = None
        assert ds == ds2

    def test_deepcopy_without_filename(self):
        """Regression test for #1571."""
        file_meta = FileMetaDataset()
        ds = FileDataset(
            filename_or_obj="", dataset={}, file_meta=file_meta, preamble=b"\0" * 128
        )
        assert ds.filename == ""
        assert ds.buffer is None

        ds2 = copy.deepcopy(ds)
        assert ds2.filename == ""
        assert ds2.buffer is None

    def test_deepcopy_dataset_subclass(self):
        """Regression test for #1813."""

        class MyDatasetSubclass(pydicom.Dataset):
            pass

        my_dataset_subclass = MyDatasetSubclass()

        ds2 = copy.deepcopy(my_dataset_subclass)
        assert ds2.__class__ is MyDatasetSubclass

    def test_deepcopy_after_update(self):
        """Regression test for #1816"""
        ds = Dataset()
        ds.BeamSequence = []

        ds2 = Dataset()
        ds2.update(ds)

        ds3 = copy.deepcopy(ds2)
        assert ds3 == ds

    def test_buffer(self):
        """Test the buffer attribute."""
        with open(get_testdata_file("CT_small.dcm"), "rb") as fb:
            buffer = io.BytesIO(fb.read())

        ds = dcmread(buffer)
        assert ds.filename is None
        assert ds.buffer is buffer
        assert ds.fileobj_type == io.BytesIO

        # Deflated datasets get inflated to a DicomBytesIO() buffer
        ds = dcmread(get_testdata_file("image_dfl.dcm"))
        assert ds.filename.endswith("image_dfl.dcm")
        assert isinstance(ds.buffer, DicomBytesIO)
        assert ds.fileobj_type == DicomBytesIO


class TestDatasetOverlayArray:
    """Tests for Dataset.overlay_array()."""

    def setup_method(self):
        """Setup the test datasets and the environment."""
        self.ds = dcmread(get_testdata_file("MR-SIEMENS-DICOM-WithOverlays.dcm"))

    @pytest.mark.skipif(HAVE_NP, reason="numpy is available")
    def test_possible_not_available(self):
        """Test with possible but not available handlers."""
        msg = r"NumPy is required for FileDataset.overlay_array\(\)"
        with pytest.raises(ImportError, match=msg):
            self.ds.overlay_array(0x6000)

    @pytest.mark.skipif(not HAVE_NP, reason="numpy is not available")
    def test_possible_available(self):
        """Test with possible and available handlers."""
        assert isinstance(self.ds.overlay_array(0x6000), numpy.ndarray)


class TestFileMeta:
    def test_type_exception(self):
        """Assigning ds.file_meta warns if not FileMetaDataset instance"""
        ds = Dataset()
        msg = "'Dataset.file_meta' must be a 'FileMetaDataset' instance"
        with pytest.raises(TypeError, match=msg):
            ds.file_meta = list()

    def test_assign_file_meta(self):
        """Test can only set group 2 elements in File Meta"""
        # FileMetaDataset accepts only group 2
        file_meta = FileMetaDataset()
        with pytest.raises(ValueError):
            file_meta.PatientID = "123"

        # No error if assign empty file meta
        ds = Dataset()
        ds.file_meta = FileMetaDataset()

        # Can assign non-empty file_meta
        ds_meta = FileMetaDataset()
        ds_meta.TransferSyntaxUID = "1.2"
        ds.file_meta = ds_meta

        # Error on assigning file meta if any non-group 2
        with pytest.raises(ValueError):
            ds_meta.PatientName = "x"

    def test_file_meta_conversion(self):
        """Test conversion to FileMetaDataset from Dataset."""
        ds = Dataset()
        meta = Dataset()
        meta.TransferSyntaxUID = "1.2"
        ds.file_meta = meta
        assert isinstance(ds.file_meta, FileMetaDataset)
        assert ds.file_meta.TransferSyntaxUID == "1.2"

        ds.file_meta = None
        meta.PatientID = "12345678"
        msg = (
            r"File meta datasets may only contain group 2 elements but the "
            r"following elements are present: \(0010,0020\)"
        )
        with pytest.raises(ValueError, match=msg):
            ds.file_meta = meta

        assert ds.file_meta is None

    def test_init_file_meta(self):
        """Check instantiation of FileMetaDataset"""
        ds_meta = Dataset()
        ds_meta.TransferSyntaxUID = "1.2"

        # Accepts with group 2
        file_meta = FileMetaDataset(ds_meta)
        assert "1.2" == file_meta.TransferSyntaxUID

        # Accepts dict
        dict_meta = {0x20010: DataElement(0x20010, "UI", "2.3")}
        file_meta = FileMetaDataset(dict_meta)
        assert "2.3" == file_meta.TransferSyntaxUID

        # Fails if not dict or Dataset
        with pytest.raises(TypeError):
            FileMetaDataset(["1", "2"])

        # Raises error if init with non-group-2
        ds_meta.PatientName = "x"
        with pytest.raises(ValueError):
            FileMetaDataset(ds_meta)

        # None can be passed, to match Dataset behavior
        FileMetaDataset(None)

    def test_set_file_meta(self):
        """Check adding items to existing FileMetaDataset"""
        file_meta = FileMetaDataset()

        # Raise error if set non-group 2
        with pytest.raises(ValueError):
            file_meta.PatientID = "1"

        # Check assigning via non-Tag
        file_meta[0x20010] = DataElement(0x20010, "UI", "2.3")

        # Check RawDataElement
        file_meta[0x20010] = RawDataElement(0x20010, "UI", 4, "1.23", 0, True, True)

    def test_del_file_meta(self):
        """Can delete the file_meta attribute"""
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        del ds.file_meta
        assert not hasattr(ds, "file_meta")

    def test_show_file_meta(self):
        orig_show = pydicom.config.show_file_meta
        pydicom.config.show_file_meta = True

        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = "1.2"
        ds.PatientName = "test"
        shown = str(ds)

        assert shown.startswith("Dataset.file_meta ---")
        assert shown.splitlines()[1].startswith("(0002,0010) Transfer Syntax UID")

        # Turn off file_meta display
        pydicom.config.show_file_meta = False
        shown = str(ds)
        assert shown.startswith("(0010,0010) Patient's Name")

        pydicom.config.show_file_meta = orig_show

    @pytest.mark.parametrize("copy_method", [Dataset.copy, copy.copy, copy.deepcopy])
    def test_copy(self, copy_method):
        ds = Dataset()
        ds.PatientName = "John^Doe"
        ds.BeamSequence = [Dataset(), Dataset(), Dataset()]
        ds.BeamSequence[0].Manufacturer = "Linac, co."
        ds.BeamSequence[1].Manufacturer = "Linac and Sons, co."
        ds.set_original_encoding(True, True, "utf-8")
        ds_copy = copy_method(ds)
        assert isinstance(ds_copy, Dataset)
        assert len(ds_copy) == 2
        assert ds_copy.PatientName == "John^Doe"
        assert ds_copy.BeamSequence[0].Manufacturer == "Linac, co."
        assert ds_copy.BeamSequence[1].Manufacturer == "Linac and Sons, co."
        if copy_method == copy.deepcopy:
            assert id(ds_copy.BeamSequence[0]) != id(ds.BeamSequence[0])
        else:
            # shallow copy
            assert id(ds_copy.BeamSequence[0]) == id(ds.BeamSequence[0])
        assert ds_copy.original_encoding == (True, True)
        assert ds_copy.original_character_set == "utf-8"

    def test_tsyntax_encoding(self):
        file_meta = FileMetaDataset()
        assert file_meta._tsyntax_encoding == (None, None)
        file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        assert file_meta._tsyntax_encoding == (True, True)
        file_meta.TransferSyntaxUID = "1.2.3.4"
        assert file_meta._tsyntax_encoding == (None, None)
        file_meta.TransferSyntaxUID = CTImageStorage
        assert file_meta._tsyntax_encoding == (None, None)


@pytest.fixture
def contains_raise():
    """Raise on invalid keys with Dataset.__contains__()"""
    original = config.INVALID_KEY_BEHAVIOR
    config.INVALID_KEY_BEHAVIOR = "RAISE"
    yield
    config.INVALID_KEY_BEHAVIOR = original


@pytest.fixture
def contains_ignore():
    """Ignore invalid keys with Dataset.__contains__()"""
    original = config.INVALID_KEY_BEHAVIOR
    config.INVALID_KEY_BEHAVIOR = "IGNORE"
    yield
    config.INVALID_KEY_BEHAVIOR = original


@pytest.fixture
def contains_warn():
    """Warn on invalid keys with Dataset.__contains__()"""
    original = config.INVALID_KEY_BEHAVIOR
    config.INVALID_KEY_BEHAVIOR = "WARN"
    yield
    config.INVALID_KEY_BEHAVIOR = original


CAMEL_CASE = (
    [  # Shouldn't warn
        "Rows",
        "_Rows",
        "Rows_",
        "rows",
        "_rows",
        "__rows",
        "rows_",
        "ro_ws",
        "rowds",
        "BitsStored",
        "bits_Stored",
        "Bits_Stored",
        "bits_stored",
        "_BitsStored",
        "BitsStored_",
        "B_itsStored",
        "BitsS_tored",
        "12LeadECG",
        "file_meta",
        "filename",
        "is_implicit_VR",
        "is_little_endian",
        "preamble",
        "timestamp",
        "fileobj_type",
        "patient_records",
        "_parent_encoding",
        "_dict",
        "is_decompressed",
        "read_encoding",
        "_private_blocks",
        "default_element_format",
        "indent_chars",
        "default_sequence_element_format",
        "PatientName",
    ],
    [  # Should warn
        "bitsStored",
        "BitSStored",
        "TwelveLeadECG",
        "SOPInstanceUId",
        "PatientsName",
        "Rowds",
    ],
)


@pytest.fixture
def setattr_raise():
    """Raise on Dataset.__setattr__() close keyword matches."""
    original = config.INVALID_KEYWORD_BEHAVIOR
    config.INVALID_KEYWORD_BEHAVIOR = "RAISE"
    yield
    config.INVALID_KEYWORD_BEHAVIOR = original


@pytest.fixture
def setattr_ignore():
    """Ignore Dataset.__setattr__() close keyword matches."""
    original = config.INVALID_KEYWORD_BEHAVIOR
    config.INVALID_KEYWORD_BEHAVIOR = "IGNORE"
    yield
    config.INVALID_KEYWORD_BEHAVIOR = original


@pytest.fixture
def setattr_warn():
    """Warn on Dataset.__setattr__() close keyword matches."""
    original = config.INVALID_KEYWORD_BEHAVIOR
    config.INVALID_KEYWORD_BEHAVIOR = "WARN"
    yield
    config.INVALID_KEYWORD_BEHAVIOR = original


def test_setattr_warns(setattr_warn):
    """ "Test warnings for Dataset.__setattr__() for close matches."""
    with assert_no_warning():
        ds = Dataset()

    deprecations = (
        "is_implicit_VR",
        "is_little_endian",
        "read_encoding",
    )

    for s in CAMEL_CASE[0]:
        if s in deprecations:
            with pytest.warns(DeprecationWarning):
                val = getattr(ds, s, None)
                setattr(ds, s, val)
        else:
            with assert_no_warning():
                val = getattr(ds, s, None)
                setattr(ds, s, val)

    for s in CAMEL_CASE[1]:
        msg = (
            r"Camel case attribute '" + s + r"' used which is not in the "
            r"element keyword data dictionary"
        )
        with pytest.warns(UserWarning, match=msg):
            val = getattr(ds, s, None)
            setattr(ds, s, None)


def test_setattr_raises(setattr_raise):
    """ "Test exceptions for Dataset.__setattr__() for close matches."""
    with assert_no_warning():
        ds = Dataset()

    deprecations = (
        "is_implicit_VR",
        "is_little_endian",
        "read_encoding",
    )

    for s in CAMEL_CASE[0]:
        if s in deprecations:
            with pytest.warns(DeprecationWarning):
                val = getattr(ds, s, None)
                setattr(ds, s, val)
        else:
            with assert_no_warning():
                val = getattr(ds, s, None)
                setattr(ds, s, val)

    for s in CAMEL_CASE[1]:
        msg = (
            r"Camel case attribute '" + s + r"' used which is not in the "
            r"element keyword data dictionary"
        )
        with pytest.raises(ValueError, match=msg):
            val = getattr(ds, s, None)
            setattr(ds, s, None)


def test_setattr_ignore(setattr_ignore):
    """Test config.INVALID_KEYWORD_BEHAVIOR = 'IGNORE'"""
    with assert_no_warning():
        ds = Dataset()

    deprecations = (
        "is_implicit_VR",
        "is_little_endian",
        "read_encoding",
    )

    for s in CAMEL_CASE[0]:
        if s in deprecations:
            with pytest.warns(DeprecationWarning):
                val = getattr(ds, s, None)
                setattr(ds, s, val)
        else:
            with assert_no_warning():
                val = getattr(ds, s, None)
                setattr(ds, s, val)

    ds = Dataset()
    for s in CAMEL_CASE[1]:
        with assert_no_warning():
            getattr(ds, s, None)
            setattr(ds, s, None)


class TestDatasetWithBufferedData:
    """Tests for datasets with buffered element values"""

    def test_pickle_bytesio(self):
        """Test pickling a dataset with buffered element value"""
        b = io.BytesIO(b"\x00\x01")
        ds = Dataset()
        ds.PixelData = b

        s = pickle.dumps({"ds": ds})
        ds1 = pickle.loads(s)["ds"]
        assert ds.PixelData is not ds1.PixelData
        assert ds == ds1

    def test_pickle_bufferedreader_raises(self):
        with tempfile.TemporaryDirectory() as tdir:
            with open(f"{tdir}/foo.bin", "wb") as f:
                f.write(b"\x00\x01\x02\x03\x04")

            with open(f"{tdir}/foo.bin", "rb") as f:
                ds = Dataset()
                ds.PixelData = f

            with pytest.raises(TypeError, match="cannot"):
                pickle.dumps({"ds": ds})

    def test_copy_bytesio(self):
        """Test copy.copy() for dataset with buffered element value"""
        b = io.BytesIO(b"\x00\x01")
        ds = Dataset()
        ds.PixelData = b
        ds2 = copy.copy(ds)
        assert isinstance(ds2.PixelData, io.BytesIO)
        assert ds2.PixelData is ds.PixelData

    def test_copy_bytesio_closed(self):
        """Test copy.copy() for dataset with buffered element value"""
        b = io.BytesIO(b"\x00\x01")
        ds = Dataset()
        ds.PixelData = b
        b.close()

        ds2 = copy.copy(ds)
        assert isinstance(ds2.PixelData, io.BytesIO)
        assert ds2.PixelData is ds.PixelData
        assert ds2.PixelData.closed

    def test_copy_bufferedreader(self):
        with tempfile.TemporaryDirectory() as tdir:
            with open(f"{tdir}/foo.bin", "wb") as f:
                f.write(b"\x00\x01\x02\x03\x04")

            with open(f"{tdir}/foo.bin", "rb") as f:
                ds = Dataset()
                ds.PixelData = f

            ds2 = copy.copy(ds)
            assert isinstance(ds2.PixelData, io.BufferedReader)
            assert ds2.PixelData is ds.PixelData

    def test_copy_bufferedreader_closed(self):
        with tempfile.TemporaryDirectory() as tdir:
            with open(f"{tdir}/foo.bin", "wb") as f:
                f.write(b"\x00\x01\x02\x03\x04")

            with open(f"{tdir}/foo.bin", "rb") as f:
                ds = Dataset()
                ds.PixelData = f

            ds.PixelData.close()

            ds2 = copy.copy(ds)
            assert isinstance(ds2.PixelData, io.BufferedReader)
            assert ds2.PixelData is ds.PixelData
            assert ds2.PixelData.closed

    def test_deepcopy_bytesio(self):
        """Test copy.deepcopy() for dataset with buffered element value"""
        b = io.BytesIO(b"\x00\x01")
        ds = Dataset()
        ds.PixelData = b

        ds2 = copy.deepcopy(ds)
        assert isinstance(ds2.PixelData, io.BytesIO)
        assert ds2.PixelData is not ds.PixelData
        assert ds2.PixelData.getvalue() == ds.PixelData.getvalue()

    def test_deepcopy_bytesio_closed(self):
        """Test copy.deepcopy() for dataset with buffered element value"""
        b = io.BytesIO(b"\x00\x01")
        ds = Dataset()
        ds.PixelData = b
        b.close()

        msg = (
            r"Error deepcopying the buffered element \(7FE0,0010\) 'Pixel Data': I/O "
            "operation on closed file"
        )
        with pytest.raises(ValueError, match=msg):
            copy.deepcopy(ds)

    def test_deepcopy_bufferedreader_raises(self):
        with tempfile.TemporaryDirectory() as tdir:
            with open(f"{tdir}/foo.bin", "wb") as f:
                f.write(b"\x00\x01\x02\x03\x04")

            with open(f"{tdir}/foo.bin", "rb") as f:
                ds = Dataset()
                ds.PixelData = f

        msg = (
            r"Error deepcopying the buffered element \(7FE0,0010\) 'Pixel Data': "
            r"cannot (.*) '_io.BufferedReader' object"
        )
        with pytest.raises(TypeError, match=msg):
            copy.deepcopy(ds)


@pytest.fixture
def use_future():
    original = config._use_future
    config._use_future = True
    yield
    config._use_future = original


class TestFuture:
    def test_save_as_write_like_original_raises(self, use_future):
        ds = Dataset()
        msg = (
            "'write_like_original' is no longer accepted as a positional or "
            "keyword argument, use 'enforce_file_format' instead"
        )
        with pytest.raises(TypeError, match=msg):
            ds.save_as(None, write_like_original=False)

    def test_save_as_endianness_conversion(self, use_future):
        ds = Dataset()
        ds._is_implicit_VR = True
        ds._is_little_endian = True

        ds._read_implicit = False
        ds._read_little = False
        ds.save_as(DicomBytesIO())

        ds._read_little = True
        ds._is_little_endian = False
        ds.save_as(DicomBytesIO())

    def test_is_original_encoding(self, use_future):
        ds = Dataset()
        ds._read_charset = ["latin_1"]
        ds.SpecificCharacterSet = "ISO_IR 100"
        assert ds.is_original_encoding
        ds.SpecificCharacterSet = "ISO_IR 192"
        assert not ds.is_original_encoding
        ds.SpecificCharacterSet = "ISO_IR 100"
        assert ds.is_original_encoding

    def test_is_little_endian_raises(self, use_future):
        ds = Dataset()
        assert not hasattr(ds, "_is_little_endian")

        msg = "'Dataset' object has no attribute 'is_little_endian'"
        with pytest.raises(AttributeError, match=msg):
            ds.is_little_endian = True

        ds._is_little_endian = True
        with pytest.raises(AttributeError, match=msg):
            ds.is_little_endian

    def test_is_implicit_VR_raises(self, use_future):
        ds = Dataset()
        assert not hasattr(ds, "_is_implicit_VR")

        msg = "'Dataset' object has no attribute 'is_implicit_VR'"
        with pytest.raises(AttributeError, match=msg):
            ds.is_implicit_VR = True

        ds._is_implicit_VR = True
        with pytest.raises(AttributeError, match=msg):
            ds.is_implicit_VR

    def test_read_encoding_raises(self, use_future):
        ds = Dataset()
        msg = "'Dataset' object has no attribute 'read_encoding'"
        with pytest.raises(AttributeError, match=msg):
            ds.read_encoding = "foo"

        ds._read_charset = "foo"
        with pytest.raises(AttributeError, match=msg):
            ds.read_encoding

    def test_read_implicit_vr_raises(self, use_future):
        ds = Dataset()
        ds._read_implicit = True
        msg = "'Dataset' object has no attribute 'read_implicit_vr'"
        with pytest.raises(AttributeError, match=msg):
            ds.read_implicit_vr

    def test_read_little_endian_raises(self, use_future):
        ds = Dataset()
        ds._read_little = True
        msg = "'Dataset' object has no attribute 'read_little_endian'"
        with pytest.raises(AttributeError, match=msg):
            ds.read_little_endian

    def test_slice(self, use_future):
        ds = Dataset()
        ds._is_little_endian = True
        ds._is_implicit_VR = True

        ds = ds[0x00080001:]
        assert not hasattr(ds, "_is_little_endian")
        assert not hasattr(ds, "_is_implicit_VR")

    def test_convert_pixel_data(self, use_future):
        msg = "'Dataset' object has no attribute 'convert_pixel_data'"
        with pytest.raises(AttributeError, match=msg):
            Dataset().convert_pixel_data()

    def test_pixel_array_options(self, use_future):
        msg = (
            r"Dataset.pixel_array_options\(\) got an unexpected "
            "keyword argument 'use_v2_backend'"
        )
        with pytest.raises(TypeError, match=msg):
            Dataset().pixel_array_options(use_v2_backend=True)

    def test_decompress(self, use_future):
        msg = (
            r"Dataset.decompress\(\) got an unexpected "
            "keyword argument 'handler_name'"
        )
        with pytest.raises(TypeError, match=msg):
            Dataset().decompress(handler_name="foo")
