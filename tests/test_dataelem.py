# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Unit tests for the pydicom.dataelem module."""

# Many tests of DataElement class are implied in test_dataset also
import copy
import datetime
import math
import io
import platform
import re
import tempfile

import pytest

from pydicom import filewriter, config, dcmread
from pydicom.charset import default_encoding
from pydicom.data import get_testdata_file
from pydicom.datadict import add_private_dict_entry
from pydicom.dataelem import (
    DataElement,
    RawDataElement,
    convert_raw_data_element,
)
from pydicom.dataset import Dataset
from pydicom.errors import BytesLengthException
from pydicom.filebase import DicomBytesIO
from pydicom.fileutil import read_buffer
from pydicom.hooks import (
    hooks,
    raw_element_value_retry,
    raw_element_value_fix_separator,
)
from pydicom.multival import MultiValue
from pydicom.tag import Tag, BaseTag
from .test_util import save_private_dict
from pydicom.uid import UID
from pydicom.valuerep import BUFFERABLE_VRS, DSfloat, validate_value


IS_WINDOWS = platform.system() == "Windows"


class TestDataElement:
    """Tests for dataelem.DataElement."""

    @pytest.fixture(autouse=True)
    def create_data(self, disable_value_validation):
        self.data_elementSH = DataElement((1, 2), "SH", "hello")
        self.data_elementIS = DataElement((1, 2), "IS", "42")
        self.data_elementDS = DataElement((1, 2), "DS", "42.00001")
        self.data_elementMulti = DataElement((1, 2), "DS", ["42.1", "42.2", "42.3"])
        self.data_elementCommand = DataElement(0x00000000, "UL", 100)
        self.data_elementPrivate = DataElement(0x00090000, "UL", 101)
        self.data_elementRetired = DataElement(0x00080010, "SH", "102")
        config.use_none_as_empty_text_VR_value = False
        yield
        config.use_none_as_empty_text_VR_value = False

    @pytest.fixture
    def replace_un_with_known_vr(self):
        old_value = config.replace_un_with_known_vr
        config.replace_un_with_known_vr = True
        yield
        config.replace_un_with_known_vr = old_value

    def test_AT(self):
        """VR of AT takes Tag variants when set"""
        elem1 = DataElement("OffendingElement", "AT", 0x100010)
        elem2 = DataElement("OffendingElement", "AT", (0x10, 0x10))
        elem3 = DataElement("FrameIncrementPointer", "AT", [0x540010, 0x540020])
        elem4 = DataElement("OffendingElement", "AT", "PatientName")
        assert isinstance(elem1.value, BaseTag)
        assert isinstance(elem2.value, BaseTag)
        assert elem1.value == elem2.value == elem4.value
        assert elem1.value == 0x100010
        assert isinstance(elem3.value, MultiValue)
        assert len(elem3.value) == 2

        # Test also using Dataset, and check 0x00000000 works
        ds = Dataset()
        ds.OffendingElement = 0
        assert isinstance(ds.OffendingElement, BaseTag)
        ds.OffendingElement = (0x0000, 0x0000)
        assert isinstance(ds.OffendingElement, BaseTag)
        assert ds.OffendingElement == 0

        # An invalid Tag should throw an error
        with pytest.raises(OverflowError):
            _ = DataElement("OffendingElement", "AT", 0x100000000)

    def test_VM_1(self):
        """DataElement: return correct value multiplicity for VM > 1"""
        assert 3 == self.data_elementMulti.VM

    def test_VM_2(self):
        """DataElement: return correct value multiplicity for VM = 1"""
        assert 1 == self.data_elementIS.VM

    def test_DSFloat_conversion(self):
        """Test that strings are correctly converted if changing the value."""
        assert isinstance(self.data_elementDS.value, DSfloat)
        assert isinstance(self.data_elementMulti.value[0], DSfloat)
        assert DSfloat("42.1") == self.data_elementMulti.value[0]

        # multi-value append/insert
        self.data_elementMulti.value.append("42.4")
        assert isinstance(self.data_elementMulti.value[3], DSfloat)
        assert DSfloat("42.4") == self.data_elementMulti.value[3]

        self.data_elementMulti.value.insert(0, "42.0")
        assert isinstance(self.data_elementMulti.value[0], DSfloat)
        assert DSfloat("42.0") == self.data_elementMulti.value[0]

        # change single value of multi-value
        self.data_elementMulti.value[3] = "123.4"
        assert isinstance(self.data_elementMulti.value[3], DSfloat)
        assert DSfloat("123.4") == self.data_elementMulti.value[3]

    def test_DSFloat_conversion_auto_format(self):
        """Test that strings are being auto-formatted correctly."""
        data_element = DataElement((1, 2), "DS", DSfloat(math.pi, auto_format=True))
        assert math.pi == data_element.value
        assert "3.14159265358979" == str(data_element.value)

    def test_backslash(self):
        """DataElement: String with '\\' sets multi-valued data_element."""
        data_element = DataElement((1, 2), "DS", r"42.1\42.2\42.3")
        assert 3 == data_element.VM

    def test_UID(self):
        """DataElement: setting or changing UID results in UID type."""
        ds = Dataset()
        ds.TransferSyntaxUID = "1.2.3"
        assert isinstance(ds.TransferSyntaxUID, UID)
        ds.TransferSyntaxUID += ".4.5.6"
        assert isinstance(ds.TransferSyntaxUID, UID)

    def test_keyword(self):
        """DataElement: return correct keyword"""
        assert "CommandGroupLength" == self.data_elementCommand.keyword
        assert "" == self.data_elementPrivate.keyword

    def test_retired(self):
        """DataElement: return correct is_retired"""
        assert self.data_elementCommand.is_retired is False
        assert self.data_elementRetired.is_retired is True
        assert self.data_elementPrivate.is_retired is False

    def test_name_group_length(self):
        """Test DataElement.name for Group Length element"""
        elem = DataElement(0x00100000, "LO", 12345)
        assert "Group Length" == elem.name

    def test_name_unknown_private(self):
        """Test DataElement.name with an unknown private element"""
        elem = DataElement(0x00110010, "LO", 12345)
        elem.private_creator = "TEST"
        assert "Private tag data" == elem.name
        elem = DataElement(0x00110F00, "LO", 12345)
        assert elem.tag.is_private
        assert elem.private_creator is None
        assert "Private tag data" == elem.name

    def test_name_unknown(self):
        """Test DataElement.name with an unknown element"""
        elem = DataElement(0x00000004, "LO", 12345)
        assert "" == elem.name

    def test_equality_standard_element(self):
        """DataElement: equality returns correct value for simple elements"""
        dd = DataElement(0x00100010, "PN", "ANON")
        assert dd == dd  # noqa: PLR0124 Need to check equality with self
        ee = DataElement(0x00100010, "PN", "ANON")
        assert dd == ee

        # Check value
        ee.value = "ANAN"
        assert not dd == ee

        # Check tag
        ee = DataElement(0x00100011, "PN", "ANON")
        assert not dd == ee

        # Check VR
        ee = DataElement(0x00100010, "SH", "ANON")
        assert not dd == ee

        dd = DataElement(0x00080018, "UI", "1.2.3.4")
        ee = DataElement(0x00080018, "UI", "1.2.3.4")
        assert dd == ee

        ee = DataElement(0x00080018, "PN", "1.2.3.4")
        assert not dd == ee

    def test_equality_private_element(self):
        """DataElement: equality returns correct value for private elements"""
        dd = DataElement(0x01110001, "PN", "ANON")
        assert dd == dd  # noqa: PLR0124 Need to check equality with self
        ee = DataElement(0x01110001, "PN", "ANON")
        assert dd == ee

        # Check value
        ee.value = "ANAN"
        assert not dd == ee

        # Check tag
        ee = DataElement(0x01110002, "PN", "ANON")
        assert not dd == ee

        # Check VR
        ee = DataElement(0x01110001, "SH", "ANON")
        assert not dd == ee

    def test_equality_sequence_element(self):
        """DataElement: equality returns correct value for sequence elements"""
        dd = DataElement(0x300A00B0, "SQ", [])
        assert dd == dd  # noqa: PLR0124 Need to check equality with self
        ee = DataElement(0x300A00B0, "SQ", [])
        assert dd == ee

        # Check value
        e = Dataset()
        e.PatientName = "ANON"
        ee.value = [e]
        assert not dd == ee

        # Check tag
        ee = DataElement(0x01110002, "SQ", [])
        assert not dd == ee

        # Check VR
        ee = DataElement(0x300A00B0, "SH", [])
        assert not dd == ee

        # Check with dataset
        dd = DataElement(0x300A00B0, "SQ", [Dataset()])
        dd.value[0].PatientName = "ANON"
        ee = DataElement(0x300A00B0, "SQ", [Dataset()])
        ee.value[0].PatientName = "ANON"
        assert dd == ee

        # Check uneven sequences
        dd.value.append(Dataset())
        dd.value[1].PatientName = "ANON"
        assert not dd == ee

        ee.value.append(Dataset())
        ee.value[1].PatientName = "ANON"
        assert dd == ee
        ee.value.append(Dataset())
        ee.value[2].PatientName = "ANON"
        assert not dd == ee

    def test_equality_not_rlement(self):
        """DataElement: equality returns correct value when not same class"""
        dd = DataElement(0x00100010, "PN", "ANON")
        ee = {"0x00100010": "ANON"}
        assert not dd == ee

    def test_equality_inheritance(self):
        """DataElement: equality returns correct value for subclasses"""

        class DataElementPlus(DataElement):
            pass

        dd = DataElement(0x00100010, "PN", "ANON")
        ee = DataElementPlus(0x00100010, "PN", "ANON")
        assert ee == ee  # noqa: PLR0124 Need to check equality with self
        assert dd == ee
        assert ee == dd

        ee = DataElementPlus(0x00100010, "PN", "ANONY")
        assert not dd == ee
        assert not ee == dd

    def test_equality_class_members(self):
        """Test equality is correct when ignored class members differ."""
        dd = DataElement(0x00100010, "PN", "ANON")
        dd.showVR = False
        dd.file_tell = 10
        dd.maxBytesToDisplay = 0
        dd.descripWidth = 0
        assert DataElement(0x00100010, "PN", "ANON") == dd

    def test_inequality_standard(self):
        """Test DataElement.__ne__ for standard element"""
        dd = DataElement(0x00100010, "PN", "ANON")
        assert not dd != dd  # noqa: PLR0124 Need to check inequality with self
        assert DataElement(0x00100010, "PN", "ANONA") != dd

        # Check tag
        assert DataElement(0x00100011, "PN", "ANON") != dd

        # Check VR
        assert DataElement(0x00100010, "SH", "ANON") != dd

    def test_inequality_sequence(self):
        """Test DataElement.__ne__ for sequence element"""
        dd = DataElement(0x300A00B0, "SQ", [])
        assert not dd != dd  # noqa: PLR0124 Need to check inequality with self
        assert not DataElement(0x300A00B0, "SQ", []) != dd
        ee = DataElement(0x300A00B0, "SQ", [Dataset()])
        assert ee != dd

        # Check value
        dd.value = [Dataset()]
        dd[0].PatientName = "ANON"
        ee[0].PatientName = "ANON"
        assert not ee != dd
        ee[0].PatientName = "ANONA"
        assert ee != dd

    def test_hash(self):
        """Test hash(DataElement) raises TypeError"""
        with pytest.raises(TypeError, match=r"unhashable"):
            hash(DataElement(0x00100010, "PN", "ANON"))

    def test_repeater_str(self):
        """Test a repeater group element displays the element name."""
        elem = DataElement(0x60023000, "OB", b"\x00")
        assert "Overlay Data" in elem.__str__()

    def test_str_no_vr(self):
        """Test DataElement.__str__ output with no VR"""
        elem = DataElement(0x00100010, "PN", "ANON")
        assert "(0010,0010) Patient's Name" in str(elem)
        assert "PN: 'ANON'" in str(elem)
        elem.showVR = False
        assert "(0010,0010) Patient's Name" in str(elem)
        assert "PN" not in str(elem)

    def test_repr_seq(self):
        """Test DataElement.__repr__ with a sequence"""
        elem = DataElement(0x300A00B0, "SQ", [Dataset()])
        elem[0].PatientID = "1234"
        assert repr(elem) == str(elem)

    def test_getitem_raises(self):
        """Test DataElement.__getitem__ raise if value not indexable"""
        elem = DataElement(0x00100010, "US", 123)
        with pytest.raises(TypeError):
            elem[0]

    def test_repval_large_elem(self):
        """Test DataElement.repval doesn't return a huge string for a large
        value"""
        elem = DataElement(0x00820003, "UT", "a" * 1000)
        assert len(elem.repval) < 100

    def test_repval_large_vm(self):
        """Test DataElement.repval doesn't return a huge string for a large
        vm"""
        elem = DataElement(0x00080054, "AE", "a\\" * 1000 + "a")
        assert len(elem.repval) < 100

    def test_repval_strange_type(self):
        """Test DataElement.repval doesn't break with bad types"""
        elem = DataElement(0x00020001, "OB", 0)
        assert len(elem.repval) < 100

    def test_private_tag_in_repeater_range(self):
        """Test that an unknown private tag (e.g. a tag not in the private
        dictionary) in the repeater range is not handled as a repeater tag
        if using Implicit Little Endian transfer syntax."""
        # regression test for #689
        ds = Dataset()
        ds[0x50F10010] = RawDataElement(
            Tag(0x50F10010), None, 8, b"FDMS 1.0", 0, True, True
        )
        ds[0x50F1100A] = RawDataElement(
            Tag(0x50F1100A), None, 6, b"ACC0.6", 0, True, True
        )
        private_creator_data_elem = ds[0x50F10010]
        assert "Private Creator" == private_creator_data_elem.name
        assert "LO" == private_creator_data_elem.VR

        private_data_elem = ds[0x50F1100A]
        assert "[FNC Parameters]" == private_data_elem.name
        assert "SH" == private_data_elem.VR

    def test_private_repeater_tag(self):
        """Test that a known private tag in the repeater range is correctly
        handled using Implicit Little Endian transfer syntax."""
        ds = Dataset()
        ds[0x60210012] = RawDataElement(
            Tag(0x60210012), None, 12, b"PAPYRUS 3.0 ", 0, True, True
        )
        ds[0x60211200] = RawDataElement(
            Tag(0x60211200), None, 6, b"123456", 0, True, True
        )
        private_creator_data_elem = ds[0x60210012]
        assert "Private Creator" == private_creator_data_elem.name
        assert "LO" == private_creator_data_elem.VR

        private_data_elem = ds[0x60211200]
        assert "[Overlay ID]" == private_data_elem.name
        assert "IS" == private_data_elem.VR

    def test_known_tags_with_UN_VR(self, replace_un_with_known_vr):
        """Known tags with VR UN are correctly decoded."""
        ds = Dataset()
        ds[0x00080005] = DataElement(0x00080005, "UN", b"ISO_IR 126")
        ds[0x00100010] = DataElement(0x00100010, "UN", "Διονυσιος".encode("iso_ir_126"))
        ds.decode()
        assert "CS" == ds[0x00080005].VR
        assert "PN" == ds[0x00100010].VR
        assert "Διονυσιος" == ds[0x00100010].value

        ds = Dataset()
        ds[0x00080005] = DataElement(
            0x00080005, "UN", b"ISO 2022 IR 100\\ISO 2022 IR 126"
        )
        ds[0x00100010] = DataElement(
            0x00100010,
            "UN",
            b"Dionysios=\x1b\x2d\x46" + "Διονυσιος".encode("iso_ir_126"),
        )
        ds.decode()
        assert "CS" == ds[0x00080005].VR
        assert "PN" == ds[0x00100010].VR
        assert "Dionysios=Διονυσιος" == ds[0x00100010].value

    def test_reading_ds_with_known_tags_with_UN_VR(self, replace_un_with_known_vr):
        """Known tags with VR UN are correctly read."""
        test_file = get_testdata_file("explicit_VR-UN.dcm")
        ds = dcmread(test_file)
        assert "CS" == ds[0x00080005].VR
        assert "TM" == ds[0x00080030].VR
        assert "PN" == ds[0x00100010].VR
        assert "PN" == ds[0x00100010].VR
        assert "DA" == ds[0x00100030].VR

    def test_unknown_tags_with_UN_VR(self):
        """Unknown tags with VR UN are not decoded."""
        ds = Dataset()
        ds[0x00080005] = DataElement(0x00080005, "CS", b"ISO_IR 126")
        ds[0x00111010] = DataElement(0x00111010, "UN", "Διονυσιος".encode("iso_ir_126"))
        ds.decode()
        assert "UN" == ds[0x00111010].VR
        assert "Διονυσιος".encode("iso_ir_126") == ds[0x00111010].value

    def test_tag_with_long_value_UN_VR(self):
        """Tag with length > 64kb with VR UN is not changed."""
        ds = Dataset()
        ds[0x00080005] = DataElement(0x00080005, "CS", b"ISO_IR 126")

        single_value = b"123456.789012345"
        large_value = b"\\".join([single_value] * 4500)
        ds[0x30040058] = DataElement(
            0x30040058, "UN", large_value, is_undefined_length=False
        )
        ds.decode()
        assert "UN" == ds[0x30040058].VR

    @pytest.mark.parametrize("use_none, empty_value", ((True, None), (False, "")))
    def test_empty_text_values(self, use_none, empty_value, no_datetime_conversion):
        """Test that assigning an empty value behaves as expected."""

        def check_empty_text_element(value):
            setattr(ds, tag_name, value)
            elem = ds[tag_name]
            assert bool(elem.value) is False
            assert 0 == elem.VM
            assert elem.value == value
            fp = DicomBytesIO()
            fp.is_implicit_VR = True
            fp.is_little_endian = True
            filewriter.write_dataset(fp, ds)
            ds_read = dcmread(fp, force=True)
            assert empty_value == ds_read[tag_name].value

        text_vrs = {
            "AE": "RetrieveAETitle",
            "AS": "PatientAge",
            "CS": "QualityControlSubject",
            "DA": "PatientBirthDate",
            "DT": "AcquisitionDateTime",
            "LO": "DataSetSubtype",
            "LT": "ExtendedCodeMeaning",
            "PN": "PatientName",
            "SH": "CodeValue",
            "ST": "InstitutionAddress",
            "TM": "StudyTime",
            "UC": "LongCodeValue",
            "UI": "SOPClassUID",
            "UR": "CodingSchemeURL",
            "UT": "StrainAdditionalInformation",
        }
        config.use_none_as_empty_text_VR_value = use_none
        ds = Dataset()
        # set value to new element
        for tag_name in text_vrs.values():
            check_empty_text_element(None)
            del ds[tag_name]
            check_empty_text_element("")
            del ds[tag_name]
            check_empty_text_element([])
            del ds[tag_name]

        # set value to existing element
        for tag_name in text_vrs.values():
            check_empty_text_element(None)
            check_empty_text_element("")
            check_empty_text_element([])
            check_empty_text_element(None)

    def test_empty_binary_values(self):
        """Test that assigning an empty value behaves as expected for
        non-text VRs."""

        def check_empty_binary_element(value):
            setattr(ds, tag_name, value)
            elem = ds[tag_name]
            assert bool(elem.value) is False
            assert 0 == elem.VM
            assert elem.value == value
            fp = DicomBytesIO()
            fp.is_implicit_VR = True
            fp.is_little_endian = True
            filewriter.write_dataset(fp, ds)
            ds_read = dcmread(fp, force=True)
            assert ds_read[tag_name].value is None

        non_text_vrs = {
            "AT": "OffendingElement",
            "DS": "PatientWeight",
            "IS": "BeamNumber",
            "SL": "RationalNumeratorValue",
            "SS": "SelectorSSValue",
            "UL": "SimpleFrameList",
            "US": "SourceAcquisitionBeamNumber",
            "FD": "RealWorldValueLUTData",
            "FL": "VectorAccuracy",
            "OB": "FillPattern",
            "OD": "DoubleFloatPixelData",
            "OF": "UValueData",
            "OL": "TrackPointIndexList",
            "OW": "TrianglePointIndexList",
            "UN": "SelectorUNValue",
        }
        ds = Dataset()
        # set value to new element
        for tag_name in non_text_vrs.values():
            check_empty_binary_element(None)
            del ds[tag_name]
            check_empty_binary_element([])
            del ds[tag_name]
            check_empty_binary_element(MultiValue(int, []))
            del ds[tag_name]

        # set value to existing element
        for tag_name in non_text_vrs.values():
            check_empty_binary_element(None)
            check_empty_binary_element([])
            check_empty_binary_element(MultiValue(int, []))
            check_empty_binary_element(None)

    def test_empty_sequence_is_handled_as_array(self):
        ds = Dataset()
        ds.AcquisitionContextSequence = []
        elem = ds["AcquisitionContextSequence"]
        assert bool(elem.value) is False
        assert elem.value == []

        fp = DicomBytesIO()
        fp.is_implicit_VR = True
        fp.is_little_endian = True
        filewriter.write_dataset(fp, ds)
        ds_read = dcmread(fp, force=True)
        elem = ds_read["AcquisitionContextSequence"]
        assert elem.value == []

    def test_is_private(self):
        """Test the is_private property."""
        elem = DataElement(0x00090010, "UN", None)
        assert elem.is_private
        elem = DataElement(0x00080010, "UN", None)
        assert not elem.is_private

    def test_is_empty_sequence(self):
        """Test DataElement.is_empty for SQ."""
        elem = DataElement(0x300A00B0, "SQ", [])
        assert elem.VR == "SQ"
        assert len(elem.value) == 0
        assert elem.is_empty
        elem.value = [Dataset()]
        assert len(elem.value) == 1
        assert not elem.is_empty

    def test_vm_sequence(self):
        """Test DataElement.VM for SQ."""
        elem = DataElement(0x300A00B0, "SQ", [])
        assert not elem.is_buffered
        assert elem.VR == "SQ"
        assert len(elem.value) == 0
        assert elem.VM == 1
        elem.value = [Dataset(), Dataset()]
        assert len(elem.value) == 2
        assert elem.VM == 1


class TestRawDataElement:
    """Tests for dataelem.RawDataElement."""

    def test_invalid_tag_warning(self, allow_reading_invalid_values):
        """RawDataElement: conversion of unknown tag warns..."""
        raw = RawDataElement(Tag(0x88880088), None, 4, b"unknown", 0, True, True)

        with pytest.warns(UserWarning, match=r"\(8888,0088\)"):
            element = convert_raw_data_element(raw)
            assert element.VR == "UN"

    def test_key_error(self, enforce_valid_values):
        """RawDataElement: conversion of unknown tag throws KeyError..."""
        # raw data element -> tag VR length value
        #                       value_tell is_implicit_VR is_little_endian'
        # Unknown (not in DICOM dict), non-private, non-group 0 for this test
        raw = RawDataElement(Tag(0x88880002), None, 4, b"unknown", 0, True, True)

        msg = r"VR lookup failed for the raw element with tag \(8888,0002\)"
        with pytest.raises(KeyError, match=msg):
            convert_raw_data_element(raw)

    def test_valid_tag(self, no_datetime_conversion):
        """RawDataElement: conversion of known tag succeeds..."""
        raw = RawDataElement(Tag(0x00080020), "DA", 8, b"20170101", 0, False, True)
        element = convert_raw_data_element(raw, encoding=default_encoding)
        assert "Study Date" == element.name
        assert "DA" == element.VR
        assert "20170101" == element.value

        raw = RawDataElement(
            Tag(0x00080000), None, 4, b"\x02\x00\x00\x00", 0, True, True
        )
        elem = convert_raw_data_element(raw, encoding=default_encoding)
        assert "UL" == elem.VR

    def test_data_element_without_encoding(self):
        """RawDataElement: no encoding needed."""
        raw = RawDataElement(
            Tag(0x00104000), "LT", 23, b"comment\\comment2\\comment3", 0, False, True
        )
        element = convert_raw_data_element(raw)
        assert "Patient Comments" == element.name

    def test_unknown_vr(self):
        """Test converting a raw element with unknown VR"""
        raw = RawDataElement(Tag(0x00080000), "AA", 8, b"20170101", 0, False, True)
        with pytest.raises(NotImplementedError):
            convert_raw_data_element(raw, encoding=default_encoding)

    @pytest.fixture
    def accept_wrong_length(self, request):
        old_value = config.convert_wrong_length_to_UN
        config.convert_wrong_length_to_UN = request.param
        yield
        config.convert_wrong_length_to_UN = old_value

    @pytest.mark.parametrize("accept_wrong_length", [False], indirect=True)
    def test_wrong_bytes_length_exception(self, accept_wrong_length):
        """Check exception when number of raw bytes is not correct."""
        raw = RawDataElement(Tag(0x00190000), "FD", 1, b"1", 0, False, True)
        with pytest.raises(BytesLengthException):
            convert_raw_data_element(raw)

    @pytest.mark.parametrize("accept_wrong_length", [True], indirect=True)
    def test_wrong_bytes_length_convert_to_UN(self, accept_wrong_length):
        """Check warning and behavior for incorrect number of raw bytes."""
        value = b"1"
        raw = RawDataElement(Tag(0x00190000), "FD", 1, value, 0, False, True)
        msg = (
            r"Expected total bytes to be an even multiple of bytes per value. "
            r"Instead received b'1' with length 1 and struct format 'd' which "
            r"corresponds to bytes per value of 8. This occurred while trying "
            r"to parse \(0019,0000\) according to VR 'FD'. "
            r"Setting VR to 'UN'."
        )
        with pytest.warns(UserWarning, match=msg):
            raw_elem = convert_raw_data_element(raw)
            assert "UN" == raw_elem.VR
            assert value == raw_elem.value

    def test_read_known_private_tag_implicit(self):
        fp = DicomBytesIO()
        ds = Dataset()
        ds.set_original_encoding(True, True)
        ds[0x00410010] = RawDataElement(
            Tag(0x00410010), "LO", 8, b"ACME 3.2", 0, True, True
        )
        ds[0x00411001] = RawDataElement(
            Tag(0x00411001), "US", 2, b"\x2A\x00", 0, True, True
        )
        ds[0x00431001] = RawDataElement(
            Tag(0x00431001), "SH", 8, b"Unknown ", 0, True, True
        )
        ds.save_as(fp)
        ds = dcmread(fp, force=True)
        elem = ds[0x00411001]
        assert elem.VR == "UN"
        assert elem.name == "Private tag data"
        assert elem.value == b"\x2A\x00"

        with save_private_dict():
            add_private_dict_entry("ACME 3.2", 0x00410001, "US", "Some Number")
            ds = dcmread(fp, force=True)
            elem = ds[0x00411001]
            assert elem.VR == "US"
            assert elem.name == "[Some Number]"
            assert elem.value == 42

            # Unknown private tag is handled as before
            elem = ds[0x00431001]
            assert elem.VR == "UN"
            assert elem.name == "Private tag data"
            assert elem.value == b"Unknown "

    def test_read_known_private_tag_explicit(self):
        fp = DicomBytesIO()
        ds = Dataset()
        ds.set_original_encoding(False, True)
        ds[0x00410010] = RawDataElement(
            Tag(0x00410010), "LO", 8, b"ACME 3.2", 0, False, True
        )
        ds[0x00411002] = RawDataElement(
            Tag(0x00411002), "UN", 8, b"SOME_AET", 0, False, True
        )
        ds.save_as(fp)
        ds = dcmread(fp, force=True)
        elem = ds[0x00411002]
        assert elem.VR == "UN"
        assert elem.name == "Private tag data"
        assert elem.value == b"SOME_AET"

        with save_private_dict():
            add_private_dict_entry("ACME 3.2", 0x00410002, "AE", "Some AET")
            ds = dcmread(fp, force=True)
            elem = ds[0x00411002]
            assert elem.VR == "AE"
            assert elem.name == "[Some AET]"
            assert elem.value == "SOME_AET"

    def test_read_known_private_tag_explicit_no_lookup(
        self, dont_replace_un_with_known_vr
    ):
        with save_private_dict():
            add_private_dict_entry("ACME 3.2", 0x00410003, "IS", "Another Number")
            fp = DicomBytesIO()
            ds = Dataset()
            ds.set_original_encoding(False, True)
            ds[0x00410010] = RawDataElement(
                Tag(0x00410010), "LO", 8, b"ACME 3.2", 0, False, True
            )
            ds[0x00411003] = RawDataElement(
                Tag(0x00411003), "UN", 8, b"12345678", 0, False, True
            )
            ds.save_as(fp)
            ds = dcmread(fp, force=True)
            elem = ds[0x00411003]
            assert elem.VR == "UN"
            assert elem.name == "[Another Number]"
            assert elem.value == b"12345678"

    def test_lut_descriptor_modifier_invalid(self):
        """Test fixing value for LUT Descriptor if value is not an int"""
        raw = RawDataElement(Tag(0x00283002), None, 4, ["a", 0, 1], 0, True, True)
        elem = convert_raw_data_element(raw)
        assert elem.value == ["a", 0, 1]

    def test_UN_unknown_public_tag(self):
        """Test converting a UN element with unknown public tag"""
        raw = RawDataElement(Tag(0x88883002), "UN", 4, b"\x02\x04", 0, True, True)
        elem = convert_raw_data_element(raw)
        assert elem.value == b"\x02\x04"
        assert elem.tag == 0x88883002
        assert elem.VR == "UN"


@pytest.fixture
def reset_hooks():
    original = (
        hooks.raw_element_vr,
        hooks.raw_element_value,
        hooks.raw_element_kwargs,
    )
    yield
    (
        hooks.raw_element_vr,
        hooks.raw_element_value,
        hooks.raw_element_kwargs,
    ) = original


class TestConvertRawDataElementHooks:
    """Tests for the hooks in convert_raw_data_element()"""

    def test_vr(self, reset_hooks):
        """Test the 'raw_element_vr' hook"""
        ds = Dataset()
        ds.PatientName = "Foo"
        raw = RawDataElement(Tag(0x00100020), None, 4, b"unknown", 0, True, True)

        d = {}

        def func(raw, data, **kwargs):
            data["VR"] = "LO"
            d.update(kwargs)

        kwargs = {"a": 1, "b": []}

        hooks.register_callback("raw_element_vr", func)
        hooks.register_kwargs("raw_element_kwargs", kwargs)

        elem = convert_raw_data_element(raw, encoding=default_encoding, ds=ds)
        assert elem.value == "unknown"
        assert elem.VR == "LO"
        assert elem.tag == (0x00100020)

        assert d["encoding"] == default_encoding
        assert d["ds"] == ds
        assert d["a"] == 1
        assert d["b"] == []

    def test_value(self, reset_hooks):
        """Test the 'raw_element_vr' hook"""
        ds = Dataset()
        ds.PatientName = "Foo"
        raw = RawDataElement(Tag(0x00100020), "LO", 4, b"unknown", 0, True, True)

        d = {}

        def func(raw, data, **kwargs):
            data["value"] = "12345"
            d.update(kwargs)

        kwargs = {"c": 3, "d": None}

        hooks.register_callback("raw_element_value", func)
        hooks.register_kwargs("raw_element_kwargs", kwargs)

        elem = convert_raw_data_element(raw, encoding=default_encoding, ds=ds)
        assert elem.value == "12345"
        assert elem.VR == "LO"
        assert elem.tag == (0x00100020)

        assert d["encoding"] == default_encoding
        assert d["ds"] == ds
        assert d["c"] == 3
        assert d["d"] is None

    def test_value_retry(self, reset_hooks):
        """Test the 'raw_element_value_retry' function"""
        raw = RawDataElement(Tag(0x00000903), None, 4, b"12345", 0, True, True)

        # Original function raises and exception
        msg = "Expected total bytes to be an even multiple of bytes per value"
        with pytest.raises(BytesLengthException, match=msg):
            convert_raw_data_element(raw)

        # No target_VRs set, no change
        hooks.register_callback("raw_element_value", raw_element_value_retry)
        with pytest.raises(BytesLengthException, match=msg):
            convert_raw_data_element(raw)

        kwargs = {"target_VRs": {"US": ("SS", "SH")}}
        hooks.register_kwargs("raw_element_kwargs", kwargs)

        # Test candidate VRs to see if they can be used instead
        #   in this case SS will fail and SH will succeed
        elem = convert_raw_data_element(raw)
        assert elem.value == "12345"
        assert elem.VR == "SH"

        # If unable to convert then raise original exception
        kwargs["target_VRs"]["US"] = ("SS",)
        with pytest.raises(BytesLengthException, match=msg):
            convert_raw_data_element(raw)

    def test_value_fix_separator(self, reset_hooks):
        """Test the 'raw_element_value_fix_separator' function"""
        raw = RawDataElement(
            Tag(0x00000902), None, 4, b"\x41\x42\x2C\x43\x44\x2C\x45\x46", 0, True, True
        )

        elem = convert_raw_data_element(raw)
        assert elem.value == "AB,CD,EF"

        hooks.register_callback("raw_element_value", raw_element_value_fix_separator)

        # No target_VRs set, no change
        elem = convert_raw_data_element(raw)
        assert elem.value == "AB,CD,EF"

        kwargs = {"target_VRs": ("LO",)}
        hooks.register_kwargs("raw_element_kwargs", kwargs)

        elem = convert_raw_data_element(raw)
        assert elem.value == ["AB", "CD", "EF"]

        kwargs["separator"] = ":"
        raw = raw._replace(value=raw.value.replace(b"\x2C", b":"))
        elem = convert_raw_data_element(raw)
        assert elem.value == ["AB", "CD", "EF"]

        raw = raw._replace(VR="SH")
        elem = convert_raw_data_element(raw)
        assert elem.value == "AB:CD:EF"


class TestDataElementValidation:
    @staticmethod
    def check_invalid_vr(vr, value, check_warn=True):
        msg = rf"Invalid value for VR {vr}: *"
        if check_warn:
            with pytest.warns(UserWarning, match=msg):
                DataElement(0x00410001, vr, value, validation_mode=config.WARN)
            with pytest.warns(UserWarning, match=msg):
                validate_value(vr, value, config.WARN)
        with pytest.raises(ValueError, match=msg):
            DataElement(0x00410001, vr, value, validation_mode=config.RAISE)
        with pytest.raises(ValueError, match=msg):
            validate_value(vr, value, config.RAISE)

    @staticmethod
    def check_valid_vr(vr, value):
        DataElement(0x00410001, vr, value, validation_mode=config.RAISE)
        validate_value(vr, value, config.RAISE)

    @pytest.mark.parametrize(
        "vr, length",
        (
            ("AE", 17),
            ("CS", 17),
            ("DS", 27),
            ("LO", 66),
            ("LT", 10250),
            ("SH", 17),
            ("ST", 1025),
            ("UI", 65),
        ),
    )
    def test_maxvalue_exceeded(self, vr, length, no_datetime_conversion):
        msg = rf"The value length \({length}\) exceeds the maximum length *"
        with pytest.warns(UserWarning, match=msg):
            DataElement(0x00410001, vr, "1" * length, validation_mode=config.WARN)
        with pytest.raises(ValueError, match=msg):
            DataElement(0x00410001, vr, "2" * length, validation_mode=config.RAISE)

    @pytest.mark.parametrize(
        "value", ("Руссский", b"ctrl\tchar", "new\n", b"newline\n", "Äneas")
    )
    def test_invalid_ae(self, value):
        self.check_invalid_vr("AE", value)

    @pytest.mark.parametrize("value", ("My AETitle", b"My AETitle", "", None))
    def test_valid_ae(self, value):
        self.check_valid_vr("AE", value)

    @pytest.mark.parametrize("value", ("12Y", "0012Y", b"012B", "Y012", "012Y\n"))
    def test_invalid_as(self, value):
        self.check_invalid_vr("AS", value)

    @pytest.mark.parametrize("value", ("012Y", "345M", b"052W", b"789D", "", None))
    def test_valid_as(self, value):
        self.check_valid_vr("AS", value)

    @pytest.mark.parametrize(
        "value", ("abcd", b"ABC+D", "ABCD-Z", "ÄÖÜ", "ÄÖÜ".encode(), "ABC\n")
    )
    def test_invalid_cs(self, value):
        self.check_invalid_vr("CS", value)

    @pytest.mark.parametrize("value", ("VALID_13579 ", b"VALID_13579", "", None))
    def test_valid_cs(self, value):
        self.check_valid_vr("CS", value)

    @pytest.mark.parametrize(
        "value",
        (
            "201012",
            "2010122505",
            b"20102525",
            b"-20101225-",
            "20101620",
            "20101040",
            "20101033",
            "20101225 20201224 ",
        ),
    )
    def test_invalid_da(self, value):
        self.check_invalid_vr("DA", value)

    @pytest.mark.parametrize(
        "value",
        (
            b"19560303",
            "20101225-20201224 ",
            datetime.date(2022, 5, 1),
            b"-19560303",
            "19560303-",
            "",
            None,
        ),
    )
    def test_valid_da(self, value):
        self.check_valid_vr("DA", value)

    @pytest.mark.parametrize(
        "value", ("201012+", "20A0", "+-123.66", "-123.5 E4", b"123F4 ", "- 195.6")
    )
    def test_invalid_ds(self, value):
        self.check_invalid_vr("DS", value, check_warn=False)

    @pytest.mark.parametrize(
        "value",
        ("12345", "+.1234 ", "-0345.76", b"1956E3", b"-1956e+3", "+195.6e-3", "", None),
    )
    def test_valid_ds(self, value):
        self.check_valid_vr("DS", value)

    @pytest.mark.parametrize(
        "value", ("201012+", "20A0", b"123.66", "-1235E4", "12 34")
    )
    def test_invalid_is(self, value):
        self.check_invalid_vr("IS", value, check_warn=False)

    @pytest.mark.parametrize("value", (" 12345 ", b"+1234 ", "-034576", "", None))
    def test_valid_is(self, value):
        self.check_valid_vr("IS", value)

    @pytest.mark.parametrize(
        "value",
        (
            "234",
            "1",
            "01015",
            "225959.",
            b"0000.345",
            "222222.2222222",
            "-1234-",
            "+123456",
            b"-123456-1330",
            "006000",
            "005961",
            "0000aa",
            "0000.00",
            "123461-1330",
            "123400-1360",
        ),
    )
    def test_invalid_tm(self, value):
        self.check_invalid_vr("TM", value)

    @pytest.mark.parametrize(
        "value",
        (
            "23",
            "1234",
            b"010159",
            "225959.3",
            "000000.345",
            "222222.222222",
            "-1234",
            "123456-",
            b"123460-1330",
            "005960",
            "",
            None,
            datetime.time(11, 11, 0),
        ),
    )
    def test_valid_tm(self, value):
        self.check_valid_vr("TM", value)

    @pytest.mark.parametrize(
        "value",
        (
            "19",
            "198",
            "20011",
            b"20200101.222",
            "187712311",
            "20001301",
            "19190432010159",
            "203002020222.2222222",
            b"203002020270.2",
            "1984+2000",
            "+1877123112-0030",
            "19190430010161",
            "19190430016000",
        ),
    )
    def test_invalid_dt(self, value):
        self.check_invalid_vr("DT", value)

    @pytest.mark.parametrize(
        "value",
        (
            "1984",
            "200112",
            b"20200101",
            "1877123112",
            "200006012020",
            "19190420015960",
            "20300202022222.222222",
            b"20300202022222.2",
            "1984+0600",
            "1877123112-0030",
            "20300202022222.2-1200",
            "20000101-",
            "-2020010100",
            "1929-1997",
            "",
            None,
            datetime.datetime(1999, 12, 24, 12, 0, 0),
        ),
    )
    def test_valid_dt(self, value):
        self.check_valid_vr("DT", value)

    @pytest.mark.parametrize(
        "value", ("Руссский", "ctrl\tchar", '"url"', "a<b", "{abc}")
    )
    def test_invalid_ui(self, value):
        self.check_invalid_vr("UR", value)

    @pytest.mark.parametrize(
        "value", ("1234.567890.333", "0.0.0", "1234." * 12 + "1234", None)
    )
    def test_valid_ui(self, value):
        self.check_valid_vr("UI", value)

    @pytest.mark.parametrize(
        "value", (".123.456", "00.1.2", "123..456", "123.45.", "12a.45", "123.04")
    )
    def test_invalid_ur(self, value):
        self.check_invalid_vr("UI", value)

    @pytest.mark.parametrize(
        "value", ("https://www.a.b/sdf_g?a=1&b=5", "/a#b(c)[d]@!", "'url'", "", None)
    )
    def test_valid_ur(self, value):
        self.check_valid_vr("UR", value)

    def test_invalid_pn(self):
        msg = r"The number of PN components length \(4\) exceeds *"
        with pytest.warns(UserWarning, match=msg):
            DataElement(
                0x00410001, "PN", "Jim=John=Jimmy=Jonny", validation_mode=config.WARN
            )
        msg = r"The PN component length \(65\) exceeds *"
        with pytest.raises(ValueError, match=msg):
            DataElement(0x00410001, "PN", b"Jimmy" * 13, validation_mode=config.RAISE)

    @pytest.mark.parametrize(
        "value, value_type", [(42, "int"), (complex(1, 2), "complex"), (1.45, "float")]
    )
    @pytest.mark.parametrize(
        "vr", ("AE", "AS", "CS", "DA", "DT", "LO", "LT", "SH", "ST", "TM", "UR")
    )
    def test_invalid_string_value(self, value, value_type, vr):
        msg = (
            f"A value of type '{value_type}' cannot be assigned"
            f" to a tag with VR {vr}."
        )
        with pytest.warns(UserWarning, match=msg):
            DataElement(0x00410001, vr, value, validation_mode=config.WARN)
        with pytest.raises(ValueError, match=msg):
            DataElement(0x00410001, vr, value, validation_mode=config.RAISE)

    @pytest.mark.parametrize(
        "value, value_type", [(42, "int"), (complex(1, 2), "complex"), (1.45, "float")]
    )
    def test_invalid_pn_value_type(self, value, value_type):
        msg = (
            f"A value of type '{value_type}' cannot be assigned"
            f" to a tag with VR PN."
        )
        with pytest.warns(UserWarning, match=msg):
            # will raise an exception as it cannot handle these types later
            with pytest.raises(AttributeError):
                DataElement(0x00410001, "PN", value, validation_mode=config.WARN)
        with pytest.raises(ValueError, match=msg):
            DataElement(0x00410001, "PN", value, validation_mode=config.RAISE)

    @pytest.mark.parametrize("value", ("John^Doe", "Yamada^Tarou=山田^太郎", "", None))
    def test_valid_pn(self, value):
        self.check_valid_vr("PN", value)

    def test_write_valid_length_non_ascii_text(self, enforce_writing_invalid_values):
        fp = DicomBytesIO()
        ds = Dataset()
        ds.set_original_encoding(True, True)
        ds.SpecificCharacterSet = "ISO_IR 192"  # UTF-8
        ds.add(DataElement(0x00080050, "SH", "洪^吉洞=홍^길동"))
        # shall not raise, as the number of characters is considered,
        # not the number of bytes (which is > 16)
        dcmread(fp, force=True)

    def test_write_valid_non_ascii_pn(self, enforce_writing_invalid_values):
        fp = DicomBytesIO()
        ds = Dataset()
        ds.set_original_encoding(False, True)
        ds.SpecificCharacterSet = "ISO_IR 192"  # UTF-8
        # string length is 40
        ds.add(DataElement(0x00100010, "PN", "洪^吉洞" * 10))
        # shall not raise, as the number of characters is considered,
        # not the number of bytes (which is > 64)
        ds.save_as(fp)

    def test_read_valid_length_non_ascii_text(self):
        fp = DicomBytesIO()
        ds = Dataset()
        ds.set_original_encoding(True, True)
        ds.SpecificCharacterSet = "ISO_IR 192"  # UTF-8
        ds.add(DataElement(0x00080050, "SH", "洪^吉洞=홍^길동"))
        # shall not raise, as the number of characters is considered,
        # not the number of bytes (which is > 16)
        ds.save_as(fp)
        dcmread(fp, force=True)

    @pytest.mark.parametrize(
        "value, value_type", [("1", "str"), (1.5, "float"), (complex(1, 2), "complex")]
    )
    @pytest.mark.parametrize("vr", ("US", "SS", "UV", "SV"))
    def test_invalid_numeric_value(self, value, value_type, vr):
        msg = (
            f"A value of type '{value_type}' cannot be assigned"
            f" to a tag with VR {vr}."
        )
        with pytest.warns(UserWarning, match=msg):
            DataElement(0x00410001, vr, value, validation_mode=config.WARN)
        with pytest.raises(ValueError, match=msg):
            DataElement(0x00410001, vr, value, validation_mode=config.RAISE)

    @pytest.mark.parametrize(
        "value, value_type", [("1", "str"), (complex(1, 2), "complex")]
    )
    @pytest.mark.parametrize("vr", ("FL", "FD"))
    def test_invalid_float_value(self, value, value_type, vr):
        msg = (
            f"A value of type '{value_type}' cannot be assigned"
            f" to a tag with VR {vr}."
        )
        with pytest.warns(UserWarning, match=msg):
            DataElement(0x00410001, vr, value, validation_mode=config.WARN)
        with pytest.raises(ValueError, match=msg):
            DataElement(0x00410001, vr, value, validation_mode=config.RAISE)

    @pytest.mark.parametrize("value", (-1.5, 0, 1, 1234.5678))
    @pytest.mark.parametrize("vr", ("FL", "FD"))
    def test_valid_float_value(self, value, vr):
        DataElement(0x00410001, vr, value, validation_mode=config.RAISE)

    @pytest.mark.parametrize(
        "value", (0, 1, 65535, b"", b"\xf3\x42", b"\x01\x00\x02\x00")
    )
    def test_valid_us_value(self, value):
        DataElement(0x00410001, "US", value, validation_mode=config.RAISE)

    @pytest.mark.parametrize("value", (-1, 66000))
    def test_invalid_us_value(self, value):
        msg = (
            "Invalid value: a value for a tag with VR US "
            "must be between 0 and 65535."
        )
        with pytest.warns(UserWarning, match=msg):
            DataElement(0x00410001, "US", value, validation_mode=config.WARN)
        with pytest.raises(ValueError, match=msg):
            DataElement(0x00410001, "US", value, validation_mode=config.RAISE)
        with pytest.warns(UserWarning, match=msg):
            ds = Dataset()
            ds.add_new(0x00410001, "US", value)

    @pytest.mark.parametrize("value", (-32768, 0, 32767, b"\xff\xff", b"\0\0\0\0"))
    def test_valid_ss_value(self, value):
        DataElement(0x00410001, "SS", value, validation_mode=config.RAISE)

    @pytest.mark.parametrize("value", (-33000, 32768))
    def test_invalid_ss_value(self, value):
        msg = (
            "Invalid value: a value for a tag with VR SS "
            "must be between -32768 and 32767."
        )
        with pytest.warns(UserWarning, match=msg):
            DataElement(0x00410001, "SS", value, validation_mode=config.WARN)
        with pytest.raises(ValueError, match=msg):
            DataElement(0x00410001, "SS", value, validation_mode=config.RAISE)

    @pytest.mark.parametrize("vr", ("US", "SS"))
    @pytest.mark.parametrize("value", (b"\x01", b"\x00\x00\x00"))
    def test_invalid_short_value_length(self, vr, value):
        msg = (
            f"Invalid value length {len(value)}: the value length for a "
            f"tag with VR {vr} must be a multiple of 2."
        )
        with pytest.warns(UserWarning, match=msg):
            DataElement(0x00410001, vr, value, validation_mode=config.WARN)
        with pytest.raises(ValueError, match=msg):
            DataElement(0x00410001, vr, value, validation_mode=config.RAISE)

    @pytest.mark.parametrize("value", (0, 1, 4294967295, b"\x00\x01\x02\x03"))
    def test_valid_ul_value(self, value):
        DataElement(0x00410001, "UL", value, validation_mode=config.RAISE)

    @pytest.mark.parametrize("value", (-2, 4294967300))
    def test_invalid_ul_value(self, value):
        msg = (
            "Invalid value: a value for a tag with VR UL "
            "must be between 0 and 4294967295."
        )
        with pytest.warns(UserWarning, match=msg):
            DataElement(0x00410001, "UL", value, validation_mode=config.WARN)
        with pytest.raises(ValueError, match=msg):
            DataElement(0x00410001, "UL", value, validation_mode=config.RAISE)

    @pytest.mark.parametrize(
        "value", (-2147483648, 0, 2147483647, b"\x12\x34\x56\x78\x9a\xbc\xde\xf0")
    )
    def test_valid_sl_value(self, value):
        DataElement(0x00410001, "SL", value, validation_mode=config.RAISE)

    @pytest.mark.parametrize("value", (-2147483650, 2147483648))
    def test_invalid_sl_value(self, value):
        msg = (
            "Invalid value: a value for a tag with VR SL "
            "must be between -2147483648 and 2147483647."
        )
        with pytest.warns(UserWarning, match=msg):
            DataElement(0x00410001, "SL", value, validation_mode=config.WARN)
        with pytest.raises(ValueError, match=msg):
            DataElement(0x00410001, "SL", value, validation_mode=config.RAISE)

    @pytest.mark.parametrize("vr", ("UL", "SL"))
    @pytest.mark.parametrize("value", (b"\x0b\x00", b"\x01\x34\x11", b"\xff" * 5))
    def test_invalid_long_value_length(self, vr, value):
        msg = (
            f"Invalid value length {len(value)}: the value length for a "
            f"tag with VR {vr} must be a multiple of 4."
        )
        with pytest.warns(UserWarning, match=msg):
            DataElement(0x00410001, vr, value, validation_mode=config.WARN)
        with pytest.raises(ValueError, match=msg):
            DataElement(0x00410001, vr, value, validation_mode=config.RAISE)

    @pytest.mark.parametrize("value", (0, 1, 18446744073709551615, b"01" * 8))
    def test_valid_uv_value(self, value):
        DataElement(0x00410001, "UV", value, validation_mode=config.RAISE)

    @pytest.mark.parametrize("value", (-1, 18446744073709551617))
    def test_invalid_uv_value(self, value):
        msg = (
            "Invalid value: a value for a tag with VR UV "
            "must be between 0 and 18446744073709551615."
        )
        with pytest.warns(UserWarning, match=msg):
            DataElement(0x00410001, "UV", value, validation_mode=config.WARN)
        with pytest.raises(ValueError, match=msg):
            DataElement(0x00410001, "UV", value, validation_mode=config.RAISE)

    @pytest.mark.parametrize(
        "value", (-9223372036854775808, 0, 9223372036854775807, b"ff" * 24)
    )
    def test_valid_sv_value(self, value):
        DataElement(0x00410001, "SV", value, validation_mode=config.RAISE)

    @pytest.mark.parametrize("value", (-9223372036854775809, 9223372036854775808))
    def test_invalid_sv_value(self, value):
        msg = (
            "Invalid value: a value for a tag with VR SV must be between "
            "-9223372036854775808 and 9223372036854775807."
        )
        with pytest.warns(UserWarning, match=msg):
            DataElement(0x00410001, "SV", value, validation_mode=config.WARN)
        with pytest.raises(ValueError, match=msg):
            DataElement(0x00410001, "SV", value, validation_mode=config.RAISE)

    @pytest.mark.parametrize("vr", ("UV", "SV"))
    @pytest.mark.parametrize(
        "value",
        (
            b"\x0b\x00",
            b"\x01\x34\x11\x00",
            b"\xff" * 6,
            b"\x00" * 9,
        ),
    )
    def test_invalid_very_long_value_length(self, vr, value):
        msg = (
            f"Invalid value length {len(value)}: the value length for a "
            f"tag with VR {vr} must be a multiple of 8."
        )
        with pytest.warns(UserWarning, match=msg):
            DataElement(0x00410001, vr, value, validation_mode=config.WARN)
        with pytest.raises(ValueError, match=msg):
            DataElement(0x00410001, vr, value, validation_mode=config.RAISE)

    @pytest.mark.skipif(not config.have_numpy, reason="Numpy is not available")
    def test_pixel_data_ndarray_raises(self):
        """Test exception raised if setting PixelData using ndarray"""
        import numpy as np

        ds = Dataset()
        ds.PixelData = b"\x00\x01"
        assert ds.PixelData == b"\x00\x01"

        msg = (
            r"The value for \(7FE0,0010\) 'Pixel Data' should be set using 'bytes' "
            r"not 'numpy.ndarray'. See the Dataset.set_pixel_data\(\) method for "
            "an alternative that supports ndarrays."
        )
        with pytest.raises(TypeError, match=msg):
            ds.PixelData = np.ones((3, 4), dtype="u1")

        assert ds.PixelData == b"\x00\x01"

    @pytest.mark.parametrize("value", (None, b"", b"\x00", b"\x00\x01\x02\x03"))
    def test_valid_o_star_bytes(self, value):
        for vr in ("OB", "OD", "OF", "OL", "OW", "OV"):
            DataElement(0x00410001, "vr", value, validation_mode=config.RAISE)

    @pytest.mark.parametrize("value", (bytearray(), bytearray(b"\x00\x01\x02\x03")))
    def test_valid_o_star_bytearray(self, value):
        for vr in ("OB", "OD", "OF", "OL", "OW", "OV"):
            DataElement(0x00410001, "vr", value, validation_mode=config.RAISE)

    @pytest.mark.parametrize("value", (-2, 4294967300))
    def test_invalid_o_star_value(self, value):
        for vr in ("OB", "OD", "OF", "OL", "OW", "OV"):
            msg = f"A value of type 'int' cannot be assigned to a tag with VR {vr}"
            with pytest.warns(UserWarning, match=msg):
                DataElement(0x00410001, vr, value, validation_mode=config.WARN)
            with pytest.raises(ValueError, match=msg):
                DataElement(0x00410001, vr, value, validation_mode=config.RAISE)


class TestBufferedDataElement:
    """Tests setting a DataElement value to a buffer"""

    @pytest.mark.parametrize("vr", BUFFERABLE_VRS)
    def test_reading_dataelement_buffer(self, vr):
        value = b"\x00\x01\x02\x03"
        buffer = io.BytesIO(value)
        elem = DataElement("PixelData", vr, buffer)

        data: bytes = b""
        # while read_bytes is tested in test_buffer.py, this tests the integration
        # between the helper and DataElement since this is the main use case
        for chunk in read_buffer(elem.value):
            data += chunk

        assert data == value

    def test_unsupported_vr_raises(self):
        """Test using a buffer with an unsupported VR raises"""
        msg = (
            "Elements with a VR of 'PN' cannot be used with buffered values, "
            "supported VRs are: OB, OD, OF, OL, OV, OW"
        )
        with pytest.raises(ValueError, match=msg):
            DataElement("PersonName", "PN", io.BytesIO())

    @pytest.mark.skipif(IS_WINDOWS, reason="TemporaryFile on Windows always readable")
    def test_invalid_buffer_raises(self):
        """Test invalid buffer raises on setting the value"""
        b = io.BytesIO()
        b.close()
        msg = (
            r"Invalid buffer for \(0040,A123\) 'Person Name': the buffer has been "
            "closed"
        )
        with pytest.raises(ValueError, match=msg):
            DataElement("PersonName", "OB", b)

        msg = (
            r"Invalid buffer for \(0040,A123\) 'Person Name': the buffer must be "
            "readable and seekable"
        )
        with tempfile.TemporaryFile(mode="wb") as t:
            with pytest.raises(ValueError, match=msg):
                DataElement("PersonName", "OB", t)

    def test_printing_value(self):
        value = b"\x00\x01\x02\x03"
        buffer = io.BytesIO(value)
        elem = DataElement("PixelData", "OB", buffer)
        assert elem.is_buffered
        assert re.compile(
            r"^\(7FE0,0010\) Pixel Data\W*OB: <_io.BytesIO object.*$"
        ).match(str(elem))
        assert elem.repval.startswith("<_io.BytesIO object at")
        assert repr(elem) == str(elem)

    def test_VM(self):
        """Test buffered element VM"""
        elem = DataElement("PersonName", "OB", io.BytesIO())
        assert elem.VM == 0
        elem = DataElement("PersonName", "OB", io.BytesIO(b"\x00\x01"))
        assert elem.VM == 1

    def test_equality(self):
        """Test element equality"""
        # First is buffered, second is not
        elem = DataElement("PersonName", "OB", b"\x00\x01")
        b_elem = DataElement("PersonName", "OB", io.BytesIO(b"\x00\x01"))

        # Test equality multiple times to ensure buffer can be re-read
        assert b_elem == elem
        assert b_elem == elem

        elem.value = b"\x01\x02"
        assert b_elem != elem
        assert b_elem != elem

        # First and second are both buffered
        b_elem2 = DataElement("PersonName", "OB", io.BytesIO(b"\x00\x01"))
        assert b_elem == b_elem2
        assert b_elem == b_elem2

        b_elem2 = DataElement("PersonName", "OB", io.BytesIO(b"\x01\x02"))
        assert b_elem != b_elem2
        assert b_elem != b_elem2

        # First is not buffered, second is
        # Test equality multiple times to ensure buffer can be re-read
        assert elem != b_elem
        assert elem != b_elem

    def test_equality_offset(self):
        """Test equality when the buffer isn't positioned at the start"""
        elem = DataElement("PersonName", "OB", b"\x00\x01")

        b = io.BytesIO(b"\x00\x01")
        b_elem = DataElement("PersonName", "OB", b)
        b.seek(2)

        assert b_elem == elem
        assert b_elem == elem

        c = io.BytesIO(b"\x00\x01")
        c_elem = DataElement("PersonName", "OB", c)
        c.seek(1)

        assert b_elem == c_elem
        assert b_elem == c_elem

    def test_equality_larger(self):
        """Test equality when bytes is larger than buffer"""
        elem = DataElement("PersonName", "OB", b"\x00\x01\x02\x03")
        b_elem = DataElement("PersonName", "OB", io.BytesIO(b"\x00\x01"))

        assert b_elem != elem

        c_elem = DataElement("PersonName", "OB", io.BytesIO(b"\x00\x01\x02\x03"))
        assert b_elem != c_elem

    def test_equality_multichunk(self):
        """Test element equality when the value gets chunked"""
        # Test multiple of default chunk size
        value = b"\x00\x01\x02" * 8192
        elem = DataElement("PersonName", "OB", value)
        b_elem = DataElement("PersonName", "OB", io.BytesIO(value))
        assert b_elem == elem

        # Test not a multiple of default chunk size
        value = b"\x00\x01\x02" * 8418
        elem = DataElement("PersonName", "OB", value)
        b_elem = DataElement("PersonName", "OB", io.BytesIO(value))
        assert b_elem == elem

        # Test empty
        value = b""
        elem = DataElement("PersonName", "OB", value)
        b_elem = DataElement("PersonName", "OB", io.BytesIO(value))
        assert b_elem == elem

    def test_equality_raises(self):
        """Test equality raises if buffer invalid."""
        elem = DataElement("PersonName", "OB", b"\x00\x01")
        b = io.BytesIO(b"\x00\x01")
        b_elem = DataElement("PersonName", "OB", b)

        assert b_elem == elem

        # First buffer is invalid
        b.close()
        msg = (
            r"Invalid buffer for \(0040,A123\) 'Person Name': the buffer has been "
            "closed"
        )
        with pytest.raises(ValueError, match=msg):
            b_elem == elem

        # Second buffer is invalid
        with pytest.raises(ValueError, match=msg):
            elem == b_elem

        # Both buffers are invalid
        c = io.BytesIO(b"\x00\x01")
        c_elem = DataElement("PersonName", "OB", c)
        c.close()

        with pytest.raises(ValueError, match=msg):
            b_elem == c_elem

    def test_deepcopy(self):
        """Test deepcopy with a buffered value"""
        b = io.BytesIO(b"\x00\x01")
        elem = DataElement("PersonName", "OB", b)

        elem2 = copy.deepcopy(elem)
        assert isinstance(elem.value, io.BytesIO)
        assert isinstance(elem2.value, io.BytesIO)
        assert elem.value.getvalue() == b.getvalue()
        assert elem2.value.getvalue() == b.getvalue()
        assert elem2.value is not elem.value
        assert elem2 == elem

    def test_deepcopy_closed(self):
        """Test deepcopy with a buffered value"""
        b = io.BytesIO(b"\x00\x01")
        elem = DataElement("PersonName", "OB", b)
        b.close()

        msg = (
            r"Error deepcopying the buffered element \(0040,A123\) 'Person Name': "
            "I/O operation on closed file"
        )
        with pytest.raises(ValueError, match=msg):
            copy.deepcopy(elem)


@pytest.fixture
def use_future():
    original = config._use_future
    config._use_future = True
    yield
    config._use_future = original


def test_deprecation_warnings():
    from pydicom.dataelem import DataElement_from_raw

    raw = RawDataElement(Tag(0x00100010), None, 4, b"unknown", 0, True, True)
    msg = (
        "'pydicom.dataelem.DataElement_from_raw' is deprecated and will be removed "
        "in v4.0, please use 'pydicom.dataelem.convert_raw_data_element' instead"
    )
    with pytest.warns(DeprecationWarning, match=msg):
        DataElement_from_raw(raw)


def test_import_raises(use_future):
    with pytest.raises(ImportError):
        from pydicom.dataelem import DataElement_from_raw
