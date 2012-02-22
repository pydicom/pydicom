# -*- coding: latin_1 -*-
# test_charset.py
#PZ 9 Feb 2012
"""unittest cases for dicom.charset module"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com
import sys
if sys.hexversion >= 0x02060000 and sys.hexversion < 0x03000000: 
    inPy26 = True
    inPy3 = False    
elif sys.hexversion >= 0x03000000: 
    inPy3 = True
    inPy26 = False
    basestring = str

import unittest
import dicom
import os
import os.path

testcharset_dir = os.path.join(os.path.dirname(dicom.__file__), "testcharsetfiles")
latin1_file = os.path.join(testcharset_dir, "chrFren.dcm")
jp_file = os.path.join(testcharset_dir, "chrH31.dcm")
multiPN_file = os.path.join(testcharset_dir, "chrFrenMulti.dcm")

test_dir = os.path.join(os.path.dirname(dicom.__file__), "testfiles")
normal_file = os.path.join(test_dir, "CT_small.dcm")


class charsetTests(unittest.TestCase):
    def testLatin1(self):
        """charset: can read and decode latin_1 file........................"""
        ds = dicom.read_file(latin1_file)
        ds.decode()
        # Make sure don't get unicode encode error on converting to string
#PZ Py3 no u        
        expected = "Buc^Jérôme"
        got = ds.PatientName
        self.assertEqual(expected, got, "Expected %r, got %r" % (expected, got))
    def testStandardFile(self):
        """charset: can read and decode standard file without special char.."""
        ds = dicom.read_file(normal_file)
        ds.decode()
    def testMultiPN(self):
        """charset: can decode file with multi-valued data elements........."""
        ds = dicom.read_file(multiPN_file)
        ds.decode()

if __name__ == "__main__":
    # This is called if run alone, but not if loaded through run_tests.py
    # If not run from the directory where the sample images are, then need to switch there

    dir_name = os.path.dirname(sys.argv[0])
    save_dir = os.getcwd()
    if dir_name:
        os.chdir(dir_name)
    os.chdir(os.path.join("..","testfiles"))
    unittest.main()
    os.chdir(save_dir)