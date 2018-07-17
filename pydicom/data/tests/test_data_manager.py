# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Test the data manager"""

import os
import unittest
from os.path import basename
from pydicom.data import (get_charset_files,
                          get_testdata_files)

from pydicom.data.data_manager import DATA_ROOT


class TestGetData(unittest.TestCase):

    def test_get_dataset(self):
        """Test the different functions to get lists of data files."""

        # Test base locations
        charbase = os.path.join(DATA_ROOT, 'charset_files')
        self.assertTrue(os.path.exists(charbase))

        testbase = os.path.join(DATA_ROOT, 'test_files')
        self.assertTrue(os.path.exists(testbase))

        # Test file get
        chardata = get_charset_files()
        self.assertTrue(len(chardata) > 15)

        # Test that top level file is included
        bases = [basename(x) for x in chardata]

        # Test that subdirectory files included
        testdata = get_testdata_files()
        bases = [basename(x) for x in testdata]
        self.assertTrue('2693' in bases)
        self.assertTrue(len(testdata) > 70)

        # The files should be from their respective bases
        [self.assertTrue(testbase in x) for x in testdata]
        [self.assertTrue(charbase in x) for x in chardata]

    def test_get_dataset_pattern(self):
        """Test that pattern is working properly."""

        pattern = 'CT_small'
        filename = get_testdata_files(pattern)
        self.assertTrue(filename[0].endswith('CT_small.dcm'))

        pattern = 'chrX1'
        filename = get_charset_files(pattern)
        self.assertTrue(filename[0].endswith('chrX1.dcm'))
