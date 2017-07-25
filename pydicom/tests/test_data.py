"""Test the data manager"""

import unittest

from pydicom.data import get_dataset

class TestData(unittest.TestCase):

    def test_get_dataset(self):
        """Test the get_dataset function"""

        # No specification returns None
        datasets = get_dataset()
        self.assertTrue(datasets is None)

        # parent directory base for all of files
        testbase = get_dataset('test', return_base=True)
        testdata = get_dataset('test')
        self.assertTrue(len(testdata)>20)
        [self.assertTrue(testbase in x) for x in testdata]

        # Matching a pattern
        dicoms = get_dataset('test', pattern='*.dcm')
        [self.assertTrue(x.endswith('.dcm')) for x in dicoms]
