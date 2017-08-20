# Copyright 2008-2017 pydicom authors. See LICENSE file for details.
"""Test for encaps.py"""

import pytest

from pydicom.data import get_testdata_files
from pydicom.dicomdir import DicomDir
from pydicom import read_file


TEST_FILE = get_testdata_files('DICOMDIR')[0]


class TestDicomDir(object):
    """Test dicomdir.DicomDir class"""
    def test_read_file(self):
        """Test creation of DicomDir instance using filereader.read_file"""
        ds = read_file(TEST_FILE)
        assert isinstance(ds, DicomDir)

    def test_invalid_sop_class(self):
        """Test exception raised if SOP Class is not Media Storage Directory"""
        ds = read_file(get_testdata_files('CT_small.dcm')[0])
