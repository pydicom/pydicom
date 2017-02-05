# -*- coding: latin_1 -*-
# test_charset.py
"""unittest cases for pydicom.charset module"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

import unittest
from pydicom import dicomio
import os.path

test_dir = os.path.dirname(__file__)
testcharset_dir = os.path.join(test_dir, 'charset_files')

latin1_file = os.path.join(testcharset_dir, "chrFren.dcm")
jp_file = os.path.join(testcharset_dir, "chrH31.dcm")
multiPN_file = os.path.join(testcharset_dir, "chrFrenMulti.dcm")
sq_encoding_file = os.path.join(testcharset_dir, "chrSQEncoding.dcm")
explicit_ir6_file = os.path.join(testcharset_dir, "chrJapMultiExplicitIR6.dcm")

test_files = os.path.join(test_dir, 'test_files')
normal_file = os.path.join(test_files, "CT_small.dcm")


class charsetTests(unittest.TestCase):
    def testLatin1(self):
        """charset: can read and decode latin_1 file........................"""
        ds = dicomio.read_file(latin1_file)
        ds.decode()
        # Make sure don't get unicode encode error on converting to string
        expected = u'Buc^J\xe9r\xf4me'
        got = ds.PatientName
        self.assertEqual(expected, got,
                         "Expected %r, got %r" % (expected, got))

    def testNestedCharacterSets(self):
        """charset: can read and decode SQ with different encodings........."""
        ds = dicomio.read_file(sq_encoding_file)
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
        ds = dicomio.read_file(normal_file)
        ds.decode()

    def testExplicitISO2022_IR6(self):
        """charset: can decode file with multi-valued data elements........."""
        ds = dicomio.read_file(explicit_ir6_file)
        ds.decode()


    def testMultiPN(self):
        """charset: can decode file with multi-valued data elements........."""
        ds = dicomio.read_file(multiPN_file)
        ds.decode()


if __name__ == "__main__":
    # This is called if run alone, but not if loaded through run_tests.py
    # If not run from the directory where the sample images are,
    #   then need to switch there
    unittest.main()
