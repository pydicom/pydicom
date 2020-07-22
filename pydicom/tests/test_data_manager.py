# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Unit tests for pydicom.data_manager"""

import os
from os.path import basename

import pytest

from pydicom.data import (
    get_charset_files, get_testdata_files, get_palette_files
)
from pydicom.data.data_manager import (
    DATA_ROOT, get_testdata_file, EXTERNAL_DATA_SOURCES
)
from pydicom.data.download import get_data_dir


class TestGetData:
    def test_get_dataset(self):
        """Test the different functions to get lists of data files."""
        # The cached files downloaded from the pydicom-data repo
        cached_data_test_files = str(get_data_dir())

        # If pydicom-data is available locally
        ext_path = None
        if 'pydicom-data' in EXTERNAL_DATA_SOURCES:
            ext_path = EXTERNAL_DATA_SOURCES['pydicom-data'].data_path

        # Test base locations
        charbase = os.path.join(DATA_ROOT, 'charset_files')
        assert os.path.exists(charbase)

        testbase = os.path.join(DATA_ROOT, 'test_files')
        assert os.path.exists(testbase)

        # Test file get
        chardata = get_charset_files()
        assert 15 < len(chardata)

        # Test that top level file is included
        bases = [basename(x) for x in chardata]

        # Test that subdirectory files included
        testdata = get_testdata_files()
        bases = [basename(x) for x in testdata]
        assert '2693' in bases
        assert 70 < len(testdata)

        # The files should be from their respective bases
        for x in testdata:
            # Don't check files from external sources other than pydicom-data
            if (
                testbase not in x
                and cached_data_test_files not in x
                and (ext_path not in x if ext_path else True)
            ):
                continue

            assert (
                testbase in x
                or cached_data_test_files in x
                or (ext_path in x if ext_path else False)
            )

        for x in chardata:
            assert charbase in x

    def test_get_dataset_pattern(self):
        """Test that pattern is working properly."""
        pattern = 'CT_small'
        filename = get_testdata_files(pattern)
        assert filename[0].endswith('CT_small.dcm')

        pattern = 'chrX1'
        filename = get_charset_files(pattern)
        assert filename[0].endswith('chrX1.dcm')

    def test_get_testdata_file(self):
        """Test that file name is working properly."""
        name = 'DICOMDIR'
        filename = get_testdata_file(name)
        assert filename and filename.endswith('DICOMDIR')

    def test_get_palette_files(self):
        """Test data_manager.get_palette_files."""
        palbase = os.path.join(DATA_ROOT, 'palettes')
        assert os.path.exists(palbase)

        palettes = get_palette_files('*.dcm')
        assert 8 == len(palettes)

        for x in palettes:
            assert palbase in x
