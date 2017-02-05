# test_util.py
"""Test suite for util functions"""
# Copyright (c) 2014 Darcy Mason
# This file is part of pydicom, released under an MIT-style license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

from io import BytesIO
import os
import unittest

from pydicom import compat
from pydicom import config
from pydicom import filereader
from pydicom.util import fixer
from pydicom.util import hexutil
from pydicom import valuerep


test_dir = os.path.dirname(__file__)
raw_hex_module = os.path.join(test_dir, '_write_stds.py')
raw_hex_code = open(raw_hex_module, "rb").read()


class DataElementCallbackTests(unittest.TestCase):
    def setUp(self):
        # Set up a dataset with commas in one item instead of backslash
        config.enforce_valid_values = True
        namespace = {}
        exec(raw_hex_code, {}, namespace)
        ds_bytes = hexutil.hex2bytes(namespace['impl_LE_deflen_std_hex'])
        # Change "2\4\8\16" to "2,4,8,16"
        ds_bytes = ds_bytes.replace(b"\x32\x5c\x34\x5c\x38\x5c\x31\x36",
                                    b"\x32\x2c\x34\x2c\x38\x2c\x31\x36")

        self.bytesio = BytesIO(ds_bytes)

    def tearDown(self):
        config.enforce_valid_values = False

    def testBadSeparator(self):
        """Ensure that unchanged bad separator does raise an error..........."""
        ds = filereader.read_dataset(self.bytesio, is_little_endian=True,
                                     is_implicit_VR=True)
        contour = ds.ROIContourSequence[0].ContourSequence[0]
        self.assertRaises(ValueError, getattr, contour, "ContourData")

    def testImplVRcomma(self):
        """util.fix_separator: Able to replace comma in Implicit VR dataset.."""
        fixer.fix_separator(b",", for_VRs=["DS", "IS"],
                            process_unknown_VRs=False)
        ds = filereader.read_dataset(self.bytesio, is_little_endian=True,
                                     is_implicit_VR=True)
        expected = [valuerep.DSfloat(x) for x in ["2", "4", "8", "16"]]
        got = ds.ROIContourSequence[0].ContourSequence[0].ContourData
        config.reset_data_element_callback()

        msg = "Expected {0}, got {1}".format(expected, got)
        self.assertEqual(expected, got, msg)


if __name__ == "__main__":
    unittest.main()
