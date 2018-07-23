# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Test suite for MultiValue class"""

import unittest
from pydicom.multival import MultiValue
from pydicom.valuerep import DS, DSfloat, DSdecimal, IS
from pydicom import config
from copy import deepcopy

import sys
python_version = sys.version_info


class MultiValuetests(unittest.TestCase):
    def testMultiDS(self):
        """MultiValue: Multi-valued data elements can be created........"""
        multival = MultiValue(DS, ['11.1', '22.2', '33.3'])
        for val in multival:
            self.assertTrue(isinstance(val, (DSfloat, DSdecimal)),
                            "Multi-value DS item not converted to DS")

    def testEmptyElements(self):
        """MultiValue: Empty number string elements are not converted..."""
        multival = MultiValue(DSfloat, ['1.0', ''])
        self.assertEqual(1.0, multival[0])
        self.assertEqual('', multival[1])
        multival = MultiValue(IS, ['1', ''])
        self.assertEqual(1, multival[0])
        self.assertEqual('', multival[1])
        multival = MultiValue(DSdecimal, ['1', ''])
        self.assertEqual(1, multival[0])
        self.assertEqual('', multival[1])

    def testLimits(self):
        """MultiValue: Raise error if any item outside DICOM limits...."""
        original_flag = config.enforce_valid_values
        config.enforce_valid_values = True
        self.assertRaises(OverflowError,
                          MultiValue,
                          IS, [1, -2 ** 31 - 1])
        # Overflow error not raised for IS out of DICOM valid range
        config.enforce_valid_values = original_flag

    def testAppend(self):
        """MultiValue: Append of item converts it to required type..."""
        multival = MultiValue(IS, [1, 5, 10])
        multival.append('5')
        self.assertTrue(isinstance(multival[-1], IS))
        self.assertEqual(multival[-1], 5,
                         "Item set by append is not correct value")

    def testSetIndex(self):
        """MultiValue: Setting list item converts it to required type"""
        multival = MultiValue(IS, [1, 5, 10])
        multival[1] = '7'
        self.assertTrue(isinstance(multival[1], IS))
        self.assertEqual(multival[1], 7,
                         "Item set by index is not correct value")

    def testDeleteIndex(self):
        """MultiValue: Deleting item at index behaves as expected..."""
        multival = MultiValue(IS, [1, 5, 10])
        del multival[1]
        self.assertEqual(2, len(multival))
        self.assertEqual(multival[0], 1)
        self.assertEqual(multival[1], 10)

    def testExtend(self):
        """MultiValue: Extending a list converts all to required type"""
        multival = MultiValue(IS, [1, 5, 10])
        multival.extend(['7', 42])
        self.assertTrue(isinstance(multival[-2], IS))
        self.assertTrue(isinstance(multival[-1], IS))
        self.assertEqual(multival[-2], 7,
                         "Item set by extend not correct value")

    def testSlice(self):
        """MultiValue: Setting slice converts items to required type."""
        multival = MultiValue(IS, range(7))
        multival[2:7:2] = [4, 16, 36]
        for val in multival:
            self.assertTrue(isinstance(val, IS),
                            "Slice IS value not correct type")
        self.assertEqual(multival[4], 16,
                         "Set by slice failed for item 4 of list")

    def testIssue236DeepCopy(self):
        """MultiValue: deepcopy of MultiValue does not generate an error"""
        multival = MultiValue(IS, range(7))
        deepcopy(multival)
        multival = MultiValue(DS, range(7))
        deepcopy(multival)
        multival = MultiValue(DSfloat, range(7))
        deepcopy(multival)

    def testSorting(self):
        """MultiValue: allow inline sort."""
        multival = MultiValue(DS, [12, 33, 5, 7, 1])
        multival.sort()
        self.assertEqual([1, 5, 7, 12, 33], multival)
        multival.sort(reverse=True)
        self.assertEqual([33, 12, 7, 5, 1], multival)
        multival.sort(key=str)
        self.assertEqual([1, 12, 33, 5, 7], multival)

    def test_equal(self):
        """MultiValue: test equality operator"""
        multival = MultiValue(DS, [12, 33, 5, 7, 1])
        multival2 = MultiValue(DS, [12, 33, 5, 7, 1])
        multival3 = MultiValue(DS, [33, 12, 5, 7, 1])
        self.assertTrue(multival == multival2)
        self.assertFalse(multival == multival3)
        multival = MultiValue(str, ['a', 'b', 'c'])
        multival2 = MultiValue(str, ['a', 'b', 'c'])
        multival3 = MultiValue(str, ['b', 'c', 'a'])
        self.assertTrue(multival == multival2)
        self.assertFalse(multival == multival3)

    def test_not_equal(self):
        """MultiValue: test equality operator"""
        multival = MultiValue(DS, [12, 33, 5, 7, 1])
        multival2 = MultiValue(DS, [12, 33, 5, 7, 1])
        multival3 = MultiValue(DS, [33, 12, 5, 7, 1])
        self.assertFalse(multival != multival2)
        self.assertTrue(multival != multival3)
        multival = MultiValue(str, ['a', 'b', 'c'])
        multival2 = MultiValue(str, ['a', 'b', 'c'])
        multival3 = MultiValue(str, ['b', 'c', 'a'])
        self.assertFalse(multival != multival2)
        self.assertTrue(multival != multival3)


if __name__ == "__main__":
    unittest.main()
