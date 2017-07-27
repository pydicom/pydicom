"""Test the data manager"""

import os
import unittest

from pydicom.data import (get_charset_files,
                          get_testdata_files,
                          get_testdata_base,
                          get_charset_base)

from pydicom.data.base import get_datadir
from pydicom.data.utils import get_files


class TestGetData(unittest.TestCase):

    def test_get_dataset(self):
        """Test the different functions
        to get lists of data files"""

        # Test base locations
        charbase = get_charset_base()
        self.assertTrue(charbase.endswith('charset_files'))
        self.assertTrue(os.path.exists(charbase))

        testbase = get_testdata_base()
        self.assertTrue(testbase.endswith('test_files'))
        self.assertTrue(os.path.exists(testbase))

        # Test file get
        chardata = get_charset_files()
        self.assertTrue(len(chardata) > 15)
        testdata = get_testdata_files()
        self.assertTrue(len(testdata) > 70)

        # The files should be from their respective bases
        [self.assertTrue(testbase in x) for x in testdata]
        [self.assertTrue(charbase in x) for x in chardata]

        # Matching a pattern
        dicoms = get_testdata_files("*dcm")
        [self.assertTrue(x.endswith('.dcm')) for x in dicoms]

    def test_dataset_utils(self):
        '''utils functions for dataset manager'''

        # get_files returns files in folders
        datadir = get_datadir()
        test_folder = "%s/test_files/dicomdirtests" % (datadir)
        files = get_files(test_folder)
        self.assertTrue(len(files) > 1)
