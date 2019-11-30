# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Test for dicomdir.py"""

import pytest

from pydicom.data import get_testdata_files
from pydicom.dicomdir import DicomDir
from pydicom.errors import InvalidDicomError
from pydicom import config, dcmread

TEST_FILE = get_testdata_files('DICOMDIR')[0]
IMPLICIT_TEST_FILE = get_testdata_files('DICOMDIR-implicit')[0]
BIGENDIAN_TEST_FILE = get_testdata_files('DICOMDIR-bigEnd')[0]


class TestDicomDir(object):
    """Test dicomdir.DicomDir class"""

    def teardown(self):
        config.enforce_valid_values = False

    def test_read_file(self):
        """Test creation of DicomDir instance using pydicom.dcmread"""
        ds = dcmread(TEST_FILE)
        assert isinstance(ds, DicomDir)

    def test_invalid_sop_file_meta(self):
        """Test exception raised if SOP Class is not Media Storage Directory"""
        ds = dcmread(get_testdata_files('CT_small.dcm')[0])
        with pytest.raises(InvalidDicomError,
                           match=r"SOP Class is not Media Storage "
                                 r"Directory \(DICOMDIR\)"):
            DicomDir("some_name", ds, b'\x00' * 128, ds.file_meta, True, True)

    def test_invalid_sop_no_file_meta(self):
        """Test exception raised if invalid sop class but no file_meta"""
        ds = dcmread(get_testdata_files('CT_small.dcm')[0])
        with pytest.raises(AttributeError,
                           match="'DicomDir' object has no attribute "
                                 "'DirectoryRecordSequence'"):
            DicomDir("some_name", ds, b'\x00' * 128, None, True, True)

    def test_parse_records(self):
        """Test DicomDir.parse_records"""
        ds = dcmread(TEST_FILE)
        assert hasattr(ds, 'patient_records')
        # There are two top level PATIENT records
        assert len(ds.patient_records) == 2
        assert ds.patient_records[0].PatientName == 'Doe^Archibald'
        assert ds.patient_records[1].PatientName == 'Doe^Peter'

    def test_invalid_transfer_syntax(self):
        with pytest.warns(UserWarning, match='Invalid transfer syntax*'):
            dcmread(IMPLICIT_TEST_FILE)
        with pytest.warns(UserWarning, match='Invalid transfer syntax*'):
            dcmread(BIGENDIAN_TEST_FILE)

    def test_invalid_transfer_syntax_strict_mode(self):
        config.enforce_valid_values = True
        with pytest.raises(InvalidDicomError,
                           match='Invalid transfer syntax*'):
            dcmread(IMPLICIT_TEST_FILE)
        with pytest.raises(InvalidDicomError,
                           match='Invalid transfer syntax*'):
            dcmread(BIGENDIAN_TEST_FILE)
