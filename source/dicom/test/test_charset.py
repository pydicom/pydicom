# -*- coding: latin_1 -*-
# test_charset.py
"""unittest cases for dicom.charset module"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import unittest
import dicom
import os.path

from pkg_resources import Requirement, resource_filename
testcharset_dir = resource_filename(Requirement.parse("pydicom"),
                                    "dicom/testcharsetfiles")

latin1_file = os.path.join(testcharset_dir, "chrFren.dcm")
jp_file = os.path.join(testcharset_dir, "chrH31.dcm")
multiPN_file = os.path.join(testcharset_dir, "chrFrenMulti.dcm")
sq_encoding_file = os.path.join(testcharset_dir, "chrSQEncoding.dcm")

test_dir = resource_filename(Requirement.parse("pydicom"), "dicom/testfiles")
normal_file = os.path.join(test_dir, "CT_small.dcm")


class charsetTests(unittest.TestCase):
    def testLatin1(self):
        """charset: can read and decode latin_1 file........................"""
        ds = dicom.read_file(latin1_file)
        ds.decode()
        # Make sure don't get unicode encode error on converting to string
        expected = u'Buc^J\xe9r\xf4me'
        got = ds.PatientName
        self.assertEqual(expected, got,
                         "Expected %r, got %r" % (expected, got))

    def testNestedCharacterSets(self):
        """charset: can read and decode SQ with different encodings........."""
        ds = dicom.read_file(sq_encoding_file)
        ds.decode()
        # These datasets inside of the SQ cannot be decoded with default_encoding
        # OR UTF-8 (the parent dataset's encoding). Instead, we make sure that it
        # is decoded using the (0008,0005) tag of the dataset
        expected = u'\uff94\uff8f\uff80\uff9e^\uff80\uff9b\uff73=\u5c71\u7530^\u592a\u90ce=\u3084\u307e\u3060^\u305f\u308d\u3046'
        got = ds[0x32, 0x1064][0].PatientName
        self.assertEqual(expected, got,
                         "Expected %r, got %r" % (expected, got))

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
    # If not run from the directory where the sample images are,
    #   then need to switch there
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
