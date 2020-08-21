# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Test for dicomdir.py"""

from pathlib import Path

import pytest

from pydicom import config, dcmread
from pydicom.data import get_testdata_file
from pydicom.dataset import Dataset
from pydicom.dicomdir import DicomDir, FileSet, File
from pydicom.errors import InvalidDicomError
from pydicom.uid import UID

TEST_FILE = get_testdata_file('DICOMDIR')
IMPLICIT_TEST_FILE = get_testdata_file('DICOMDIR-implicit')
BIGENDIAN_TEST_FILE = get_testdata_file('DICOMDIR-bigEnd')

TEST_FILES = (
    get_testdata_file('DICOMDIR'),
    get_testdata_file('DICOMDIR-reordered'),
    get_testdata_file('DICOMDIR-nooffset')
)


class TestDicomDir:
    """Test dicomdir.DicomDir class"""
    @pytest.mark.parametrize("testfile", TEST_FILES)
    def test_read_file(self, testfile):
        """Test creation of DicomDir instance using filereader.read_file"""
        ds = dcmread(testfile)
        assert isinstance(ds, DicomDir)

    def test_invalid_sop_file_meta(self):
        """Test exception raised if SOP Class is not Media Storage Directory"""
        ds = dcmread(get_testdata_file('CT_small.dcm'))
        msg = (
            r"The 'Media Storage SOP Class UID' for a DICOMDIR dataset "
            r"must be '1.2.840.10008.1.3.10' - Media Storage Directory"
        )
        with pytest.raises(InvalidDicomError, match=msg):
            DicomDir("some_name", ds, b'\x00' * 128, ds.file_meta, True, True)

    def test_invalid_sop_no_file_meta(self, allow_invalid_values):
        """Test exception raised if invalid sop class but no file_meta"""
        ds = dcmread(get_testdata_file('CT_small.dcm'))
        with pytest.raises(AttributeError,
                           match="'DicomDir' object has no attribute "
                                 "'DirectoryRecordSequence'"):
            with pytest.warns(UserWarning, match=r"Invalid transfer syntax"):
                DicomDir("some_name", ds, b'\x00' * 128, None, True, True)

    @pytest.mark.parametrize("testfile", TEST_FILES)
    def test_parse_records(self, testfile):
        """Test DicomDir.parse_records"""
        ds = dcmread(testfile)
        assert hasattr(ds, 'patient_records')
        # There are two top level PATIENT records
        assert len(ds.patient_records) == 2
        assert ds.patient_records[0].PatientName == 'Doe^Archibald'
        assert ds.patient_records[1].PatientName == 'Doe^Peter'

    def test_invalid_transfer_syntax(self, allow_invalid_values):
        with pytest.warns(UserWarning, match='Invalid transfer syntax*'):
            dcmread(IMPLICIT_TEST_FILE)
        with pytest.warns(UserWarning, match='Invalid transfer syntax*'):
            dcmread(BIGENDIAN_TEST_FILE)

    def test_empty(self):
        """Test that an empty DICOMDIR can be read."""
        ds = dcmread(get_testdata_file('DICOMDIR-empty.dcm'))
        assert [] == ds.DirectoryRecordSequence

    def test_invalid_transfer_syntax_strict_mode(self, enforce_valid_values):
        with pytest.raises(InvalidDicomError,
                           match='Invalid transfer syntax*'):
            dcmread(IMPLICIT_TEST_FILE)
        with pytest.raises(InvalidDicomError,
                           match='Invalid transfer syntax*'):
            dcmread(BIGENDIAN_TEST_FILE)


@pytest.fixture
def dicomdir():
    """Return a DICOMDIR dataset."""
    return dcmread(TEST_FILE)


class TestFileSetLoad:
    """Tests for dicomdir.FileSet creating from an existing File-set."""
    def test_loading(self, dicomdir):
        """Test loading an existing File-set."""
        fs = FileSet(dicomdir)
        assert dicomdir == fs.DICOMDIR
        assert "PYDICOM_TEST" == fs.FileSetID
        assert "1.2.276.0.7230010.3.1.4.0.31906.1359940846.78187" == fs.FileSetUID

        print(fs)

    def test_change_file_set_id(self, dicomdir):
        """Test changing the File-set ID."""
        fs = FileSet(dicomdir)
        fs.FileSetID = "MYFILESET"
        assert "MYFILESET" == fs.FileSetID
        assert "MYFILESET" == dicomdir.FileSetID

    def test_records(self, dicomdir):
        """Test the records."""
        fs = FileSet(dicomdir)
        tree = fs._tree
        # Patient level
        assert ['77654033', '98890234'] == list(tree.keys())
        studies = tree['77654033']
        assert (
            [
                '1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.1',
                '1.3.6.1.4.1.5962.1.1.0.0.0.1196530851.28319.0.1'
            ] == list(studies.keys())
        )
        series = studies['1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.1']
        assert (
            [
                '1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.10',
                '1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.6',
                '1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.8'
            ] == list(series.keys())
        )
        images = series['1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.10']
        assert (
            ['1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.11']
            == list(images.keys())
        )
        record = images['1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.11']
        assert "IMAGE" == record.record_type

    def test_iter(self, dicomdir):
        """Test iter(FileSet)."""
        fs = FileSet(dicomdir)
        ii = 0
        for record in fs:
            ii += 1
            assert isinstance(record, File)

        assert 31 == ii

    def test_iter_files(self, dicomdir):
        """Test iterating the File-set records."""
        fs = FileSet(dicomdir)
        ii = 0
        for record in fs.iter_files():
            ii += 1
            assert isinstance(record, File)

        assert 31 == ii

    def test_iter_patient(self, dicomdir):
        """Test iterating the records for a patient."""
        fs = FileSet(dicomdir)
        ii = 0
        for record in fs.iter_patient('77654033'):
            ii += 1
            assert isinstance(record, File)

        assert 7 == ii

        ii = 0
        for record in fs.iter_patient('98890234'):
            ii += 1
            assert isinstance(record, File)

        assert 24 == ii

    def test_iter_study(self, dicomdir):
        """Test iterating the records for a patient's study."""
        fs = FileSet(dicomdir)
        ii = 0
        study_uid = '1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.1'
        for record in fs.iter_study('77654033', study_uid):
            ii += 1
            assert isinstance(record, File)

        assert 3 == ii

        ii = 0
        study_uid = '1.3.6.1.4.1.5962.1.1.0.0.0.1196530851.28319.0.1'
        for record in fs.iter_study('77654033', study_uid):
            ii += 1
            assert isinstance(record, File)

        assert 4 == ii

    def test_iter_series(self, dicomdir):
        """Test iterating the records for a patient's study."""
        fs = FileSet(dicomdir)
        study_uid = '1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.1'
        series = [
            '1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.10',
            '1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.6',
            '1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.8',
        ]
        for series_uid in series:
            ii = 0
            for record in fs.iter_series('77654033', study_uid, series_uid):
                ii += 1
                assert isinstance(record, File)

            assert 1 == ii

        ii = 0
        study_uid = '1.3.6.1.4.1.5962.1.1.0.0.0.1196530851.28319.0.1'
        series_uid = '1.3.6.1.4.1.5962.1.1.0.0.0.1196530851.28319.0.2'
        for record in fs.iter_series('77654033', study_uid, series_uid):
            ii += 1
            assert isinstance(record, File)

        assert 4 == ii

    def test_instance(self, dicomdir):
        """Test loading a File's dataset."""
        fs = FileSet(dicomdir)
        study_uid = '1.3.6.1.4.1.5962.1.1.0.0.0.1196530851.28319.0.1'
        series_uid = '1.3.6.1.4.1.5962.1.1.0.0.0.1196530851.28319.0.2'
        ii = 0
        for record in fs.iter_files('77654033', study_uid, series_uid):
            fpath = Path(record.filepath)
            assert fpath.exists() and fpath.is_file()
            ds = record.instance
            assert '77654033' == ds.PatientID
            assert study_uid == ds.StudyInstanceUID
            assert series_uid == ds.SeriesInstanceUID
            assert "Doe^Archibald" == ds.PatientName
            ii += 1

        assert 4 == ii

    def test_len(self, dicomdir):
        """Test len(FileSet)."""
        fs = FileSet()
        assert 0 == len(fs)

        fs = FileSet(dicomdir)
        assert 31 == len(fs)


class TestFileSetNew:
    """Tests for dicomdir.FileSet from a File-set created from scratch."""
    def test_empty_DICOMDIR(self):
        """Test DICOMDIR with no records."""
        fs = FileSet()
        ds = fs.DICOMDIR
        assert isinstance(ds, Dataset)
        assert ds.FileSetID is None

    def test_file_set_uid(self):
        """Test that the File-set UID is created and constant."""
        fs = FileSet()
        uid = fs.FileSetUID
        assert uid.is_valid
        uid2 = fs.FileSetUID
        assert uid == uid2

        fs.FileSetUID = '1.2.3.4'
        assert '1.2.3.4' == fs.FileSetUID
