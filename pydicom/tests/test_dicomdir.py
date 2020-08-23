# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Test for dicomdir.py"""

import os
from pathlib import Path

import pytest

from pydicom import config, dcmread
from pydicom.data import get_testdata_file
from pydicom.dataset import Dataset
from pydicom.dicomdir import DicomDir, FileSet, FileInstance
from pydicom.errors import InvalidDicomError
from pydicom._storage_sopclass_uids import MediaStorageDirectoryStorage
from pydicom.tag import Tag
from pydicom.uid import UID, ExplicitVRLittleEndian

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
        msg = (
            r"'DicomDir' object has no attribute 'DirectoryRecordSequence'"
        )
        with pytest.raises(AttributeError, match=msg):
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


class TestFileInstance:
    """Tests for FileInstance."""
    def test_properties(self, dicomdir):
        """Test the FileInstance properties."""
        fs = FileSet(dicomdir)
        instance = fs._instances[0]
        assert fs == instance.file_set
        assert "77654033/CR1/6154" in instance.path
        assert isinstance(instance.path, str)
        sop_instance = "1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.11"

        records = instance._records
        assert 4 == len(records)
        patient = records["PATIENT"]
        study = records["STUDY"]
        series = records["SERIES"]
        image = records["IMAGE"]
        assert sop_instance == image.record.ReferencedSOPInstanceUIDInFile

        assert sop_instance == instance.SOPInstanceUID
        assert ExplicitVRLittleEndian == instance.TransferSyntaxUID
        assert "1.2.840.10008.5.1.4.1.1.1" == instance.SOPClassUID

    def test_load(self, dicomdir):
        """Test FileInstance.load()."""
        fs = FileSet(dicomdir)
        instance = fs._instances[0]
        ds = instance.load()
        assert isinstance(ds, Dataset)
        sop_instance = "1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.11"
        assert sop_instance == ds.SOPInstanceUID

    def test_getattr(self, dicomdir):
        """Test FileInstance.__getattribute__."""
        fs = FileSet(dicomdir)
        instance = fs._instances[0]
        assert "20010101" == instance.StudyDate
        instance.my_attr = 1234
        assert 1234 == instance.my_attr
        msg = r"'FileInstance' object has no attribute 'missing_attr'"
        with pytest.raises(AttributeError, match=msg):
            instance.missing_attr

    def test_getitem(self, dicomdir):
        """Test FileInstance.__getitem__."""
        fs = FileSet(dicomdir)
        instance = fs._instances[0]
        assert "20010101" == instance["StudyDate"].value
        assert "20010101" == instance[0x00080020].value
        assert "20010101" == instance[Tag(0x00080020)].value
        assert "20010101" == instance[(0x0008, 0x0020)].value
        assert "20010101" == instance["0x00080020"].value

        with pytest.raises(KeyError, match=r"(0000, 0000)"):
            instance[0x00000000]

    def test_private(self, dicomdir):
        """Test FileInstance with PRIVATE records."""
        record = Dataset()

        ds = dicomdir
        ds.DirectoryRecordSequence.append(record)


class TestFileSetLoad:
    """Tests for a FileSet creating from an existing File-set."""
    def test_loading(self, dicomdir):
        """Test loading an existing File-set."""
        fs = FileSet(dicomdir)
        assert dicomdir == fs._dicomdir
        assert "PYDICOM_TEST" == fs.ID
        assert "1.2.276.0.7230010.3.1.4.0.31906.1359940846.78187" == fs.UID
        assert "dicomdirtests" in fs.path
        assert 31 == len(fs)

    def test_change_file_set_id(self, dicomdir):
        """Test changing the File-set ID."""
        fs = FileSet(dicomdir)
        fs.ID = "MYFILESET"
        assert "MYFILESET" == fs.ID
        assert "MYFILESET" == dicomdir.FileSetID

    def test_change_file_set_uid(self, dicomdir):
        """Test changing the File-set ID."""
        original = dicomdir.file_meta.MediaStorageSOPInstanceUID
        fs = FileSet(dicomdir)
        assert original == fs.UID
        new = "1.2.3.4"
        fs.UID = new
        assert new == fs.UID
        assert new == dicomdir.file_meta.MediaStorageSOPInstanceUID

    def test_tree(self, dicomdir):
        """Test the tree."""
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
        instance = images['1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.11']
        assert isinstance(instance, FileInstance)

    def test_iter(self, dicomdir):
        """Test iter(FileSet)."""
        fs = FileSet(dicomdir)
        for instance in fs:
            assert isinstance(instance, FileInstance)

        assert 7 == len([ii for ii in fs if ii.PatientID == '77654033'])
        assert 24 == len([ii for ii in fs if ii.PatientID == '98890234'])

    def test_load(self, dicomdir):
        """Test loading the referenced SOP Instance dataset."""
        fs = FileSet(dicomdir)
        study_uid = '1.3.6.1.4.1.5962.1.1.0.0.0.1196530851.28319.0.1'
        series_uid = '1.3.6.1.4.1.5962.1.1.0.0.0.1196530851.28319.0.2'
        matches = fs.find(SeriesInstanceUID=series_uid)
        assert 4 == len(matches)
        for instance in matches:
            ds = instance.load()
            assert '77654033' == ds.PatientID
            assert study_uid == ds.StudyInstanceUID
            assert series_uid == ds.SeriesInstanceUID
            assert "Doe^Archibald" == ds.PatientName

        matches = fs.find(StudyDescription="XR C Spine Comp Min 4 Views")
        assert 3 == len(matches)

    def test_instances(self, dicomdir):
        """That that File-set instances are correct."""
        pass


class TestFileSetNew:
    """Tests for a File-set created from scratch."""
    def test_new_no_records(self):
        """Test new with no records."""
        fs = FileSet()

        # Test DICOMDIR
        ds = fs._dicomdir
        assert isinstance(ds, Dataset)
        assert ds.FileSetID is None
        assert 'DICOMDIR' == ds.filename
        # Test DICOMDIR file meta
        meta = ds.file_meta
        assert MediaStorageDirectoryStorage == meta.MediaStorageSOPClassUID
        assert meta.MediaStorageSOPInstanceUID.is_valid
        assert ExplicitVRLittleEndian == meta.TransferSyntaxUID

        # Test FileSet
        # TODO: make sure this path is correct (based on cwd?)
        #assert 'pydicom/tests' in fs.path
        assert 'DICOMDIR' not in fs.path
        assert fs.ID is None
        assert fs.UID.is_valid
        assert 0 == len(fs)

        with pytest.raises(StopIteration):
            next(iter(fs))

    def test_file_set_uid(self):
        """Test that the File-set UID is created and constant."""
        fs = FileSet()
        uid = fs.UID
        assert uid.is_valid
        uid2 = fs.UID
        assert uid == uid2

        fs.UID = '1.2.3.4'
        assert '1.2.3.4' == fs.UID
