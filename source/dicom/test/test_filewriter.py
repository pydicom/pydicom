# test_filewriter.py
"""unittest cases for dicom.filewriter module"""

import os.path
import os
import sys
import unittest
from dicom.filereader import ReadFile
from dicom.filewriter import WriteFile
from dicom.tag import Tag

testdir = os.path.dirname(sys.argv[0])

rtplan_name = os.path.join(testdir, "rtplan.dcm")
rtdose_name = os.path.join(testdir, "rtdose.dcm")
ct_name     = os.path.join(testdir, "CT_small.dcm")
mr_name     = os.path.join(testdir, "MR_small.dcm")
jpeg_name   = os.path.join(testdir, "JPEG2000.dcm")

# Set up replan_out, rtdose_out etc filenames as above, with '2' appended
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

class WriterTests(unittest.TestCase):
    def compare(self, in_, out_):
        """Read file1, write file2, then compare. Return value as for files_identical"""
        dataset = ReadFile(in_)
        WriteFile(out_, dataset)
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
        """Input file, write back and verify them identical (JPEG2000 file)....."""
        self.compare(jpeg_name, jpeg_out)   
        

if __name__ == "__main__":
    unittest.main()