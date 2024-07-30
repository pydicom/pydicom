# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""test cases for pydicom.filewriter module"""
import tempfile
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO
import os
import sys
from pathlib import Path
import pickle
import platform

from struct import unpack
from tempfile import TemporaryFile
from typing import cast
import zlib

try:
    import resource

    HAVE_RESOURCE = True
except ImportError:
    HAVE_RESOURCE = False

import pytest

from pydicom import config, __version_info__, uid
from pydicom.data import get_testdata_file, get_charset_files
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.dataelem import DataElement, RawDataElement
from pydicom.filebase import DicomBytesIO
from pydicom.filereader import dcmread, read_dataset
from pydicom.filewriter import (
    _determine_encoding,
    write_data_element,
    write_dataset,
    correct_ambiguous_vr,
    write_file_meta_info,
    correct_ambiguous_vr_element,
    write_numbers,
    write_PN,
    _format_DT,
    write_text,
    write_OBvalue,
    write_OWvalue,
    writers,
    dcmwrite,
)
from pydicom.multival import MultiValue
from pydicom.sequence import Sequence
from .test_helpers import assert_no_warning
from pydicom.uid import (
    ImplicitVRLittleEndian,
    ExplicitVRBigEndian,
    ExplicitVRLittleEndian,
    RLELossless,
    PYDICOM_IMPLEMENTATION_UID,
    CTImageStorage,
    UID,
)
from pydicom.util.hexutil import hex2bytes
from pydicom.valuerep import BUFFERABLE_VRS, DA, DT, TM, VR
from pydicom.values import convert_text
from ._write_stds import impl_LE_deflen_std_hex

rtplan_name = get_testdata_file("rtplan.dcm")
rtdose_name = get_testdata_file("rtdose.dcm")
ct_name = get_testdata_file("CT_small.dcm")
mr_name = get_testdata_file("MR_small.dcm")
mr_implicit_name = get_testdata_file("MR_small_implicit.dcm")
mr_bigendian_name = get_testdata_file("MR_small_bigendian.dcm")
jpeg_name = get_testdata_file("JPEG2000.dcm")
no_ts = get_testdata_file("meta_missing_tsyntax.dcm")
color_pl_name = get_testdata_file("color-pl.dcm")
sc_rgb_name = get_testdata_file("SC_rgb.dcm")
datetime_name = mr_name

unicode_name = get_charset_files("chrH31.dcm")[0]
multiPN_name = get_charset_files("chrFrenMulti.dcm")[0]
deflate_name = get_testdata_file("image_dfl.dcm")

base_version = ".".join(str(i) for i in __version_info__)


IS_WINDOWS = platform.system() == "Windows"


def files_identical(a, b):
    """Return a tuple (file a == file b, index of first difference)"""
    with open(a, "rb") as A:
        with open(b, "rb") as B:
            a_bytes = A.read()
            b_bytes = B.read()

    return bytes_identical(a_bytes, b_bytes)


def bytes_identical(a_bytes, b_bytes):
    """Return a tuple
    (bytes a == bytes b, index of first difference)"""
    if len(a_bytes) != len(b_bytes):
        return False, min([len(a_bytes), len(b_bytes)])
    elif a_bytes == b_bytes:
        return True, 0  # True, dummy argument
    else:
        pos = 0
        while a_bytes[pos] == b_bytes[pos]:
            pos += 1
        return False, pos  # False if not identical, position of 1st diff


def as_assertable(dataset):
    """Copy the elements in a Dataset (including the file_meta, if any)
    to a set that can be safely compared using pytest's assert.
    (Datasets can't be so compared because DataElements are not
    hashable.)"""
    safe_dict = dict(
        (str(elem.tag) + " " + elem.keyword, elem.value) for elem in dataset
    )
    if hasattr(dataset, "file_meta"):
        safe_dict.update(as_assertable(dataset.file_meta))
    return safe_dict


class TestWriteFile:
    def setup_method(self):
        self.file_out = TemporaryFile("w+b")

    def teardown_method(self):
        self.file_out.close()

    def compare(self, in_filename):
        """Read Dataset from in_filename, write to file, compare"""
        with open(in_filename, "rb") as f:
            bytes_in = BytesIO(f.read())
            bytes_in.seek(0)

        ds = dcmread(bytes_in)
        ds.save_as(self.file_out)
        self.file_out.seek(0)
        bytes_out = BytesIO(self.file_out.read())
        bytes_in.seek(0)
        bytes_out.seek(0)
        same, pos = bytes_identical(bytes_in.getvalue(), bytes_out.getvalue())
        assert same

    def compare_bytes(self, bytes_in, bytes_out):
        """Compare two bytestreams for equality"""
        same, pos = bytes_identical(bytes_in, bytes_out)
        assert same

    def testRTPlan(self):
        """Input file, write back and verify
        them identical (RT Plan file)"""
        self.compare(rtplan_name)

    def testRTDose(self):
        """Input file, write back and
        verify them identical (RT Dose file)"""
        self.compare(rtdose_name)

    def testCT(self):
        """Input file, write back and
        verify them identical (CT file)....."""
        self.compare(ct_name)

    def testMR(self):
        """Input file, write back and verify
        them identical (MR file)....."""
        self.compare(mr_name)

    def testUnicode(self):
        """Ensure decoded string DataElements
        are written to file properly"""
        self.compare(unicode_name)

    def testMultiPN(self):
        """Ensure multiple Person Names are written
        to the file correctly."""
        self.compare(multiPN_name)

    def testJPEG2000(self):
        """Input file, write back and verify
        them identical (JPEG2K file)."""
        self.compare(jpeg_name)

    def test_None_parent(self):
        """Ensure can write nested sequence with no parent dataset"""
        # from issues 1836, 1838, 1839

        # (0040,9096)  Real World Value Mapping Sequence  1 item(s) ----
        #    (0040,9211) Real World Value Last Value Mapped  US: 8699
        byts = (
            b"\0" * 128
            + b"DICM"
            + bytes.fromhex(
                "4000 9690 FFFFFFFF"  # (0040,9096) Sequence undefined length
                "  FEFF 00E0 FFFFFFFF"  # Sequence Item undefined length
                "    4000 1192 02000000"  # (0040,9211) length 2
                "    FB 21                  "  # value
                "  FEFF 0DE0 00000000"  # Item Delimiter
                "FEFF DDE0 00000000"  # Sequence Delimiter
            )
        )

        ds = dcmread(BytesIO(byts))
        # original bug raises 'NoneType' object is not callable on decode
        ds.decode()

    def test_pathlib_path_filename(self):
        """Check that file can be written using pathlib.Path"""
        ds = dcmread(Path(ct_name))
        ds.save_as(self.file_out)
        self.file_out.seek(0)
        ds1 = dcmread(self.file_out)
        assert ds.PatientName == ds1.PatientName

    def testListItemWriteBack(self):
        """Change item in a list and confirm
        it is written to file"""
        DS_expected = 0
        CS_expected = "new"
        SS_expected = 999
        ds = dcmread(ct_name)
        ds.ImagePositionPatient[2] = DS_expected
        ds.ImageType[1] = CS_expected
        ds[(0x0043, 0x1012)].value[0] = SS_expected
        ds.save_as(self.file_out)
        self.file_out.seek(0)
        # Now read it back in and check that the values were changed
        ds = dcmread(self.file_out)
        assert CS_expected == ds.ImageType[1]
        assert SS_expected == ds[0x00431012].value[0]
        assert DS_expected == ds.ImagePositionPatient[2]

    def testwrite_short_uid(self):
        ds = dcmread(rtplan_name)
        ds.SOPInstanceUID = "1.2"
        ds.save_as(self.file_out)
        self.file_out.seek(0)
        ds = dcmread(self.file_out)
        assert "1.2" == ds.SOPInstanceUID

    def test_write_no_ts(self):
        """Test reading a file with no ts and writing it out identically."""
        ds = dcmread(no_ts)
        ds.save_as(self.file_out)
        self.file_out.seek(0)
        with open(no_ts, "rb") as ref_file:
            written_bytes = self.file_out.read()
            read_bytes = ref_file.read()
            self.compare_bytes(read_bytes, written_bytes)

    def test_write_double_filemeta(self):
        """Test writing file meta from Dataset doesn't work"""
        ds = dcmread(ct_name)
        ds.TransferSyntaxUID = "1.1"
        with pytest.raises(ValueError):
            ds.save_as(self.file_out)

    def test_write_ffff_ffff(self):
        """Test writing element (FFFF,FFFF) to file #92"""
        fp = DicomBytesIO()
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.add_new(0xFFFFFFFF, "LO", "123456")
        ds.save_as(fp, implicit_vr=True)

        fp.seek(0)
        ds = dcmread(fp, force=True)
        assert ds[0xFFFFFFFF].value == b"123456"

    def test_write_removes_grouplength(self):
        ds = dcmread(color_pl_name)
        assert 0x00080000 in ds
        ds.save_as(self.file_out)
        self.file_out.seek(0)
        ds = dcmread(self.file_out)
        # group length has been removed
        assert 0x00080000 not in ds

    def test_write_empty_sequence(self):
        """Make sure that empty sequence is correctly written."""
        # regression test for #1030
        ds = dcmread(get_testdata_file("test-SR.dcm"))
        ds.save_as(self.file_out)
        self.file_out.seek(0)
        ds = dcmread(self.file_out)
        assert ds.PerformedProcedureCodeSequence == []

    def test_write_deflated_retains_elements(self):
        """Read a Deflated Explicit VR Little Endian file, write it,
        and then read the output, to verify that the written file
        contains the same data.
        """
        original = dcmread(deflate_name)
        original.save_as(self.file_out)

        self.file_out.seek(0)
        rewritten = dcmread(self.file_out)

        assert as_assertable(rewritten) == as_assertable(original)

    def test_write_deflated_deflates_post_file_meta(self):
        """Read a Deflated Explicit VR Little Endian file, write it,
        and then check the bytes in the output, to verify that the
        written file is deflated past the file meta information.
        """
        original = dcmread(deflate_name)
        original.save_as(self.file_out)

        first_byte_past_file_meta = 0x14E
        with open(deflate_name, "rb") as original_file:
            original_file.seek(first_byte_past_file_meta)
            original_post_meta_file_bytes = original_file.read()
        unzipped_original = zlib.decompress(
            original_post_meta_file_bytes, -zlib.MAX_WBITS
        )

        self.file_out.seek(first_byte_past_file_meta)
        rewritten_post_meta_file_bytes = self.file_out.read()
        unzipped_rewritten = zlib.decompress(
            rewritten_post_meta_file_bytes, -zlib.MAX_WBITS
        )

        assert unzipped_rewritten == unzipped_original

    def test_write_dataset_without_encoding(self):
        """Test that write_dataset() raises if encoding not set."""
        msg = (
            "Unable to determine the encoding to use for writing the dataset, "
            "please set the file meta's Transfer Syntax UID or use the "
            "'implicit_vr' and 'little_endian' arguments"
        )
        with pytest.raises(ValueError, match=msg):
            dcmwrite(BytesIO(), Dataset())


class TestScratchWriteDateTime(TestWriteFile):
    """Write and reread simple or multi-value DA/DT/TM data elements"""

    def setup_method(self):
        config.datetime_conversion = True
        self.file_out = TemporaryFile("w+b")

    def teardown_method(self):
        config.datetime_conversion = False
        self.file_out.close()

    def test_multivalue_DA(self):
        """Write DA/DT/TM data elements.........."""
        multi_DA_expected = (date(1961, 8, 4), date(1963, 11, 22))
        DA_expected = date(1961, 8, 4)
        tzinfo = timezone(timedelta(seconds=-21600), "-0600")
        multi_DT_expected = (
            datetime(1961, 8, 4),
            datetime(1963, 11, 22, 12, 30, 0, 0, tzinfo),
        )
        multi_TM_expected = (time(1, 23, 45), time(11, 11, 11))
        TM_expected = time(11, 11, 11, 1)
        ds = dcmread(datetime_name)
        # Add date/time data elements
        ds.CalibrationDate = MultiValue(DA, multi_DA_expected)
        ds.DateOfLastCalibration = DA(DA_expected)
        ds.ReferencedDateTime = MultiValue(DT, multi_DT_expected)
        ds.CalibrationTime = MultiValue(TM, multi_TM_expected)
        ds.TimeOfLastCalibration = TM(TM_expected)
        ds.save_as(self.file_out)
        self.file_out.seek(0)
        # Now read it back in and check the values are as expected
        ds = dcmread(self.file_out)
        assert all([a == b for a, b in zip(ds.CalibrationDate, multi_DA_expected)])
        assert DA_expected == ds.DateOfLastCalibration
        assert all([a == b for a, b in zip(ds.ReferencedDateTime, multi_DT_expected)])
        assert all([a == b for a, b in zip(ds.CalibrationTime, multi_TM_expected)])
        assert TM_expected == ds.TimeOfLastCalibration


class TestWriteDataElement:
    """Attempt to write data elements has the expected behaviour"""

    def setup_method(self):
        # Create a dummy (in memory) file to write to
        self.f1 = DicomBytesIO()
        self.f1.is_little_endian = True
        self.f1.is_implicit_VR = True

    @staticmethod
    def encode_element(elem, is_implicit_VR=True, is_little_endian=True):
        """Return the encoded `elem`.

        Parameters
        ----------
        elem : pydicom.dataelem.DataElement
            The element to encode
        is_implicit_VR : bool
            Encode using implicit VR, default True
        is_little_endian : bool
            Encode using little endian, default True

        Returns
        -------
        str or bytes
            The encoded element as str (python2) or bytes (python3)
        """
        with DicomBytesIO() as fp:
            fp.is_implicit_VR = is_implicit_VR
            fp.is_little_endian = is_little_endian
            write_data_element(fp, elem)
            return fp.getvalue()

    def test_empty_AT(self):
        """Write empty AT correctly.........."""
        # Was issue 74
        data_elem = DataElement(0x00280009, "AT", [])
        expected = hex2bytes(
            " 28 00 09 00"  # (0028,0009) Frame Increment Pointer
            " 00 00 00 00"  # length 0
        )
        write_data_element(self.f1, data_elem)
        assert expected == self.f1.getvalue()

    def check_data_element(self, data_elem, expected):
        encoded_elem = self.encode_element(data_elem)
        assert expected == encoded_elem

    def test_write_empty_LO(self):
        data_elem = DataElement(0x00080070, "LO", None)
        expected = b"\x08\x00\x70\x00\x00\x00\x00\x00"  # tag  # length  # value
        self.check_data_element(data_elem, expected)

    def test_write_DA(self):
        data_elem = DataElement(0x00080022, "DA", "20000101")
        expected = (
            b"\x08\x00\x22\x00"  # tag
            b"\x08\x00\x00\x00"  # length
            b"20000101"
        )  # value
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x00080022, "DA", date(2000, 1, 1))
        self.check_data_element(data_elem, expected)

    def test_write_multi_DA(self):
        data_elem = DataElement(0x0014407E, "DA", ["20100101", b"20101231"])
        expected = (
            b"\x14\x00\x7E\x40"  # tag
            b"\x12\x00\x00\x00"  # length
            b"20100101\\20101231 "
        )  # padded value
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(
            0x0014407E, "DA", [date(2010, 1, 1), date(2010, 12, 31)]
        )
        self.check_data_element(data_elem, expected)

    def test_write_TM(self):
        data_elem = DataElement(0x00080030, "TM", "010203")
        expected = (
            b"\x08\x00\x30\x00"  # tag
            b"\x06\x00\x00\x00"  # length
            b"010203"
        )  # padded value
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x00080030, "TM", b"010203")
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x00080030, "TM", time(1, 2, 3))
        self.check_data_element(data_elem, expected)

    def test_write_multi_TM(self):
        data_elem = DataElement(0x0014407C, "TM", ["082500", b"092655"])
        expected = (
            b"\x14\x00\x7C\x40"  # tag
            b"\x0E\x00\x00\x00"  # length
            b"082500\\092655 "
        )  # padded value
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x0014407C, "TM", [time(8, 25), time(9, 26, 55)])
        self.check_data_element(data_elem, expected)

    def test_write_DT(self):
        data_elem = DataElement(0x0008002A, "DT", "20170101120000")
        expected = (
            b"\x08\x00\x2A\x00"  # tag
            b"\x0E\x00\x00\x00"  # length
            b"20170101120000"
        )  # value
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x0008002A, "DT", b"20170101120000")
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x0008002A, "DT", datetime(2017, 1, 1, 12))
        self.check_data_element(data_elem, expected)

    def test_write_multi_DT(self):
        data_elem = DataElement(0x0040A13A, "DT", ["20120820120804", b"20130901111111"])
        expected = (
            b"\x40\x00\x3A\xA1"  # tag
            b"\x1E\x00\x00\x00"  # length
            b"20120820120804\\20130901111111 "
        )  # padded value
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x0040A13A, "DT", "20120820120804\\20130901111111")
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x0040A13A, "DT", b"20120820120804\\20130901111111")
        self.check_data_element(data_elem, expected)

        data_elem = DataElement(
            0x0040A13A,
            "DT",
            [datetime(2012, 8, 20, 12, 8, 4), datetime(2013, 9, 1, 11, 11, 11)],
        )
        self.check_data_element(data_elem, expected)

    def test_write_ascii_vr_with_padding(self):
        expected = (
            b"\x08\x00\x54\x00"  # tag
            b"\x0C\x00\x00\x00"  # length
            b"CONQUESTSRV "
        )  # padded value
        data_elem = DataElement(0x00080054, "AE", "CONQUESTSRV")
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x00080054, "AE", b"CONQUESTSRV")
        self.check_data_element(data_elem, expected)

        expected = (
            b"\x08\x00\x62\x00"  # tag
            b"\x06\x00\x00\x00"  # length
            b"1.2.3\x00"
        )  # padded value
        data_elem = DataElement(0x00080062, "UI", "1.2.3")
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x00080062, "UI", b"1.2.3")
        self.check_data_element(data_elem, expected)

        expected = b"\x08\x00\x60\x00\x04\x00\x00\x00REG "  # tag  # length
        data_elem = DataElement(0x00080060, "CS", "REG")
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x00080060, "CS", b"REG")
        self.check_data_element(data_elem, expected)

    def test_write_OB_odd(self):
        """Test an odd-length OB element is padded during write"""
        value = b"\x00\x01\x02"
        elem = DataElement(0x7FE00010, "OB", value)
        encoded_elem = self.encode_element(elem)
        ref_bytes = b"\xe0\x7f\x10\x00\x04\x00\x00\x00" + value + b"\x00"
        assert ref_bytes == encoded_elem

        # Empty data
        elem.value = b""
        encoded_elem = self.encode_element(elem)
        ref_bytes = b"\xe0\x7f\x10\x00\x00\x00\x00\x00"
        assert ref_bytes == encoded_elem

    def test_write_OD_implicit_little(self):
        """Test writing elements with VR of OD works correctly."""
        # VolumetricCurvePoints
        bytestring = b"\x00\x01\x02\x03\x04\x05\x06\x07\x01\x01\x02\x03\x04\x05\x06\x07"
        elem = DataElement(0x0070150D, "OD", bytestring)
        encoded_elem = self.encode_element(elem)
        # Tag pair (0070,150D): 70 00 0d 15
        # Length (16): 10 00 00 00
        #             | Tag          |   Length      |    Value ->
        ref_bytes = b"\x70\x00\x0d\x15\x10\x00\x00\x00" + bytestring
        assert ref_bytes == encoded_elem

        # Empty data
        elem.value = b""
        encoded_elem = self.encode_element(elem)
        ref_bytes = b"\x70\x00\x0d\x15\x00\x00\x00\x00"
        assert ref_bytes == encoded_elem

    def test_write_OD_explicit_little(self):
        """Test writing elements with VR of OD works correctly.

        Elements with a VR of 'OD' use the newer explicit VR
        encoding (see PS3.5 Section 7.1.2).
        """
        # VolumetricCurvePoints
        bytestring = b"\x00\x01\x02\x03\x04\x05\x06\x07\x01\x01\x02\x03\x04\x05\x06\x07"
        elem = DataElement(0x0070150D, "OD", bytestring)
        encoded_elem = self.encode_element(elem, False, True)
        # Tag pair (0070,150D): 70 00 0d 15
        # VR (OD): \x4f\x44
        # Reserved: \x00\x00
        # Length (16): \x10\x00\x00\x00
        #             | Tag          | VR    |
        ref_bytes = b"\x70\x00\x0d\x15\x4f\x44\x00\x00\x10\x00\x00\x00" + bytestring
        #             |Rsrvd |   Length      |    Value ->
        assert ref_bytes == encoded_elem

        # Empty data
        elem.value = b""
        encoded_elem = self.encode_element(elem, False, True)
        ref_bytes = b"\x70\x00\x0d\x15\x4f\x44\x00\x00\x00\x00\x00\x00"
        assert ref_bytes == encoded_elem

    def test_write_OL_implicit_little(self):
        """Test writing elements with VR of OL works correctly."""
        # TrackPointIndexList
        bytestring = b"\x00\x01\x02\x03\x04\x05\x06\x07\x01\x01\x02\x03"
        elem = DataElement(0x00660129, "OL", bytestring)
        encoded_elem = self.encode_element(elem)
        # Tag pair (0066,0129): 66 00 29 01
        # Length (12): 0c 00 00 00
        #             | Tag          |   Length      |    Value ->
        ref_bytes = b"\x66\x00\x29\x01\x0c\x00\x00\x00" + bytestring
        assert ref_bytes == encoded_elem

        # Empty data
        elem.value = b""
        encoded_elem = self.encode_element(elem)
        ref_bytes = b"\x66\x00\x29\x01\x00\x00\x00\x00"
        assert ref_bytes == encoded_elem

    def test_write_OL_explicit_little(self):
        """Test writing elements with VR of OL works correctly.

        Elements with a VR of 'OL' use the newer explicit VR
        encoding (see PS3.5 Section 7.1.2).
        """
        # TrackPointIndexList
        bytestring = b"\x00\x01\x02\x03\x04\x05\x06\x07\x01\x01\x02\x03"
        elem = DataElement(0x00660129, "OL", bytestring)
        encoded_elem = self.encode_element(elem, False, True)
        # Tag pair (0066,0129): 66 00 29 01
        # VR (OL): \x4f\x4c
        # Reserved: \x00\x00
        # Length (12): 0c 00 00 00
        #             | Tag          | VR    |
        ref_bytes = b"\x66\x00\x29\x01\x4f\x4c\x00\x00\x0c\x00\x00\x00" + bytestring
        #             |Rsrvd |   Length      |    Value ->
        assert ref_bytes == encoded_elem

        # Empty data
        elem.value = b""
        encoded_elem = self.encode_element(elem, False, True)
        ref_bytes = b"\x66\x00\x29\x01\x4f\x4c\x00\x00\x00\x00\x00\x00"
        assert ref_bytes == encoded_elem

    def test_write_UC_implicit_little(self):
        """Test writing elements with VR of UC works correctly."""
        # VM 1, even data
        elem = DataElement(0x00189908, "UC", "Test")
        encoded_elem = self.encode_element(elem)
        # Tag pair (0018,9908): 08 00 20 01
        # Length (4): 04 00 00 00
        # Value: \x54\x65\x73\x74
        ref_bytes = b"\x18\x00\x08\x99\x04\x00\x00\x00\x54\x65\x73\x74"
        assert ref_bytes == encoded_elem

        # VM 1, odd data - padded to even length
        elem.value = "Test."
        encoded_elem = self.encode_element(elem)
        ref_bytes = b"\x18\x00\x08\x99\x06\x00\x00\x00\x54\x65\x73\x74\x2e\x20"
        assert ref_bytes == encoded_elem

        # VM 3, even data
        elem.value = ["Aa", "B", "C"]
        encoded_elem = self.encode_element(elem)
        ref_bytes = b"\x18\x00\x08\x99\x06\x00\x00\x00\x41\x61\x5c\x42\x5c\x43"
        assert ref_bytes == encoded_elem

        # VM 3, odd data - padded to even length
        elem.value = ["A", "B", "C"]
        encoded_elem = self.encode_element(elem)
        ref_bytes = b"\x18\x00\x08\x99\x06\x00\x00\x00\x41\x5c\x42\x5c\x43\x20"
        assert ref_bytes == encoded_elem

        # Empty data
        elem.value = ""
        encoded_elem = self.encode_element(elem)
        ref_bytes = b"\x18\x00\x08\x99\x00\x00\x00\x00"
        assert ref_bytes == encoded_elem

    def test_write_UC_explicit_little(self):
        """Test writing elements with VR of UC works correctly.

        Elements with a VR of 'UC' use the newer explicit VR
        encoding (see PS3.5 Section 7.1.2).
        """
        # VM 1, even data
        elem = DataElement(0x00189908, "UC", "Test")
        encoded_elem = self.encode_element(elem, False, True)
        # Tag pair (0018,9908): 08 00 20 01
        # VR (UC): \x55\x43
        # Reserved: \x00\x00
        # Length (4): \x04\x00\x00\x00
        # Value: \x54\x65\x73\x74
        ref_bytes = b"\x18\x00\x08\x99\x55\x43\x00\x00\x04\x00\x00\x00\x54\x65\x73\x74"
        assert ref_bytes == encoded_elem

        # VM 1, odd data - padded to even length
        elem.value = "Test."
        encoded_elem = self.encode_element(elem, False, True)
        ref_bytes = (
            b"\x18\x00\x08\x99\x55\x43\x00\x00\x06\x00\x00\x00"
            b"\x54\x65\x73\x74\x2e\x20"
        )
        assert ref_bytes == encoded_elem

        # VM 3, even data
        elem.value = ["Aa", "B", "C"]
        encoded_elem = self.encode_element(elem, False, True)
        ref_bytes = (
            b"\x18\x00\x08\x99\x55\x43\x00\x00\x06\x00\x00\x00"
            b"\x41\x61\x5c\x42\x5c\x43"
        )
        assert ref_bytes == encoded_elem

        # VM 3, odd data - padded to even length
        elem.value = ["A", "B", "C"]
        encoded_elem = self.encode_element(elem, False, True)
        ref_bytes = (
            b"\x18\x00\x08\x99\x55\x43\x00\x00\x06\x00\x00\x00"
            b"\x41\x5c\x42\x5c\x43\x20"
        )
        assert ref_bytes == encoded_elem

        # Empty data
        elem.value = ""
        encoded_elem = self.encode_element(elem, False, True)
        ref_bytes = b"\x18\x00\x08\x99\x55\x43\x00\x00\x00\x00\x00\x00"
        assert ref_bytes == encoded_elem

    def test_write_UR_implicit_little(self):
        """Test writing elements with VR of UR works correctly."""
        # Even length URL
        elem = DataElement(0x00080120, "UR", "http://github.com/darcymason/pydicom")
        encoded_elem = self.encode_element(elem)
        # Tag pair (0008,2001): 08 00 20 01
        # Length (36): 24 00 00 00
        # Value: 68 to 6d
        ref_bytes = (
            b"\x08\x00\x20\x01\x24\x00\x00\x00\x68\x74"
            b"\x74\x70\x3a\x2f\x2f\x67\x69\x74\x68\x75"
            b"\x62\x2e\x63\x6f\x6d\x2f\x64\x61\x72\x63"
            b"\x79\x6d\x61\x73\x6f\x6e\x2f\x70\x79\x64"
            b"\x69\x63\x6f\x6d"
        )
        assert ref_bytes == encoded_elem

        # Odd length URL has trailing \x20 (SPACE) padding
        elem.value = "../test/test.py"
        encoded_elem = self.encode_element(elem)
        # Tag pair (0008,2001): 08 00 20 01
        # Length (16): 10 00 00 00
        # Value: 2e to 20
        ref_bytes = (
            b"\x08\x00\x20\x01\x10\x00\x00\x00\x2e\x2e"
            b"\x2f\x74\x65\x73\x74\x2f\x74\x65\x73\x74"
            b"\x2e\x70\x79\x20"
        )
        assert ref_bytes == encoded_elem

        # Empty value
        elem.value = ""
        encoded_elem = self.encode_element(elem)
        assert b"\x08\x00\x20\x01\x00\x00\x00\x00" == encoded_elem

    def test_write_UR_explicit_little(self):
        """Test writing elements with VR of UR works correctly.

        Elements with a VR of 'UR' use the newer explicit VR
        encoded (see PS3.5 Section 7.1.2).
        """
        # Even length URL
        elem = DataElement(0x00080120, "UR", "ftp://bits")
        encoded_elem = self.encode_element(elem, False, True)
        # Tag pair (0008,2001): 08 00 20 01
        # VR (UR): \x55\x52
        # Reserved: \x00\x00
        # Length (4): \x0a\x00\x00\x00
        # Value: \x66\x74\x70\x3a\x2f\x2f\x62\x69\x74\x73
        ref_bytes = (
            b"\x08\x00\x20\x01\x55\x52\x00\x00\x0a\x00\x00\x00"
            b"\x66\x74\x70\x3a\x2f\x2f\x62\x69\x74\x73"
        )
        assert ref_bytes == encoded_elem

        # Odd length URL has trailing \x20 (SPACE) padding
        elem.value = "ftp://bit"
        encoded_elem = self.encode_element(elem, False, True)
        ref_bytes = (
            b"\x08\x00\x20\x01\x55\x52\x00\x00\x0a\x00\x00\x00"
            b"\x66\x74\x70\x3a\x2f\x2f\x62\x69\x74\x20"
        )
        assert ref_bytes == encoded_elem

        # Empty value
        elem.value = ""
        encoded_elem = self.encode_element(elem, False, True)
        ref_bytes = b"\x08\x00\x20\x01\x55\x52\x00\x00\x00\x00\x00\x00"
        assert ref_bytes == encoded_elem

    def test_write_UN_implicit_little(self):
        """Test writing UN VR in implicit little"""
        elem = DataElement(0x00100010, "UN", b"\x01\x02")
        assert self.encode_element(elem) == (
            b"\x10\x00\x10\x00\x02\x00\x00\x00\x01\x02"
        )

    def test_write_unknown_vr_raises(self):
        """Test exception raised trying to write unknown VR element"""
        fp = DicomBytesIO()
        fp.is_implicit_VR = True
        fp.is_little_endian = True
        elem = DataElement(0x00100010, "ZZ", "Test")
        with pytest.raises(
            NotImplementedError,
            match="write_data_element: unknown Value Representation 'ZZ'",
        ):
            write_data_element(fp, elem)


class TestCorrectAmbiguousVR:
    """Test correct_ambiguous_vr."""

    def test_pixel_representation_vm_one(self):
        """Test correcting VM 1 elements which require PixelRepresentation."""
        ref_ds = Dataset()

        # If PixelRepresentation is 0 then VR should be US
        ref_ds.PixelRepresentation = 0
        ref_ds.SmallestValidPixelValue = b"\x00\x01"  # Little endian 256
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        assert 256 == ds.SmallestValidPixelValue
        assert "US" == ds[0x00280104].VR

        # If PixelRepresentation is 1 then VR should be SS
        ref_ds.PixelRepresentation = 1
        ref_ds.SmallestValidPixelValue = b"\x00\x01"  # Big endian 1
        ds = correct_ambiguous_vr(deepcopy(ref_ds), False)
        assert 1 == ds.SmallestValidPixelValue
        assert "SS" == ds[0x00280104].VR

        # If no PixelRepresentation and no PixelData is present 'US' is set
        ref_ds = Dataset()
        ref_ds.SmallestValidPixelValue = b"\x00\x01"  # Big endian 1
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        assert "US" == ds[0x00280104].VR

        # If no PixelRepresentation but PixelData is present
        # AttributeError shall be raised
        ref_ds.PixelData = b"123"
        with pytest.raises(
            AttributeError,
            match=r"Failed to resolve ambiguous VR for tag "
            r"\(0028,0104\):.* 'PixelRepresentation'",
        ):
            correct_ambiguous_vr(deepcopy(ref_ds), True)

    def test_pixel_representation_vm_three(self):
        """Test correcting VM 3 elements which require PixelRepresentation."""
        ref_ds = Dataset()

        # If PixelRepresentation is 0 then VR should be US - Little endian
        ref_ds.PixelRepresentation = 0
        ref_ds.LUTDescriptor = b"\x01\x00\x00\x01\x10\x00"  # 1\256\16
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        assert [1, 256, 16] == ds.LUTDescriptor
        assert "US" == ds[0x00283002].VR

        # If PixelRepresentation is 1 then VR should be SS
        ref_ds.PixelRepresentation = 1
        ref_ds.LUTDescriptor = b"\x01\x00\x00\x01\x00\x10"
        ds = correct_ambiguous_vr(deepcopy(ref_ds), False)
        assert [256, 1, 16] == ds.LUTDescriptor
        assert "SS" == ds[0x00283002].VR

        # If no PixelRepresentation and no PixelData is present 'US' is set
        ref_ds = Dataset()
        ref_ds.LUTDescriptor = b"\x01\x00\x00\x01\x00\x10"
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        assert "US" == ds[0x00283002].VR

        # If no PixelRepresentation AttributeError shall be raised
        ref_ds.PixelData = b"123"
        with pytest.raises(
            AttributeError,
            match=r"Failed to resolve ambiguous VR for tag "
            r"\(0028,3002\):.* 'PixelRepresentation'",
        ):
            correct_ambiguous_vr(deepcopy(ref_ds), False)

    def test_pixel_data(self):
        """Test correcting PixelData."""
        ref_ds = Dataset()

        # If BitsAllocated  > 8 then VR must be OW
        ref_ds.BitsAllocated = 16
        ref_ds.PixelData = b"\x00\x01"  # Little endian 256
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)  # Little endian
        assert b"\x00\x01" == ds.PixelData
        assert "OW" == ds[0x7FE00010].VR
        ds = correct_ambiguous_vr(deepcopy(ref_ds), False)  # Big endian
        assert b"\x00\x01" == ds.PixelData
        assert "OW" == ds[0x7FE00010].VR

        # If BitsAllocated <= 8 then VR can be OB or OW: we set it to OB
        ref_ds = Dataset()
        ref_ds.BitsAllocated = 8
        ref_ds.Rows = 2
        ref_ds.Columns = 2
        ref_ds.PixelData = b"\x01\x00\x02\x00\x03\x00\x04\x00"
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        assert b"\x01\x00\x02\x00\x03\x00\x04\x00" == ds.PixelData
        assert "OB" == ds[0x7FE00010].VR

        # If no BitsAllocated set then AttributesError is raised
        ref_ds = Dataset()
        ref_ds.PixelData = b"\x00\x01"  # Big endian 1
        with pytest.raises(
            AttributeError,
            match=r"Failed to resolve ambiguous VR for tag "
            r"\(7FE0,0010\):.* 'BitsAllocated'",
        ):
            correct_ambiguous_vr(deepcopy(ref_ds), True)

    def test_waveform_bits_allocated(self):
        """Test correcting elements which require WaveformBitsAllocated."""
        ref_ds = Dataset()
        ref_ds.set_original_encoding(False, True)

        # If WaveformBitsAllocated  > 8 then VR must be OW
        ref_ds.WaveformBitsAllocated = 16
        ref_ds.WaveformData = b"\x00\x01"  # Little endian 256
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)  # Little endian
        assert b"\x00\x01" == ds.WaveformData
        assert "OW" == ds[0x54001010].VR
        ds = correct_ambiguous_vr(deepcopy(ref_ds), False)  # Big endian
        assert b"\x00\x01" == ds.WaveformData
        assert "OW" == ds[0x54001010].VR

        # If WaveformBitsAllocated == 8 then VR is OB or OW - set it to OB
        ref_ds.WaveformBitsAllocated = 8
        ref_ds.WaveformData = b"\x01\x02"
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        assert b"\x01\x02" == ds.WaveformData
        assert "OB" == ds[0x54001010].VR

        # For implicit VR, VR is always OW
        ref_ds.set_original_encoding(True, True)
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        assert b"\x01\x02" == ds.WaveformData
        assert "OW" == ds[0x54001010].VR
        ref_ds.set_original_encoding(False, True)

        # If no WaveformBitsAllocated then AttributeError shall be raised
        ref_ds = Dataset()
        ref_ds.WaveformData = b"\x00\x01"  # Big endian 1
        with pytest.raises(
            AttributeError,
            match=r"Failed to resolve ambiguous VR for tag "
            r"\(5400,1010\):.* 'WaveformBitsAllocated'",
        ):
            correct_ambiguous_vr(deepcopy(ref_ds), True)

    def test_lut_descriptor(self):
        """Test correcting elements which require LUTDescriptor."""
        ref_ds = Dataset()
        ref_ds.PixelRepresentation = 0

        # If LUTDescriptor[0] is 1 then LUTData VR is 'US'
        ref_ds.LUTDescriptor = b"\x01\x00\x00\x01\x10\x00"  # 1\256\16
        ref_ds.LUTData = b"\x00\x01"  # Little endian 256
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)  # Little endian
        assert 1 == ds.LUTDescriptor[0]
        assert "US" == ds[0x00283002].VR
        assert 256 == ds.LUTData
        assert "US" == ds[0x00283006].VR

        # If LUTDescriptor[0] is not 1 then LUTData VR is 'OW'
        ref_ds.LUTDescriptor = b"\x02\x00\x00\x01\x10\x00"  # 2\256\16
        ref_ds.LUTData = b"\x00\x01\x00\x02"
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)  # Little endian
        assert 2 == ds.LUTDescriptor[0]
        assert "US" == ds[0x00283002].VR
        assert b"\x00\x01\x00\x02" == ds.LUTData
        assert "OW" == ds[0x00283006].VR

        # If no LUTDescriptor then raise AttributeError
        ref_ds = Dataset()
        ref_ds.LUTData = b"\x00\x01"
        with pytest.raises(
            AttributeError,
            match=r"Failed to resolve ambiguous VR for tag "
            r"\(0028,3006\):.* 'LUTDescriptor'",
        ):
            correct_ambiguous_vr(deepcopy(ref_ds), True)

    def test_overlay(self):
        """Test correcting OverlayData"""
        # VR must be 'OW'
        ref_ds = Dataset()
        ref_ds.set_original_encoding(True, True)
        ref_ds.add(DataElement(0x60003000, "OB or OW", b"\x00"))
        ref_ds.add(DataElement(0x601E3000, "OB or OW", b"\x00"))
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        assert "OW" == ds[0x60003000].VR
        assert "OW" == ds[0x601E3000].VR
        assert "OB or OW" == ref_ds[0x60003000].VR
        assert "OB or OW" == ref_ds[0x601E3000].VR

        ref_ds.set_original_encoding(False, True)
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        assert "OW" == ds[0x60003000].VR
        assert "OB or OW" == ref_ds[0x60003000].VR

    def test_sequence(self):
        """Test correcting elements in a sequence."""
        ref_ds = Dataset()
        ref_ds.BeamSequence = [Dataset()]
        ref_ds.BeamSequence[0].PixelRepresentation = 0
        ref_ds.BeamSequence[0].SmallestValidPixelValue = b"\x00\x01"
        ref_ds.BeamSequence[0].BeamSequence = [Dataset()]

        ref_ds.BeamSequence[0].BeamSequence[0].PixelRepresentation = 0
        ref_ds.BeamSequence[0].BeamSequence[0].SmallestValidPixelValue = b"\x00\x01"

        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        assert ds.BeamSequence[0].SmallestValidPixelValue == 256
        assert ds.BeamSequence[0][0x00280104].VR == "US"
        assert ds.BeamSequence[0].BeamSequence[0].SmallestValidPixelValue == 256
        assert ds.BeamSequence[0].BeamSequence[0][0x00280104].VR == "US"

    def test_write_new_ambiguous(self):
        """Regression test for #781"""
        ds = Dataset()
        ds.SmallestImagePixelValue = 0
        assert ds[0x00280106].VR == "US or SS"
        ds.PixelRepresentation = 0
        ds.LUTDescriptor = [1, 0]
        assert ds[0x00283002].VR == "US or SS"
        ds.LUTData = 0
        assert ds[0x00283006].VR == "US or OW"
        ds.save_as(DicomBytesIO(), implicit_vr=True)

        assert ds[0x00280106].VR == "US"
        assert ds.SmallestImagePixelValue == 0
        assert ds[0x00283006].VR == "US"
        assert ds.LUTData == 0
        assert ds[0x00283002].VR == "US"
        assert ds.LUTDescriptor == [1, 0]

    def dataset_with_modality_lut_sequence(self, pixel_repr):
        ds = Dataset()
        ds.PixelRepresentation = pixel_repr
        ds.ModalityLUTSequence = [Dataset()]
        ds.ModalityLUTSequence[0].LUTDescriptor = [0, 0, 16]
        ds.ModalityLUTSequence[0].LUTExplanation = None
        ds.ModalityLUTSequence[0].ModalityLUTType = "US"  # US = unspecified
        ds.ModalityLUTSequence[0].LUTData = b"\x0000\x149a\x1f1c\xc2637"
        return ds

    def test_ambiguous_element_in_sequence_explicit_using_attribute(self):
        """Test that writing a sequence with an ambiguous element
        as explicit transfer syntax works if accessing the tag via keyword."""
        # regression test for #804
        ds = self.dataset_with_modality_lut_sequence(pixel_repr=0)
        fp = BytesIO()
        ds.save_as(fp, implicit_vr=False)
        ds = dcmread(fp, force=True)
        assert "US" == ds.ModalityLUTSequence[0][0x00283002].VR

        ds = self.dataset_with_modality_lut_sequence(pixel_repr=1)
        fp = BytesIO()
        ds.save_as(fp, implicit_vr=False)
        ds = dcmread(fp, force=True)
        assert "SS" == ds.ModalityLUTSequence[0][0x00283002].VR

    def test_ambiguous_element_in_sequence_explicit_using_index(self):
        """Test that writing a sequence with an ambiguous element
        as explicit transfer syntax works if accessing the tag
        via the tag number."""
        ds = self.dataset_with_modality_lut_sequence(pixel_repr=0)
        fp = BytesIO()
        ds.save_as(fp, implicit_vr=False)
        ds = dcmread(fp, force=True)
        assert "US" == ds[0x00283000][0][0x00283002].VR

        ds = self.dataset_with_modality_lut_sequence(pixel_repr=1)
        fp = BytesIO()
        ds.save_as(fp, implicit_vr=False)
        ds = dcmread(fp, force=True)
        assert "SS" == ds[0x00283000][0][0x00283002].VR

    def test_ambiguous_element_in_sequence_implicit_using_attribute(self):
        """Test that reading a sequence with an ambiguous element
        from a file with implicit transfer syntax works if accessing the
        tag via keyword."""
        # regression test for #804
        ds = self.dataset_with_modality_lut_sequence(pixel_repr=0)
        fp = BytesIO()
        ds.save_as(fp, implicit_vr=True)
        ds = dcmread(fp, force=True)
        assert "US" == ds.ModalityLUTSequence[0][0x00283002].VR

        ds = self.dataset_with_modality_lut_sequence(pixel_repr=1)
        fp = BytesIO()
        ds.save_as(fp, implicit_vr=True)
        ds = dcmread(fp, force=True)
        assert "SS" == ds.ModalityLUTSequence[0][0x00283002].VR

    def test_ambiguous_element_in_sequence_implicit_using_index(self):
        """Test that reading a sequence with an ambiguous element
        from a file with implicit transfer syntax works if accessing the tag
        via the tag number."""
        ds = self.dataset_with_modality_lut_sequence(pixel_repr=0)
        fp = BytesIO()
        ds.save_as(fp, implicit_vr=True)
        ds = dcmread(fp, force=True)
        assert "US" == ds[0x00283000][0][0x00283002].VR

        ds = self.dataset_with_modality_lut_sequence(pixel_repr=1)
        fp = BytesIO()
        ds.save_as(fp, implicit_vr=True)
        ds = dcmread(fp, force=True)
        assert "SS" == ds[0x00283000][0][0x00283002].VR

    def test_ambiguous_element_sequence_implicit_nearest(self):
        """Test that the nearest dataset with pixel rep to the ambiguous
        element is used for correction.
        """
        ds = self.dataset_with_modality_lut_sequence(pixel_repr=0)
        ds.ModalityLUTSequence[0].PixelRepresentation = 1
        fp = BytesIO()
        ds.save_as(fp, implicit_vr=True)
        ds = dcmread(fp, force=True)
        assert "SS" == ds[0x00283000][0][0x00283002].VR

        ds = self.dataset_with_modality_lut_sequence(pixel_repr=1)
        ds.ModalityLUTSequence[0].PixelRepresentation = 0
        fp = BytesIO()
        ds.save_as(fp, implicit_vr=True)
        ds = dcmread(fp, force=True)
        assert "US" == ds[0x00283000][0][0x00283002].VR

    def test_ambiguous_element_sequence_explicit_nearest(self):
        """Test that the nearest dataset with pixel rep to the ambiguous
        element is used for correction.
        """
        ds = self.dataset_with_modality_lut_sequence(pixel_repr=0)
        ds.ModalityLUTSequence[0].PixelRepresentation = 1
        fp = BytesIO()
        ds.save_as(fp, implicit_vr=False)
        ds = dcmread(fp, force=True)
        assert "SS" == ds[0x00283000][0][0x00283002].VR

        ds = self.dataset_with_modality_lut_sequence(pixel_repr=1)
        ds.ModalityLUTSequence[0].PixelRepresentation = 0
        fp = BytesIO()
        ds.save_as(fp, implicit_vr=False)
        ds = dcmread(fp, force=True)
        assert "US" == ds[0x00283000][0][0x00283002].VR

    def test_pickle_deepcopy_implicit(self):
        """Test we can correct VR after pickling and deepcopy."""
        ds = self.dataset_with_modality_lut_sequence(pixel_repr=0)
        fp = BytesIO()
        ds.save_as(fp, implicit_vr=True)
        ds = dcmread(fp, force=True)
        ds.filename = None

        ds2 = deepcopy(ds)

        s = pickle.dumps({"ds": ds})
        ds = pickle.loads(s)["ds"]

        assert "US" == ds[0x00283000][0][0x00283002].VR
        assert "US" == ds2[0x00283000][0][0x00283002].VR

        ds = self.dataset_with_modality_lut_sequence(pixel_repr=1)
        fp = BytesIO()
        ds.save_as(fp, implicit_vr=True)
        ds = dcmread(fp, force=True)
        ds.filename = None

        ds2 = deepcopy(ds)

        s = pickle.dumps({"ds": ds})
        ds = pickle.loads(s)["ds"]

        assert "SS" == ds[0x00283000][0][0x00283002].VR
        assert "SS" == ds2[0x00283000][0][0x00283002].VR

    def test_pickle_deepcopy_explicit(self):
        """Test we can correct VR after pickling and deepcopy."""
        ds = self.dataset_with_modality_lut_sequence(pixel_repr=0)
        fp = BytesIO()
        ds.save_as(fp, implicit_vr=False)
        ds = dcmread(fp, force=True)
        ds.filename = None

        ds2 = deepcopy(ds)

        s = pickle.dumps({"ds": ds})
        ds = pickle.loads(s)["ds"]

        assert "US" == ds[0x00283000][0][0x00283002].VR
        assert "US" == ds2[0x00283000][0][0x00283002].VR

        ds = self.dataset_with_modality_lut_sequence(pixel_repr=1)
        fp = BytesIO()
        ds.save_as(fp, implicit_vr=False)
        ds = dcmread(fp, force=True)
        ds.filename = None

        ds2 = deepcopy(ds)

        s = pickle.dumps({"ds": ds})
        ds = pickle.loads(s)["ds"]

        assert "SS" == ds[0x00283000][0][0x00283002].VR
        assert "SS" == ds2[0x00283000][0][0x00283002].VR

    def test_parent_change_implicit(self):
        """Test ambiguous VR correction when parent is changed."""
        ds = Dataset()
        ds.PixelRepresentation = 0
        ds.BeamSequence = [Dataset()]
        # Nesting Modality LUT Sequence to avoid raw -> elem conversion
        seq = ds.BeamSequence[0]
        seq.ModalityLUTSequence = [Dataset()]
        seq.ModalityLUTSequence[0].LUTDescriptor = [0, 0, 16]
        seq.ModalityLUTSequence[0].LUTExplanation = None
        seq.ModalityLUTSequence[0].ModalityLUTType = "US"  # US = unspecified
        seq.ModalityLUTSequence[0].LUTData = b"\x0000\x149a\x1f1c\xc2637"

        fp = BytesIO()
        ds.save_as(fp, implicit_vr=True)
        ds = dcmread(fp, force=True)

        ds1 = dcmread(ct_name)
        ds1.PixelRepresentation = 1
        ds1.BeamSequence = ds.BeamSequence
        assert ds1._pixel_rep == 1
        assert ds1["BeamSequence"][0]._pixel_rep == 1
        assert isinstance(ds1.BeamSequence[0]._dict[0x00283000], RawDataElement)

        modality_seq = ds1.BeamSequence[0].ModalityLUTSequence
        assert modality_seq[0]._pixel_rep == 1
        assert "SS" == ds1.BeamSequence[0][0x00283000][0][0x00283002].VR

    def test_pixel_repr_none_in_nearer_implicit(self):
        """Test a pixel representation of None in a nearer dataset."""
        ds = self.dataset_with_modality_lut_sequence(0)
        ds.ModalityLUTSequence[0].PixelRepresentation = None

        fp = BytesIO()
        ds.save_as(fp, implicit_vr=True)
        ds = dcmread(fp, force=True)

        item = ds.ModalityLUTSequence[0]
        assert ds._pixel_rep == 0
        assert item._pixel_rep == 0
        assert "US" == item[0x00283002].VR

    def test_pixel_repr_none_in_further_implicit(self):
        """Test a pixel representation of None in a further dataset."""
        ds = self.dataset_with_modality_lut_sequence(None)
        ds.ModalityLUTSequence[0].PixelRepresentation = 0

        fp = BytesIO()
        ds.save_as(fp, implicit_vr=True)
        ds = dcmread(fp, force=True)

        item = ds.ModalityLUTSequence[0]
        assert not hasattr(ds, "_pixel_rep")
        assert item._pixel_rep == 0
        assert "US" == item[0x00283002].VR


class TestCorrectAmbiguousVRElement:
    """Test filewriter.correct_ambiguous_vr_element"""

    def test_not_ambiguous(self):
        """Test no change in element if not ambiguous"""
        elem = DataElement(0x60003000, "OB", b"\x00")
        out = correct_ambiguous_vr_element(elem, Dataset(), True)
        assert out.VR == "OB"
        assert out.tag == 0x60003000
        assert out.value == b"\x00"

    def test_not_ambiguous_raw_data_element(self):
        """Test no change in raw data element if not ambiguous"""
        elem = RawDataElement(0x60003000, "OB", 1, b"\x00", 0, True, True)
        out = correct_ambiguous_vr_element(elem, Dataset(), True)
        assert out == elem
        assert isinstance(out, RawDataElement)

    def test_correct_ambiguous_data_element(self):
        """Test correct ambiguous US/SS element"""
        ds = Dataset()
        ds.PixelPaddingValue = b"\xfe\xff"
        out = correct_ambiguous_vr_element(ds[0x00280120], ds, True)
        # assume US if PixelData is not set
        assert "US" == out.VR

        ds = Dataset()
        ds.PixelPaddingValue = b"\xfe\xff"
        ds.PixelData = b"3456"
        with pytest.raises(
            AttributeError,
            match=r"Failed to resolve ambiguous VR for tag "
            r"\(0028,0120\):.* 'PixelRepresentation'",
        ):
            correct_ambiguous_vr_element(ds[0x00280120], ds, True)

        ds.PixelRepresentation = 0
        out = correct_ambiguous_vr_element(ds[0x00280120], ds, True)
        assert out.VR == "US"
        assert out.value == 0xFFFE

    def test_correct_ambiguous_raw_data_element(self):
        """Test that correcting ambiguous US/SS raw data element
        works and converts it to a data element"""
        ds = Dataset()
        elem = RawDataElement(0x00280120, "US or SS", 2, b"\xfe\xff", 0, True, True)
        ds[0x00280120] = elem
        ds.PixelRepresentation = 0
        out = correct_ambiguous_vr_element(elem, ds, True)
        assert isinstance(out, DataElement)
        assert out.VR == "US"
        assert out.value == 0xFFFE

    def test_empty_value(self):
        """Regression test for #1193: empty value raises exception."""
        ds = Dataset()
        elem = RawDataElement(0x00280106, "US or SS", 0, None, 0, True, True)
        ds[0x00280106] = elem
        out = correct_ambiguous_vr_element(elem, ds, True)
        assert isinstance(out, DataElement)
        assert out.VR == "US"

        ds.LUTDescriptor = [1, 1, 1]
        elem = RawDataElement(0x00283006, "US or SS", 0, None, 0, True, True)
        assert out.value is None
        ds[0x00283006] = elem
        out = correct_ambiguous_vr_element(elem, ds, True)
        assert isinstance(out, DataElement)
        assert out.VR == "US"
        assert out.value is None


class TestWriteAmbiguousVR:
    """Attempt to write data elements with ambiguous VR."""

    def setup_method(self):
        # Create a dummy (in memory) file to write to
        self.fp = DicomBytesIO()
        self.fp.is_implicit_VR = False
        self.fp.is_little_endian = True

    def test_write_explicit_vr_raises(self):
        """Test writing explicit vr raises exception if unsolved element."""
        ds = Dataset()
        ds.PerimeterValue = b"\x00\x01"
        with pytest.raises(ValueError):
            write_dataset(self.fp, ds)

    def test_write_explicit_vr_little_endian(self):
        """Test writing explicit little data for ambiguous elements."""
        # Create a dataset containing element with ambiguous VRs
        ref_ds = Dataset()
        ref_ds.PixelRepresentation = 0
        ref_ds.SmallestValidPixelValue = b"\x00\x01"  # Little endian 256

        fp = BytesIO()
        file_ds = FileDataset(fp, ref_ds)
        file_ds.save_as(fp, implicit_vr=False)
        fp.seek(0)

        ds = read_dataset(fp, False, True, parent_encoding="latin1")
        assert 256 == ds.SmallestValidPixelValue
        assert "US" == ds[0x00280104].VR
        msg = "'Dataset.read_implicit_vr' will be removed in v4.0"
        with pytest.warns(DeprecationWarning, match=msg):
            assert not ds.read_implicit_vr

        msg = "'Dataset.read_little_endian' will be removed in v4.0"
        with pytest.warns(DeprecationWarning, match=msg):
            assert ds.read_little_endian

        msg = "'Dataset.read_encoding' will be removed in v4.0"
        with pytest.warns(DeprecationWarning, match=msg):
            assert ds.read_encoding == "latin1"

    def test_write_explicit_vr_big_endian(self):
        """Test writing explicit big data for ambiguous elements."""
        # Create a dataset containing element with ambiguous VRs
        ds = Dataset()
        ds.PixelRepresentation = 1
        ds.SmallestValidPixelValue = b"\x00\x01"  # Big endian 1
        ds.SpecificCharacterSet = b"ISO_IR 192"

        fp = BytesIO()
        ds.save_as(fp, implicit_vr=False, little_endian=False)
        fp.seek(0)

        ds = read_dataset(fp, False, False)
        assert 1 == ds.SmallestValidPixelValue
        assert "SS" == ds[0x00280104].VR
        with pytest.warns(DeprecationWarning):
            assert not ds.read_implicit_vr
            assert not ds.read_little_endian

        msg = "'Dataset.read_encoding' will be removed in v4.0"
        with pytest.warns(DeprecationWarning, match=msg):
            assert ["UTF8"] == ds.read_encoding


class TestScratchWrite:
    """Simple dataset from scratch, written in all endian/VR combinations"""

    def setup_method(self):
        # Create simple dataset for all tests
        ds = Dataset()
        ds.PatientName = "Name^Patient"
        ds.InstanceNumber = None

        # Set up a simple nested sequence
        # first, the innermost sequence
        subitem1 = Dataset()
        subitem1.ContourNumber = 1
        subitem1.ContourData = ["2", "4", "8", "16"]
        subitem2 = Dataset()
        subitem2.ContourNumber = 2
        subitem2.ContourData = ["32", "64", "128", "196"]

        sub_ds = Dataset()
        sub_ds.ContourSequence = Sequence((subitem1, subitem2))

        # Now the top-level sequence
        ds.ROIContourSequence = Sequence((sub_ds,))  # Comma to make one-tuple

        # Store so each test can use it
        self.ds = ds

    def compare_write(self, hex_std, file_ds):
        """Write file and compare with expected byte string

        :arg hex_std: the bytes which should be written, as space separated hex
        :arg file_ds: a FileDataset instance containing the dataset to write
        """
        out_filename = "scratch.dcm"
        file_ds.save_as(out_filename)
        std = hex2bytes(hex_std)
        with open(out_filename, "rb") as f:
            bytes_written = f.read()
        # print "std    :", bytes2hex(std)
        # print "written:", bytes2hex(bytes_written)
        same, pos = bytes_identical(std, bytes_written)
        assert same

        if os.path.exists(out_filename):
            os.remove(out_filename)  # get rid of the file

    def testImpl_LE_deflen_write(self):
        """Scratch Write for implicit VR little endian, defined length SQs"""
        file_ds = FileDataset("test", self.ds)
        self.compare_write(impl_LE_deflen_std_hex, file_ds)


class TestDCMWrite:
    """Tests for dcmwrite()"""

    def test_implicit_big_raises(self):
        """Test implicit VR big endian encoding raises exception."""
        msg = "Implicit VR and big endian is not a valid encoding combination"
        with pytest.raises(ValueError, match=msg):
            dcmwrite(DicomBytesIO(), Dataset(), implicit_vr=True, little_endian=False)

    def test_implicit_big_force_encoding(self):
        """Test implicit VR big endian encoding with force_encoding"""
        fp = DicomBytesIO()
        ds = Dataset()
        ds.PatientName = "Foo"
        dcmwrite(fp, ds, implicit_vr=True, little_endian=False, force_encoding=True)
        fp.seek(0)
        assert fp.getvalue() == b"\x00\x10\x00\x10\x00\x00\x00\x04\x46\x6f\x6f\x20"

    def test_bad_filename(self):
        """Test that TypeError is raised for a bad filename."""
        ds = dcmread(ct_name)
        with pytest.raises(
            TypeError,
            match=(
                "dcmwrite: Expected a file path, file-like or writeable "
                "buffer, but got NoneType"
            ),
        ):
            ds.save_as(None)
        with pytest.raises(
            TypeError,
            match=(
                "dcmwrite: Expected a file path, file-like or writeable "
                "buffer, but got int"
            ),
        ):
            ds.save_as(42)

    def test_write_like_original_warns(self):
        """Test deprecation warning for write_like_original."""
        fp = DicomBytesIO()
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        ds.SOPClassUID = "1.2"
        ds.SOPInstanceUID = "1.2.3"
        msg = (
            "'write_like_original' is deprecated and will be removed in "
            "v4.0, please use 'enforce_file_format' instead"
        )
        with pytest.warns(DeprecationWarning, match=msg):
            dcmwrite(fp, ds, write_like_original=False)

        with pytest.warns(DeprecationWarning, match=msg):
            dcmwrite(fp, ds, write_like_original=True)

        with pytest.warns(DeprecationWarning, match=msg):
            dcmwrite(fp, ds, False)

        with pytest.warns(DeprecationWarning, match=msg):
            dcmwrite(fp, ds, True)

    def test_extra_kwargs_raises(self):
        """Test unknown kwargs raise exception."""
        msg = r"Invalid keyword argument\(s\) for dcmwrite\(\): is_implicit_VR"
        with pytest.warns(DeprecationWarning):
            with pytest.raises(TypeError, match=msg):
                dcmwrite(
                    DicomBytesIO(),
                    Dataset(),
                    implicit_vr=False,
                    write_like_original=True,
                    is_implicit_VR=False,
                )

    def test_extra_args_raises(self):
        """Test unknown kwargs raise exception."""
        msg = r"dcmwrite\(\) takes from 2 to 3 positional arguments but 4 were given"
        with pytest.raises(TypeError, match=msg):
            dcmwrite(
                DicomBytesIO(),
                Dataset(),
                True,
                False,
                is_implicit_VR=False,
            )

    def test_position_and_keyword_raises(self):
        """Test position and keyword arg raises exception."""
        msg = (
            "'write_like_original' cannot be used as both a positional and "
            "keyword argument"
        )
        with pytest.raises(TypeError, match=msg):
            dcmwrite(
                DicomBytesIO(),
                Dataset(),
                True,
                implicit_vr=False,
                write_like_original=True,
                is_implicit_VR=False,
            )

    def test_command_set_raises(self):
        """Test exception if command set elements present."""
        ds = Dataset()
        ds.MessageID = 1
        msg = (
            r"Command Set elements \(0000,eeee\) are not allowed when using "
            r"dcmwrite\(\), use write_dataset\(\) instead"
        )
        with pytest.raises(ValueError, match=msg):
            dcmwrite(
                DicomBytesIO(),
                ds,
                implicit_vr=True,
                enforce_file_format=True,
            )

    def test_file_meta_raises(self):
        """Test file meta elements in dataset raises exception."""
        ds = Dataset()
        ds.TransferSyntaxUID = ImplicitVRLittleEndian
        msg = (
            r"File Meta Information Group elements \(0002,eeee\) must be in a "
            r"FileMetaDataset instance in the 'Dataset.file_meta' attribute"
        )
        with pytest.raises(ValueError, match=msg):
            dcmwrite(DicomBytesIO(), ds, implicit_vr=True)

    def test_dataset_file_meta_unchanged(self):
        """Test writing the dataset doesn't change its file_meta."""
        # Dataset has no file_meta
        ds = Dataset()
        ds.SOPClassUID = "1.2"
        ds.SOPInstanceUID = "1.2.3"

        fp = DicomBytesIO()
        dcmwrite(fp, ds, implicit_vr=True)
        assert not hasattr(ds, "file_meta")

        dcmwrite(fp, ds, implicit_vr=True, enforce_file_format=True)
        assert not hasattr(ds, "file_meta")

        # Dataset has file_meta
        ds.file_meta = FileMetaDataset()
        ds.file_meta.ImplementationVersionName = "Foo"

        dcmwrite(fp, ds, implicit_vr=True)
        assert len(ds.file_meta) == 1
        assert ds.file_meta.ImplementationVersionName == "Foo"

        dcmwrite(fp, ds, implicit_vr=True, enforce_file_format=True)
        assert len(ds.file_meta) == 1
        assert ds.file_meta.ImplementationVersionName == "Foo"

    def test_preamble_custom(self):
        """Test that a custom preamble is written correctly when present."""
        ds = dcmread(ct_name)
        ds.preamble = b"\x01\x02\x03\x04" + b"\x00" * 124
        fp = DicomBytesIO()
        dcmwrite(fp, ds)
        fp.seek(0)
        assert b"\x01\x02\x03\x04" + b"\x00" * 124 == fp.read(128)

    def test_preamble_default(self):
        """Test that the default preamble is written correctly when present."""
        ds = dcmread(ct_name)
        ds.preamble = b"\x00" * 128
        fp = DicomBytesIO()
        dcmwrite(fp, ds)
        fp.seek(0)
        assert b"\x00" * 128 == fp.read(128)

    def test_convert_big_to_little(self):
        """Test simple conversion from big to little endian."""
        # Note that O* and UN elements are not converted
        ds = dcmread(mr_bigendian_name)
        assert not ds.original_encoding[1]
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        fp = DicomBytesIO()
        dcmwrite(fp, ds)
        fp.seek(0)
        ds_out = dcmread(fp)
        assert ds_out.original_encoding[1]

        # pixel data is not converted automatically
        ds_explicit = dcmread(mr_name)
        del ds_out.PixelData
        del ds_explicit.PixelData
        for elem_in, elem_out in zip(ds_explicit, ds_out):
            assert elem_in == elem_out

    def test_convert_little_to_big(self):
        """Test simple conversion from little to big endian."""
        # Note that O* and UN elements are not converted
        ds = dcmread(mr_name)
        assert ds.original_encoding[1]
        ds.file_meta.TransferSyntaxUID = ExplicitVRBigEndian
        fp = DicomBytesIO()
        dcmwrite(fp, ds, little_endian=False)
        fp.seek(0)
        ds_out = dcmread(fp)
        assert not ds_out.original_encoding[1]

        # pixel data is not converted automatically
        ds_explicit = dcmread(mr_bigendian_name)
        del ds_out.PixelData
        del ds_explicit.PixelData
        for elem_in, elem_out in zip(ds_explicit, ds_out):
            assert elem_in == elem_out

    def test_raw_elements_preserved_implicit_vr(self):
        """Test writing the dataset preserves raw elements."""
        ds = dcmread(rtplan_name)

        # raw data elements after reading
        assert ds.get_item(0x00080070).is_raw  # Manufacturer
        assert ds.get_item(0x00100020).is_raw  # Patient ID
        assert ds.get_item(0x300A0006).is_raw  # RT Plan Date
        assert ds.get_item(0x300A0010).is_raw  # Dose Reference Sequence

        dcmwrite(DicomBytesIO(), ds, enforce_file_format=True)

        # data set still contains raw data elements after writing
        assert ds.get_item(0x00080070).is_raw  # Manufacturer
        assert ds.get_item(0x00100020).is_raw  # Patient ID
        assert ds.get_item(0x300A0006).is_raw  # RT Plan Date
        assert ds.get_item(0x300A0010).is_raw  # Dose Reference Sequence

    def test_raw_elements_preserved_explicit_vr(self):
        """Test writing the dataset preserves raw elements."""
        ds = dcmread(color_pl_name)

        # raw data elements after reading
        assert ds.get_item(0x00080070).is_raw  # Manufacturer
        assert ds.get_item(0x00100010).is_raw  # Patient Name
        assert ds.get_item(0x00080030).is_raw  # Study Time
        assert ds.get_item(0x00089215).is_raw  # Derivation Code Sequence

        dcmwrite(DicomBytesIO(), ds, enforce_file_format=True)

        # data set still contains raw data elements after writing
        assert ds.get_item(0x00080070).is_raw  # Manufacturer
        assert ds.get_item(0x00100010).is_raw  # Patient Name
        assert ds.get_item(0x00080030).is_raw  # Study Time
        assert ds.get_item(0x00089215).is_raw  # Derivation Code Sequence

    def test_convert_implicit_to_explicit_vr(self):
        # make sure conversion from implicit to explicit VR works
        # without private tags
        ds = dcmread(mr_implicit_name)
        assert ds.is_implicit_VR
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

        fp = DicomBytesIO()
        dcmwrite(fp, ds, enforce_file_format=True)
        fp.seek(0)
        ds_out = dcmread(fp)
        assert not ds_out.is_implicit_VR
        ds_explicit = dcmread(mr_name)

        for elem_in, elem_out in zip(ds_explicit, ds_out):
            assert elem_in == elem_out

    def test_convert_implicit_to_explicit_vr_using_destination(self):
        # make sure conversion from implicit to explicit VR works
        # if setting the property in the destination
        ds = dcmread(mr_implicit_name)
        assert ds.is_implicit_VR
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        fp = DicomBytesIO()
        dcmwrite(fp, ds, enforce_file_format=True)
        fp.seek(0)
        ds_out = dcmread(fp)
        assert not ds_out.is_implicit_VR
        ds_explicit = dcmread(mr_name)

        for elem_in, elem_out in zip(ds_explicit, ds_out):
            assert elem_in == elem_out

    def test_convert_explicit_to_implicit_vr(self):
        # make sure conversion from explicit to implicit VR works
        # without private tags
        ds = dcmread(mr_name)
        assert not ds.is_implicit_VR
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        fp = DicomBytesIO()
        dcmwrite(fp, ds, enforce_file_format=True)
        fp.seek(0)
        ds_out = dcmread(fp)
        assert ds_out.is_implicit_VR
        ds_implicit = dcmread(mr_implicit_name)

        for elem_in, elem_out in zip(ds_implicit, ds_out):
            assert elem_in == elem_out

    def test_changed_character_set(self):
        """Make sure that a changed character set is reflected
        in the written data elements."""
        ds = dcmread(multiPN_name)
        # Latin 1 original encoding
        assert ds.get_item(0x00100010).value == b"Buc^J\xe9r\xf4me"

        # change encoding to UTF-8
        ds.SpecificCharacterSet = "ISO_IR 192"
        fp = DicomBytesIO()
        dcmwrite(fp, ds, enforce_file_format=True)
        fp.seek(0)
        ds_out = dcmread(fp)
        # patient name shall be UTF-8 encoded
        assert ds_out.get_item(0x00100010).value == b"Buc^J\xc3\xa9r\xc3\xb4me"
        # decoded values shall be the same as in original dataset
        for elem_in, elem_out in zip(ds, ds_out):
            assert elem_in == elem_out

    def test_private_tag_vr_from_implicit_data(self):
        """Test that private tags have the correct VR if converting
        a dataset from implicit to explicit VR.
        """
        # convert a dataset with private tags to Implicit VR
        ds_orig = dcmread(ct_name)
        assert not ds_orig.is_implicit_VR
        ds_orig.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        fp = DicomBytesIO()
        dcmwrite(fp, ds_orig, enforce_file_format=True)
        fp.seek(0)
        ds_impl = dcmread(fp)

        # convert the dataset back to explicit VR - private tag VR now unknown
        assert ds_impl.is_implicit_VR
        ds_impl.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        fp = DicomBytesIO()
        dcmwrite(fp, ds_impl, enforce_file_format=True)
        fp.seek(0)
        ds_expl = dcmread(fp)
        assert not ds_expl.is_implicit_VR

        assert ds_expl[(0x0009, 0x0010)].VR == "LO"  # private creator
        assert ds_expl[(0x0009, 0x1001)].VR == "LO"
        assert ds_expl[(0x0009, 0x10E7)].VR == "UL"
        assert ds_expl[(0x0043, 0x1010)].VR == "US"

    def test_convert_rgb_from_implicit_to_explicit_vr(self, no_numpy_use):
        """Test converting an RGB dataset from implicit to explicit VR
        and vice verse."""
        ds_orig = dcmread(sc_rgb_name)
        assert not ds_orig.is_implicit_VR
        ds_orig.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        fp = DicomBytesIO()
        dcmwrite(fp, ds_orig, enforce_file_format=True)
        fp.seek(0)
        ds_impl = dcmread(fp)
        assert ds_impl.is_implicit_VR
        for elem_orig, elem_conv in zip(ds_orig, ds_impl):
            assert elem_orig.value == elem_conv.value
        assert "OW" == ds_impl[0x7FE00010].VR

        ds_impl.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        fp = DicomBytesIO()
        dcmwrite(fp, ds_impl, enforce_file_format=True)
        fp.seek(0)
        # used to raise, see #620
        ds_expl = dcmread(fp)
        assert not ds_expl.is_implicit_VR
        for elem_orig, elem_conv in zip(ds_orig, ds_expl):
            assert elem_orig.value == elem_conv.value

    def test_overwrite(self):
        """Test the overwrite argument"""
        ds = dcmread(ct_name)
        patient_name = ds.PatientName

        with tempfile.TemporaryDirectory() as tdir:
            p = Path(tdir) / "foo.dcm"
            p.touch()

            assert p.exists()

            msg = r"File exists: '(.*)foo.dcm'"
            with pytest.raises(FileExistsError, match=msg):
                dcmwrite(p, ds, overwrite=False)

            dcmwrite(p, ds, overwrite=True)
            assert dcmread(p).PatientName == patient_name


class TestDCMWrite_EnforceFileFormat:
    """Tests for dcmwrite(enforce_file_format=True)"""

    def test_force_encoding_raises(self):
        """Test that force_encoding raises."""
        msg = "'force_encoding' cannot be used with 'enforce_file_format'"
        with pytest.raises(ValueError, match=msg):
            dcmwrite(
                DicomBytesIO(),
                Dataset(),
                force_encoding=True,
                enforce_file_format=True,
            )

    def test_preamble_default(self):
        """Test that the default preamble is written correctly when present."""
        fp = DicomBytesIO()
        ds = dcmread(ct_name)
        ds.preamble = b"\x00" * 128
        ds.save_as(fp, enforce_file_format=True)
        fp.seek(0)
        assert fp.read(128) == b"\x00" * 128

    def test_preamble_custom(self):
        """Test that a custom preamble is written correctly when present."""
        fp = DicomBytesIO()
        ds = dcmread(ct_name)
        ds.preamble = b"\x01\x02\x03\x04" + b"\x00" * 124
        ds.save_as(fp, enforce_file_format=True)
        fp.seek(0)
        assert fp.read(128) == b"\x01\x02\x03\x04" + b"\x00" * 124

    def test_no_preamble(self):
        """Test that a default preamble is written when absent."""
        fp = DicomBytesIO()
        ds = dcmread(ct_name)
        del ds.preamble
        ds.save_as(fp, enforce_file_format=True)
        fp.seek(0)
        assert fp.read(128) == b"\x00" * 128

        fp = DicomBytesIO()
        ds = dcmread(ct_name)
        ds.preamble = None
        ds.save_as(fp, enforce_file_format=True)
        fp.seek(0)
        assert fp.read(128) == b"\x00" * 128

    def test_bad_preamble(self):
        """Test that ValueError is raised when preamble is bad."""
        ds = dcmread(ct_name)
        msg = "'FileDataset.preamble' must be 128-bytes long"
        for preamble in (b"\x00" * 127, b"\x00" * 129):
            ds.preamble = preamble
            with pytest.raises(ValueError, match=msg):
                ds.save_as(DicomBytesIO(), enforce_file_format=True)

    def test_prefix(self):
        """Test that the 'DICM' prefix is written with preamble."""
        fp = DicomBytesIO()
        ds = dcmread(ct_name)
        ds.preamble = b"\x00" * 128
        ds.save_as(fp, enforce_file_format=True)
        fp.seek(128)
        assert fp.read(4) == b"DICM"

        fp = DicomBytesIO()
        ds = dcmread(ct_name)
        ds.preamble = None
        ds.save_as(fp, enforce_file_format=True)
        fp.seek(128)
        assert fp.read(4) == b"DICM"

    def test_file_meta_none(self):
        """Test writing a dataset with no file_meta"""
        fp = DicomBytesIO()
        version = "PYDICOM " + base_version
        ds = dcmread(rtplan_name)
        transfer_syntax = ds.file_meta.TransferSyntaxUID
        ds.file_meta = FileMetaDataset()
        ds.save_as(fp, enforce_file_format=True)
        fp.seek(0)
        out = dcmread(fp)
        assert out.file_meta.MediaStorageSOPClassUID == ds.SOPClassUID
        assert out.file_meta.MediaStorageSOPInstanceUID == ds.SOPInstanceUID
        assert out.file_meta.ImplementationClassUID == PYDICOM_IMPLEMENTATION_UID
        assert out.file_meta.ImplementationVersionName == version
        assert out.file_meta.TransferSyntaxUID == transfer_syntax

        fp = DicomBytesIO()
        del ds.file_meta
        ds.save_as(fp, enforce_file_format=True)
        fp.seek(0)
        out = dcmread(fp)
        assert out.file_meta.MediaStorageSOPClassUID == ds.SOPClassUID
        assert out.file_meta.MediaStorageSOPInstanceUID == ds.SOPInstanceUID
        assert out.file_meta.ImplementationClassUID == PYDICOM_IMPLEMENTATION_UID
        assert out.file_meta.ImplementationVersionName == version
        assert out.file_meta.TransferSyntaxUID == transfer_syntax

    def test_file_meta_no_syntax(self):
        """Test a file meta with no transfer syntax."""
        ds = Dataset()
        ds.SOPClassUID = "1.2"
        ds.SOPInstanceUID = "1.2.3"
        fp = DicomBytesIO()
        dcmwrite(fp, ds, implicit_vr=True, little_endian=True, enforce_file_format=True)
        fp.seek(0)
        out = dcmread(fp)
        assert out.file_meta.TransferSyntaxUID == ImplicitVRLittleEndian

        fp = DicomBytesIO()
        dcmwrite(
            fp, ds, implicit_vr=False, little_endian=False, enforce_file_format=True
        )
        fp.seek(0)
        out = dcmread(fp)
        assert out.file_meta.TransferSyntaxUID == ExplicitVRBigEndian

        msg = (
            r"Required File Meta Information elements are either missing "
            r"or have an empty value: \(0002,0010\) Transfer Syntax UID"
        )
        with pytest.raises(AttributeError, match=msg):
            dcmwrite(
                fp, ds, implicit_vr=False, little_endian=True, enforce_file_format=True
            )

    def test_file_meta_sop_class_sop_instance(self):
        """Test a file meta with no Media Storage SOP Class/Instance UID."""
        # Test values overwritten if missing or None
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.SOPClassUID = "1.2"
        ds.SOPInstanceUID = "1.2.3"
        fp = DicomBytesIO()
        dcmwrite(fp, ds, implicit_vr=True, enforce_file_format=True)
        fp.seek(0)
        out = dcmread(fp)
        assert out.file_meta.MediaStorageSOPClassUID == "1.2"
        assert out.file_meta.MediaStorageSOPInstanceUID == "1.2.3"

        ds.file_meta.MediaStorageSOPClassUID = None
        ds.file_meta.MediaStorageSOPInstanceUID = None
        fp = DicomBytesIO()
        dcmwrite(fp, ds, implicit_vr=True, enforce_file_format=True)
        fp.seek(0)
        out = dcmread(fp)
        assert out.file_meta.MediaStorageSOPClassUID == "1.2"
        assert out.file_meta.MediaStorageSOPInstanceUID == "1.2.3"

        # Test value not overwritten if None in dataset
        ds.SOPClassUID = None
        ds.SOPInstanceUID = None
        ds.file_meta.MediaStorageSOPClassUID = "1.2"
        ds.file_meta.MediaStorageSOPInstanceUID = "1.2.3"
        fp = DicomBytesIO()
        dcmwrite(
            fp, ds, implicit_vr=False, little_endian=False, enforce_file_format=True
        )
        fp.seek(0)
        out = dcmread(fp)
        assert out.file_meta.MediaStorageSOPClassUID == "1.2"
        assert out.file_meta.MediaStorageSOPInstanceUID == "1.2.3"

        # Test exception if missing or None
        del ds.file_meta
        msg = (
            r"Required File Meta Information elements are either missing "
            r"or have an empty value: \(0002,0002\) Media Storage SOP Class "
            r"UID, \(0002,0003\) Media Storage SOP Instance UID"
        )
        with pytest.raises(AttributeError, match=msg):
            dcmwrite(fp, ds, implicit_vr=True, enforce_file_format=True)


class TestDetermineEncoding:
    """Tests for _determine_encoding()."""

    def test_force_encoding_raises(self):
        """Test exception raised if force_encoding used without args."""
        ds = Dataset()
        ds._read_implicit = True
        ds._read_little = True
        tsyntax = ImplicitVRLittleEndian
        msg = (
            "'implicit_vr' and 'little_endian' are required if "
            "'force_encoding' is used"
        )
        with pytest.raises(ValueError, match=msg):
            _determine_encoding(ds, tsyntax, None, True, True)

        with pytest.raises(ValueError, match=msg):
            _determine_encoding(ds, tsyntax, True, None, True)

    def test_force_encoding(self):
        """Test results with force_encoding are as expected."""
        ds = Dataset()
        ds._is_implicit_VR = True
        ds._is_little_endian = True
        tsyntax = ImplicitVRLittleEndian
        result = _determine_encoding(ds, tsyntax, False, False, True)
        assert result == (False, False)

    def test_transfer_syntax(self):
        """Test when transfer syntax is available."""
        ds = Dataset()
        ds._is_implicit_VR = False
        ds._is_little_endian = True
        tsyntax = ImplicitVRLittleEndian
        result = _determine_encoding(ds, tsyntax, True, None, False)
        assert result == (True, True)

    def test_args(self):
        """Test fallback to args when transfer syntax not available."""
        ds = Dataset()
        ds._is_implicit_VR = False
        ds._is_little_endian = True
        result = _determine_encoding(ds, None, True, False, False)
        assert result == (True, False)

    def test_dataset(self):
        """Test fallback to dataset when transfer syntax and args not available."""
        ds = Dataset()
        ds._is_implicit_VR = False
        ds._is_little_endian = True
        result = _determine_encoding(ds, None, None, False, False)
        assert result == (False, True)

    def test_original(self):
        """Test fallback to original when tsyntax, args and ds attr not available."""
        ds = Dataset()
        ds._read_implicit = False
        ds._read_little = True
        result = _determine_encoding(ds, None, None, False, False)
        assert result == (False, True)

    def test_none_raises(self):
        """Test exception raised if unable to determine encoding."""
        msg = (
            "Unable to determine the encoding to use for writing the dataset, "
            "please set the file meta's Transfer Syntax UID or use the "
            "'implicit_vr' and 'little_endian' arguments"
        )
        with pytest.raises(ValueError, match=msg):
            _determine_encoding(Dataset(), None, None, None, False)

    def test_private_transfer_syntax_raises(self):
        """Test private syntax raises if no args."""
        syntax = UID("1.2.3")
        msg = (
            "The 'implicit_vr' and 'little_endian' arguments are required "
            "when using a private transfer syntax"
        )
        with pytest.raises(ValueError, match=msg):
            _determine_encoding(Dataset(), syntax, None, None, False)

    def test_private_transfer_syntax(self):
        """Test private syntax raises if no args."""
        syntax = UID("1.2.3")
        result = _determine_encoding(Dataset(), syntax, True, True, False)
        assert result == (True, True)

    def test_invalid_transfer_syntax_raises(self):
        """Test public non-transfer syntax raises."""
        syntax = CTImageStorage
        msg = (
            "The Transfer Syntax UID 'CT Image Storage' is not a valid "
            "transfer syntax"
        )
        with pytest.raises(ValueError, match=msg):
            _determine_encoding(Dataset(), syntax, False, True, False)

    def test_mismatch_raises(self):
        """Test mismatch between args and transfer syntax raises."""
        ds = Dataset()
        ds._is_implicit_VR = False
        ds._is_little_endian = True
        tsyntax = ImplicitVRLittleEndian
        msg = (
            "The 'little_endian' value is not consistent with the required "
            "endianness for the 'Implicit VR Little Endian' transfer syntax"
        )
        with pytest.raises(ValueError, match=msg):
            _determine_encoding(ds, tsyntax, True, False, False)

        msg = (
            "The 'implicit_vr' value is not consistent with the required "
            "VR encoding for the 'Implicit VR Little Endian' transfer syntax"
        )
        with pytest.raises(ValueError, match=msg):
            _determine_encoding(ds, tsyntax, False, True, False)


class TestWriteDataset:
    """Tests for write_dataset()"""

    def test_encoding_buffer(self):
        """Test buffer.is_implicit_VR, buffer.is_little_endian used."""
        ds = Dataset()
        ds.PatientName = "Foo"
        ds._read_little = False
        ds._read_implicit = False
        ds._is_little_endian = False
        ds._is_implicit_VR = False
        fp = DicomBytesIO()
        fp.is_implicit_VR = True
        fp.is_little_endian = True
        # Should use fp's encoding - implicit little
        write_dataset(fp, ds)
        assert fp.getvalue()[:8] == b"\x10\x00\x10\x00\x04\x00\x00\x00"

    def test_encoding_ds_attr(self):
        """Tests ds.is_implicit_VR, ds.is_little_endian used."""
        ds = Dataset()
        ds.PatientName = "Foo"
        ds._read_little = False
        ds._read_implicit = False
        ds._is_little_endian = True
        ds._is_implicit_VR = True
        fp = DicomBytesIO()
        # Should use ds's encoding - implicit little
        write_dataset(fp, ds)
        assert fp.getvalue()[:8] == b"\x10\x00\x10\x00\x04\x00\x00\x00"

    def test_encoding_ds_original(self):
        """Test original ds encoding used."""
        ds = Dataset()
        ds.PatientName = "Foo"
        ds._read_little = True
        ds._read_implicit = True
        fp = DicomBytesIO()
        # Should use ds's original encoding - implicit little
        write_dataset(fp, ds)
        assert fp.getvalue()[:8] == b"\x10\x00\x10\x00\x04\x00\x00\x00"

    def test_encoding_raises(self):
        """Test raises exception if no encoding set"""

    def test_write_dataset(self):
        # make sure writing and reading back a dataset works correctly
        ds = dcmread(mr_implicit_name)
        fp = DicomBytesIO()
        write_dataset(fp, ds)
        fp.seek(0)
        ds_read = read_dataset(fp, is_implicit_VR=True, is_little_endian=True)
        for elem_orig, elem_read in zip(ds_read, ds):
            assert elem_orig == elem_read

    def test_write_dataset_with_explicit_vr(self):
        # make sure conversion from implicit to explicit VR does not
        # raise (regression test for #632)
        ds = dcmread(mr_implicit_name)
        fp = DicomBytesIO()
        fp.is_implicit_VR = False
        fp.is_little_endian = True
        write_dataset(fp, ds)
        fp.seek(0)
        ds_read = read_dataset(fp, is_implicit_VR=False, is_little_endian=True)
        for elem_orig, elem_read in zip(ds_read, ds):
            assert elem_orig == elem_read

    def test_no_source_raises(self):
        """Test trying to write without an encoding source raises."""
        ds = Dataset()
        fp = DicomBytesIO()
        msg = "'fp.is_implicit_VR' and 'fp.is_little_endian' attributes are required"
        with pytest.raises(AttributeError, match=msg):
            write_dataset(fp, ds)


class TestWriteFileMetaInfoToStandard:
    """Unit tests for writing File Meta Info to the DICOM standard."""

    def test_bad_elements(self):
        """Test that non-group 2 elements aren't written to the file meta."""
        fp = DicomBytesIO()
        meta = Dataset()
        meta.PatientID = "12345678"
        meta.MediaStorageSOPClassUID = "1.1"
        meta.MediaStorageSOPInstanceUID = "1.2"
        meta.TransferSyntaxUID = "1.3"
        meta.ImplementationClassUID = "1.4"
        with pytest.raises(ValueError):
            write_file_meta_info(fp, meta, enforce_standard=True)

    def test_missing_elements(self):
        """Test that missing required elements raises ValueError."""
        fp = DicomBytesIO()
        meta = Dataset()
        msg = (
            r"Required File Meta Information elements are either missing or "
            r"have an empty value: \(0002,0002\) Media Storage SOP Class UID, "
            r"\(0002,0003\) Media Storage SOP Instance UID, \(0002,0010\) "
            r"Transfer Syntax UID"
        )
        with pytest.raises(AttributeError, match=msg):
            write_file_meta_info(fp, meta)

        msg = (
            r"Required File Meta Information elements are either missing or "
            r"have an empty value: \(0002,0003\) Media Storage SOP Instance "
            r"UID, \(0002,0010\) Transfer Syntax UID"
        )
        meta.MediaStorageSOPClassUID = "1.1"
        with pytest.raises(AttributeError, match=msg):
            write_file_meta_info(fp, meta)

        msg = (
            r"Required File Meta Information elements are either missing or "
            r"have an empty value: \(0002,0010\) Transfer Syntax UID"
        )
        meta.MediaStorageSOPInstanceUID = "1.2"
        with pytest.raises(AttributeError, match=msg):
            write_file_meta_info(fp, meta)

        meta.TransferSyntaxUID = "1.3"
        write_file_meta_info(fp, meta, enforce_standard=True)

    def test_group_length(self):
        """Test that the value for FileMetaInformationGroupLength is OK."""
        fp = DicomBytesIO()
        meta = Dataset()
        meta.MediaStorageSOPClassUID = "1.1"
        meta.MediaStorageSOPInstanceUID = "1.2"
        meta.TransferSyntaxUID = "1.3"
        write_file_meta_info(fp, meta, enforce_standard=True)

        class_length = len(PYDICOM_IMPLEMENTATION_UID)
        if class_length % 2:
            class_length += 1
        version_length = len(meta.ImplementationVersionName)
        # Padded to even length
        if version_length % 2:
            version_length += 1

        fp.seek(8)
        test_length = unpack("<I", fp.read(4))[0]
        assert test_length == 66 + class_length + version_length

    def test_group_length_updated(self):
        """Test that FileMetaInformationGroupLength gets updated if present."""
        fp = DicomBytesIO()
        meta = Dataset()
        meta.FileMetaInformationGroupLength = 100  # Not actual length
        meta.MediaStorageSOPClassUID = "1.1"
        meta.MediaStorageSOPInstanceUID = "1.2"
        meta.TransferSyntaxUID = "1.3"
        write_file_meta_info(fp, meta, enforce_standard=True)

        class_length = len(PYDICOM_IMPLEMENTATION_UID)
        if class_length % 2:
            class_length += 1
        version_length = len(meta.ImplementationVersionName)
        # Padded to even length
        if version_length % 2:
            version_length += 1

        fp.seek(8)
        test_length = unpack("<I", fp.read(4))[0]
        assert test_length == (61 + class_length + version_length + len(base_version))
        # Check original file meta is unchanged/updated
        assert meta.FileMetaInformationGroupLength == test_length
        assert meta.FileMetaInformationVersion == b"\x00\x01"
        assert meta.MediaStorageSOPClassUID == "1.1"
        assert meta.MediaStorageSOPInstanceUID == "1.2"
        assert meta.TransferSyntaxUID == "1.3"
        # Updated to meet standard
        assert meta.ImplementationClassUID == PYDICOM_IMPLEMENTATION_UID
        assert meta.ImplementationVersionName == "PYDICOM " + base_version

    def test_version(self):
        """Test that the value for FileMetaInformationVersion is OK."""
        fp = DicomBytesIO()
        meta = Dataset()
        meta.MediaStorageSOPClassUID = "1.1"
        meta.MediaStorageSOPInstanceUID = "1.2"
        meta.TransferSyntaxUID = "1.3"
        write_file_meta_info(fp, meta, enforce_standard=True)

        fp.seek(12 + 12)
        assert fp.read(2) == b"\x00\x01"

    def test_implementation_version_name_length(self):
        """Test that the written Implementation Version Name length is OK"""
        fp = DicomBytesIO()
        meta = Dataset()
        meta.MediaStorageSOPClassUID = "1.1"
        meta.MediaStorageSOPInstanceUID = "1.2"
        meta.TransferSyntaxUID = "1.3"
        write_file_meta_info(fp, meta, enforce_standard=True)
        version_length = len(meta.ImplementationVersionName)
        # VR of SH, 16 bytes max
        assert version_length <= 16

    def test_implementation_class_uid_length(self):
        """Test that the written Implementation Class UID length is OK"""
        fp = DicomBytesIO()
        meta = Dataset()
        meta.MediaStorageSOPClassUID = "1.1"
        meta.MediaStorageSOPInstanceUID = "1.2"
        meta.TransferSyntaxUID = "1.3"
        write_file_meta_info(fp, meta, enforce_standard=True)
        class_length = len(meta.ImplementationClassUID)
        # VR of UI, 64 bytes max
        assert class_length <= 64

    def test_filelike_position(self):
        """Test that the file-like's ending position is OK."""
        fp = DicomBytesIO()
        meta = Dataset()
        meta.MediaStorageSOPClassUID = "1.1"
        meta.MediaStorageSOPInstanceUID = "1.2"
        meta.TransferSyntaxUID = "1.3"
        write_file_meta_info(fp, meta, enforce_standard=True)

        # 8 + 4 bytes FileMetaInformationGroupLength
        # 12 + 2 bytes FileMetaInformationVersion
        # 8 + 4 bytes MediaStorageSOPClassUID
        # 8 + 4 bytes MediaStorageSOPInstanceUID
        # 8 + 4 bytes TransferSyntaxUID
        # 8 + XX bytes ImplementationClassUID
        # 8 + YY bytes ImplementationVersionName
        # 78 + XX + YY bytes total
        class_length = len(PYDICOM_IMPLEMENTATION_UID)
        if class_length % 2:
            class_length += 1
        version_length = len(meta.ImplementationVersionName)
        # Padded to even length
        if version_length % 2:
            version_length += 1

        assert fp.tell() == 78 + class_length + version_length

        fp = DicomBytesIO()
        # 8 + 6 bytes MediaStorageSOPInstanceUID
        meta.MediaStorageSOPInstanceUID = "1.4.1"
        write_file_meta_info(fp, meta, enforce_standard=True)
        # Check File Meta length
        assert fp.tell() == 80 + class_length + version_length

        # Check Group Length - 68 + XX + YY as bytes
        fp.seek(8)
        test_length = unpack("<I", fp.read(4))[0]
        assert test_length == 68 + class_length + version_length


class TestWriteNonStandard:
    """Unit tests for writing datasets not to the DICOM standard."""

    def setup_method(self):
        """Create an empty file-like for use in testing."""
        self.fp = DicomBytesIO()
        self.fp.is_little_endian = True
        self.fp.is_implicit_VR = True

    def compare_bytes(self, bytes_in, bytes_out):
        """Compare two bytestreams for equality"""
        same, pos = bytes_identical(bytes_in, bytes_out)
        assert same

    def ensure_no_raw_data_elements(self, ds):
        for _ in ds.file_meta:
            pass
        for _ in ds:
            pass

    def test_no_preamble(self):
        """Test no preamble or prefix is written if preamble absent."""
        ds = dcmread(ct_name)
        preamble = ds.preamble[:]
        del ds.preamble
        ds.save_as(self.fp)
        self.fp.seek(0)
        assert b"\x00" * 128 != self.fp.read(128)
        self.fp.seek(0)
        assert preamble != self.fp.read(128)
        self.fp.seek(0)
        assert b"DICM" != self.fp.read(4)

    def test_ds_unchanged(self):
        """Test writing the dataset doesn't change it."""
        ds = dcmread(rtplan_name)
        ref_ds = dcmread(rtplan_name)
        ds.save_as(self.fp)

        self.ensure_no_raw_data_elements(ds)
        self.ensure_no_raw_data_elements(ref_ds)
        assert ref_ds == ds

    def test_file_meta_unchanged(self):
        """Test no file_meta elements are added if missing."""
        ds = dcmread(rtplan_name)
        ds.file_meta = FileMetaDataset()
        ds.save_as(self.fp)
        assert Dataset() == ds.file_meta

    def test_dataset(self):
        """Test dataset written OK with no preamble or file meta"""
        ds = dcmread(ct_name)
        del ds.preamble
        del ds.file_meta
        ds.save_as(self.fp)
        self.fp.seek(0)
        assert b"\x00" * 128 != self.fp.read(128)
        self.fp.seek(0)
        assert b"DICM" != self.fp.read(4)

        self.fp.seek(0)
        ds_out = dcmread(self.fp, force=True)
        assert ds_out.preamble is None
        assert Dataset() == ds_out.file_meta
        assert "PatientID" in ds_out

    def test_preamble_dataset(self):
        """Test dataset written OK with no file meta"""
        ds = dcmread(ct_name)
        del ds.file_meta
        preamble = ds.preamble[:]
        ds.save_as(self.fp)
        self.fp.seek(0)
        assert preamble == self.fp.read(128)
        assert b"DICM" == self.fp.read(4)

        self.fp.seek(0)
        ds_out = dcmread(self.fp, force=True)
        assert Dataset() == ds_out.file_meta
        assert "PatientID" in ds_out

    def test_filemeta_dataset(self):
        """Test file meta written OK if preamble absent."""
        ds = dcmread(ct_name)
        preamble = ds.preamble[:]
        del ds.preamble
        ds.save_as(self.fp)
        self.fp.seek(0)
        assert b"\x00" * 128 != self.fp.read(128)
        self.fp.seek(0)
        assert preamble != self.fp.read(128)
        self.fp.seek(0)
        assert b"DICM" != self.fp.read(4)

        self.fp.seek(0)
        ds_out = dcmread(self.fp, force=True)
        assert "ImplementationClassUID" in ds_out.file_meta
        assert ds_out.preamble is None
        assert "PatientID" in ds_out

    def test_preamble_filemeta_dataset(self):
        """Test non-standard file meta written with preamble OK"""
        ds = dcmread(ct_name)
        preamble = ds.preamble[:]
        ds.save_as(self.fp)
        self.fp.seek(0)
        assert preamble == self.fp.read(128)
        assert b"DICM" == self.fp.read(4)

        self.fp.seek(0)
        ds_out = dcmread(self.fp, force=True)
        self.ensure_no_raw_data_elements(ds)
        self.ensure_no_raw_data_elements(ds_out)

        assert ds.file_meta[:] == ds_out.file_meta[:]
        assert "TransferSyntaxUID" in ds_out.file_meta[:]
        assert preamble == ds_out.preamble
        assert "PatientID" in ds_out

    def test_read_write_identical(self):
        """Test the written bytes matches the read bytes."""
        for dcm_in in [
            rtplan_name,
            rtdose_name,
            ct_name,
            mr_name,
            jpeg_name,
            no_ts,
            unicode_name,
            multiPN_name,
        ]:
            with open(dcm_in, "rb") as f:
                bytes_in = BytesIO(f.read())
                ds_in = dcmread(bytes_in)
                bytes_out = BytesIO()
                ds_in.save_as(bytes_out)
                self.compare_bytes(bytes_in.getvalue(), bytes_out.getvalue())


class TestWriteFileMetaInfoNonStandard:
    """Unit tests for writing File Meta Info not to the DICOM standard."""

    def setup_method(self):
        """Create an empty file-like for use in testing."""
        self.fp = DicomBytesIO()

    def test_transfer_syntax_not_added(self):
        """Test that the TransferSyntaxUID isn't added if missing"""
        ds = dcmread(no_ts)
        write_file_meta_info(self.fp, ds.file_meta, enforce_standard=False)
        assert "TransferSyntaxUID" not in ds.file_meta
        assert "ImplementationClassUID" in ds.file_meta

        # Check written meta dataset doesn't contain TransferSyntaxUID
        written_ds = dcmread(self.fp, force=True)
        assert "ImplementationClassUID" in written_ds.file_meta
        assert "TransferSyntaxUID" not in written_ds.file_meta

    def test_bad_elements(self):
        """Test that non-group 2 elements aren't written to the file meta."""
        meta = Dataset()
        meta.PatientID = "12345678"
        meta.MediaStorageSOPClassUID = "1.1"
        meta.MediaStorageSOPInstanceUID = "1.2"
        meta.TransferSyntaxUID = "1.3"
        meta.ImplementationClassUID = "1.4"
        with pytest.raises(ValueError):
            write_file_meta_info(self.fp, meta, enforce_standard=False)

    def test_missing_elements(self):
        """Test that missing required elements doesn't raise ValueError."""
        meta = Dataset()
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        meta.MediaStorageSOPClassUID = "1.1"
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        meta.MediaStorageSOPInstanceUID = "1.2"
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        meta.TransferSyntaxUID = "1.3"
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        meta.ImplementationClassUID = "1.4"
        write_file_meta_info(self.fp, meta, enforce_standard=False)

    def test_group_length_updated(self):
        """Test that FileMetaInformationGroupLength gets updated if present."""
        meta = Dataset()
        meta.FileMetaInformationGroupLength = 100
        meta.MediaStorageSOPClassUID = "1.1"
        meta.MediaStorageSOPInstanceUID = "1.2"
        meta.TransferSyntaxUID = "1.3"
        meta.ImplementationClassUID = "1.4"
        write_file_meta_info(self.fp, meta, enforce_standard=False)

        # 8 + 4 bytes FileMetaInformationGroupLength
        # 8 + 4 bytes MediaStorageSOPClassUID
        # 8 + 4 bytes MediaStorageSOPInstanceUID
        # 8 + 4 bytes TransferSyntaxUID
        # 8 + 4 bytes ImplementationClassUID
        # 60 bytes total, - 12 for group length = 48
        self.fp.seek(8)
        assert b"\x30\x00\x00\x00" == self.fp.read(4)
        # Check original file meta is unchanged/updated
        assert 48 == meta.FileMetaInformationGroupLength
        assert "FileMetaInformationVersion" not in meta
        assert "1.1" == meta.MediaStorageSOPClassUID
        assert "1.2" == meta.MediaStorageSOPInstanceUID
        assert "1.3" == meta.TransferSyntaxUID
        assert "1.4" == meta.ImplementationClassUID

    def test_filelike_position(self):
        """Test that the file-like's ending position is OK."""
        # 8 + 4 bytes MediaStorageSOPClassUID
        # 8 + 4 bytes MediaStorageSOPInstanceUID
        # 8 + 4 bytes TransferSyntaxUID
        # 8 + 4 bytes ImplementationClassUID
        # 48 bytes total
        meta = Dataset()
        meta.MediaStorageSOPClassUID = "1.1"
        meta.MediaStorageSOPInstanceUID = "1.2"
        meta.TransferSyntaxUID = "1.3"
        meta.ImplementationClassUID = "1.4"
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        assert 48 == self.fp.tell()

        # 8 + 6 bytes ImplementationClassUID
        # 50 bytes total
        self.fp.seek(0)
        meta.ImplementationClassUID = "1.4.1"
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        # Check File Meta length
        assert 50 == self.fp.tell()

    def test_meta_unchanged(self):
        """Test that the meta dataset doesn't change when writing it"""
        # Empty
        meta = Dataset()
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        assert Dataset() == meta

        # Incomplete
        meta = Dataset()
        meta.MediaStorageSOPClassUID = "1.1"
        meta.MediaStorageSOPInstanceUID = "1.2"
        meta.TransferSyntaxUID = "1.3"
        meta.ImplementationClassUID = "1.4"
        ref_meta = deepcopy(meta)
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        assert ref_meta == meta

        # Conformant
        meta = Dataset()
        meta.FileMetaInformationGroupLength = 62  # Correct length
        meta.FileMetaInformationVersion = b"\x00\x01"
        meta.MediaStorageSOPClassUID = "1.1"
        meta.MediaStorageSOPInstanceUID = "1.2"
        meta.TransferSyntaxUID = "1.3"
        meta.ImplementationClassUID = "1.4"
        ref_meta = deepcopy(meta)
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        assert ref_meta == meta


class TestWriteNumbers:
    """Test filewriter.write_numbers"""

    def test_write_empty_value(self):
        """Test writing an empty value does nothing"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x00100010, "US", None)
        fmt = "H"
        write_numbers(fp, elem, fmt)
        assert fp.getvalue() == b""

    def test_write_list(self):
        """Test writing an element value with VM > 1"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x00100010, "US", [1, 2, 3, 4])
        fmt = "H"
        write_numbers(fp, elem, fmt)
        assert fp.getvalue() == b"\x01\x00\x02\x00\x03\x00\x04\x00"

    def test_write_singleton(self):
        """Test writing an element value with VM = 1"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x00100010, "US", 1)
        fmt = "H"
        write_numbers(fp, elem, fmt)
        assert fp.getvalue() == b"\x01\x00"

    def test_exception(self):
        """Test exceptions raise OSError"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        with pytest.warns(UserWarning, match="Invalid value length 1"):
            elem = DataElement(0x00100010, "US", b"\x00")
        fmt = "H"
        with pytest.raises(OSError, match=r"for data_element:\n\(0010,0010\)"):
            write_numbers(fp, elem, fmt)

    def test_write_big_endian(self):
        """Test writing big endian"""
        fp = DicomBytesIO()
        fp.is_little_endian = False
        elem = DataElement(0x00100010, "US", 1)
        fmt = "H"
        write_numbers(fp, elem, fmt)
        assert fp.getvalue() == b"\x00\x01"

    def test_write_lut_descriptor(self):
        """Test writing LUT Descriptor"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x00283002, "SS", [32768, 0, 16])
        write_numbers(fp, elem, "h")
        assert fp.getvalue() == b"\x00\x80\x00\x00\x10\x00"

        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x00283002, "SS", [])
        write_numbers(fp, elem, "h")
        assert fp.getvalue() == b""

        fp = DicomBytesIO()
        fp.is_little_endian = False
        elem = DataElement(0x00283002, "SS", [32768, 0, 16])
        write_numbers(fp, elem, "h")
        assert fp.getvalue() == b"\x80\x00\x00\x00\x00\x10"


class TestWriteOtherVRs:
    """Tests for writing the 'O' VRs like OB, OW, OF, etc."""

    def test_write_ob(self):
        """Test writing element with VR OF"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x7FE00008, "OB", b"\x00\x01\x02\x03")
        write_OBvalue(fp, elem)
        assert fp.getvalue() == b"\x00\x01\x02\x03"

        # Odd length value padded
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x7FE00008, "OB", b"\x00\x01\x02")
        write_OBvalue(fp, elem)
        assert fp.getvalue() == b"\x00\x01\x02\x00"

    def test_write_ob_buffered(self):
        fp = DicomBytesIO()
        fp.is_little_endian = True
        b = BytesIO(b"\x00\x01\x02\x03")
        elem = DataElement(0x7FE00008, "OB", b)
        write_OBvalue(fp, elem)
        assert fp.getvalue() == b"\x00\x01\x02\x03"

        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x7FE00008, "OB", b)
        b.close()
        msg = "the buffer has been closed"
        with pytest.raises(ValueError, match=msg):
            write_OBvalue(fp, elem)

        # Odd length value padded
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x7FE00008, "OB", BytesIO(b"\x00\x01\x02"))
        write_OBvalue(fp, elem)
        assert fp.getvalue() == b"\x00\x01\x02\x00"

    def test_write_ow(self):
        """Test writing element with VR OW"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x7FE00008, "OW", b"\x00\x01\x02\x03")
        write_OWvalue(fp, elem)
        assert fp.getvalue() == b"\x00\x01\x02\x03"

        # Odd length value padded
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x7FE00008, "OW", b"\x00\x01\x02")
        write_OWvalue(fp, elem)
        assert fp.getvalue() == b"\x00\x01\x02\x00"

    def test_write_ow_buffered(self):
        fp = DicomBytesIO()
        fp.is_little_endian = True
        b = BytesIO(b"\x00\x01\x02\x03")
        elem = DataElement(0x7FE00008, "OW", b)
        write_OBvalue(fp, elem)
        assert fp.getvalue() == b"\x00\x01\x02\x03"

        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x7FE00008, "OW", b)
        b.close()
        msg = "the buffer has been closed"
        with pytest.raises(ValueError, match=msg):
            write_OBvalue(fp, elem)

        # Odd length value padded
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x7FE00008, "OW", BytesIO(b"\x00\x01\x02"))
        write_OBvalue(fp, elem)
        assert fp.getvalue() == b"\x00\x01\x02\x00"

    def test_write_of(self):
        """Test writing element with VR OF"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x7FE00008, "OF", b"\x00\x01\x02\x03")
        write_OWvalue(fp, elem)
        assert fp.getvalue() == b"\x00\x01\x02\x03"

    def test_write_of_dataset(self):
        """Test writing a dataset with an element with VR OF."""
        fp = DicomBytesIO()
        ds = Dataset()
        ds.FloatPixelData = b"\x00\x01\x02\x03"
        ds.save_as(fp, implicit_vr=False)
        assert fp.getvalue() == (
            # Tag             | VR            | Length        | Value
            b"\xe0\x7f\x08\x00\x4F\x46\x00\x00\x04\x00\x00\x00\x00\x01\x02\x03"
        )


class TestWritePN:
    """Test filewriter.write_PN"""

    def test_no_encoding(self):
        """If PN element has no encoding info, default is used"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        # data element with encoded value
        elem = DataElement(0x00100010, "PN", "Test")
        write_PN(fp, elem)
        assert b"Test" == fp.getvalue()

        fp = DicomBytesIO()
        fp.is_little_endian = True
        # data element with decoded value
        elem = DataElement(0x00100010, "PN", "Test")
        write_PN(fp, elem)
        assert b"Test" == fp.getvalue()

    def test_single_byte_multi_charset_groups(self):
        """Test component groups with different encodings"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        encodings = ["latin_1", "iso_ir_126"]
        # data element with encoded value
        encoded = b"Dionysios=\x1b\x2d\x46\xc4\xe9\xef\xed\xf5\xf3\xe9\xef\xf2"
        elem = DataElement(0x00100010, "PN", encoded)
        write_PN(fp, elem)
        assert encoded == fp.getvalue()

        # regression test: make sure no warning is issued, e.g. the
        # PersonName value has not saved the default encoding
        fp = DicomBytesIO()
        fp.is_little_endian = True
        with assert_no_warning():
            write_PN(fp, elem, encodings)
        assert encoded == fp.getvalue()

        fp = DicomBytesIO()
        fp.is_little_endian = True
        # data element with decoded value
        elem = DataElement(0x00100010, "PN", "Dionysios=Διονυσιος")
        write_PN(fp, elem, encodings=encodings)
        assert encoded == fp.getvalue()

    def test_single_byte_multi_charset_values(self):
        """Test multiple values with different encodings"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        encodings = ["latin_1", "iso_ir_144", "iso_ir_126"]
        # data element with encoded value
        encoded = (
            b"Buc^J\xe9r\xf4me\\\x1b\x2d\x46"
            b"\xc4\xe9\xef\xed\xf5\xf3\xe9\xef\xf2\\"
            b"\x1b\x2d\x4C"
            b"\xbb\xee\xda\x63\x65\xdc\xd1\x79\x70\xd3 "
        )
        elem = DataElement(0x00100060, "PN", encoded)
        write_PN(fp, elem)
        assert encoded == fp.getvalue()

        fp = DicomBytesIO()
        fp.is_little_endian = True
        # data element with decoded value
        elem = DataElement(0x00100060, "PN", ["Buc^Jérôme", "Διονυσιος", "Люкceмбypг"])
        write_PN(fp, elem, encodings=encodings)
        assert encoded == fp.getvalue()


class TestWriteText:
    """Test filewriter.write_PN"""

    def test_no_encoding(self):
        """If text element has no encoding info, default is used"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        # data element with encoded value
        elem = DataElement(0x00081039, "LO", "Test")
        write_text(fp, elem)
        assert b"Test" == fp.getvalue()

        fp = DicomBytesIO()
        fp.is_little_endian = True
        # data element with decoded value
        elem = DataElement(0x00081039, "LO", "Test")
        write_text(fp, elem)
        assert b"Test" == fp.getvalue()

    def test_single_byte_multi_charset_text(self):
        """Test changed encoding inside the string"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        encoded = b"Dionysios=\x1b\x2d\x46\xc4\xe9\xef\xed\xf5\xf3\xe9\xef\xf2"
        # data element with encoded value
        elem = DataElement(0x00081039, "LO", encoded)
        encodings = ["latin_1", "iso_ir_126"]
        write_text(fp, elem)
        assert encoded == fp.getvalue()

        fp = DicomBytesIO()
        fp.is_little_endian = True
        # data element with decoded value
        elem = DataElement(0x00081039, "LO", "Dionysios is Διονυσιος")
        write_text(fp, elem, encodings=encodings)
        # encoding may not be the same, so decode it first
        encoded = fp.getvalue()
        assert "Dionysios is Διονυσιος" == convert_text(encoded, encodings)

    def test_encode_mixed_charsets_text(self):
        """Test encodings used inside the string in arbitrary order"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        encodings = ["latin_1", "euc_kr", "iso-2022-jp", "iso_ir_127"]
        decoded = "山田-قباني-吉洞-لنزار"

        # data element with encoded value
        elem = DataElement(0x00081039, "LO", decoded)
        write_text(fp, elem, encodings=encodings)
        encoded = fp.getvalue()
        # make sure that the encoded string can be converted back
        assert decoded == convert_text(encoded, encodings)

    def test_single_byte_multi_charset_text_multivalue(self):
        """Test multiple values with different encodings"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        encoded = (
            b"Buc^J\xe9r\xf4me\\\x1b\x2d\x46"
            b"\xc4\xe9\xef\xed\xf5\xf3\xe9\xef\xf2\\"
            b"\x1b\x2d\x4C"
            b"\xbb\xee\xda\x63\x65\xdc\xd1\x79\x70\xd3 "
        )
        # data element with encoded value
        elem = DataElement(0x00081039, "LO", encoded)
        encodings = ["latin_1", "iso_ir_144", "iso_ir_126"]
        write_text(fp, elem, encodings=encodings)
        assert encoded == fp.getvalue()

        fp = DicomBytesIO()
        fp.is_little_endian = True
        # data element with decoded value
        decoded = ["Buc^Jérôme", "Διονυσιος", "Люкceмбypг"]
        elem = DataElement(0x00081039, "LO", decoded)
        write_text(fp, elem, encodings=encodings)
        # encoding may not be the same, so decode it first
        encoded = fp.getvalue()
        assert decoded == convert_text(encoded, encodings)

    def test_invalid_encoding(self, allow_writing_invalid_values):
        """Test encoding text with invalid encodings"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        # data element with decoded value
        elem = DataElement(0x00081039, "LO", "Dionysios Διονυσιος")
        msg = "Failed to encode value with encodings: iso-2022-jp"
        expected = b"Dionysios \x1b$B&$&I&O&M&T&R&I&O\x1b(B? "
        with pytest.warns(UserWarning, match=msg):
            # encode with one invalid encoding
            write_text(fp, elem, encodings=["iso-2022-jp"])
            assert expected == fp.getvalue()

        fp = DicomBytesIO()
        fp.is_little_endian = True
        # data element with decoded value
        elem = DataElement(0x00081039, "LO", "Dionysios Διονυσιος")
        msg = "Failed to encode value with encodings: iso-2022-jp, iso_ir_58"
        with pytest.warns(UserWarning, match=msg):
            # encode with two invalid encodings
            write_text(fp, elem, encodings=["iso-2022-jp", "iso_ir_58"])
            assert expected == fp.getvalue()

    def test_invalid_encoding_enforce_standard(self, enforce_writing_invalid_values):
        """Test encoding text with invalid encodings with
        `config.settings.reading_validation_mode` is RAISE"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        # data element with decoded value
        elem = DataElement(0x00081039, "LO", "Dionysios Διονυσιος")
        msg = (
            r"'iso2022_jp' codec can't encode character u?'\\u03c2' in "
            r"position 18: illegal multibyte sequence"
        )
        with pytest.raises(UnicodeEncodeError, match=msg):
            # encode with one invalid encoding
            write_text(fp, elem, encodings=["iso-2022-jp"])

        fp = DicomBytesIO()
        fp.is_little_endian = True
        # data element with decoded value
        elem = DataElement(0x00081039, "LO", "Dionysios Διονυσιος")
        with pytest.raises(UnicodeEncodeError, match=msg):
            # encode with two invalid encodings
            write_text(fp, elem, encodings=["iso-2022-jp", "iso_ir_58"])

    def test_single_value_with_delimiters(self):
        """Test that text with delimiters encodes correctly"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        decoded = "Διονυσιος\r\nJérôme/Люкceмбypг\tJérôme"
        elem = DataElement(0x00081039, "LO", decoded)
        encodings = ("latin_1", "iso_ir_144", "iso_ir_126")
        write_text(fp, elem, encodings=encodings)
        encoded = fp.getvalue()
        assert decoded == convert_text(encoded, encodings)


class TestWriteDT:
    """Test filewriter.write_DT"""

    def test_format_dt(self):
        """Test _format_DT"""
        elem = DataElement(0x00181078, "DT", DT("20010203123456.123456"))
        assert hasattr(elem.value, "original_string")
        assert _format_DT(elem.value) == "20010203123456.123456"
        del elem.value.original_string
        assert not hasattr(elem.value, "original_string")
        assert elem.value.microsecond > 0
        assert _format_DT(elem.value) == "20010203123456.123456"

        elem = DataElement(0x00181078, "DT", DT("20010203123456"))
        del elem.value.original_string
        assert _format_DT(elem.value) == "20010203123456"


class TestWriteUndefinedLengthPixelData:
    """Test write_data_element() for pixel data with undefined length."""

    def setup_method(self):
        self.fp = DicomBytesIO()

    def test_little_endian_correct_data(self):
        """Pixel data starting with an item tag is written."""
        self.fp.is_little_endian = True
        self.fp.is_implicit_VR = False
        pixel_data = DataElement(
            0x7FE00010,
            "OB",
            b"\xfe\xff\x00\xe0\x00\x01\x02\x03",
            is_undefined_length=True,
        )
        write_data_element(self.fp, pixel_data)

        expected = (
            b"\xe0\x7f\x10\x00"  # tag
            b"OB\x00\x00"  # VR
            b"\xff\xff\xff\xff"  # length
            b"\xfe\xff\x00\xe0\x00\x01\x02\x03"  # contents
            b"\xfe\xff\xdd\xe0\x00\x00\x00\x00"
        )  # SQ delimiter
        self.fp.seek(0)
        assert self.fp.read() == expected

    def test_big_endian_correct_data(self):
        """Pixel data starting with an item tag is written."""
        self.fp.is_little_endian = False
        self.fp.is_implicit_VR = False
        pixel_data = DataElement(
            0x7FE00010,
            "OB",
            b"\xff\xfe\xe0\x00\x00\x01\x02\x03",
            is_undefined_length=True,
        )
        write_data_element(self.fp, pixel_data)
        expected = (
            b"\x7f\xe0\x00\x10"  # tag
            b"OB\x00\x00"  # VR
            b"\xff\xff\xff\xff"  # length
            b"\xff\xfe\xe0\x00\x00\x01\x02\x03"  # contents
            b"\xff\xfe\xe0\xdd\x00\x00\x00\x00"
        )  # SQ delimiter
        self.fp.seek(0)
        assert self.fp.read() == expected

    @pytest.mark.parametrize(
        "data",
        (
            b"\xff\xff\x00\xe0" b"\x00\x01\x02\x03" b"\xfe\xff\xdd\xe0",
            BytesIO(b"\xff\xff\x00\xe0" b"\x00\x01\x02\x03" b"\xfe\xff\xdd\xe0"),
        ),
    )
    def test_little_endian_incorrect_data(self, data):
        """Writing pixel data not starting with an item tag raises."""
        self.fp.is_little_endian = True
        self.fp.is_implicit_VR = False
        pixel_data = DataElement(
            0x7FE00010,
            "OB",
            data,
            is_undefined_length=True,
        )
        msg = (
            r"The \(7FE0,0010\) 'Pixel Data' element value hasn't been encapsulated "
            "as required for a compressed transfer syntax - see "
            r"pydicom.encaps.encapsulate\(\) for more information"
        )
        with pytest.raises(ValueError, match=msg):
            write_data_element(self.fp, pixel_data)

    @pytest.mark.parametrize(
        "data",
        (
            b"\x00\x00\x00\x00" b"\x00\x01\x02\x03" b"\xff\xfe\xe0\xdd",
            BytesIO(b"\x00\x00\x00\x00" b"\x00\x01\x02\x03" b"\xff\xfe\xe0\xdd"),
        ),
    )
    def test_big_endian_incorrect_data(self, data):
        """Writing pixel data not starting with an item tag raises."""
        self.fp.is_little_endian = False
        self.fp.is_implicit_VR = False
        pixel_data = DataElement(
            0x7FE00010,
            "OB",
            data,
            is_undefined_length=True,
        )
        msg = (
            r"The \(7FE0,0010\) 'Pixel Data' element value hasn't been encapsulated "
            "as required for a compressed transfer syntax - see "
            r"pydicom.encaps.encapsulate\(\) for more information"
        )
        with pytest.raises(ValueError, match=msg):
            write_data_element(self.fp, pixel_data)

    def test_writing_to_gzip(self):
        file_path = tempfile.NamedTemporaryFile(suffix=".dcm").name
        ds = dcmread(rtplan_name)
        import gzip

        with gzip.open(file_path, "w") as fp:
            ds.save_as(fp, enforce_file_format=True)
        with gzip.open(file_path, "r") as fp:
            ds_unzipped = dcmread(fp)
            for elem_in, elem_out in zip(ds, ds_unzipped):
                assert elem_in == elem_out

    def test_writing_too_big_data_in_explicit_encoding(self):
        """Data too large to be written in explicit transfer syntax."""
        self.fp.is_little_endian = True
        self.fp.is_implicit_VR = True
        # make a multi-value larger than 64kB
        single_value = b"123456.789012345"
        large_value = b"\\".join([single_value] * 4500)
        # can be written with implicit transfer syntax,
        # where the length field is 4 bytes long
        pixel_data = DataElement(
            0x30040058, "DS", large_value, is_undefined_length=False
        )
        write_data_element(self.fp, pixel_data)
        self.fp.seek(0)
        ds = read_dataset(self.fp, True, True)
        assert "DS" == ds[0x30040058].VR

        self.fp = DicomBytesIO()
        self.fp.is_little_endian = True
        self.fp.is_implicit_VR = False

        msg = (
            r"The value for the data element \(3004,0058\) exceeds the "
            r"size of 64 kByte and cannot be written in an explicit "
            r"transfer syntax. The data element VR is changed from "
            r"'DS' to 'UN' to allow saving the data."
        )

        with pytest.warns(UserWarning, match=msg):
            write_data_element(self.fp, pixel_data)
        self.fp.seek(0)
        ds = read_dataset(self.fp, False, True)
        assert "UN" == ds[0x30040058].VR

        # we expect the same behavior in Big Endian transfer syntax
        self.fp = DicomBytesIO()
        self.fp.is_little_endian = False
        self.fp.is_implicit_VR = False
        with pytest.warns(UserWarning, match=msg):
            write_data_element(self.fp, pixel_data)
        self.fp.seek(0)
        ds = read_dataset(self.fp, False, False)
        assert "UN" == ds[0x30040058].VR


def test_all_writers():
    """Test that the VR writer functions are complete"""
    assert set(VR) == set(writers)


class TestWritingBufferedPixelData:
    @pytest.mark.parametrize("bits_allocated", (8, 16))
    def test_writing_dataset_with_buffered_pixel_data(self, bits_allocated):
        pixel_data = b"\x00\x01\x02\x03"

        # Baseline
        fp = DicomBytesIO()
        fp.is_little_endian = True
        fp.is_implicit_VR = False

        ds = Dataset()
        ds.BitsAllocated = bits_allocated
        ds.PixelData = pixel_data

        ds.save_as(fp, implicit_vr=False, little_endian=True)

        fp_buffered = DicomBytesIO()
        fp_buffered.is_little_endian = True
        fp_buffered.is_implicit_VR = False

        ds_buffered = Dataset()
        ds_buffered.BitsAllocated = bits_allocated
        ds_buffered.PixelData = BytesIO(pixel_data)

        ds_buffered.save_as(fp_buffered, implicit_vr=False, little_endian=True)

        assert fp.getvalue() == fp_buffered.getvalue()

    @pytest.mark.skipif(not HAVE_RESOURCE, reason="resource is unix only")
    @pytest.mark.parametrize("bits_allocated", (8, 16))
    def test_writing_dataset_with_buffered_pixel_data_reads_data_in_chunks(
        self, bits_allocated
    ):
        KILOBYTE = 1000
        MEGABYTE = KILOBYTE * 1000
        FILE_SIZE = 50 * MEGABYTE

        ds = Dataset()
        ds.BitsAllocated = bits_allocated

        with TemporaryFile("+wb") as buffer, TemporaryFile("+wb") as fp:
            buffer.write(b"\x00" * FILE_SIZE)
            buffer.seek(0)

            # take a snapshot of memory
            baseline_memory_usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

            # set the pixel data to the buffer
            ds.PixelData = buffer
            ds.save_as(fp, little_endian=True, implicit_vr=False)

            memory_usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

            # on MacOS, maxrss is in bytes. On unix, its in kilobytes
            limit = 0
            if sys.platform.startswith("linux"):
                # memory usage is in kilobytes
                limit = (FILE_SIZE / 5 * 4) / KILOBYTE
            elif sys.platform.startswith("darwin"):
                # memory usage is in bytes
                limit = FILE_SIZE / 5 * 4
            else:
                pytest.skip("This test is not setup to run on this platform")

            # if we have successfully kept the PixelData out of memory, then our peak
            #   memory usage # usage be less than prev peak + the size of the file
            assert memory_usage < (baseline_memory_usage + limit)

    @pytest.mark.parametrize("vr", BUFFERABLE_VRS)
    def test_all_supported_VRS_can_write_a_buffered_value(self, vr):
        data = b"\x00\x01\x02\x03"
        buffer = BytesIO(data)

        fp = DicomBytesIO()
        fp.is_little_endian = True
        fp.is_implicit_VR = False

        fn, _ = writers[cast(VR, vr)]
        fn(fp, DataElement("PixelData", vr, buffer))

        assert fp.getvalue() == data

    @pytest.mark.skipif(IS_WINDOWS, reason="TemporaryFile on Windows always readable")
    def test_saving_a_file_with_a_closed_file(self):
        ds = Dataset()
        ds.BitsAllocated = 8

        with TemporaryFile("+wb") as f:
            ds.PixelData = f

        with TemporaryFile("+wb") as f:
            msg = (
                r"Invalid buffer for \(7FE0,0010\) 'Pixel Data': the buffer has been "
                "closed"
            )
            with pytest.raises(ValueError, match=msg):
                ds.save_as(f, little_endian=True, implicit_vr=True)


@pytest.fixture
def use_future():
    original = config._use_future
    config._use_future = True
    yield
    config._use_future = original


class TestFuture:
    def test_dcmwrite_write_like_original_raises(self, use_future):
        ds = Dataset()
        msg = (
            "'write_like_original' is no longer accepted as a positional "
            "or keyword argument, use 'enforce_file_format' instead"
        )
        with pytest.raises(TypeError, match=msg):
            dcmwrite(None, ds, write_like_original=True)

        with pytest.raises(TypeError, match=msg):
            dcmwrite(None, ds, write_like_original=False)

        with pytest.raises(TypeError, match=msg):
            dcmwrite(None, ds, False)

        with pytest.raises(TypeError, match=msg):
            dcmwrite(None, ds, True)

    def test_dcmwrite_arg_kwarg_raises(self, use_future):
        ds = Dataset()
        msg = (
            "'write_like_original' is no longer accepted as a positional "
            "or keyword argument, use 'enforce_file_format' instead"
        )
        with pytest.raises(TypeError, match=msg):
            dcmwrite(None, ds, True, write_like_original=True)
