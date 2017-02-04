# test_filewriter.py
"""unittest cases for pydicom.filewriter module"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

from copy import deepcopy
from datetime import date, datetime, time
from io import BytesIO
import os
import os.path
import sys

have_dateutil = True
try:
    from dateutil.tz import tzoffset
except ImportError:
    have_dateutil = False
import unittest
try:
    unittest.TestCase.assertSequenceEqual
except AttributeError:
    try:
        import unittest2 as unittest
    except ImportError:
        print("unittest2 is required for testing in python2.6")

from pydicom import config
from pydicom.dataset import Dataset, FileDataset
from pydicom.dataelem import DataElement
from pydicom.filebase import DicomBytesIO
from pydicom.filereader import read_file, read_dataset
from pydicom.filewriter import write_data_element, write_dataset, \
                               correct_ambiguous_vr
from pydicom.multival import MultiValue
from pydicom.sequence import Sequence
from pydicom.util.hexutil import hex2bytes, bytes2hex
from pydicom.valuerep import DA, DT, TM

test_dir = os.path.dirname(__file__)
test_files = os.path.join(test_dir, 'test_files')
testcharset_dir = os.path.join(test_dir, 'charset_files')

rtplan_name = os.path.join(test_files, "rtplan.dcm")
rtdose_name = os.path.join(test_files, "rtdose.dcm")
ct_name = os.path.join(test_files, "CT_small.dcm")
mr_name = os.path.join(test_files, "MR_small.dcm")
jpeg_name = os.path.join(test_files, "JPEG2000.dcm")
datetime_name = mr_name

unicode_name = os.path.join(testcharset_dir, "chrH31.dcm")
multiPN_name = os.path.join(testcharset_dir, "chrFrenMulti.dcm")

# Set up rtplan_out, rtdose_out etc. Filenames as above, with '2' appended
rtplan_out = rtplan_name + '2'
rtdose_out = rtdose_name + '2'
ct_out = ct_name + '2'
mr_out = mr_name + '2'
jpeg_out = jpeg_name + '2'
datetime_out = datetime_name + '2'

unicode_out = unicode_name + '2'
multiPN_out = multiPN_name + '2'


def files_identical(a, b):
    """Return a tuple (file a == file b, index of first difference)"""
    with open(a, "rb") as A:
        with open(b, "rb") as B:
            a_bytes = A.read()
            b_bytes = B.read()

    return bytes_identical(a_bytes, b_bytes)

def bytes_identical(a_bytes, b_bytes):
    """Return a tuple (bytes a == bytes b, index of first difference)"""
    if a_bytes == b_bytes:
        return True, 0     # True, dummy argument
    else:
        pos = 0
        while a_bytes[pos] == b_bytes[pos]:
            pos += 1
        return False, pos   # False if not identical, position of 1st diff


class WriteFileTests(unittest.TestCase):
    def compare(self, in_filename, out_filename, decode=False):
        """Read file1, write file2, then compare.
        Return value as for files_identical.
        """
        dataset = read_file(in_filename)
        if decode:
            dataset.decode()

        dataset.save_as(out_filename)
        same, pos = files_identical(in_filename, out_filename)
        self.assertTrue(same,
                        "Files are not identical - first difference at 0x%x" % pos)
        if os.path.exists(out_filename):
            os.remove(out_filename)  # get rid of the file

    def testRTPlan(self):
        """Input file, write back and verify them identical (RT Plan file)"""
        self.compare(rtplan_name, rtplan_out)

    def testRTDose(self):
        """Input file, write back and verify them identical (RT Dose file)"""
        self.compare(rtdose_name, rtdose_out)

    def testCT(self):
        """Input file, write back and verify them identical (CT file)....."""
        self.compare(ct_name, ct_out)

    def testMR(self):
        """Input file, write back and verify them identical (MR file)....."""
        self.compare(mr_name, mr_out)

    def testUnicode(self):
        """Ensure decoded string DataElements are written to file properly"""
        self.compare(unicode_name, unicode_out, decode=True)

    def testMultiPN(self):
        """Ensure multiple Person Names are written to the file correctly."""
        self.compare(multiPN_name, multiPN_out, decode=True)

    def testJPEG2000(self):
        """Input file, write back and verify them identical (JPEG2K file)."""
        self.compare(jpeg_name, jpeg_out)

    def testListItemWriteBack(self):
        """Change item in a list and confirm it is written to file      .."""
        DS_expected = 0
        CS_expected = "new"
        SS_expected = 999
        ds = read_file(ct_name)
        ds.ImagePositionPatient[2] = DS_expected
        ds.ImageType[1] = CS_expected
        ds[(0x0043, 0x1012)].value[0] = SS_expected
        ds.save_as(ct_out)
        # Now read it back in and check that the values were changed
        ds = read_file(ct_out)
        self.assertTrue(ds.ImageType[1] == CS_expected,
                        "Item in a list not written correctly to file (VR=CS)")
        self.assertTrue(ds[0x00431012].value[0] == SS_expected,
                        "Item in a list not written correctly to file (VR=SS)")
        self.assertTrue(ds.ImagePositionPatient[2] == DS_expected,
                        "Item in a list not written correctly to file (VR=DS)")
        if os.path.exists(ct_out):
            os.remove(ct_out)

    def testwrite_short_uid(self):
        ds = read_file(rtplan_name)
        ds.SOPInstanceUID = "1.2"
        ds.save_as(rtplan_out)
        ds = read_file(rtplan_out)
        ds.save_as(rtplan_out)
        self.assertEqual(ds.SOPInstanceUID, "1.2")
        if os.path.exists(rtplan_out):
            os.remove(rtplan_out)  # get rid of the file


@unittest.skipIf(not have_dateutil, "Need python-dateutil installed for these tests")
class ScratchWriteDateTimeTests(WriteFileTests):
    """Write and reread simple or multi-value DA/DT/TM data elements"""
    def setUp(self):
        config.datetime_conversion = True

    def tearDown(self):
        config.datetime_conversion = False

    def test_multivalue_DA(self):
        """Write DA/DT/TM data elements.........."""
        multi_DA_expected = (date(1961, 8, 4), date(1963, 11, 22))
        DA_expected = date(1961, 8, 4)
        tzinfo = tzoffset('-0600', -21600)
        multi_DT_expected = (datetime(1961, 8, 4),
                             datetime(1963, 11, 22, 12, 30, 0, 0,
                                      tzoffset('-0600', -21600)))
        multi_TM_expected = (time(1, 23, 45), time(11, 11, 11))
        TM_expected = time(11, 11, 11, 1)
        ds = read_file(datetime_name)
        # Add date/time data elements
        ds.CalibrationDate = MultiValue(DA, multi_DA_expected)
        ds.DateOfLastCalibration = DA(DA_expected)
        ds.ReferencedDateTime = MultiValue(DT, multi_DT_expected)
        ds.CalibrationTime = MultiValue(TM, multi_TM_expected)
        ds.TimeOfLastCalibration = TM(TM_expected)
        ds.save_as(datetime_out)
        # Now read it back in and check the values are as expected
        ds = read_file(datetime_out)
        self.assertSequenceEqual(multi_DA_expected, ds.CalibrationDate, "Multiple dates not written correctly (VR=DA)")
        self.assertEqual(DA_expected, ds.DateOfLastCalibration, "Date not written correctly (VR=DA)")
        self.assertSequenceEqual(multi_DT_expected, ds.ReferencedDateTime, "Multiple datetimes not written correctly (VR=DT)")
        self.assertSequenceEqual(multi_TM_expected, ds.CalibrationTime, "Multiple times not written correctly (VR=TM)")
        self.assertEqual(TM_expected, ds.TimeOfLastCalibration, "Time not written correctly (VR=DA)")
        if os.path.exists(datetime_out):
            os.remove(datetime_out)  # get rid of the file


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
        fp = DicomBytesIO()
        fp.is_implicit_VR = is_implicit_VR
        fp.is_little_endian = is_little_endian
        write_data_element(fp, elem)
        byte_string = fp.parent.getvalue()
        fp.close()
        return byte_string

    def test_empty_AT(self):
        """Write empty AT correctly.........."""
        # Was issue 74
        data_elem = DataElement(0x00280009, "AT", [])
        expected = hex2bytes((
            " 28 00 09 00"   # (0028,0009) Frame Increment Pointer
            " 00 00 00 00"   # length 0
        ))
        write_data_element(self.f1, data_elem)
        got = self.f1.parent.getvalue()
        msg = ("Did not write zero-length AT value correctly. "
               "Expected %r, got %r") % (bytes2hex(expected), bytes2hex(got))
        msg = "%r %r" % (type(expected), type(got))
        msg = "'%r' '%r'" % (expected, got)
        self.assertEqual(expected, got, msg)

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
        #             | Tag          | VR    | Rsrvd |   Length      |    Value ->
        ref_bytes = b'\x70\x00\x0d\x15\x4f\x44\x00\x00\x10\x00\x00\x00' + bytestring
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
        #             | Tag          | VR    | Rsrvd |   Length      |    Value ->
        ref_bytes = b'\x66\x00\x29\x01\x4f\x4c\x00\x00\x0c\x00\x00\x00' + bytestring
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
        self.assertEqual(encoded_elem, b'\x08\x00\x20\x01\x00\x00\x00\x00')

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


class TestCorrectAmbiguousVR(unittest.TestCase):
    """Test correct_ambiguous_vr."""
    def test_pixel_representation_vm_one(self):
        """Test correcting VM 1 elements which require PixelRepresentation."""
        ref_ds = Dataset()

        # If PixelRepresentation is 0 then VR should be US
        ref_ds.PixelRepresentation = 0
        ref_ds.SmallestValidPixelValue = b'\x00\x01' # Little endian 256
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.SmallestValidPixelValue, 256)
        self.assertEqual(ds[0x00280104].VR, 'US')

        # If PixelRepresentation is 1 then VR should be SS
        ref_ds.PixelRepresentation = 1
        ref_ds.SmallestValidPixelValue = b'\x00\x01' # Big endian 1
        ds = correct_ambiguous_vr(deepcopy(ref_ds), False)
        self.assertEqual(ds.SmallestValidPixelValue, 1)
        self.assertEqual(ds[0x00280104].VR, 'SS')

        # If no PixelRepresentation then should be unchanged
        ref_ds = Dataset()
        ref_ds.SmallestValidPixelValue = b'\x00\x01' # Big endian 1
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.SmallestValidPixelValue, b'\x00\x01')
        self.assertEqual(ds[0x00280104].VR, 'US or SS')

    def test_pixel_representation_vm_three(self):
        """Test correcting VM 3 elements which require PixelRepresentation."""
        ref_ds = Dataset()

        # If PixelRepresentation is 0 then VR should be US - Little endian
        ref_ds.PixelRepresentation = 0
        ref_ds.LUTDescriptor = b'\x01\x00\x00\x01\x10\x00' # 1\256\16
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
        ref_ds.PixelData = b'\x00\x01' # Little endian 256
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True) # Little endian
        self.assertEqual(ds.PixelData, b'\x00\x01')
        self.assertEqual(ds[0x7fe00010].VR, 'OW')
        ds = correct_ambiguous_vr(deepcopy(ref_ds), False) # Big endian
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
        ref_ds.PixelData = b'\x00\x01' # Big endian 1
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
        ref_ds.WaveformData = b'\x00\x01' # Little endian 256
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True) # Little endian
        self.assertEqual(ds.WaveformData, b'\x00\x01')
        self.assertEqual(ds[0x54001010].VR, 'OW')
        ds = correct_ambiguous_vr(deepcopy(ref_ds), False) # Big endian
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
        ref_ds.WaveformData = b'\x00\x01' # Big endian 1
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.WaveformData, b'\x00\x01')
        self.assertEqual(ds[0x54001010].VR, 'OB or OW')

    def test_lut_descriptor(self):
        """Test correcting elements which require LUTDescriptor."""
        ref_ds = Dataset()
        ref_ds.PixelRepresentation = 0

        # If LUTDescriptor[0] is 1 then LUTData VR is 'US'
        ref_ds.LUTDescriptor = b'\x01\x00\x00\x01\x10\x00' # 1\256\16
        ref_ds.LUTData = b'\x00\x01' # Little endian 256
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True) # Little endian
        self.assertEqual(ds.LUTDescriptor[0], 1)
        self.assertEqual(ds[0x00283002].VR, 'US')
        self.assertEqual(ds.LUTData, 256)
        self.assertEqual(ds[0x00283006].VR, 'US')

        # If LUTDescriptor[0] is not 1 then LUTData VR is 'OW'
        ref_ds.LUTDescriptor = b'\x02\x00\x00\x01\x10\x00' # 2\256\16
        ref_ds.LUTData = b'\x00\x01\x00\x02'
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True) # Little endian
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

    def test_sequence(self):
        """Test correcting elements in a sequence."""
        ref_ds = Dataset()
        ref_ds.BeamSequence = [Dataset()]
        ref_ds.BeamSequence[0].PixelRepresentation = 0
        ref_ds.BeamSequence[0].SmallestValidPixelValue = b'\x00\x01'
        ref_ds.BeamSequence[0].BeamSequence = [Dataset()]
        ref_ds.BeamSequence[0].BeamSequence[0].PixelRepresentation = 0
        ref_ds.BeamSequence[0].BeamSequence[0].SmallestValidPixelValue = b'\x00\x01'

        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.BeamSequence[0].SmallestValidPixelValue, 256)
        self.assertEqual(ds.BeamSequence[0][0x00280104].VR, 'US')
        self.assertEqual(ds.BeamSequence[0].BeamSequence[0].SmallestValidPixelValue, 256)
        self.assertEqual(ds.BeamSequence[0].BeamSequence[0][0x00280104].VR, 'US')


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
        ref_ds.SmallestValidPixelValue = b'\x00\x01' # Little endian 256

        fp = BytesIO()
        file_ds = FileDataset(fp, ref_ds)
        file_ds.is_implicit_VR = False
        file_ds.is_little_endian = True
        file_ds.save_as(fp)
        fp.seek(0)

        ds = read_dataset(fp, False, True)
        self.assertEqual(ds.SmallestValidPixelValue, 256)
        self.assertEqual(ds[0x00280104].VR, 'US')

    def test_write_explicit_vr_big_endian(self):
        """Test writing explicit big data for ambiguous elements."""
        # Create a dataset containing element with ambiguous VRs
        ref_ds = Dataset()
        ref_ds.PixelRepresentation = 1
        ref_ds.SmallestValidPixelValue = b'\x00\x01' # Big endian 1

        fp = BytesIO()
        file_ds = FileDataset(fp, ref_ds)
        file_ds.is_implicit_VR = False
        file_ds.is_little_endian = False
        file_ds.save_as(fp)
        fp.seek(0)

        ds = read_dataset(fp, False, False)
        self.assertEqual(ds.SmallestValidPixelValue, 1)
        self.assertEqual(ds[0x00280104].VR, 'SS')


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
        with open(out_filename, 'rb') as f:
            bytes_written = f.read()
        # print "std    :", bytes2hex(std)
        # print "written:", bytes2hex(bytes_written)
        same, pos = bytes_identical(std, bytes_written)
        self.assertTrue(same,
                        "Writing from scratch unexpected result - 1st diff at 0x%x" % pos)
        if os.path.exists(out_filename):
            os.remove(out_filename)  # get rid of the file

    def testImpl_LE_deflen_write(self):
        """Scratch Write for implicit VR little endian, defined length SQ's"""
        from _write_stds import impl_LE_deflen_std_hex as std

        file_ds = FileDataset("test", self.ds)
        self.compare_write(std, file_ds)


if __name__ == "__main__":
    # This is called if run alone, but not if loaded through run_tests.py
    # If not run from the directory where the sample images are,
    #    then need to switch there
    unittest.main()
