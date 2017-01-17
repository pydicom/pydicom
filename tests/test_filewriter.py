# test_filewriter.py
"""unittest cases for pydicom.filewriter module"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

# from io import BytesIO
import sys
import os.path
import os
from datetime import date, datetime, time

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
from pydicom.filereader import read_file
from pydicom.filewriter import write_data_element
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
        """Return the encoded `elem` using little endian implicit.
        
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

    def test_write_UR(self):
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
        #print('\\x' + '\\x'.join(format(byte, '02x') for byte in encoded_elem))


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
