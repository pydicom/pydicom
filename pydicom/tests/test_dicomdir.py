# Copyright 2008-2017 pydicom authors. See LICENSE file for details.
"""Test for dicomdir.py"""

import pytest

from pydicom.data import get_testdata_files
from pydicom.dicomdir import DicomDir
from pydicom.errors import InvalidDicomError
from pydicom import read_file


TEST_FILE = get_testdata_files('DICOMDIR')[0]


def assert_raises_regex(type_error, message, func, *args, **kwargs):
    """Test a raised exception against an expected exception.

    Parameters
    ----------
    type_error : Exception
        The expected raised exception.
    message : str
        A string that will be used as a regex pattern to match against the
        actual exception message. If using the actual expected message don't
        forget to escape any regex special characters like '|', '(', ')', etc.
    func : callable
        The function that is expected to raise the exception.
    args
        The callable function `func`'s arguments.
    kwargs
        The callable function `func`'s keyword arguments.

    Notes
    -----
    Taken from https://github.com/glemaitre/specio, BSD 3 license.
    """
    with pytest.raises(type_error) as excinfo:
        func(*args, **kwargs)
    excinfo.match(message)


class TestDicomDir(object):
    """Test dicomdir.DicomDir class"""
    def test_read_file(self):
        """Test creation of DicomDir instance using filereader.read_file"""
        ds = read_file(TEST_FILE)
        assert isinstance(ds, DicomDir)

    def test_invalid_sop_file_meta(self):
        """Test exception raised if SOP Class is not Media Storage Directory"""
        ds = read_file(get_testdata_files('CT_small.dcm')[0])
        assert_raises_regex(InvalidDicomError,
                            "SOP Class is not Media Storage "
                            "Directory \(DICOMDIR\)",
                            DicomDir,
                            "some_name",
                            ds,
                            b'\x00' * 128,
                            ds.file_meta,
                            True,
                            True)

    def test_invalid_sop_no_file_meta(self):
        """Test exception raised if invalid sop class but no file_meta"""
        ds = read_file(get_testdata_files('CT_small.dcm')[0])
        assert_raises_regex(AttributeError,
                            "'DicomDir' object has no attribute "
                            "'DirectoryRecordSequence'",
                            DicomDir,
                            "some_name",
                            ds,
                            b'\x00' * 128,
                            None,
                            True,
                            True)

    def test_parse_records(self):
        """Test DicomDir.parse_records"""
        ds = read_file(TEST_FILE)
        assert hasattr(ds, 'patient_records')
        # There are two top level PATIENT records
        assert len(ds.patient_records) == 2
        assert ds.patient_records[0].PatientName == 'Doe^Archibald'
        assert ds.patient_records[1].PatientName == 'Doe^Peter'
