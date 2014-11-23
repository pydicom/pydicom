# test_filewriter.py
"""unittest cases for dicom.filewriter module"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import sys
import os.path
import os
import unittest
from dicom.filereader import read_file
from dicom.filewriter import write_data_element
from dicom.dataset import Dataset, FileDataset
from dicom.sequence import Sequence
from dicom.util.hexutil import hex2bytes, bytes2hex

# from io import BytesIO
from dicom.filebase import DicomBytesIO
from dicom.dataelem import DataElement

from pkg_resources import Requirement, resource_filename
test_dir = resource_filename(Requirement.parse("pydicom"), "dicom/testfiles")
testcharset_dir = resource_filename(Requirement.parse("pydicom"),
                                    "dicom/testcharsetfiles")

rtplan_name = os.path.join(test_dir, "rtplan.dcm")
rtdose_name = os.path.join(test_dir, "rtdose.dcm")
ct_name = os.path.join(test_dir, "CT_small.dcm")
mr_name = os.path.join(test_dir, "MR_small.dcm")
jpeg_name = os.path.join(test_dir, "JPEG2000.dcm")

unicode_name = os.path.join(testcharset_dir, "chrH31.dcm")
multiPN_name = os.path.join(testcharset_dir, "chrFrenMulti.dcm")

# Set up rtplan_out, rtdose_out etc. Filenames as above, with '2' appended
rtplan_out = rtplan_name + '2'
rtdose_out = rtdose_name + '2'
ct_out = ct_name + '2'
mr_out = mr_name + '2'
jpeg_out = jpeg_name + '2'
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


class WriteDataElementTests(unittest.TestCase):
    """Attempt to write data elements has the expected behaviour"""
    def setUp(self):
        # Create a dummy (in memory) file to write to
        self.f1 = DicomBytesIO()
        self.f1.is_little_endian = True
        self.f1.is_implicit_VR = True

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


class ScratchWriteTests(unittest.TestCase):
    """Simple dataset from scratch, written in all endian/VR combinations"""
    def setUp(self):
        # Create simple dataset for all tests
        ds = Dataset()
        ds.PatientName = "Name^Patient"

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
        from dicom.test._write_stds import impl_LE_deflen_std_hex as std

        file_ds = FileDataset("test", self.ds)
        self.compare_write(std, file_ds)


if __name__ == "__main__":
    # This is called if run alone, but not if loaded through run_tests.py
    # If not run from the directory where the sample images are,
    #    then need to switch there
    dir_name = os.path.dirname(sys.argv[0])
    save_dir = os.getcwd()
    if dir_name:
        os.chdir(dir_name)
    os.chdir("../testfiles")
    unittest.main()
    os.chdir(save_dir)
