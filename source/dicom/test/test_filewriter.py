# test_filewriter.py
"""unittest cases for dicom.filewriter module"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import sys
import os.path
import os
import unittest
from dicom.filereader import read_file
from dicom.filewriter import write_file, write_data_element
from dicom.tag import Tag
# from cStringIO import StringIO
from dicom.filebase import DicomStringIO
from dicom.dataelem import DataElement
from dicom.util.hexutil import hex2bytes, bytes2hex

from pkg_resources import Requirement, resource_filename
test_dir = resource_filename(Requirement.parse("pydicom"),"dicom/testfiles")

rtplan_name = os.path.join(test_dir, "rtplan.dcm")
rtdose_name = os.path.join(test_dir, "rtdose.dcm")
ct_name     = os.path.join(test_dir, "CT_small.dcm")
mr_name     = os.path.join(test_dir, "MR_small.dcm")
jpeg_name   = os.path.join(test_dir, "JPEG2000.dcm")

# Set up rtplan_out, rtdose_out etc. Filenames as above, with '2' appended
for inname in ['rtplan', 'rtdose', 'ct', 'mr', 'jpeg']:
    exec(inname + "_out = " + inname + "_name + '2'")

def files_identical(a, b):
    """Return a tuple (file a == file b, index of first difference)"""
    a_bytes = file(a, "rb").read()
    b_bytes = file(b, "rb").read()
    if a_bytes == b_bytes:
        return True, 0     # True, dummy argument
    else:
        pos = 0
        while a_bytes[pos] == b_bytes[pos]:
            pos += 1
        return False, pos   # False (not identical files), position of first difference

class WriteFileTests(unittest.TestCase):
    def compare(self, in_, out_):
        """Read file1, write file2, then compare. Return value as for files_identical"""
        dataset = read_file(in_)
        write_file(out_, dataset)
        same, pos = files_identical(in_, out_)
        self.assert_(same, "Files are not identical - first difference at 0x%x" % pos)
        if os.path.exists(out_):
            os.remove(out_)  # get rid of the file
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
    def testJPEG2000(self):
        """Input file, write back and verify them identical (JPEG2K file)."""
        self.compare(jpeg_name, jpeg_out)
     
class WriteDataElementTests(unittest.TestCase):
    """Attempt to data elements has the expected behaviour"""
    def setUp(self):
        # Create a dummy (in memory) file to write to
        self.f1 = DicomStringIO()
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
        
    
if __name__ == "__main__":
    # This is called if run alone, but not if loaded through run_tests.py
    # If not run from the directory where the sample images are, then need to switch there
    dir_name = os.path.dirname(sys.argv[0])
    save_dir = os.getcwd()
    if dir_name:
        os.chdir(dir_name)
    os.chdir("../testfiles")
    unittest.main()
    os.chdir(save_dir)