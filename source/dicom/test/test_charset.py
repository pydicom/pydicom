# -*- coding: latin_1 -*-
# test_charset.py
"""unittest cases for dicom.charset module"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import unittest
import dicom

latin1_file = "../testcharsetfiles/chrFren.dcm"
jp_file = "../testcharsetfiles/chrH31.dcm"

class charsetTests(unittest.TestCase):
    def testLatin1(self):
        """charset: can read and decode latin_1 file........................"""
        ds = dicom.read_file(latin1_file)
        ds.decode()
        # Make sure don't get unicode encode error on converting to string
        expected = u"Buc^Jérôme"
        got = ds.PatientsName
        self.assertEqual(expected, got, "Expected %r, got %r" % (expected, got))
        

if __name__ == "__main__":
    # This is called if run alone, but not if loaded through run_tests.py
    # If not run from the directory where the sample images are, then need to switch there
    import sys
    import os
    import os.path
    dir_name = os.path.dirname(sys.argv[0])
    save_dir = os.getcwd()
    if dir_name:
        os.chdir(dir_name)
    os.chdir("../testfiles")
    unittest.main()
    os.chdir(save_dir)