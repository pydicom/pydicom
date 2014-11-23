# test_multival.py
"""Test suite for MultiValue class"""
# Copyright (c) 2012 Darcy Mason
# This file is part of pydicom, relased under an MIT-style license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import unittest
from dicom.multival import MultiValue
from dicom.valuerep import DS, DSfloat, DSdecimal, IS
import dicom.config

import sys
python_version = sys.version_info


class MultiValuetests(unittest.TestCase):
    def testMultiDS(self):
        """MultiValue: Multi-valued data elements can be created........"""
        multival = MultiValue(DS, ['11.1', '22.2', '33.3'])
        for val in multival:
            self.assertTrue(isinstance(val, (DSfloat, DSdecimal)),
                            "Multi-value DS item not converted to DS")

    def testLimits(self):
        """MultiValue: Raise error if any item outside DICOM limits...."""
        original_flag = dicom.config.enforce_valid_values
        dicom.config.enforce_valid_values = True
        self.assertRaises(OverflowError, MultiValue, IS, [1, -2 ** 31 - 1])  # Overflow error not raised for IS out of DICOM valid range
        dicom.config.enforce_valid_values = original_flag

    def testAppend(self):
        """MultiValue: Append of item converts it to required type..."""
        multival = MultiValue(IS, [1, 5, 10])
        multival.append('5')
        self.assertTrue(isinstance(multival[-1], IS))
        self.assertEqual(multival[-1], 5, "Item set by append is not correct value")

    def testSetIndex(self):
        """MultiValue: Setting list item converts it to required type"""
        multival = MultiValue(IS, [1, 5, 10])
        multival[1] = '7'
        self.assertTrue(isinstance(multival[1], IS))
        self.assertEqual(multival[1], 7, "Item set by index is not correct value")

    def testExtend(self):
        """MultiValue: Extending a list converts all to required type"""
        multival = MultiValue(IS, [1, 5, 10])
        multival.extend(['7', 42])
        self.assertTrue(isinstance(multival[-2], IS))
        self.assertTrue(isinstance(multival[-1], IS))
        self.assertEqual(multival[-2], 7, "Item set by extend not correct value")

    def testSlice(self):
        """MultiValue: Setting slice converts items to required type."""
        multival = MultiValue(IS, range(7))
        multival[2:7:2] = [4, 16, 36]
        for val in multival:
            self.assertTrue(isinstance(val, IS), "Slice IS value not correct type")
        self.assertEqual(multival[4], 16, "Set by slice failed for item 4 of list")


if __name__ == "__main__":
    unittest.main()
