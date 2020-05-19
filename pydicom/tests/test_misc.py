# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Tests for misc.py"""

import os

import pytest

from pydicom.data import get_testdata_files
from pydicom.misc import is_dicom, size_in_bytes

test_file = get_testdata_files('CT_small.dcm')[0]
no_meta_file = get_testdata_files('ExplVR_LitEndNoMeta.dcm')[0]


class TestMisc:
    def test_is_dicom(self):
        """Test the is_dicom function."""
        invalid_file = test_file.replace('CT_', 'CT')  # invalid file
        notdicom_file = os.path.abspath(__file__)  # use own file

        # valid file returns True
        assert is_dicom(test_file)

        # return false for real file but not dicom
        assert not is_dicom(notdicom_file)

        # test invalid path
        with pytest.raises(IOError):
            is_dicom(invalid_file)

        # Test no meta prefix/preamble fails
        assert not is_dicom(no_meta_file)

    def test_size_in_bytes(self):
        """Test convenience function size_in_bytes()."""
        # None or numbers shall be returned unchanged
        assert size_in_bytes(None) is None
        assert size_in_bytes(float('inf')) is None
        assert size_in_bytes(1234) == 1234

        # string shall be parsed
        assert size_in_bytes('1234') == 1234
        assert size_in_bytes('4 kb') == 4096
        assert size_in_bytes('16 KB') == 0x4000
        assert size_in_bytes('3  MB') == 0x300000
        assert size_in_bytes('2gB') == 0x80000000

        with pytest.raises(ValueError):
            size_in_bytes('2 TB')
        with pytest.raises(ValueError):
            size_in_bytes('KB 2')
