"""Test the data manager"""

import os
import unittest

from pydicom.data import (get_charset_files,
                          get_testdata_files)

from pydicom.data.base import DATA_ROOT


class TestGetData(unittest.TestCase):

    def test_get_dataset(self):
        """Test the different functions
        to get lists of data files"""

        # Test base locations
        charbase = os.path.join(DATA_ROOT, 'charset_files')
        self.assertTrue(os.path.exists(charbase))

        testbase = os.path.join(DATA_ROOT, 'test_files')
        self.assertTrue(os.path.exists(testbase))

        # Test file get
        chardata = get_charset_files()
        self.assertTrue(len(chardata) > 15)
        testdata = get_testdata_files()
        self.assertTrue(len(testdata) > 70)

        # The files should be from their respective bases
        [self.assertTrue(testbase in x) for x in testdata]
        [self.assertTrue(charbase in x) for x in chardata]
