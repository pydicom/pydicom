# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""DICOM File Set and DICOMDIR handling."""

from collections import defaultdict
import os
from pathlib import Path
from typing import Optional, Union, List, Generator
import uuid
import warnings

from pydicom import config
from pydicom.dataset import FileDataset, Dataset
from pydicom.errors import InvalidDicomError
from pydicom._storage_sopclass_uids import MediaStorageDirectoryStorage
from pydicom.uid import generate_uid, UID


class DicomDir(FileDataset):
    """Hold a DICOMDIR dataset read from file.

    Derived from :class:`~pydicom.dataset.FileDataset`, but additional methods
    are available, specific to the Directory structure.

    :dcm:`Basic Directory IOD<part03/chapter_F.html>`
    """
    def __init__(self,
                 filename_or_obj,
                 dataset,
                 preamble=None,
                 file_meta=None,
                 is_implicit_VR=True,
                 is_little_endian=True):
        """Initialize a DICOMDIR dataset read from a DICOM file.

        Carries forward all the initialization from
        :class:`~pydicom.dataset.FileDataset`

        Parameters
        ----------
        filename_or_obj : str or PathLike or file-like or None
            Full path and filename to the file of ``None`` if
            :class:`io.BytesIO`.
        dataset : dataset.Dataset
            Some form of dictionary, usually a
            :class:`~pydicom.dataset.FileDataset` from
            :func:`~pydicom.filereader.dcmread`.
        preamble : bytes
            The 128-byte DICOM preamble.
        file_meta : dataset.Dataset
            The file meta :class:`~pydicom.dataset.Dataset`, such as
            the one returned by
            :func:`~pydicom.filereader.read_file_meta_info`, or an empty
            :class:`~pydicom.dataset.Dataset` if no file meta information is
            in the file.
        is_implicit_VR : bool
            ``True`` if implicit VR transfer syntax used (default); ``False``
            if explicit VR.
        is_little_endian : bool
            ``True`` if little endian transfer syntax used (default); ``False``
            if big endian.

        Raises
        ------
        InvalidDicomError
            If the file transfer syntax is not Little Endian Explicit and
            :func:`enforce_valid_values<pydicom.config.enforce_valid_values>`
            is ``True``.
        """
        # Usually this class is created through filereader.read_partial,
        # and it checks class SOP, but in case of direct creation,
        # check here also
        if file_meta:
            sop_class = file_meta.MediaStorageSOPClassUID
            if sop_class != MediaStorageDirectoryStorage:
                raise InvalidDicomError(
                    "The 'Media Storage SOP Class UID' for a DICOMDIR dataset "
                    "must be '1.2.840.10008.1.3.10' - Media Storage Directory"
                )

        if is_implicit_VR or not is_little_endian:
            msg = (
                "Invalid transfer syntax for DICOMDIR - Explicit Little "
                "Endian expected."
            )
            if config.enforce_valid_values:
                raise InvalidDicomError(msg)
            warnings.warn(msg, UserWarning)

        FileDataset.__init__(
            self,
            filename_or_obj,
            dataset,
            preamble,
            file_meta,
            is_implicit_VR=is_implicit_VR,
            is_little_endian=is_little_endian
        )

        self.patient_records = []
        self.parse_records()

    def parse_records(self):
        """Build the hierarchy of given directory records, and structure
        into Patient, Studies, Series, Images hierarchy.

        This is intended for initial read of file only,
        it will not reorganize correctly if records are changed.
        """

        # Define a helper function for organizing the records
        def get_siblings(record, map_offset_to_record):
            """Return a list of all siblings of the given directory record,
            including itself.
            """
            sibling_list = [record]
            current_record = record
            while (
                'OffsetOfTheNextDirectoryRecord' in current_record
                and current_record.OffsetOfTheNextDirectoryRecord
            ):
                offset_of_next = current_record.OffsetOfTheNextDirectoryRecord
                sibling = map_offset_to_record[offset_of_next]
                sibling_list.append(sibling)
                current_record = sibling
            return sibling_list

        # Build the mapping from file offsets to records
        records = self.DirectoryRecordSequence
        if not records:
            return

        map_offset_to_record = {}
        for record in records:
            map_offset_to_record[record.seq_item_tell] = record
        # logging.debug("File offsets: " + map_offset_to_record.keys())

        # Find the children of each record
        for record in records:
            record.children = []
            if 'OffsetOfReferencedLowerLevelDirectoryEntity' in record:
                child_offset = (record.
                                OffsetOfReferencedLowerLevelDirectoryEntity)
                if child_offset:
                    child = map_offset_to_record[child_offset]
                    record.children = get_siblings(child, map_offset_to_record)

        self.patient_records = [
            record for record in records
            if getattr(record, 'DirectoryRecordType') == 'PATIENT'
        ]


# TODO: Class name change to Record? Move access into DicomDir?
# TODO: FileSet -> DicomDir -> Record?
class File:
    """Representation of a Directory Record in a File-set."""
    def __init__(self, ds: Dataset, record: Dataset, offset: Optional[int] = None) -> None:
        """Create a new File-set File.

        Parameters
        ----------
        ds : pydicom.dicomdir.DicomDir
            The DICOMDIR dataset.
        record : pydicom.dataset.Dataset
            The DICOMDIR record for the File.
        """
        self._root = ds
        self.record = record
        self.offset = offset
        self.parent = None
        self.next = None
        self.previous = None
        self.children = []

    @property
    def FileID(self) -> Union[List[str], str]:
        """Return the File ID of the record if it references an instance.

        Returns
        -------
        pathlib.Path
            The relative path to the instance.
        """
        # Maximum 8 components
        return Path(*self.record.ReferencedFileID)

    @property
    def filepath(self) -> str:
        """Return the path to the File corresponding to the record."""
        fpath = Path(self._root.filename).resolve().parent / self.FileID
        return os.fspath(fpath)

    @property
    def instance(self):
        """Return the SOP Instance referenced by the record as a
        :class:`~pydicomd.dataset.Dataset`.
        """
        from pydicom.filereader import dcmread

        return dcmread(self.filepath)

    @property
    def is_instance(self):
        """Return ``True`` if the record references a SOP Instance."""
        return "ReferencedFileID" in self.record

    @property
    def key(self) -> str:
        """Return a unique key for the record as :class:`str`."""
        if self.record_type == "PATIENT":
            # PS3.3, Annex F.5.1: Each Patient ID is unique within a File-set
            return self.record.PatientID
        elif self.record_type == "STUDY" and "StudyInstanceUID" in self.record:
            # PS3.3, Annex F.5.2: Type 1C
            return self.record.StudyInstanceUID
        elif self.record_type == "SERIES":
            return self.record.SeriesInstanceUID
        elif self.record_type == "PRIVATE":
            return self.record.PrivateRecordUID

        # PS3.3, Table F.3-3: Required if record references an instance
        return getattr(
            self.record, "ReferencedSOPInstanceUIDInFile", str(uuid.uuid4())
        )

    @property
    def offset(self) -> int:
        """Return the offset of the record in the DICOMDIR instance."""
        return self._offset

    @offset.setter
    def offset(self, val: int) -> None:
        """Set the offset of the record in the DICOMDIR instance."""
        self._offset = val

    @property
    def record_type(self) -> str:
        return self.record.DirectoryRecordType

    def __str__(self) -> str:
        return f"{self.offset, self.record_type}"


class FileSet:
    """Representation of a DICOM :dcm:`File-set<part10/chapter_8.html>`."""
    def __init__(self, ds: Optional[Dataset] = None) -> None:
        """Create a new File-set.

        Parameters
        ----------
        ds : pydicom.dataset.Dataset, optional
            If loading an existing File-set, this is its DICOMDIR dataset.
        """
        self._root = ds
        self._tree = {}

        if ds:
            # Create the record tree
            self._records = self._parse()
            self._file_set_uid = ds.file_meta.MediaStorageSOPInstanceUID
        else:
            self._records = None
            self._file_set_uid = generate_uid()

    def _create_dicomdir(self) -> Dataset:
        """Return a new DICOMDIR dataset."""
        ds = Dataset()
        ds.filename = ''
        # Type 2, VR CS, VM 1
        ds.FileSetID = None

        # TODO: Add record information

        return ds

    @property
    def DICOMDIR(self) -> Dataset:
        """Return the DICOMDIR :class:`~pydicom.dataset.Dataset`."""
        if not self._root:
            self._root = self._create_dicomdir()

        return self._root

    @property
    def FileSetID(self) -> Union[str, None]:
        """Return the File-set ID (if available) or ``None``."""
        if self.DICOMDIR:
            # Type 2, CS
            return self.DICOMDIR.FileSetID

    @FileSetID.setter
    def FileSetID(self, val: Union[str, None]) -> None:
        """Set the File-set ID."""
        if val is None or 0 <= len(val) <= 16:
            self.DICOMDIR.FileSetID = val

    @property
    def FileSetUID(self) -> str:
        """Return the File-set UID."""
        return self._file_set_uid

    @FileSetUID.setter
    def FileSetUID(self, uid: UID) -> None:
        """Set the File-set UID.

        Parameters
        ----------
        uid : pydicom.uid.UID
            The UID to use as the new File-set UID.
        """
        self._file_set_uid = uid

    def __iter__(self) -> Generator[File, None, None]:
        """Yield all Files in the File-set."""
        yield from self.iter_files()

    def iter_patient(self, patient_id: str) -> Generator[File, None, None]:
        """Yield all the Files in the File-set for a patient.

        Parameters
        ----------
        patient_id : str
            The *Patient ID* of the patient.

        Yields
        ------
        pydicom.dicomdir.File
            A record belonging to the patient.
        """
        yield from self.iter_files(patient_id)

    def iter_study(self, patient_id: str, study_uid: str) -> Generator[File, None, None]:
        """Yield all the Files in the File-set for a study.

        Parameters
        ----------
        patient_id : str
            The *Patient ID* of the patient the study belongs to.
        study_uid : str
            The *Study Instance UID* of the study.

        Yields
        ------
        pydicom.dicomdir.File
            A record belonging to the study.
        """
        yield from self.iter_files(patient_id, study_uid)

    def iter_series(self, patient_id: str, study_uid: str, series_uid: str) -> Generator[File, None, None]:
        """Yield all the Files in the File-set for a series.

        Parameters
        ----------
        patient_id : str
            The *Patient ID* of the patient the study belongs to.
        study_uid : str
            The *Study Instance UID* of the study the series belongs to.
        series_uid : str
            The *Series Instance UID* of the series.

        Yields
        ------
        pydicom.dicomdir.File
            A record belonging to the series.
        """
        yield from self.iter_files(patient_id, study_uid, series_uid)

    def iter_files(self, *args: List[str]) -> Generator[File, None, None]:
        """Yield Files from the File-set.

        Parameters
        ----------
        args : list of str
            A list of File keys.

        Yields
        ------
        pydicom.dicomdir.File
            A File belonging to the File-set.
        """
        def recurse(d):
            for kk, vv in d.items():
                if isinstance(vv, dict):
                    yield from recurse(vv)
                else:
                    yield vv

        tree = self._tree
        for kk in args:
            tree = tree[kk]

        yield from recurse(tree)

    def __len__(self):
        """Return the number of Files in the File-set."""
        ii = 0
        for r in self:
            ii += 1

        return ii

    def _parse(self) -> None:
        """Parse the records in the DICOMDIR."""
        next_keyword = "OffsetOfTheNextDirectoryRecord"
        child_keyword = "OffsetOfReferencedLowerLevelDirectoryEntity"

        def get_siblings(record, parent):
            siblings = [record]
            next_offset = getattr(record.record, next_keyword, None)
            while next_offset:
                siblings.append(records[next_offset])
                record = records[next_offset]
                record.parent = parent
                next_offset = getattr(record.record, next_keyword, None)

            return siblings

        # First pass: get the offsets
        records = {}
        for record in self.DICOMDIR.DirectoryRecordSequence:
            offset = record.seq_item_tell
            records[offset] = File(self.DICOMDIR, record, offset)

        # Second pass: establish their inter-relationship
        for offset, record in records.items():
            next_offset = getattr(record.record, next_keyword, None)
            if next_offset:
                record.next = records[next_offset]
                records[next_offset].previous = record

            child_offset = getattr(record.record, child_keyword, None)
            if child_offset:
                record.children = get_siblings(records[child_offset], record)

        self._records = records

        # DICOMDIR may have no records
        if records:
            # Build up relationship tree for efficient traversing
            tree = {}

            def build_branch(record):
                if not record.children:
                    return record

                branch = {}
                for child in record.children:
                    branch[child.key] = build_branch(child)

                return branch

            # First record
            record = records[self.DICOMDIR[0x00041200].value]
            tree[record.key] = build_branch(record)
            while record.next:
                record = record.next
                tree[record.key] = build_branch(record)

            self._tree = tree

    @property
    def root(self) -> str:
        """Return the path to the File-set root directory as :class:`str`."""
        return os.fspath(Path(self.DICOMDIR.filename).resolve().parent)

    def __str__(self) -> str:
        def prettify(d, indent=0, indent_char='  '):
            s = []
            for kk, vv in d.items():
                s.append(indent_char * indent + str(kk))
                if isinstance(vv, dict):
                    s.extend(prettify(vv, indent + 1))

            return s

        s = [
            "DICOM File-set",
            f"  File-set ID: {self.FileSetID or '(no value available)'}",
            f"  File-set UID: {self.FileSetUID}",
            f"  Root directory: {self.root}",
        ]

        if self._tree:
            s.append("")
            s.extend(prettify(self._tree))

        return '\n'.join(s)
