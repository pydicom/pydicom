# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""unittest cases for pydicom.filewriter module"""

from copy import deepcopy
from datetime import date, datetime, time, timedelta
from io import BytesIO
import os
import sys
import unittest

from struct import unpack
from tempfile import TemporaryFile

import pytest

from pydicom._storage_sopclass_uids import CTImageStorage
from pydicom import config, __version_info__, uid
from pydicom.data import get_testdata_files, get_charset_files
from pydicom.dataset import Dataset, FileDataset
from pydicom.dataelem import DataElement, RawDataElement
from pydicom.filebase import DicomBytesIO
from pydicom.filereader import dcmread, read_dataset
from pydicom.filewriter import (write_data_element, write_dataset,
                                correct_ambiguous_vr, write_file_meta_info,
                                correct_ambiguous_vr_element, write_numbers,
                                write_PN, _format_DT)
from pydicom.multival import MultiValue
from pydicom.sequence import Sequence
from pydicom.uid import (ImplicitVRLittleEndian, ExplicitVRBigEndian,
                         PYDICOM_IMPLEMENTATION_UID)
from pydicom.util.hexutil import hex2bytes, bytes2hex
from pydicom.util.fixes import timezone
from pydicom.valuerep import DA, DT, TM
from ._write_stds import impl_LE_deflen_std_hex


rtplan_name = get_testdata_files("rtplan.dcm")[0]
rtdose_name = get_testdata_files("rtdose.dcm")[0]
ct_name = get_testdata_files("CT_small.dcm")[0]
mr_name = get_testdata_files("MR_small.dcm")[0]
mr_implicit_name = get_testdata_files("MR_small_implicit.dcm")[0]
mr_bigendian_name = get_testdata_files("MR_small_bigendian.dcm")[0]
jpeg_name = get_testdata_files("JPEG2000.dcm")[0]
no_ts = get_testdata_files("meta_missing_tsyntax.dcm")[0]
color_pl_name = get_testdata_files("color-pl.dcm")[0]
sc_rgb_name = get_testdata_files("SC_rgb.dcm")[0]
datetime_name = mr_name

unicode_name = get_charset_files("chrH31.dcm")[0]
multiPN_name = get_charset_files("chrFrenMulti.dcm")[0]

base_version = '.'.join(str(i) for i in __version_info__)


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


class WriteFileTests(unittest.TestCase):
    def setUp(self):
        self.file_out = TemporaryFile('w+b')

    def tearDown(self):
        self.file_out.close()

    def compare(self, in_filename):
        """Read Dataset from in_filename, write to file, compare"""
        with open(in_filename, 'rb') as f:
            bytes_in = BytesIO(f.read())
            bytes_in.seek(0)

        ds = dcmread(bytes_in)
        ds.save_as(self.file_out, write_like_original=True)
        self.file_out.seek(0)
        bytes_out = BytesIO(self.file_out.read())
        bytes_in.seek(0)
        bytes_out.seek(0)
        same, pos = bytes_identical(bytes_in.getvalue(), bytes_out.getvalue())
        self.assertTrue(same, "Read bytes is not identical to written bytes - "
                        "first difference at 0x%x" % pos)

    def compare_bytes(self, bytes_in, bytes_out):
        """Compare two bytestreams for equality"""
        same, pos = bytes_identical(bytes_in, bytes_out)
        self.assertTrue(same, "Bytestreams are not identical - first "
                        "difference at 0x%x" % pos)

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
        ds.save_as(self.file_out, write_like_original=True)
        self.file_out.seek(0)
        # Now read it back in and check that the values were changed
        ds = dcmread(self.file_out)
        self.assertTrue(ds.ImageType[1] == CS_expected,
                        "Item in a list not written correctly to file (VR=CS)")
        self.assertTrue(ds[0x00431012].value[0] == SS_expected,
                        "Item in a list not written correctly to file (VR=SS)")
        self.assertTrue(ds.ImagePositionPatient[2] == DS_expected,
                        "Item in a list not written correctly to file (VR=DS)")

    def testwrite_short_uid(self):
        ds = dcmread(rtplan_name)
        ds.SOPInstanceUID = "1.2"
        ds.save_as(self.file_out, write_like_original=True)
        self.file_out.seek(0)
        ds = dcmread(self.file_out)
        self.assertEqual(ds.SOPInstanceUID, "1.2")

    def test_write_no_ts(self):
        """Test reading a file with no ts and writing it out identically."""
        ds = dcmread(no_ts)
        ds.save_as(self.file_out, write_like_original=True)
        self.file_out.seek(0)
        with open(no_ts, 'rb') as ref_file:
            written_bytes = self.file_out.read()
            read_bytes = ref_file.read()
            self.compare_bytes(read_bytes, written_bytes)

    def test_write_double_filemeta(self):
        """Test writing file meta from Dataset doesn't work"""
        ds = dcmread(ct_name)
        ds.TransferSyntaxUID = '1.1'
        self.assertRaises(ValueError, ds.save_as, self.file_out)

    def test_write_ffff_ffff(self):
        """Test writing element (FFFF, FFFF) to file #92"""
        fp = DicomBytesIO()
        ds = Dataset()
        ds.file_meta = Dataset()
        ds.is_little_endian = True
        ds.is_implicit_VR = True
        ds.add_new(0xFFFFFFFF, 'LO', '123456')
        ds.save_as(fp, write_like_original=True)

        fp.seek(0)
        ds = dcmread(fp, force=True)
        assert ds[0xFFFFFFFF].value == b'123456'

    def test_write_removes_grouplength(self):
        ds = dcmread(color_pl_name)
        assert 0x00080000 in ds
        ds.save_as(self.file_out, write_like_original=True)
        self.file_out.seek(0)
        ds = dcmread(self.file_out)
        # group length has been removed
        assert 0x00080000 not in ds


class ScratchWriteDateTimeTests(WriteFileTests):
    """Write and reread simple or multi-value DA/DT/TM data elements"""

    def setUp(self):
        config.datetime_conversion = True
        self.file_out = TemporaryFile('w+b')

    def tearDown(self):
        config.datetime_conversion = False
        self.file_out.close()

    def test_multivalue_DA(self):
        """Write DA/DT/TM data elements.........."""
        multi_DA_expected = (date(1961, 8, 4), date(1963, 11, 22))
        DA_expected = date(1961, 8, 4)
        tzinfo = timezone(timedelta(seconds=-21600), '-0600')
        multi_DT_expected = (datetime(1961, 8, 4), datetime(
            1963, 11, 22, 12, 30, 0, 0,
            timezone(timedelta(seconds=-21600), '-0600')))
        multi_TM_expected = (time(1, 23, 45), time(11, 11, 11))
        TM_expected = time(11, 11, 11, 1)
        ds = dcmread(datetime_name)
        # Add date/time data elements
        ds.CalibrationDate = MultiValue(DA, multi_DA_expected)
        ds.DateOfLastCalibration = DA(DA_expected)
        ds.ReferencedDateTime = MultiValue(DT, multi_DT_expected)
        ds.CalibrationTime = MultiValue(TM, multi_TM_expected)
        ds.TimeOfLastCalibration = TM(TM_expected)
        ds.save_as(self.file_out, write_like_original=True)
        self.file_out.seek(0)
        # Now read it back in and check the values are as expected
        ds = dcmread(self.file_out)
        self.assertSequenceEqual(multi_DA_expected, ds.CalibrationDate)
        self.assertEqual(DA_expected, ds.DateOfLastCalibration)
        self.assertSequenceEqual(multi_DT_expected, ds.ReferencedDateTime)
        self.assertSequenceEqual(multi_TM_expected, ds.CalibrationTime)
        self.assertEqual(TM_expected, ds.TimeOfLastCalibration)


class WriteDataElementTests(unittest.TestCase):
    """Attempt to write data elements has the expected behaviour"""

    def setUp(self):
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
            return fp.parent.getvalue()

    def test_empty_AT(self):
        """Write empty AT correctly.........."""
        # Was issue 74
        data_elem = DataElement(0x00280009, "AT", [])
        expected = hex2bytes((
            " 28 00 09 00"  # (0028,0009) Frame Increment Pointer
            " 00 00 00 00"  # length 0
        ))
        write_data_element(self.f1, data_elem)
        got = self.f1.getvalue()
        msg = ("Did not write zero-length AT value correctly. "
               "Expected %r, got %r") % (bytes2hex(expected), bytes2hex(got))
        self.assertEqual(expected, got, msg)

    def check_data_element(self, data_elem, expected):
        encoded_elem = self.encode_element(data_elem)
        self.assertEqual(expected, encoded_elem)

    def test_write_empty_LO(self):
        data_elem = DataElement(0x00080070, 'LO', None)
        expected = (b'\x08\x00\x70\x00'  # tag
                    b'\x00\x00\x00\x00'  # length
                    )  # value
        self.check_data_element(data_elem, expected)

    def test_write_DA(self):
        data_elem = DataElement(0x00080022, 'DA', '20000101')
        expected = (b'\x08\x00\x22\x00'  # tag
                    b'\x08\x00\x00\x00'  # length
                    b'20000101')  # value
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x00080022, 'DA', date(2000, 1, 1))
        self.check_data_element(data_elem, expected)

    def test_write_multi_DA(self):
        data_elem = DataElement(0x0014407E, 'DA', ['20100101', b'20101231'])
        expected = (b'\x14\x00\x7E\x40'  # tag
                    b'\x12\x00\x00\x00'  # length
                    b'20100101\\20101231 ')  # padded value
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x0014407E, 'DA', [date(2010, 1, 1),
                                                   date(2010, 12, 31)])
        self.check_data_element(data_elem, expected)

    def test_write_TM(self):
        data_elem = DataElement(0x00080030, 'TM', '010203')
        expected = (b'\x08\x00\x30\x00'  # tag
                    b'\x06\x00\x00\x00'  # length
                    b'010203')  # padded value
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x00080030, 'TM', b'010203')
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x00080030, 'TM', time(1, 2, 3))
        self.check_data_element(data_elem, expected)

    def test_write_multi_TM(self):
        data_elem = DataElement(0x0014407C, 'TM', ['082500', b'092655'])
        expected = (b'\x14\x00\x7C\x40'  # tag
                    b'\x0E\x00\x00\x00'  # length
                    b'082500\\092655 ')  # padded value
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x0014407C, 'TM', [time(8, 25),
                                                   time(9, 26, 55)])
        self.check_data_element(data_elem, expected)

    def test_write_DT(self):
        data_elem = DataElement(0x0008002A, 'DT', '20170101120000')
        expected = (b'\x08\x00\x2A\x00'  # tag
                    b'\x0E\x00\x00\x00'  # length
                    b'20170101120000')  # value
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x0008002A, 'DT', b'20170101120000')
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x0008002A, 'DT', datetime(2017, 1, 1, 12))
        self.check_data_element(data_elem, expected)

    def test_write_multi_DT(self):
        data_elem = DataElement(0x0040A13A, 'DT',
                                ['20120820120804', b'20130901111111'])
        expected = (b'\x40\x00\x3A\xA1'  # tag
                    b'\x1E\x00\x00\x00'  # length
                    b'20120820120804\\20130901111111 ')  # padded value
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(
            0x0040A13A, 'DT', u'20120820120804\\20130901111111')
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(
            0x0040A13A, 'DT', b'20120820120804\\20130901111111')
        self.check_data_element(data_elem, expected)

        data_elem = DataElement(0x0040A13A, 'DT',
                                [datetime(2012, 8, 20, 12, 8, 4),
                                 datetime(2013, 9, 1, 11, 11, 11)])
        self.check_data_element(data_elem, expected)

    def test_write_ascii_vr_with_padding(self):
        expected = (b'\x08\x00\x54\x00'  # tag
                    b'\x0C\x00\x00\x00'  # length
                    b'CONQUESTSRV ')  # padded value
        data_elem = DataElement(0x00080054, 'AE', 'CONQUESTSRV')
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x00080054, 'AE', b'CONQUESTSRV')
        self.check_data_element(data_elem, expected)

        expected = (b'\x08\x00\x62\x00'  # tag
                    b'\x06\x00\x00\x00'  # length
                    b'1.2.3\x00')  # padded value
        data_elem = DataElement(0x00080062, 'UI', '1.2.3')
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x00080062, 'UI', b'1.2.3')
        self.check_data_element(data_elem, expected)

        expected = (b'\x08\x00\x60\x00'  # tag
                    b'\x04\x00\x00\x00'  # length
                    b'REG ')
        data_elem = DataElement(0x00080060, 'CS', 'REG')
        self.check_data_element(data_elem, expected)
        data_elem = DataElement(0x00080060, 'CS', b'REG')
        self.check_data_element(data_elem, expected)

    def test_write_OD_implicit_little(self):
        """Test writing elements with VR of OD works correctly."""
        # VolumetricCurvePoints
        bytestring = b'\x00\x01\x02\x03\x04\x05\x06\x07' \
                     b'\x01\x01\x02\x03\x04\x05\x06\x07'
        elem = DataElement(0x0070150d, 'OD', bytestring)
        encoded_elem = self.encode_element(elem)
        # Tag pair (0070, 150d): 70 00 0d 15
        # Length (16): 10 00 00 00
        #             | Tag          |   Length      |    Value ->
        ref_bytes = b'\x70\x00\x0d\x15\x10\x00\x00\x00' + bytestring
        self.assertEqual(encoded_elem, ref_bytes)

        # Empty data
        elem.value = b''
        encoded_elem = self.encode_element(elem)
        ref_bytes = b'\x70\x00\x0d\x15\x00\x00\x00\x00'
        self.assertEqual(encoded_elem, ref_bytes)

    def test_write_OD_explicit_little(self):
        """Test writing elements with VR of OD works correctly.

        Elements with a VR of 'OD' use the newer explicit VR
        encoding (see PS3.5 Section 7.1.2).
        """
        # VolumetricCurvePoints
        bytestring = b'\x00\x01\x02\x03\x04\x05\x06\x07' \
                     b'\x01\x01\x02\x03\x04\x05\x06\x07'
        elem = DataElement(0x0070150d, 'OD', bytestring)
        encoded_elem = self.encode_element(elem, False, True)
        # Tag pair (0070, 150d): 70 00 0d 15
        # VR (OD): \x4f\x44
        # Reserved: \x00\x00
        # Length (16): \x10\x00\x00\x00
        #             | Tag          | VR    |
        ref_bytes = b'\x70\x00\x0d\x15\x4f\x44' \
                    b'\x00\x00\x10\x00\x00\x00' + bytestring
        #             |Rsrvd |   Length      |    Value ->
        self.assertEqual(encoded_elem, ref_bytes)

        # Empty data
        elem.value = b''
        encoded_elem = self.encode_element(elem, False, True)
        ref_bytes = b'\x70\x00\x0d\x15\x4f\x44\x00\x00\x00\x00\x00\x00'
        self.assertEqual(encoded_elem, ref_bytes)

    def test_write_OL_implicit_little(self):
        """Test writing elements with VR of OL works correctly."""
        # TrackPointIndexList
        bytestring = b'\x00\x01\x02\x03\x04\x05\x06\x07' \
                     b'\x01\x01\x02\x03'
        elem = DataElement(0x00660129, 'OL', bytestring)
        encoded_elem = self.encode_element(elem)
        # Tag pair (0066, 0129): 66 00 29 01
        # Length (12): 0c 00 00 00
        #             | Tag          |   Length      |    Value ->
        ref_bytes = b'\x66\x00\x29\x01\x0c\x00\x00\x00' + bytestring
        self.assertEqual(encoded_elem, ref_bytes)

        # Empty data
        elem.value = b''
        encoded_elem = self.encode_element(elem)
        ref_bytes = b'\x66\x00\x29\x01\x00\x00\x00\x00'
        self.assertEqual(encoded_elem, ref_bytes)

    def test_write_OL_explicit_little(self):
        """Test writing elements with VR of OL works correctly.

        Elements with a VR of 'OL' use the newer explicit VR
        encoding (see PS3.5 Section 7.1.2).
        """
        # TrackPointIndexList
        bytestring = b'\x00\x01\x02\x03\x04\x05\x06\x07' \
                     b'\x01\x01\x02\x03'
        elem = DataElement(0x00660129, 'OL', bytestring)
        encoded_elem = self.encode_element(elem, False, True)
        # Tag pair (0066, 0129): 66 00 29 01
        # VR (OL): \x4f\x4c
        # Reserved: \x00\x00
        # Length (12): 0c 00 00 00
        #             | Tag          | VR    |
        ref_bytes = b'\x66\x00\x29\x01\x4f\x4c' \
                    b'\x00\x00\x0c\x00\x00\x00' + bytestring
        #             |Rsrvd |   Length      |    Value ->
        self.assertEqual(encoded_elem, ref_bytes)

        # Empty data
        elem.value = b''
        encoded_elem = self.encode_element(elem, False, True)
        ref_bytes = b'\x66\x00\x29\x01\x4f\x4c\x00\x00\x00\x00\x00\x00'
        self.assertEqual(encoded_elem, ref_bytes)

    def test_write_UC_implicit_little(self):
        """Test writing elements with VR of UC works correctly."""
        # VM 1, even data
        elem = DataElement(0x00189908, 'UC', 'Test')
        encoded_elem = self.encode_element(elem)
        # Tag pair (0018, 9908): 08 00 20 01
        # Length (4): 04 00 00 00
        # Value: \x54\x65\x73\x74
        ref_bytes = b'\x18\x00\x08\x99\x04\x00\x00\x00\x54\x65\x73\x74'
        self.assertEqual(encoded_elem, ref_bytes)

        # VM 1, odd data - padded to even length
        elem.value = 'Test.'
        encoded_elem = self.encode_element(elem)
        ref_bytes = b'\x18\x00\x08\x99\x06\x00\x00\x00\x54\x65\x73\x74\x2e\x20'
        self.assertEqual(encoded_elem, ref_bytes)

        # VM 3, even data
        elem.value = ['Aa', 'B', 'C']
        encoded_elem = self.encode_element(elem)
        ref_bytes = b'\x18\x00\x08\x99\x06\x00\x00\x00\x41\x61\x5c\x42\x5c\x43'
        self.assertEqual(encoded_elem, ref_bytes)

        # VM 3, odd data - padded to even length
        elem.value = ['A', 'B', 'C']
        encoded_elem = self.encode_element(elem)
        ref_bytes = b'\x18\x00\x08\x99\x06\x00\x00\x00\x41\x5c\x42\x5c\x43\x20'
        self.assertEqual(encoded_elem, ref_bytes)

        # Empty data
        elem.value = ''
        encoded_elem = self.encode_element(elem)
        ref_bytes = b'\x18\x00\x08\x99\x00\x00\x00\x00'
        self.assertEqual(encoded_elem, ref_bytes)

    def test_write_UC_explicit_little(self):
        """Test writing elements with VR of UC works correctly.

        Elements with a VR of 'UC' use the newer explicit VR
        encoding (see PS3.5 Section 7.1.2).
        """
        # VM 1, even data
        elem = DataElement(0x00189908, 'UC', 'Test')
        encoded_elem = self.encode_element(elem, False, True)
        # Tag pair (0018, 9908): 08 00 20 01
        # VR (UC): \x55\x43
        # Reserved: \x00\x00
        # Length (4): \x04\x00\x00\x00
        # Value: \x54\x65\x73\x74
        ref_bytes = b'\x18\x00\x08\x99\x55\x43\x00\x00\x04\x00\x00\x00' \
                    b'\x54\x65\x73\x74'
        self.assertEqual(encoded_elem, ref_bytes)

        # VM 1, odd data - padded to even length
        elem.value = 'Test.'
        encoded_elem = self.encode_element(elem, False, True)
        ref_bytes = b'\x18\x00\x08\x99\x55\x43\x00\x00\x06\x00\x00\x00' \
                    b'\x54\x65\x73\x74\x2e\x20'
        self.assertEqual(encoded_elem, ref_bytes)

        # VM 3, even data
        elem.value = ['Aa', 'B', 'C']
        encoded_elem = self.encode_element(elem, False, True)
        ref_bytes = b'\x18\x00\x08\x99\x55\x43\x00\x00\x06\x00\x00\x00' \
                    b'\x41\x61\x5c\x42\x5c\x43'
        self.assertEqual(encoded_elem, ref_bytes)

        # VM 3, odd data - padded to even length
        elem.value = ['A', 'B', 'C']
        encoded_elem = self.encode_element(elem, False, True)
        ref_bytes = b'\x18\x00\x08\x99\x55\x43\x00\x00\x06\x00\x00\x00' \
                    b'\x41\x5c\x42\x5c\x43\x20'
        self.assertEqual(encoded_elem, ref_bytes)

        # Empty data
        elem.value = ''
        encoded_elem = self.encode_element(elem, False, True)
        ref_bytes = b'\x18\x00\x08\x99\x55\x43\x00\x00\x00\x00\x00\x00'
        self.assertEqual(encoded_elem, ref_bytes)

    def test_write_UR_implicit_little(self):
        """Test writing elements with VR of UR works correctly."""
        # Even length URL
        elem = DataElement(0x00080120, 'UR',
                           'http://github.com/darcymason/pydicom')
        encoded_elem = self.encode_element(elem)
        # Tag pair (0008, 2001): 08 00 20 01
        # Length (36): 24 00 00 00
        # Value: 68 to 6d
        ref_bytes = b'\x08\x00\x20\x01\x24\x00\x00\x00\x68\x74' \
                    b'\x74\x70\x3a\x2f\x2f\x67\x69\x74\x68\x75' \
                    b'\x62\x2e\x63\x6f\x6d\x2f\x64\x61\x72\x63' \
                    b'\x79\x6d\x61\x73\x6f\x6e\x2f\x70\x79\x64' \
                    b'\x69\x63\x6f\x6d'
        self.assertEqual(encoded_elem, ref_bytes)

        # Odd length URL has trailing \x20 (SPACE) padding
        elem.value = '../test/test.py'
        encoded_elem = self.encode_element(elem)
        # Tag pair (0008, 2001): 08 00 20 01
        # Length (16): 10 00 00 00
        # Value: 2e to 20
        ref_bytes = b'\x08\x00\x20\x01\x10\x00\x00\x00\x2e\x2e' \
                    b'\x2f\x74\x65\x73\x74\x2f\x74\x65\x73\x74' \
                    b'\x2e\x70\x79\x20'
        self.assertEqual(encoded_elem, ref_bytes)

        # Empty value
        elem.value = ''
        encoded_elem = self.encode_element(elem)
        self.assertEqual(encoded_elem,
                         b'\x08\x00\x20\x01\x00\x00\x00\x00')

    def test_write_UR_explicit_little(self):
        """Test writing elements with VR of UR works correctly.

        Elements with a VR of 'UR' use the newer explicit VR
        encoded (see PS3.5 Section 7.1.2).
        """
        # Even length URL
        elem = DataElement(0x00080120, 'UR', 'ftp://bits')
        encoded_elem = self.encode_element(elem, False, True)
        # Tag pair (0008, 2001): 08 00 20 01
        # VR (UR): \x55\x52
        # Reserved: \x00\x00
        # Length (4): \x0a\x00\x00\x00
        # Value: \x66\x74\x70\x3a\x2f\x2f\x62\x69\x74\x73
        ref_bytes = b'\x08\x00\x20\x01\x55\x52\x00\x00\x0a\x00\x00\x00' \
                    b'\x66\x74\x70\x3a\x2f\x2f\x62\x69\x74\x73'
        self.assertEqual(encoded_elem, ref_bytes)

        # Odd length URL has trailing \x20 (SPACE) padding
        elem.value = 'ftp://bit'
        encoded_elem = self.encode_element(elem, False, True)
        ref_bytes = b'\x08\x00\x20\x01\x55\x52\x00\x00\x0a\x00\x00\x00' \
                    b'\x66\x74\x70\x3a\x2f\x2f\x62\x69\x74\x20'
        self.assertEqual(encoded_elem, ref_bytes)

        # Empty value
        elem.value = ''
        encoded_elem = self.encode_element(elem, False, True)
        ref_bytes = b'\x08\x00\x20\x01\x55\x52\x00\x00\x00\x00\x00\x00'
        self.assertEqual(encoded_elem, ref_bytes)

    def test_write_UN_implicit_little(self):
        """Test writing UN VR in implicit little"""
        elem = DataElement(0x00100010, 'UN', b'\x01\x02')
        assert self.encode_element(elem) == (
            b'\x10\x00\x10\x00\x02\x00\x00\x00\x01\x02')

    def test_write_unknown_vr_raises(self):
        """Test exception raised trying to write unknown VR element"""
        fp = DicomBytesIO()
        fp.is_implicit_VR = True
        fp.is_little_endian = True
        elem = DataElement(0x00100010, 'ZZ', 'Test')
        with pytest.raises(NotImplementedError,
                           match="write_data_element: unknown Value "
                                 "Representation 'ZZ'"):
            write_data_element(fp, elem)


class TestCorrectAmbiguousVR(unittest.TestCase):
    """Test correct_ambiguous_vr."""

    def test_pixel_representation_vm_one(self):
        """Test correcting VM 1 elements which require PixelRepresentation."""
        ref_ds = Dataset()

        # If PixelRepresentation is 0 then VR should be US
        ref_ds.PixelRepresentation = 0
        ref_ds.SmallestValidPixelValue = b'\x00\x01'  # Little endian 256
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.SmallestValidPixelValue, 256)
        self.assertEqual(ds[0x00280104].VR, 'US')

        # If PixelRepresentation is 1 then VR should be SS
        ref_ds.PixelRepresentation = 1
        ref_ds.SmallestValidPixelValue = b'\x00\x01'  # Big endian 1
        ds = correct_ambiguous_vr(deepcopy(ref_ds), False)
        self.assertEqual(ds.SmallestValidPixelValue, 1)
        self.assertEqual(ds[0x00280104].VR, 'SS')

        # If no PixelRepresentation then should be unchanged
        ref_ds = Dataset()
        ref_ds.SmallestValidPixelValue = b'\x00\x01'  # Big endian 1
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.SmallestValidPixelValue, b'\x00\x01')
        self.assertEqual(ds[0x00280104].VR, 'US or SS')

    def test_pixel_representation_vm_three(self):
        """Test correcting VM 3 elements which require PixelRepresentation."""
        ref_ds = Dataset()

        # If PixelRepresentation is 0 then VR should be US - Little endian
        ref_ds.PixelRepresentation = 0
        ref_ds.LUTDescriptor = b'\x01\x00\x00\x01\x10\x00'  # 1\256\16
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.LUTDescriptor, [1, 256, 16])
        self.assertEqual(ds[0x00283002].VR, 'US')

        # If PixelRepresentation is 1 then VR should be SS
        ref_ds.PixelRepresentation = 1
        ref_ds.LUTDescriptor = b'\x01\x00\x00\x01\x00\x10'
        ds = correct_ambiguous_vr(deepcopy(ref_ds), False)
        self.assertEqual(ds.LUTDescriptor, [256, 1, 16])
        self.assertEqual(ds[0x00283002].VR, 'SS')

        # If no PixelRepresentation then should be unchanged
        ref_ds = Dataset()
        ref_ds.LUTDescriptor = b'\x01\x00\x00\x01\x00\x10'
        ds = correct_ambiguous_vr(deepcopy(ref_ds), False)
        self.assertEqual(ds.LUTDescriptor, b'\x01\x00\x00\x01\x00\x10')
        self.assertEqual(ds[0x00283002].VR, 'US or SS')

    def test_pixel_data(self):
        """Test correcting PixelData."""
        ref_ds = Dataset()

        # If BitsAllocated  > 8 then VR must be OW
        ref_ds.BitsAllocated = 16
        ref_ds.PixelData = b'\x00\x01'  # Little endian 256
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)  # Little endian
        self.assertEqual(ds.PixelData, b'\x00\x01')
        self.assertEqual(ds[0x7fe00010].VR, 'OW')
        ds = correct_ambiguous_vr(deepcopy(ref_ds), False)  # Big endian
        self.assertEqual(ds.PixelData, b'\x00\x01')
        self.assertEqual(ds[0x7fe00010].VR, 'OW')

        # If BitsAllocated <= 8 then VR can be OB or OW: OW
        ref_ds = Dataset()
        ref_ds.BitsAllocated = 8
        ref_ds.Rows = 2
        ref_ds.Columns = 2
        ref_ds.PixelData = b'\x01\x00\x02\x00\x03\x00\x04\x00'
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.PixelData, b'\x01\x00\x02\x00\x03\x00\x04\x00')
        self.assertEqual(ds[0x7fe00010].VR, 'OW')

        # If BitsAllocated <= 8 then VR can be OB or OW: OB
        ref_ds = Dataset()
        ref_ds.BitsAllocated = 8
        ref_ds.Rows = 2
        ref_ds.Columns = 2
        ref_ds.PixelData = b'\x01\x02\x03\x04'
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.PixelData, b'\x01\x02\x03\x04')
        self.assertEqual(ds[0x7fe00010].VR, 'OB')

        # If no BitsAllocated then VR should be unchanged
        ref_ds = Dataset()
        ref_ds.PixelData = b'\x00\x01'  # Big endian 1
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.PixelData, b'\x00\x01')
        self.assertEqual(ds[0x7fe00010].VR, 'OB or OW')

        # If required elements missing then VR should be unchanged
        ref_ds = Dataset()
        ref_ds.BitsAllocated = 8
        ref_ds.Rows = 2
        ref_ds.PixelData = b'\x01\x02\x03\x04'
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.PixelData, b'\x01\x02\x03\x04')
        self.assertEqual(ds[0x7fe00010].VR, 'OB or OW')

    def test_waveform_bits_allocated(self):
        """Test correcting elements which require WaveformBitsAllocated."""
        ref_ds = Dataset()

        # If WaveformBitsAllocated  > 8 then VR must be OW
        ref_ds.WaveformBitsAllocated = 16
        ref_ds.WaveformData = b'\x00\x01'  # Little endian 256
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)  # Little endian
        self.assertEqual(ds.WaveformData, b'\x00\x01')
        self.assertEqual(ds[0x54001010].VR, 'OW')
        ds = correct_ambiguous_vr(deepcopy(ref_ds), False)  # Big endian
        self.assertEqual(ds.WaveformData, b'\x00\x01')
        self.assertEqual(ds[0x54001010].VR, 'OW')

        # If WaveformBitsAllocated <= 8 then VR is OB or OW, but not sure which
        #   so leave VR unchanged
        ref_ds.WaveformBitsAllocated = 8
        ref_ds.WaveformData = b'\x01\x02'
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.WaveformData, b'\x01\x02')
        self.assertEqual(ds[0x54001010].VR, 'OB or OW')

        # If no WaveformBitsAllocated then VR should be unchanged
        ref_ds = Dataset()
        ref_ds.WaveformData = b'\x00\x01'  # Big endian 1
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.WaveformData, b'\x00\x01')
        self.assertEqual(ds[0x54001010].VR, 'OB or OW')

    def test_lut_descriptor(self):
        """Test correcting elements which require LUTDescriptor."""
        ref_ds = Dataset()
        ref_ds.PixelRepresentation = 0

        # If LUTDescriptor[0] is 1 then LUTData VR is 'US'
        ref_ds.LUTDescriptor = b'\x01\x00\x00\x01\x10\x00'  # 1\256\16
        ref_ds.LUTData = b'\x00\x01'  # Little endian 256
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)  # Little endian
        self.assertEqual(ds.LUTDescriptor[0], 1)
        self.assertEqual(ds[0x00283002].VR, 'US')
        self.assertEqual(ds.LUTData, 256)
        self.assertEqual(ds[0x00283006].VR, 'US')

        # If LUTDescriptor[0] is not 1 then LUTData VR is 'OW'
        ref_ds.LUTDescriptor = b'\x02\x00\x00\x01\x10\x00'  # 2\256\16
        ref_ds.LUTData = b'\x00\x01\x00\x02'
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)  # Little endian
        self.assertEqual(ds.LUTDescriptor[0], 2)
        self.assertEqual(ds[0x00283002].VR, 'US')
        self.assertEqual(ds.LUTData, b'\x00\x01\x00\x02')
        self.assertEqual(ds[0x00283006].VR, 'OW')

        # If no LUTDescriptor then VR should be unchanged
        ref_ds = Dataset()
        ref_ds.LUTData = b'\x00\x01'
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.LUTData, b'\x00\x01')
        self.assertEqual(ds[0x00283006].VR, 'US or OW')

    def test_overlay(self):
        """Test correcting OverlayData"""
        # Implicit VR must be 'OW'
        ref_ds = Dataset()
        ref_ds.is_implicit_VR = True
        ref_ds.add(DataElement(0x60003000, 'OB or OW', b'\x00'))
        ref_ds.add(DataElement(0x601E3000, 'OB or OW', b'\x00'))
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertTrue(ds[0x60003000].VR == 'OW')
        self.assertTrue(ds[0x601E3000].VR == 'OW')
        self.assertTrue(ref_ds[0x60003000].VR == 'OB or OW')
        self.assertTrue(ref_ds[0x601E3000].VR == 'OB or OW')

        # Explicit VR may be 'OB' or 'OW' (leave unchanged)
        ref_ds.is_implicit_VR = False
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertTrue(ds[0x60003000].VR == 'OB or OW')
        self.assertTrue(ref_ds[0x60003000].VR == 'OB or OW')

        # Missing is_implicit_VR (leave unchanged)
        ref_ds.is_implicit_VR = None
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertTrue(ds[0x60003000].VR == 'OB or OW')
        self.assertTrue(ref_ds[0x60003000].VR == 'OB or OW')

    def test_sequence(self):
        """Test correcting elements in a sequence."""
        ref_ds = Dataset()
        ref_ds.BeamSequence = [Dataset()]
        ref_ds.BeamSequence[0].PixelRepresentation = 0
        ref_ds.BeamSequence[0].SmallestValidPixelValue = b'\x00\x01'
        ref_ds.BeamSequence[0].BeamSequence = [Dataset()]

        ref_ds.BeamSequence[0].BeamSequence[0].PixelRepresentation = 0
        ref_ds.BeamSequence[0].BeamSequence[0].SmallestValidPixelValue = \
            b'\x00\x01'

        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        assert ds.BeamSequence[0].SmallestValidPixelValue == 256
        assert ds.BeamSequence[0][0x00280104].VR == 'US'
        assert (
            ds.BeamSequence[0].BeamSequence[0].SmallestValidPixelValue == 256)
        assert ds.BeamSequence[0].BeamSequence[0][0x00280104].VR == 'US'


class TestCorrectAmbiguousVRElement(object):
    """Test filewriter.correct_ambiguous_vr_element"""
    def test_not_ambiguous(self):
        """Test no change in element if not ambiguous"""
        elem = DataElement(0x60003000, 'OB', b'\x00')
        out = correct_ambiguous_vr_element(elem, Dataset(), True)
        assert out.VR == 'OB'
        assert out.tag == 0x60003000
        assert out.value == b'\x00'

    def test_not_ambiguous_raw_data_element(self):
        """Test no change in raw data element if not ambiguous"""
        elem = RawDataElement(0x60003000, 'OB', 1, b'\x00', 0, True, True)
        out = correct_ambiguous_vr_element(elem, Dataset(), True)
        assert out == elem
        assert type(out) == RawDataElement

    def test_correct_ambiguous_data_element(self):
        """Test correct ambiguous US/SS element"""
        ds = Dataset()
        ds.PixelPaddingValue = b'\xfe\xff'
        out = correct_ambiguous_vr_element(ds[0x00280120], ds, True)
        assert out.VR == 'US or SS'

        ds.PixelRepresentation = 0
        out = correct_ambiguous_vr_element(ds[0x00280120], ds, True)
        assert out.VR == 'US'
        assert out.value == 0xfffe

    def test_correct_ambiguous_raw_data_element(self):
        """Test that correcting ambiguous US/SS raw data element
        works and converts it to a data element"""
        ds = Dataset()
        elem = RawDataElement(
            0x00280120, 'US or SS', 2, b'\xfe\xff', 0, True, True)
        ds[0x00280120] = elem
        ds.PixelRepresentation = 0
        out = correct_ambiguous_vr_element(elem, ds, True)
        assert type(out) == DataElement
        assert out.VR == 'US'
        assert out.value == 0xfffe

    def test_pixel_data_not_ow_or_ob(self):
        """Test no change if can't figure out bit depth"""
        ds = Dataset()
        ds.Rows = 1
        ds.Columns = 1
        ds.PixelData = b'\x00\x01\x02'
        ds[0x7fe00010].VR = 'OB or OW'
        out = correct_ambiguous_vr_element(ds[0x7fe00010], ds, True)
        assert out.VR == 'OB or OW'
        assert out.tag == 0x7fe00010
        assert out.value == b'\x00\x01\x02'


class WriteAmbiguousVRTests(unittest.TestCase):
    """Attempt to write data elements with ambiguous VR."""

    def setUp(self):
        # Create a dummy (in memory) file to write to
        self.fp = DicomBytesIO()
        self.fp.is_implicit_VR = False
        self.fp.is_little_endian = True

    def test_write_explicit_vr_raises(self):
        """Test writing explicit vr raises exception if unsolved element."""
        ds = Dataset()
        ds.PerimeterValue = b'\x00\x01'

        def test():
            write_dataset(self.fp, ds)

        self.assertRaises(ValueError, test)

    def test_write_explicit_vr_little_endian(self):
        """Test writing explicit little data for ambiguous elements."""
        # Create a dataset containing element with ambiguous VRs
        ref_ds = Dataset()
        ref_ds.PixelRepresentation = 0
        ref_ds.SmallestValidPixelValue = b'\x00\x01'  # Little endian 256

        fp = BytesIO()
        file_ds = FileDataset(fp, ref_ds)
        file_ds.is_implicit_VR = False
        file_ds.is_little_endian = True
        file_ds.save_as(fp, write_like_original=True)
        fp.seek(0)

        ds = read_dataset(fp, False, True, parent_encoding='latin1')
        assert 256 == ds.SmallestValidPixelValue
        assert 'US' == ds[0x00280104].VR
        assert not ds.read_implicit_vr
        assert ds.read_little_endian
        assert ds.read_encoding == 'latin1'

    def test_write_explicit_vr_big_endian(self):
        """Test writing explicit big data for ambiguous elements."""
        # Create a dataset containing element with ambiguous VRs
        ref_ds = Dataset()
        ref_ds.PixelRepresentation = 1
        ref_ds.SmallestValidPixelValue = b'\x00\x01'  # Big endian 1
        ref_ds.SpecificCharacterSet = b'ISO_IR 192'

        fp = BytesIO()
        file_ds = FileDataset(fp, ref_ds)
        file_ds.is_implicit_VR = False
        file_ds.is_little_endian = False
        file_ds.save_as(fp, write_like_original=True)
        fp.seek(0)

        ds = read_dataset(fp, False, False)
        assert 1 == ds.SmallestValidPixelValue
        assert 'SS' == ds[0x00280104].VR
        assert not ds.read_implicit_vr
        assert not ds.read_little_endian
        assert ['UTF8', 'UTF8', 'UTF8'] == ds.read_encoding


class ScratchWriteTests(unittest.TestCase):
    """Simple dataset from scratch, written in all endian/VR combinations"""

    def setUp(self):
        # Create simple dataset for all tests
        ds = Dataset()
        ds.PatientName = "Name^Patient"
        ds.InstanceNumber = None

        # Set up a simple nested sequence
        # first, the innermost sequence
        subitem1 = Dataset()
        subitem1.ContourNumber = 1
        subitem1.ContourData = ['2', '4', '8', '16']
        subitem2 = Dataset()
        subitem2.ContourNumber = 2
        subitem2.ContourData = ['32', '64', '128', '196']

        sub_ds = Dataset()
        sub_ds.ContourSequence = Sequence((subitem1, subitem2))

        # Now the top-level sequence
        ds.ROIContourSequence = Sequence((sub_ds, ))  # Comma to make one-tuple

        # Store so each test can use it
        self.ds = ds

    def compare_write(self, hex_std, file_ds):
        """Write file and compare with expected byte string

        :arg hex_std: the bytes which should be written, as space separated hex
        :arg file_ds: a FileDataset instance containing the dataset to write
        """
        out_filename = "scratch.dcm"
        file_ds.save_as(out_filename, write_like_original=True)
        std = hex2bytes(hex_std)
        with open(out_filename, 'rb') as f:
            bytes_written = f.read()
        # print "std    :", bytes2hex(std)
        # print "written:", bytes2hex(bytes_written)
        same, pos = bytes_identical(std, bytes_written)
        self.assertTrue(same,
                        "Writing from scratch unexpected result "
                        "- 1st diff at 0x%x" % pos)

        if os.path.exists(out_filename):
            os.remove(out_filename)  # get rid of the file

    def testImpl_LE_deflen_write(self):
        """Scratch Write for implicit VR little endian, defined length SQs"""
        file_ds = FileDataset("test", self.ds)
        self.compare_write(impl_LE_deflen_std_hex, file_ds)


class TestWriteToStandard(object):
    """Unit tests for writing datasets to the DICOM standard"""
    def test_preamble_default(self):
        """Test that the default preamble is written correctly when present."""
        fp = DicomBytesIO()
        ds = dcmread(ct_name)
        ds.preamble = b'\x00' * 128
        ds.save_as(fp, write_like_original=False)
        fp.seek(0)
        assert fp.read(128) == b'\x00' * 128

    def test_preamble_custom(self):
        """Test that a custom preamble is written correctly when present."""
        fp = DicomBytesIO()
        ds = dcmread(ct_name)
        ds.preamble = b'\x01\x02\x03\x04' + b'\x00' * 124
        ds.save_as(fp, write_like_original=False)
        fp.seek(0)
        assert fp.read(128) == b'\x01\x02\x03\x04' + b'\x00' * 124

    def test_no_preamble(self):
        """Test that a default preamble is written when absent."""
        fp = DicomBytesIO()
        ds = dcmread(ct_name)
        del ds.preamble
        ds.save_as(fp, write_like_original=False)
        fp.seek(0)
        assert fp.read(128) == b'\x00' * 128

    def test_none_preamble(self):
        """Test that a default preamble is written when None."""
        fp = DicomBytesIO()
        ds = dcmread(ct_name)
        ds.preamble = None
        ds.save_as(fp, write_like_original=False)
        fp.seek(0)
        assert fp.read(128) == b'\x00' * 128

    def test_bad_preamble(self):
        """Test that ValueError is raised when preamble is bad."""
        ds = dcmread(ct_name)
        ds.preamble = b'\x00' * 127
        with pytest.raises(ValueError):
            ds.save_as(DicomBytesIO(), write_like_original=False)
        ds.preamble = b'\x00' * 129
        with pytest.raises(ValueError):
            ds.save_as(DicomBytesIO(), write_like_original=False)

    def test_prefix(self):
        """Test that the 'DICM' prefix
           is written with preamble."""
        # Has preamble
        fp = DicomBytesIO()
        ds = dcmread(ct_name)
        ds.preamble = b'\x00' * 128
        ds.save_as(fp, write_like_original=False)
        fp.seek(128)
        assert fp.read(4) == b'DICM'

    def test_prefix_none(self):
        """Test the 'DICM' prefix is written when preamble is None"""
        fp = DicomBytesIO()
        ds = dcmread(ct_name)
        ds.preamble = None
        ds.save_as(fp, write_like_original=False)
        fp.seek(128)
        assert fp.read(4) == b'DICM'

    def test_ds_changed(self):
        """Test writing the dataset changes its file_meta."""
        ds = dcmread(rtplan_name)
        ref_ds = dcmread(rtplan_name)
        for ref_elem, test_elem in zip(ref_ds.file_meta, ds.file_meta):
            assert ref_elem == test_elem

        ds.save_as(DicomBytesIO(), write_like_original=False)
        assert ref_ds.file_meta != ds.file_meta
        del ref_ds.file_meta
        del ds.file_meta

        # Ensure no RawDataElements in ref_ds and ds
        for _ in ref_ds:
            pass
        for _ in ds:
            pass
        assert ref_ds == ds

    def test_raw_elements_preserved_implicit_vr(self):
        """Test writing the dataset preserves raw elements."""
        ds = dcmread(rtplan_name)

        # raw data elements after reading
        assert ds.get_item(0x00080070).is_raw  # Manufacturer
        assert ds.get_item(0x00100020).is_raw  # Patient ID
        assert ds.get_item(0x300A0006).is_raw  # RT Plan Date
        assert ds.get_item(0x300A0010).is_raw  # Dose Reference Sequence

        ds.save_as(DicomBytesIO(), write_like_original=False)

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

        ds.save_as(DicomBytesIO(), write_like_original=False)

        # data set still contains raw data elements after writing
        assert ds.get_item(0x00080070).is_raw  # Manufacturer
        assert ds.get_item(0x00100010).is_raw  # Patient Name
        assert ds.get_item(0x00080030).is_raw  # Study Time
        assert ds.get_item(0x00089215).is_raw  # Derivation Code Sequence

    def test_convert_implicit_to_explicit_vr(self):
        # make sure conversion from implicit to explicit VR works
        # without private tags
        ds = dcmread(mr_implicit_name)
        ds.is_implicit_VR = False
        ds.file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.1'
        fp = DicomBytesIO()
        ds.save_as(fp, write_like_original=False)
        fp.seek(0)
        ds_out = dcmread(fp)
        ds_explicit = dcmread(mr_name)

        for elem_in, elem_out in zip(ds_explicit, ds_out):
            assert elem_in == elem_out

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

    def test_convert_implicit_to_explicit_vr_using_destination(self):
        # make sure conversion from implicit to explicit VR works
        # if setting the property in the destination
        ds = dcmread(mr_implicit_name)
        ds.is_implicit_VR = False
        ds.file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.1'
        fp = DicomBytesIO()
        fp.is_implicit_VR = False
        fp.is_little_endian = True
        ds.save_as(fp, write_like_original=False)
        fp.seek(0)
        ds_out = dcmread(fp)
        ds_explicit = dcmread(mr_name)

        for elem_in, elem_out in zip(ds_explicit, ds_out):
            assert elem_in == elem_out

    def test_convert_explicit_to_implicit_vr(self):
        # make sure conversion from explicit to implicit VR works
        # without private tags
        ds = dcmread(mr_name)
        ds.is_implicit_VR = True
        ds.file_meta.TransferSyntaxUID = uid.ImplicitVRLittleEndian
        fp = DicomBytesIO()
        ds.save_as(fp, write_like_original=False)
        fp.seek(0)
        ds_out = dcmread(fp)
        ds_implicit = dcmread(mr_implicit_name)

        for elem_in, elem_out in zip(ds_implicit, ds_out):
            assert elem_in == elem_out

    def test_convert_big_to_little_endian(self):
        # make sure conversion from big to little endian works
        # except for pixel data
        ds = dcmread(mr_bigendian_name)
        ds.is_little_endian = True
        ds.file_meta.TransferSyntaxUID = uid.ExplicitVRLittleEndian
        fp = DicomBytesIO()
        ds.save_as(fp, write_like_original=False)
        fp.seek(0)
        ds_out = dcmread(fp)
        ds_explicit = dcmread(mr_name)

        # pixel data is not converted automatically
        del ds_out.PixelData
        del ds_explicit.PixelData

        for elem_in, elem_out in zip(ds_explicit, ds_out):
            assert elem_in == elem_out

    def test_convert_little_to_big_endian(self):
        # make sure conversion from little to big endian works
        # except for pixel data
        ds = dcmread(mr_name)
        ds.is_little_endian = False
        ds.file_meta.TransferSyntaxUID = uid.ExplicitVRBigEndian
        fp = DicomBytesIO()
        ds.save_as(fp, write_like_original=False)
        fp.seek(0)
        ds_out = dcmread(fp)
        ds_explicit = dcmread(mr_bigendian_name)

        # pixel data is not converted automatically
        del ds_out.PixelData
        del ds_explicit.PixelData

        for elem_in, elem_out in zip(ds_explicit, ds_out):
            assert elem_in == elem_out

    @pytest.mark.skipif(sys.version_info[0] == 2,
                        reason='Saving with another encoding fails in Python2')
    def test_changed_character_set(self):
        """Make sure that a changed character set is reflected
        in the written data elements."""
        ds = dcmread(multiPN_name)
        # Latin 1 original encoding
        assert ds.get_item(0x00100010).value == b'Buc^J\xe9r\xf4me'

        # change encoding to UTF-8
        ds.SpecificCharacterSet = 'ISO_IR 192'
        fp = DicomBytesIO()
        ds.save_as(fp, write_like_original=False)
        fp.seek(0)
        ds_out = dcmread(fp)
        # patient name shall be UTF-8 encoded
        assert ds_out.get_item(0x00100010).value == b'Buc^J\xc3\xa9r\xc3\xb4me'
        # decoded values shall be the same as in original dataset
        for elem_in, elem_out in zip(ds, ds_out):
            assert elem_in == elem_out

    def test_transfer_syntax_added(self):
        """Test TransferSyntaxUID is added/updated if possible."""
        # Only done for ImplVR LE and ExplVR BE
        # Added
        ds = dcmread(rtplan_name)
        ds.is_implicit_VR = True
        ds.is_little_endian = True
        ds.save_as(DicomBytesIO(), write_like_original=False)
        assert ds.file_meta.TransferSyntaxUID == ImplicitVRLittleEndian

        # Updated
        ds.is_implicit_VR = False
        ds.is_little_endian = False
        ds.save_as(DicomBytesIO(), write_like_original=False)
        assert ds.file_meta.TransferSyntaxUID == ExplicitVRBigEndian

    def test_private_tag_vr_from_implicit_data(self):
        """Test that private tags have the correct VR if converting
        a dataset from implicit to explicit VR.
        """
        # convert a dataset with private tags to Implicit VR
        ds_orig = dcmread(ct_name)
        ds_orig.is_implicit_VR = True
        ds_orig.is_little_endian = True
        fp = DicomBytesIO()
        ds_orig.save_as(fp, write_like_original=False)
        fp.seek(0)
        ds_impl = dcmread(fp)

        # convert the dataset back to explicit VR - private tag VR now unknown
        ds_impl.is_implicit_VR = False
        ds_impl.is_little_endian = True
        ds_impl.file_meta.TransferSyntaxUID = uid.ExplicitVRLittleEndian
        fp = DicomBytesIO()
        ds_impl.save_as(fp, write_like_original=False)
        fp.seek(0)
        ds_expl = dcmread(fp)

        assert ds_expl[(0x0009, 0x0010)].VR == 'LO'  # private creator
        assert ds_expl[(0x0009, 0x1001)].VR == 'UN'  # originally LO
        assert ds_expl[(0x0009, 0x10e7)].VR == 'UN'  # originally UL
        assert ds_expl[(0x0043, 0x1010)].VR == 'UN'  # originally US

    def test_convert_rgb_from_implicit_to_explicit_vr(self):
        """Test converting an RGB dataset from implicit to explicit VR
        and vice verse."""
        ds_orig = dcmread(sc_rgb_name)
        ds_orig.is_implicit_VR = True
        ds_orig.is_little_endian = True
        fp = DicomBytesIO()
        ds_orig.save_as(fp, write_like_original=False)
        fp.seek(0)
        ds_impl = dcmread(fp)
        for elem_orig, elem_conv in zip(ds_orig, ds_impl):
            assert elem_orig == elem_conv

        ds_impl.is_implicit_VR = False
        ds_impl.is_little_endian = True
        ds_impl.file_meta.TransferSyntaxUID = uid.ExplicitVRLittleEndian
        fp = DicomBytesIO()
        ds_impl.save_as(fp, write_like_original=False)
        fp.seek(0)
        # used to raise, see #620
        ds_expl = dcmread(fp)
        for elem_orig, elem_conv in zip(ds_orig, ds_expl):
            assert elem_orig == elem_conv

    def test_transfer_syntax_not_added(self):
        """Test TransferSyntaxUID is not added if ExplVRLE."""
        ds = dcmread(rtplan_name)
        del ds.file_meta.TransferSyntaxUID
        ds.is_implicit_VR = False
        ds.is_little_endian = True
        with pytest.raises(ValueError):
            ds.save_as(DicomBytesIO(), write_like_original=False)
        assert 'TransferSyntaxUID' not in ds.file_meta

    def test_transfer_syntax_raises(self):
        """Test TransferSyntaxUID is raises
           NotImplementedError if ImplVRBE."""
        ds = dcmread(rtplan_name)
        ds.is_implicit_VR = True
        ds.is_little_endian = False
        with pytest.raises(NotImplementedError):
            ds.save_as(DicomBytesIO(), write_like_original=False)

    def test_media_storage_sop_class_uid_added(self):
        """Test MediaStorageSOPClassUID and InstanceUID are added."""
        fp = DicomBytesIO()
        ds = Dataset()
        ds.is_little_endian = True
        ds.is_implicit_VR = True
        ds.SOPClassUID = CTImageStorage
        ds.SOPInstanceUID = '1.2.3'
        ds.save_as(fp, write_like_original=False)
        assert ds.file_meta.MediaStorageSOPClassUID == CTImageStorage
        assert ds.file_meta.MediaStorageSOPInstanceUID == '1.2.3'

    def test_write_no_file_meta(self):
        """Test writing a dataset with no file_meta"""
        fp = DicomBytesIO()
        version = 'PYDICOM ' + base_version
        ds = dcmread(rtplan_name)
        transfer_syntax = ds.file_meta.TransferSyntaxUID
        ds.file_meta = Dataset()
        ds.save_as(fp, write_like_original=False)
        fp.seek(0)
        out = dcmread(fp)
        assert out.file_meta.MediaStorageSOPClassUID == ds.SOPClassUID
        assert out.file_meta.MediaStorageSOPInstanceUID == ds.SOPInstanceUID
        assert (
            out.file_meta.ImplementationClassUID == PYDICOM_IMPLEMENTATION_UID)
        assert (out.file_meta.ImplementationVersionName == version)
        assert out.file_meta.TransferSyntaxUID == transfer_syntax

        fp = DicomBytesIO()
        del ds.file_meta
        ds.save_as(fp, write_like_original=False)
        fp.seek(0)
        out = dcmread(fp)
        assert (out.file_meta.MediaStorageSOPClassUID == ds.SOPClassUID)
        assert (
            out.file_meta.MediaStorageSOPInstanceUID == ds.SOPInstanceUID)
        assert (
            out.file_meta.ImplementationClassUID == PYDICOM_IMPLEMENTATION_UID)
        assert (out.file_meta.ImplementationVersionName == version)
        assert out.file_meta.TransferSyntaxUID == transfer_syntax

    def test_raise_no_file_meta(self):
        """Test exception is raised if trying to write with no file_meta."""
        ds = dcmread(rtplan_name)
        del ds.SOPInstanceUID
        ds.file_meta = Dataset()
        with pytest.raises(ValueError):
            ds.save_as(DicomBytesIO(), write_like_original=False)
        del ds.file_meta
        with pytest.raises(ValueError):
            ds.save_as(DicomBytesIO(), write_like_original=False)

    def test_add_file_meta(self):
        """Test that file_meta is added if it doesn't exist"""
        fp = DicomBytesIO()
        ds = Dataset()
        ds.is_little_endian = True
        ds.is_implicit_VR = True
        ds.SOPClassUID = CTImageStorage
        ds.SOPInstanceUID = '1.2.3'
        ds.save_as(fp, write_like_original=False)
        assert isinstance(ds.file_meta, Dataset)

    def test_standard(self):
        """Test preamble + file_meta + dataset written OK."""
        fp = DicomBytesIO()
        ds = dcmread(ct_name)
        preamble = ds.preamble[:]
        ds.save_as(fp, write_like_original=False)
        fp.seek(0)
        assert fp.read(128) == preamble
        assert fp.read(4) == b'DICM'

        fp.seek(0)
        ds_out = dcmread(fp)
        assert ds_out.preamble == preamble
        assert 'PatientID' in ds_out
        assert 'TransferSyntaxUID' in ds_out.file_meta

    def test_commandset_no_written(self):
        """Test that Command Set elements aren't written."""
        fp = DicomBytesIO()
        ds = dcmread(ct_name)
        preamble = ds.preamble[:]
        ds.MessageID = 3
        ds.save_as(fp, write_like_original=False)
        fp.seek(0)
        assert fp.read(128) == preamble
        assert fp.read(4) == b'DICM'
        assert 'MessageID' in ds

        fp.seek(0)
        ds_out = dcmread(fp)
        assert ds_out.preamble == preamble
        assert 'PatientID' in ds_out
        assert 'TransferSyntaxUID' in ds_out.file_meta
        assert 'MessageID' not in ds_out


class TestWriteFileMetaInfoToStandard(object):
    """Unit tests for writing File Meta Info to the DICOM standard."""
    def test_bad_elements(self):
        """Test that non-group 2 elements aren't written to the file meta."""
        fp = DicomBytesIO()
        meta = Dataset()
        meta.PatientID = '12345678'
        meta.MediaStorageSOPClassUID = '1.1'
        meta.MediaStorageSOPInstanceUID = '1.2'
        meta.TransferSyntaxUID = '1.3'
        meta.ImplementationClassUID = '1.4'
        with pytest.raises(ValueError):
            write_file_meta_info(fp, meta, enforce_standard=True)

    def test_missing_elements(self):
        """Test that missing required elements raises ValueError."""
        fp = DicomBytesIO()
        meta = Dataset()
        with pytest.raises(ValueError):
            write_file_meta_info(fp, meta)
        meta.MediaStorageSOPClassUID = '1.1'
        with pytest.raises(ValueError):
            write_file_meta_info(fp, meta)
        meta.MediaStorageSOPInstanceUID = '1.2'
        with pytest.raises(ValueError):
            write_file_meta_info(fp, meta)
        meta.TransferSyntaxUID = '1.3'
        write_file_meta_info(fp, meta, enforce_standard=True)

    def test_group_length(self):
        """Test that the value for FileMetaInformationGroupLength is OK."""
        fp = DicomBytesIO()
        meta = Dataset()
        meta.MediaStorageSOPClassUID = '1.1'
        meta.MediaStorageSOPInstanceUID = '1.2'
        meta.TransferSyntaxUID = '1.3'
        write_file_meta_info(fp, meta, enforce_standard=True)

        class_length = len(PYDICOM_IMPLEMENTATION_UID)
        if class_length % 2:
            class_length += 1
        version_length = len(meta.ImplementationVersionName)
        # Padded to even length
        if version_length % 2:
            version_length += 1

        fp.seek(8)
        test_length = unpack('<I', fp.read(4))[0]
        assert test_length == 66 + class_length + version_length

    def test_group_length_updated(self):
        """Test that FileMetaInformationGroupLength gets updated if present."""
        fp = DicomBytesIO()
        meta = Dataset()
        meta.FileMetaInformationGroupLength = 100  # Not actual length
        meta.MediaStorageSOPClassUID = '1.1'
        meta.MediaStorageSOPInstanceUID = '1.2'
        meta.TransferSyntaxUID = '1.3'
        write_file_meta_info(fp, meta, enforce_standard=True)

        class_length = len(PYDICOM_IMPLEMENTATION_UID)
        if class_length % 2:
            class_length += 1
        version_length = len(meta.ImplementationVersionName)
        # Padded to even length
        if version_length % 2:
            version_length += 1

        fp.seek(8)
        test_length = unpack('<I', fp.read(4))[0]
        assert test_length == (61 + class_length
                               + version_length
                               + len(base_version))
        # Check original file meta is unchanged/updated
        assert meta.FileMetaInformationGroupLength == test_length
        assert meta.FileMetaInformationVersion == b'\x00\x01'
        assert meta.MediaStorageSOPClassUID == '1.1'
        assert meta.MediaStorageSOPInstanceUID == '1.2'
        assert meta.TransferSyntaxUID == '1.3'
        # Updated to meet standard
        assert meta.ImplementationClassUID == PYDICOM_IMPLEMENTATION_UID
        assert meta.ImplementationVersionName == 'PYDICOM ' + base_version

    def test_version(self):
        """Test that the value for FileMetaInformationVersion is OK."""
        fp = DicomBytesIO()
        meta = Dataset()
        meta.MediaStorageSOPClassUID = '1.1'
        meta.MediaStorageSOPInstanceUID = '1.2'
        meta.TransferSyntaxUID = '1.3'
        write_file_meta_info(fp, meta, enforce_standard=True)

        fp.seek(12 + 12)
        assert fp.read(2) == b'\x00\x01'

    def test_implementation_version_name_length(self):
        """Test that the written Implementation Version Name length is OK"""
        fp = DicomBytesIO()
        meta = Dataset()
        meta.MediaStorageSOPClassUID = '1.1'
        meta.MediaStorageSOPInstanceUID = '1.2'
        meta.TransferSyntaxUID = '1.3'
        write_file_meta_info(fp, meta, enforce_standard=True)
        version_length = len(meta.ImplementationVersionName)
        # VR of SH, 16 bytes max
        assert version_length <= 16

    def test_implementation_class_uid_length(self):
        """Test that the written Implementation Class UID length is OK"""
        fp = DicomBytesIO()
        meta = Dataset()
        meta.MediaStorageSOPClassUID = '1.1'
        meta.MediaStorageSOPInstanceUID = '1.2'
        meta.TransferSyntaxUID = '1.3'
        write_file_meta_info(fp, meta, enforce_standard=True)
        class_length = len(meta.ImplementationClassUID)
        # VR of UI, 64 bytes max
        assert class_length <= 64

    def test_filelike_position(self):
        """Test that the file-like's ending position is OK."""
        fp = DicomBytesIO()
        meta = Dataset()
        meta.MediaStorageSOPClassUID = '1.1'
        meta.MediaStorageSOPInstanceUID = '1.2'
        meta.TransferSyntaxUID = '1.3'
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
        meta.MediaStorageSOPInstanceUID = '1.4.1'
        write_file_meta_info(fp, meta, enforce_standard=True)
        # Check File Meta length
        assert fp.tell() == 80 + class_length + version_length

        # Check Group Length - 68 + XX + YY as bytes
        fp.seek(8)
        test_length = unpack('<I', fp.read(4))[0]
        assert test_length == 68 + class_length + version_length


class TestWriteNonStandard(unittest.TestCase):
    """Unit tests for writing datasets not to the DICOM standard."""

    def setUp(self):
        """Create an empty file-like for use in testing."""
        self.fp = DicomBytesIO()
        self.fp.is_little_endian = True
        self.fp.is_implicit_VR = True

    def compare_bytes(self, bytes_in, bytes_out):
        """Compare two bytestreams for equality"""
        same, pos = bytes_identical(bytes_in, bytes_out)
        self.assertTrue(same, "Bytestreams are not identical - first "
                        "difference at 0x%x" % pos)

    def ensure_no_raw_data_elements(self, ds):
        for _ in ds.file_meta:
            pass
        for _ in ds:
            pass

    def test_preamble_default(self):
        """Test that the default preamble is written correctly when present."""
        ds = dcmread(ct_name)
        ds.preamble = b'\x00' * 128
        ds.save_as(self.fp, write_like_original=True)
        self.fp.seek(0)
        self.assertEqual(self.fp.read(128), b'\x00' * 128)

    def test_preamble_custom(self):
        """Test that a custom preamble is written correctly when present."""
        ds = dcmread(ct_name)
        ds.preamble = b'\x01\x02\x03\x04' + b'\x00' * 124
        self.fp.seek(0)
        ds.save_as(self.fp, write_like_original=True)
        self.fp.seek(0)
        self.assertEqual(self.fp.read(128),
                         b'\x01\x02\x03\x04' + b'\x00' * 124)

    def test_no_preamble(self):
        """Test no preamble or prefix is written if preamble absent."""
        ds = dcmread(ct_name)
        preamble = ds.preamble[:]
        del ds.preamble
        ds.save_as(self.fp, write_like_original=True)
        self.fp.seek(0)
        self.assertNotEqual(self.fp.read(128), b'\x00' * 128)
        self.fp.seek(0)
        self.assertNotEqual(self.fp.read(128), preamble)
        self.fp.seek(0)
        self.assertNotEqual(self.fp.read(4), b'DICM')

    def test_ds_unchanged(self):
        """Test writing the dataset doesn't change it."""
        ds = dcmread(rtplan_name)
        ref_ds = dcmread(rtplan_name)
        ds.save_as(self.fp, write_like_original=True)

        self.ensure_no_raw_data_elements(ds)
        self.ensure_no_raw_data_elements(ref_ds)
        self.assertTrue(ref_ds == ds)

    def test_file_meta_unchanged(self):
        """Test no file_meta elements are added if missing."""
        ds = dcmread(rtplan_name)
        ds.file_meta = Dataset()
        ds.save_as(self.fp, write_like_original=True)
        self.assertEqual(ds.file_meta, Dataset())

    def test_dataset(self):
        """Test dataset written OK with no preamble or file meta"""
        ds = dcmread(ct_name)
        del ds.preamble
        del ds.file_meta
        ds.save_as(self.fp, write_like_original=True)
        self.fp.seek(0)
        self.assertNotEqual(self.fp.read(128), b'\x00' * 128)
        self.fp.seek(0)
        self.assertNotEqual(self.fp.read(4), b'DICM')

        self.fp.seek(0)
        ds_out = dcmread(self.fp, force=True)
        self.assertEqual(ds_out.preamble, None)
        self.assertEqual(ds_out.file_meta, Dataset())
        self.assertTrue('PatientID' in ds_out)

    def test_preamble_dataset(self):
        """Test dataset written OK with no file meta"""
        ds = dcmread(ct_name)
        del ds.file_meta
        preamble = ds.preamble[:]
        ds.save_as(self.fp, write_like_original=True)
        self.fp.seek(0)
        self.assertEqual(self.fp.read(128), preamble)
        self.assertEqual(self.fp.read(4), b'DICM')

        self.fp.seek(0)
        ds_out = dcmread(self.fp, force=True)
        self.assertEqual(ds_out.file_meta, Dataset())
        self.assertTrue('PatientID' in ds_out)

    def test_filemeta_dataset(self):
        """Test file meta written OK if preamble absent."""
        ds = dcmread(ct_name)
        preamble = ds.preamble[:]
        del ds.preamble
        ds.save_as(self.fp, write_like_original=True)
        self.fp.seek(0)
        self.assertNotEqual(self.fp.read(128), b'\x00' * 128)
        self.fp.seek(0)
        self.assertNotEqual(self.fp.read(128), preamble)
        self.fp.seek(0)
        self.assertNotEqual(self.fp.read(4), b'DICM')

        self.fp.seek(0)
        ds_out = dcmread(self.fp, force=True)
        self.assertTrue('ImplementationClassUID' in ds_out.file_meta)
        self.assertEqual(ds_out.preamble, None)
        self.assertTrue('PatientID' in ds_out)

    def test_preamble_filemeta_dataset(self):
        """Test non-standard file meta written with preamble OK"""
        ds = dcmread(ct_name)
        preamble = ds.preamble[:]
        ds.save_as(self.fp, write_like_original=True)
        self.fp.seek(0)
        self.assertEqual(self.fp.read(128), preamble)
        self.assertEqual(self.fp.read(4), b'DICM')

        self.fp.seek(0)
        ds_out = dcmread(self.fp, force=True)
        self.ensure_no_raw_data_elements(ds)
        self.ensure_no_raw_data_elements(ds_out)

        self.assertEqual(ds.file_meta[:], ds_out.file_meta[:])
        self.assertTrue('TransferSyntaxUID' in ds_out.file_meta[:])
        self.assertEqual(ds_out.preamble, preamble)
        self.assertTrue('PatientID' in ds_out)

    def test_commandset_dataset(self):
        """Test written OK with command set/dataset"""
        ds = dcmread(ct_name)
        preamble = ds.preamble[:]
        del ds.preamble
        del ds.file_meta
        ds.is_little_endian = True
        ds.is_implicit_VR = True
        ds.CommandGroupLength = 8
        ds.MessageID = 1
        ds.MoveDestination = 'SOME_SCP'
        ds.Status = 0x0000
        ds.save_as(self.fp, write_like_original=True)
        self.fp.seek(0)
        self.assertNotEqual(self.fp.read(128), preamble)
        self.fp.seek(0)
        self.assertNotEqual(self.fp.read(128), b'\x00' * 128)
        self.fp.seek(0)
        self.assertNotEqual(self.fp.read(4), b'DICM')
        # Ensure Command Set Elements written as little endian implicit VRe
        self.fp.seek(0)
        self.assertEqual(self.fp.read(12),
                         b'\x00\x00\x00\x00\x04\x00\x00\x00\x08\x00\x00\x00')

        self.fp.seek(0)
        ds_out = dcmread(self.fp, force=True)
        self.assertEqual(ds_out.file_meta, Dataset())
        self.assertTrue('Status' in ds_out)
        self.assertTrue('PatientID' in ds_out)

    def test_preamble_commandset_dataset(self):
        """Test written OK with preamble/command set/dataset"""
        ds = dcmread(ct_name)
        preamble = ds.preamble[:]
        del ds.file_meta
        ds.CommandGroupLength = 8
        ds.MessageID = 1
        ds.MoveDestination = 'SOME_SCP'
        ds.Status = 0x0000
        ds.save_as(self.fp, write_like_original=True)
        self.fp.seek(0)
        self.assertEqual(self.fp.read(128), preamble)
        self.assertEqual(self.fp.read(4), b'DICM')
        # Ensure Command Set Elements written as little endian implicit VR
        self.assertEqual(self.fp.read(12),
                         b'\x00\x00\x00\x00\x04\x00\x00\x00\x08\x00\x00\x00')

        self.fp.seek(0)
        ds_out = dcmread(self.fp, force=True)
        self.assertEqual(ds_out.file_meta, Dataset())
        self.assertTrue('Status' in ds_out)
        self.assertTrue('PatientID' in ds_out)

    def test_preamble_commandset_filemeta_dataset(self):
        """Test written OK with preamble/command set/file meta/dataset"""
        ds = dcmread(ct_name)
        preamble = ds.preamble[:]
        ds.CommandGroupLength = 8
        ds.MessageID = 1
        ds.MoveDestination = 'SOME_SCP'
        ds.Status = 0x0000
        ds.save_as(self.fp, write_like_original=True)
        self.fp.seek(0)
        self.assertEqual(self.fp.read(128), preamble)
        self.assertEqual(self.fp.read(4), b'DICM')

        self.fp.seek(0)
        ds_out = dcmread(self.fp, force=True)
        self.assertTrue('TransferSyntaxUID' in ds_out.file_meta)
        self.assertTrue('Status' in ds_out)
        self.assertTrue('PatientID' in ds_out)

    def test_commandset_filemeta_dataset(self):
        """Test written OK with command set/file meta/dataset"""
        ds = dcmread(ct_name)
        preamble = ds.preamble[:]
        del ds.preamble
        ds.CommandGroupLength = 8
        ds.MessageID = 1
        ds.MoveDestination = 'SOME_SCP'
        ds.Status = 0x0000
        ds.save_as(self.fp, write_like_original=True)
        self.fp.seek(0)
        self.assertNotEqual(self.fp.read(128),
                            preamble)
        self.fp.seek(0)
        self.assertNotEqual(self.fp.read(128),
                            b'\x00' * 128)
        self.fp.seek(0)
        self.assertNotEqual(self.fp.read(4), b'DICM')
        # Ensure Command Set Elements written as little endian implicit VR
        self.fp.seek(0)

        ds_out = dcmread(self.fp, force=True)
        self.assertTrue('TransferSyntaxUID' in ds_out.file_meta)
        self.assertTrue('Status' in ds_out)
        self.assertTrue('PatientID' in ds_out)

    def test_commandset(self):
        """Test written OK with command set"""
        ds = dcmread(ct_name)
        del ds[:]
        del ds.preamble
        del ds.file_meta
        ds.CommandGroupLength = 8
        ds.MessageID = 1
        ds.MoveDestination = 'SOME_SCP'
        ds.Status = 0x0000
        ds.save_as(self.fp, write_like_original=True)
        self.fp.seek(0)
        self.assertRaises(EOFError, self.fp.read, 128, need_exact_length=True)
        self.fp.seek(0)
        self.assertNotEqual(self.fp.read(4), b'DICM')
        # Ensure Command Set Elements written as little endian implicit VR
        self.fp.seek(0)

        fp = BytesIO(self.fp.getvalue())  # Workaround to avoid #358
        ds_out = dcmread(fp, force=True)
        self.assertEqual(ds_out.file_meta, Dataset())
        self.assertTrue('Status' in ds_out)
        self.assertFalse('PatientID' in ds_out)
        self.assertEqual(ds_out[0x00010000:], Dataset())

    def test_commandset_filemeta(self):
        """Test dataset written OK with command set/file meta"""
        ds = dcmread(ct_name)
        preamble = ds.preamble[:]
        del ds[:]
        del ds.preamble
        ds.CommandGroupLength = 8
        ds.MessageID = 1
        ds.MoveDestination = 'SOME_SCP'
        ds.Status = 0x0000
        ds.save_as(self.fp, write_like_original=True)
        self.fp.seek(0)
        self.assertNotEqual(self.fp.read(128), preamble)
        self.fp.seek(0)
        self.assertNotEqual(self.fp.read(4), b'DICM')
        # Ensure Command Set Elements written as little endian implicit VR
        self.fp.seek(0)

        fp = BytesIO(self.fp.getvalue())  # Workaround to avoid #358
        ds_out = dcmread(fp, force=True)
        self.assertTrue('TransferSyntaxUID' in ds_out.file_meta)
        self.assertTrue('Status' in ds_out)
        self.assertFalse('PatientID' in ds_out)
        self.assertEqual(ds_out[0x00010000:], Dataset())

    def test_preamble_commandset(self):
        """Test written OK with preamble/command set"""
        ds = dcmread(ct_name)
        del ds[:]
        del ds.file_meta
        ds.CommandGroupLength = 8
        ds.MessageID = 1
        ds.MoveDestination = 'SOME_SCP'
        ds.Status = 0x0000
        ds.save_as(self.fp, write_like_original=True)
        self.fp.seek(0)
        self.assertEqual(self.fp.read(128), ds.preamble)
        self.assertEqual(self.fp.read(4), b'DICM')
        # Ensure Command Set Elements written as little endian implicit VR
        self.assertEqual(self.fp.read(12),
                         b'\x00\x00\x00\x00\x04\x00\x00\x00\x08\x00\x00\x00')

        fp = BytesIO(self.fp.getvalue())  # Workaround to avoid #358
        ds_out = dcmread(fp, force=True)
        self.assertEqual(ds_out.file_meta, Dataset())
        self.assertTrue('Status' in ds_out)
        self.assertFalse('PatientID' in ds_out)
        self.assertEqual(ds_out[0x00010000:], Dataset())

    def test_preamble_commandset_filemeta(self):
        """Test written OK with preamble/command set/file meta"""
        ds = dcmread(ct_name)
        del ds[:]
        ds.CommandGroupLength = 8
        ds.MessageID = 1
        ds.MoveDestination = 'SOME_SCP'
        ds.Status = 0x0000
        ds.save_as(self.fp, write_like_original=True)
        self.fp.seek(0)
        self.assertEqual(self.fp.read(128), ds.preamble)
        self.assertEqual(self.fp.read(4), b'DICM')

        self.fp.seek(0)
        ds_out = dcmread(self.fp, force=True)
        self.assertTrue('Status' in ds_out)
        self.assertTrue('TransferSyntaxUID' in ds_out.file_meta)
        self.assertFalse('PatientID' in ds_out)
        self.assertEqual(ds_out[0x00010000:], Dataset())

    def test_read_write_identical(self):
        """Test the written bytes matches the read bytes."""
        for dcm_in in [rtplan_name, rtdose_name, ct_name, mr_name, jpeg_name,
                       no_ts, unicode_name, multiPN_name]:
            with open(dcm_in, 'rb') as f:
                bytes_in = BytesIO(f.read())
                ds_in = dcmread(bytes_in)
                bytes_out = BytesIO()
                ds_in.save_as(bytes_out, write_like_original=True)
                self.compare_bytes(bytes_in.getvalue(), bytes_out.getvalue())


class TestWriteFileMetaInfoNonStandard(unittest.TestCase):
    """Unit tests for writing File Meta Info not to the DICOM standard."""

    def setUp(self):
        """Create an empty file-like for use in testing."""
        self.fp = DicomBytesIO()

    def test_transfer_syntax_not_added(self):
        """Test that the TransferSyntaxUID isn't added if missing"""
        ds = dcmread(no_ts)
        write_file_meta_info(self.fp, ds.file_meta, enforce_standard=False)
        self.assertFalse('TransferSyntaxUID' in ds.file_meta)
        self.assertTrue('ImplementationClassUID' in ds.file_meta)

        # Check written meta dataset doesn't contain TransferSyntaxUID
        written_ds = dcmread(self.fp, force=True)
        self.assertTrue('ImplementationClassUID' in written_ds.file_meta)
        self.assertFalse('TransferSyntaxUID' in written_ds.file_meta)

    def test_bad_elements(self):
        """Test that non-group 2 elements aren't written to the file meta."""
        meta = Dataset()
        meta.PatientID = '12345678'
        meta.MediaStorageSOPClassUID = '1.1'
        meta.MediaStorageSOPInstanceUID = '1.2'
        meta.TransferSyntaxUID = '1.3'
        meta.ImplementationClassUID = '1.4'
        self.assertRaises(
            ValueError,
            write_file_meta_info,
            self.fp,
            meta,
            enforce_standard=False)

    def test_missing_elements(self):
        """Test that missing required elements doesn't raise ValueError."""
        meta = Dataset()
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        meta.MediaStorageSOPClassUID = '1.1'
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        meta.MediaStorageSOPInstanceUID = '1.2'
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        meta.TransferSyntaxUID = '1.3'
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        meta.ImplementationClassUID = '1.4'
        write_file_meta_info(self.fp, meta, enforce_standard=False)

    def test_group_length_updated(self):
        """Test that FileMetaInformationGroupLength gets updated if present."""
        meta = Dataset()
        meta.FileMetaInformationGroupLength = 100
        meta.MediaStorageSOPClassUID = '1.1'
        meta.MediaStorageSOPInstanceUID = '1.2'
        meta.TransferSyntaxUID = '1.3'
        meta.ImplementationClassUID = '1.4'
        write_file_meta_info(self.fp, meta, enforce_standard=False)

        # 8 + 4 bytes FileMetaInformationGroupLength
        # 8 + 4 bytes MediaStorageSOPClassUID
        # 8 + 4 bytes MediaStorageSOPInstanceUID
        # 8 + 4 bytes TransferSyntaxUID
        # 8 + 4 bytes ImplementationClassUID
        # 60 bytes total, - 12 for group length = 48
        self.fp.seek(8)
        self.assertEqual(self.fp.read(4), b'\x30\x00\x00\x00')
        # Check original file meta is unchanged/updated
        self.assertEqual(meta.FileMetaInformationGroupLength, 48)
        self.assertFalse('FileMetaInformationVersion' in meta)
        self.assertEqual(meta.MediaStorageSOPClassUID, '1.1')
        self.assertEqual(meta.MediaStorageSOPInstanceUID, '1.2')
        self.assertEqual(meta.TransferSyntaxUID, '1.3')
        self.assertEqual(meta.ImplementationClassUID, '1.4')

    def test_filelike_position(self):
        """Test that the file-like's ending position is OK."""
        # 8 + 4 bytes MediaStorageSOPClassUID
        # 8 + 4 bytes MediaStorageSOPInstanceUID
        # 8 + 4 bytes TransferSyntaxUID
        # 8 + 4 bytes ImplementationClassUID
        # 48 bytes total
        meta = Dataset()
        meta.MediaStorageSOPClassUID = '1.1'
        meta.MediaStorageSOPInstanceUID = '1.2'
        meta.TransferSyntaxUID = '1.3'
        meta.ImplementationClassUID = '1.4'
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        self.assertEqual(self.fp.tell(), 48)

        # 8 + 6 bytes ImplementationClassUID
        # 50 bytes total
        self.fp.seek(0)
        meta.ImplementationClassUID = '1.4.1'
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        # Check File Meta length
        self.assertEqual(self.fp.tell(), 50)

    def test_meta_unchanged(self):
        """Test that the meta dataset doesn't change when writing it"""
        # Empty
        meta = Dataset()
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        self.assertEqual(meta, Dataset())

        # Incomplete
        meta = Dataset()
        meta.MediaStorageSOPClassUID = '1.1'
        meta.MediaStorageSOPInstanceUID = '1.2'
        meta.TransferSyntaxUID = '1.3'
        meta.ImplementationClassUID = '1.4'
        ref_meta = deepcopy(meta)
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        self.assertEqual(meta, ref_meta)

        # Conformant
        meta = Dataset()
        meta.FileMetaInformationGroupLength = 62  # Correct length
        meta.FileMetaInformationVersion = b'\x00\x01'
        meta.MediaStorageSOPClassUID = '1.1'
        meta.MediaStorageSOPInstanceUID = '1.2'
        meta.TransferSyntaxUID = '1.3'
        meta.ImplementationClassUID = '1.4'
        ref_meta = deepcopy(meta)
        write_file_meta_info(self.fp, meta, enforce_standard=False)
        self.assertEqual(meta, ref_meta)


class TestWriteNumbers(object):
    """Test filewriter.write_numbers"""
    def test_write_empty_value(self):
        """Test writing an empty value does nothing"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x00100010, 'US', '')
        fmt = 'H'
        write_numbers(fp, elem, fmt)
        assert fp.getvalue() == b''

    def test_write_list(self):
        """Test writing an element value with VM > 1"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x00100010, 'US', [1, 2, 3, 4])
        fmt = 'H'
        write_numbers(fp, elem, fmt)
        assert fp.getvalue() == b'\x01\x00\x02\x00\x03\x00\x04\x00'

    def test_write_singleton(self):
        """Test writing an element value with VM = 1"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x00100010, 'US', 1)
        fmt = 'H'
        write_numbers(fp, elem, fmt)
        assert fp.getvalue() == b'\x01\x00'

    def test_exception(self):
        """Test exceptions raise IOError"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x00100010, 'US', b'\x00')
        fmt = 'H'
        with pytest.raises(IOError,
                           match="for data_element:\n\(0010, 0010\)"):
            write_numbers(fp, elem, fmt)

    def test_write_big_endian(self):
        """Test writing big endian"""
        fp = DicomBytesIO()
        fp.is_little_endian = False
        elem = DataElement(0x00100010, 'US', 1)
        fmt = 'H'
        write_numbers(fp, elem, fmt)
        assert fp.getvalue() == b'\x00\x01'


class TestWritePN(object):
    """Test filewriter.write_PN"""
    def test_no_encoding_unicode(self):
        """If PN element has no encoding info, default is used"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x00100010, 'PN', u'\u03b8')
        write_PN(fp, elem)

    def test_no_encoding(self):
        """If PN element has no encoding info, default is used"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x00100010, 'PN', 'Test')
        write_PN(fp, elem)
        assert fp.getvalue() == b'Test'


class TestWriteDT(object):
    """Test filewriter.write_DT"""
    def test_format_dt(self):
        """Test _format_DT"""
        elem = DataElement(0x00181078, 'DT', DT('20010203123456.123456'))
        assert hasattr(elem.value, 'original_string')
        assert _format_DT(elem.value) == '20010203123456.123456'
        del elem.value.original_string
        assert not hasattr(elem.value, 'original_string')
        assert elem.value.microsecond > 0
        assert _format_DT(elem.value) == '20010203123456.123456'

        elem = DataElement(0x00181078, 'DT', DT('20010203123456'))
        del elem.value.original_string
        assert _format_DT(elem.value) == '20010203123456'


class TestWriteUndefinedLengthPixelData(unittest.TestCase):
    """Test write_data_element() for pixel data with undefined length."""

    def setUp(self):
        self.fp = DicomBytesIO()

    def test_little_endian_correct_data(self):
        """Pixel data starting with an item tag is written."""
        self.fp.is_little_endian = True
        self.fp.is_implicit_VR = False
        pixel_data = DataElement(0x7fe00010, 'OB',
                                 b'\xfe\xff\x00\xe0'
                                 b'\x00\x01\x02\x03',
                                 is_undefined_length=True)
        write_data_element(self.fp, pixel_data)

        expected = (b'\xe0\x7f\x10\x00'  # tag
                    b'OB\x00\x00'  # VR
                    b'\xff\xff\xff\xff'  # length
                    b'\xfe\xff\x00\xe0\x00\x01\x02\x03'  # contents
                    b'\xfe\xff\xdd\xe0\x00\x00\x00\x00')  # SQ delimiter
        self.fp.seek(0)
        assert self.fp.read() == expected

    def test_big_endian_correct_data(self):
        """Pixel data starting with an item tag is written."""
        self.fp.is_little_endian = False
        self.fp.is_implicit_VR = False
        pixel_data = DataElement(0x7fe00010, 'OB',
                                 b'\xff\xfe\xe0\x00'
                                 b'\x00\x01\x02\x03',
                                 is_undefined_length=True)
        write_data_element(self.fp, pixel_data)
        expected = (b'\x7f\xe0\x00\x10'  # tag
                    b'OB\x00\x00'  # VR
                    b'\xff\xff\xff\xff'  # length
                    b'\xff\xfe\xe0\x00\x00\x01\x02\x03'  # contents
                    b'\xff\xfe\xe0\xdd\x00\x00\x00\x00')  # SQ delimiter
        self.fp.seek(0)
        assert self.fp.read() == expected

    def test_little_endian_incorrect_data(self):
        """Writing pixel data not starting with an item tag raises."""
        self.fp.is_little_endian = True
        self.fp.is_implicit_VR = False
        pixel_data = DataElement(0x7fe00010, 'OB',
                                 b'\xff\xff\x00\xe0'
                                 b'\x00\x01\x02\x03'
                                 b'\xfe\xff\xdd\xe0',
                                 is_undefined_length=True)
        with pytest.raises(ValueError, match='Pixel Data .* must '
                                             'start with an item tag'):
            write_data_element(self.fp, pixel_data)

    def test_big_endian_incorrect_data(self):
        """Writing pixel data not starting with an item tag raises."""
        self.fp.is_little_endian = False
        self.fp.is_implicit_VR = False
        pixel_data = DataElement(0x7fe00010, 'OB',
                                 b'\x00\x00\x00\x00'
                                 b'\x00\x01\x02\x03'
                                 b'\xff\xfe\xe0\xdd',
                                 is_undefined_length=True)
        with pytest.raises(ValueError, match='Pixel Data .+ must '
                                             'start with an item tag'):
            write_data_element(self.fp, pixel_data)


class TestWriteNumbers(object):
    """Test filewriter.write_numbers"""
    def test_write_empty_value(self):
        """Test writing an empty value does nothing"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x00100010, 'US', '')
        fmt = 'H'
        write_numbers(fp, elem, fmt)
        assert fp.getvalue() == b''

    def test_write_list(self):
        """Test writing an element value with VM > 1"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x00100010, 'US', [1, 2, 3, 4])
        fmt = 'H'
        write_numbers(fp, elem, fmt)
        assert fp.getvalue() == b'\x01\x00\x02\x00\x03\x00\x04\x00'

    def test_write_singleton(self):
        """Test writing an element value with VM = 1"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x00100010, 'US', 1)
        fmt = 'H'
        write_numbers(fp, elem, fmt)
        assert fp.getvalue() == b'\x01\x00'

    def test_exception(self):
        """Test exceptions raise IOError"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x00100010, 'US', b'\x00')
        fmt = 'H'
        with pytest.raises(IOError,
                           match="for data_element:\n\(0010, 0010\)"):
            write_numbers(fp, elem, fmt)

    def test_write_big_endian(self):
        """Test writing big endian"""
        fp = DicomBytesIO()
        fp.is_little_endian = False
        elem = DataElement(0x00100010, 'US', 1)
        fmt = 'H'
        write_numbers(fp, elem, fmt)
        assert fp.getvalue() == b'\x00\x01'


class TestWritePN(object):
    """Test filewriter.write_PN"""
    def test_no_encoding_unicode(self):
        """If PN element as no encoding info, default is used"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x00100010, 'PN', u'\u00e8')
        write_PN(fp, elem)

    def test_no_encoding(self):
        """If PN element as no encoding info, default is used"""
        fp = DicomBytesIO()
        fp.is_little_endian = True
        elem = DataElement(0x00100010, 'PN', 'Test')
        write_PN(fp, elem)
        assert fp.getvalue() == b'Test'


class TestWriteDT(object):
    """Test filewriter.write_DT"""
    def test_format_dt(self):
        """Test _format_DT"""
        elem = DataElement(0x00181078, 'DT', DT('20010203123456.123456'))
        assert hasattr(elem.value, 'original_string')
        assert _format_DT(elem.value) == '20010203123456.123456'
        del elem.value.original_string
        assert not hasattr(elem.value, 'original_string')
        assert elem.value.microsecond > 0
        assert _format_DT(elem.value) == '20010203123456.123456'

        elem = DataElement(0x00181078, 'DT', DT('20010203123456'))
        del elem.value.original_string
        assert _format_DT(elem.value) == '20010203123456'


if __name__ == "__main__":
    # This is called if run alone, but not if loaded through run_tests.py
    # If not run from the directory where the sample images are,
    #    then need to switch there
    unittest.main()
