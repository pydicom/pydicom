# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Test for dicomdir.py"""

from io import BytesIO
import os
from pathlib import Path

import pytest

from pydicom import config, dcmread
from pydicom.data import get_testdata_file
from pydicom.dataset import Dataset
from pydicom.dicomdir import DicomDir, FileSet, FileInstance
from pydicom.errors import InvalidDicomError
from pydicom.filebase import DicomBytesIO
from pydicom.filewriter import write_dataset
from pydicom._storage_sopclass_uids import MediaStorageDirectoryStorage
from pydicom.tag import Tag
from pydicom.uid import UID, ExplicitVRLittleEndian, generate_uid

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

    def test_record_keys(self, dicomdir):
        """Test the keys for the directory records."""
        ds = dicomdir
        records = ds._records
        patient = records[396]
        assert patient.key == "77654033"
        study = records[510]
        assert study.key == "1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.1"
        series = records[724]
        assert series.key == "1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.10"
        image = records[1090]
        assert image.key == "1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.6"


@pytest.fixture
def dicomdir():
    """Return a DICOMDIR dataset."""
    return dcmread(TEST_FILE)


@pytest.fixture
def private(dicomdir):
    """Return a DICOMDIR dataset with PRIVATE records."""
    def private_record():
        record = Dataset()
        record.OffsetOfReferencedLowerLevelDirectoryEntity = 0
        record.RecordInUseFlag = 65535
        record.OffsetOfTheNextDirectoryRecord = 0
        record.DirectoryRecordType = "PRIVATE"
        record.PrivateRecordUID = generate_uid()

        return record

    ds = dicomdir

    top = private_record()
    middle = private_record()
    bottom = private_record()
    bottom.ReferencedSOPClassUIDInFile = "1.2.3.4"
    bottom.ReferencedFileID = "DICOMDIR-nopatient"
    bottom.ReferencedSOPInstanceUIDInFile = (
        "1.2.276.0.7230010.3.1.4.0.31906.1359940846.78187"
    )
    bottom.ReferencedTransferSyntaxUIDInFile = ExplicitVRLittleEndian

    len_top = len(write_record(top))  # 112
    len_middle = len(write_record(middle))  # 112
    len_bottom = len(write_record(bottom))  # 238
    len_last = len(write_record(ds.DirectoryRecordSequence[-1]))  # 248

    # Top PRIVATE
    # Offset to the top PRIVATE - 10860 + 248 + 8
    offset = ds.DirectoryRecordSequence[-1].seq_item_tell + len_last + 8

    # Change the last top-level record to point at the top PRIVATE
    # Original is 3126
    last = ds.OffsetOfTheLastDirectoryRecordOfTheRootDirectoryEntity
    record = ds._records[last]
    record.record.OffsetOfTheNextDirectoryRecord = offset

    # Change the last record offset
    ds.OffsetOfTheLastDirectoryRecordOfTheRootDirectoryEntity = offset
    top.seq_item_tell = offset

    # Offset to the middle PRIVATE
    offset += len_top + 8
    top.OffsetOfReferencedLowerLevelDirectoryEntity = offset
    ds.DirectoryRecordSequence.append(top)
    middle.seq_item_tell = offset

    # Middle PRIVATE
    # Offset to the bottom PRIVATE
    offset += len_middle + 8
    middle.OffsetOfReferencedLowerLevelDirectoryEntity = offset
    ds.DirectoryRecordSequence.append(middle)

    # Bottom PRIVATE
    ds.DirectoryRecordSequence.append(bottom)
    bottom.seq_item_tell = offset

    # Redo the record parsing to reflect changes
    ds._parse_records()

    return ds


def write_record(ds):
    """Return `ds` as explicit little encoded bytes."""
    fp = DicomBytesIO()
    fp.is_implicit_VR = False
    fp.is_little_endian = True
    write_dataset(fp, ds)

    return fp.parent.getvalue()


class TestFileInstance:
    """Tests for FileInstance."""
    def test_properties(self, dicomdir):
        """Test the FileInstance properties."""
        fs = FileSet(dicomdir)
        instance = fs._instances[0]
        assert fs == instance.file_set
        assert os.fspath(Path("77654033/CR1/6154")) in instance.path
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

    def test_contains(self, dicomdir):
        """Test FileInstance.__contains__."""
        fs = FileSet(dicomdir)
        instance = fs._instances[0]
        assert "StudyDate" in instance
        assert 0x00080020 in instance
        assert Tag(0x00080020) in instance
        assert (0x0008, 0x0020) in instance
        assert "0x00080020" in instance

    def test_private(self, private):
        """Test FileInstance with PRIVATE records."""
        ds = private
        fs = FileSet(ds)

        instances = fs._instances
        assert 32 == len(instances)

        instance = instances[-1]
        assert 3 == len(instance._records)
        for record in instance._records.values():
            assert record.record_type == "PRIVATE"

        path = os.fspath(Path("dicomdirtests/DICOMDIR-nopatient"))
        assert path in instances[-1].path

        assert "1.2.3.4" == instance.SOPClassUID
        assert "1.2.276.0.7230010.3.1.4.0.31906.1359940846.78187" == (
            instance.SOPInstanceUID
        )
        assert ExplicitVRLittleEndian == instance.TransferSyntaxUID

    def test_setattr(self, dicomdir):
        """Test FileInstance.__setattr__."""
        fs = FileSet(dicomdir)
        instance = fs._instances[0]
        assert "20010101" == instance.StudyDate

        msg = (
            r"Modifying a FileInstance's corresponding element values "
            r"is not supported"
        )
        with pytest.raises(AttributeError, match=msg):
            instance.StudyDate = '20010102'

        instance.my_attr = 1234
        assert 1234 == instance.my_attr

    def test_setitem(self, dicomdir):
        """Test FileInstance.__getitem__."""
        fs = FileSet(dicomdir)
        instance = fs._instances[0]
        elem = instance["StudyDate"]
        msg = r"'FileInstance' object does not support item assignment"
        with pytest.raises(TypeError, match=msg):
            instance["StudyDate"] = elem


class TestFileSetLoad:
    """Tests for a FileSet created from an existing File-set."""
    def test_loading(self, dicomdir):
        """Test loading an existing File-set."""
        fs = FileSet(dicomdir)
        assert dicomdir == fs._dicomdir
        assert "PYDICOM_TEST" == fs.ID
        assert "1.2.276.0.7230010.3.1.4.0.31906.1359940846.78187" == fs.UID
        assert "dicomdirtests" in fs.path
        assert 31 == len(fs)

    def test_loading_raises(self, dicomdir):
        """Test loading an invalid DICOMDIR raises exceptions."""
        dicomdir.filename = None
        msg = (
            r"Unable to load the File-set as the 'filename' "
            r"attribute for the DICOMDIR dataset is not a string or "
            r"Path object"
        )
        with pytest.raises(TypeError, match=msg):
            FileSet(dicomdir)

        dicomdir.filename = BytesIO()
        with pytest.raises(TypeError, match=msg):
            FileSet(dicomdir)

        dicomdir.filename = Path() / 'my_invalid_path'
        msg = (
            r"Unable to load the File-set as the 'filename' attribute "
            r"for the DICOMDIR dataset is not a valid path"
        )
        with pytest.raises(FileNotFoundError, match=msg):
            FileSet(dicomdir)

        dicomdir.file_meta.MediaStorageSOPClassUID = '1.2.3.4'
        msg = (
            r"Unable to load the File-set as the supplied dataset is "
            r"not a 'Media Storage Directory' instance"
        )
        with pytest.raises(ValueError, match=msg):
            FileSet(dicomdir)

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

    def test_find(self, dicomdir):
        """Tests for FileSet.find()."""
        fs = FileSet(dicomdir)
        assert 31 == len(fs.find())
        assert 7 == len(fs.find(PatientID='77654033'))
        assert 24 == len(fs.find(PatientID='98890234'))

        matches = fs.find(PatientID='98890234', StudyDate="20030505")
        assert 17 == len(matches)
        for ii in matches:
            assert isinstance(ii, FileInstance)

        sop_instances = [ii.SOPInstanceUID for ii in matches]
        assert 17 == len(list(set(sop_instances)))

    def test_find_load(self, private):
        """Test FileSet.find(load=True)."""
        fs = FileSet(private)
        msg = (
            r"None of the records in the DICOMDIR dataset contain all "
            r"the query elements, consider using the 'load' parameter "
            r"to expand the search to the corresponding SOP instances"
        )
        with pytest.warns(UserWarning, match=msg):
            results = fs.find(
                load=False, PhotometricInterpretation="MONOCHROME1"
            )
            assert not results

        results = fs.find(
            load=True, PhotometricInterpretation="MONOCHROME1"
        )
        assert 3 == len(results)

    def test_str(self, private):
        """That FileSet.__str__"""
        fs = FileSet(private)
        s = str(fs)
        assert (
            "      STUDY: StudyDate=20010101, StudyTime=000000, "
            "StudyDescription=XR C Spine Comp Min 4 Views"
        ) in s
        assert "        SERIES: Modality=MR, SeriesNumber=1" in s
        assert (
            "    PATIENT: PatientID=77654033, PatientName=Doe^Archibald" in s
        )
        assert (
            "          IMAGE: SOPInstanceUID="
            "1.3.6.1.4.1.5962.1.1.0.0.0.1194734704.16302.0.12"
        ) in s

    def test_find_values(self, private):
        """Test searching the FileSet for element values."""
        fs = FileSet(private)
        assert ['77654033', '98890234'] == fs.find_values("PatientID")
        assert (
            [
                'XR C Spine Comp Min 4 Views',
                'CT, HEAD/BRAIN WO CONTRAST',
                '',
                'Carotids',
                'Brain',
                'Brain-MRA'
            ] == fs.find_values("StudyDescription")
        )

    def test_find_values_load(self, private):
        """Test FileSet.find_values(load=True)."""
        fs = FileSet(private)
        msg = (
            r"None of the records in the DICOMDIR dataset contain "
            r"the query element, consider using the 'load' parameter "
            r"to expand the search to the corresponding SOP instances"
        )
        with pytest.warns(UserWarning, match=msg):
            results = fs.find_values("PhotometricInterpretation", load=False)
            assert not results

        assert ['MONOCHROME1', 'MONOCHROME2'] == fs.find_values(
            "PhotometricInterpretation", load=True
        )

    def test_as_tree(self, private):
        """Test FileSet.patient_tree."""
        fs = FileSet(private)
        tree = fs.as_tree()

        assert 2 == len(tree)
        assert '77654033' in tree
        assert '98890234' in tree
        studies = tree['77654033']
        assert '1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.1' in studies
        assert 2 == len(studies)
        series = studies['1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.1']
        assert '1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.10' in series
        assert 3 == len(series)
        instances = series['1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.10']
        assert 1 == len(instances)
        assert isinstance(instances[0], FileInstance)

        # Lol
        tree = fs.as_tree(hierarchy=["PATIENT"])
        assert 2 == len(tree)
        instances = tree['77654033']
        assert 7 == len(instances)
        assert isinstance(instances[0], FileInstance)
        instances = tree['98890234']
        assert 24 == len(instances)
        assert isinstance(instances[0], FileInstance)


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
