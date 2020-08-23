# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""DICOM File-set handling."""

import os
from pathlib import Path
from typing import Optional, Union, List, Generator, Any
import uuid
import warnings

from pydicom import config
from pydicom.datadict import tag_for_keyword
from pydicom.dataelem import DataElement
from pydicom.dataset import FileDataset, Dataset, FileMetaDataset
from pydicom.errors import InvalidDicomError
from pydicom._storage_sopclass_uids import MediaStorageDirectoryStorage
from pydicom.tag import Tag, BaseTag
from pydicom.uid import generate_uid, UID, ExplicitVRLittleEndian


class DicomDir(FileDataset):
    """Hold a DICOMDIR dataset read from file.

    Derived from :class:`~pydicom.dataset.FileDataset`, but additional methods
    are available, specific to the Directory structure.

    :dcm:`Basic Directory IOD<part03/chapter_F.html>`

    Attributes
    ----------
    root : list of pydicom.dicomdir.DirectoryRecord
        A list of the top-level directory records in the DICOMDIR's *Directory
        Record Sequence*.
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

        self.root = []
        # {offset, DirectoryRecord}
        self._records = {}
        self._parse_records()

    def _parse_records(self) -> None:
        """Parse the directory records in the DICOMDIR and build the
        relationship between them.
        """
        next_keyword = "OffsetOfTheNextDirectoryRecord"
        child_keyword = "OffsetOfReferencedLowerLevelDirectoryEntity"

        def get_siblings(record, parent):
            record.parent = parent
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
        for record in self.DirectoryRecordSequence:
            offset = record.seq_item_tell
            record = DirectoryRecord(self, record, offset)
            records[offset] = record

        # Second pass: establish their inter-relationship
        for offset, record in records.items():
            next_offset = getattr(record.record, next_keyword, None)
            if next_offset:
                record.next = records[next_offset]
                records[next_offset].previous = record

            child_offset = getattr(record.record, child_keyword, None)
            if child_offset:
                record.children = get_siblings(records[child_offset], record)

        if records:
            # Add the top-level records to the tree root
            offset = "OffsetOfTheFirstDirectoryRecordOfTheRootDirectoryEntity"
            record = records[self[offset].value]
            self.root.append(record)
            while record.next:
                record = record.next
                self.root.append(record)

        self._records = records

    @property
    def patient_records(self) -> List[Dataset]:
        """Return a list of PATIENT directory records.

        Returns
        -------
        list of pydicom.dataset.Dataset
            The ``PATIENT`` type records in the *Directory Record Sequence*.
        """
        return [ii.record for ii in self.root if ii.record_type == "PATIENT"]


class DirectoryRecord:
    """Representation of a Directory Record in a DICOMDIR file."""
    def __init__(self,
                 ds: Dataset,
                 record: Dataset,
                 offset: Optional[int] = None) -> None:
        """Create a new directory record.

        Parameters
        ----------
        ds : pydicom.dicomdir.DicomDir
            The DICOMDIR dataset.
        record : pydicom.dataset.Dataset
            The DICOMDIR record.
        offset : int, optional
            The byte offset to the record in the DICOMDIR file.

        Attributes
        ----------
        children : list of pydicom.dicomdir.DirectoryRecord
            The child records for the current record.
        next : pydicom.dicomdir.DirectoryRecord or None
            The next record at the current level of the directory, or ``None``
            if there is no next record.
        parent : pydicom.dicomdir.DirectoryRecord or None
            The parent record, or ``None`` for top-level records.
        previous : pydicom.dicomdir.DirectoryRecord or None
            The previous record at the current level of the directory, or
            ``None`` if there is no previous record.
        """
        self._dicomdir = ds
        self.record = record
        self._offset = offset

        self.parent = None
        self.next = None
        self.previous = None
        self.children = []

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
    def record_type(self) -> str:
        """Return the record's *Directory Record Type* as :class:`str`."""
        return self.record.DirectoryRecordType

    def __str__(self) -> str:
        return f"{self.record_type} ({self._offset}) - {self.key}"


class FileInstance:
    """Representation of a File in a File-set."""
    def __init__(self, fs: "FileSet") -> None:
        """Create a new FileInstance.

        Parameters
        ----------
        fs : pydicom.dicomdir.FileSet
            The File-set this File belongs to.
        """
        # The directory records that make up the instance
        # {record type or record key for PRIVATE: record}
        self._records = {}
        self._fs = fs

    @property
    def file_set(self) -> "FileSet":
        """Return the File-set the File is part of."""
        return self._fs

    def __getattribute__(self, name: str) -> Any:
        """Return the class attribute value for `name`.

        Parameters
        ----------
        name : str
            An element keyword or a class attribute name.

        Returns
        -------
        object
            If `name` matches a DICOM keyword and the element is
            present in one of the directory records then returns the
            corresponding element's value. Otherwise returns the class
            attribute's value (if present).
        """
        tag = tag_for_keyword(name)
        if tag is not None:
            tag = Tag(tag)
            for record in self._records.values():
                if tag in record.record:
                    return record.record[tag].value

        return super().__getattribute__(name)

    def __getitem__(self, key: Union[str, int]) -> DataElement:
        """Return the DataElement with keyword or tag `key`.

        Parameters
        ----------
        key : str or int
            An element keyword or tag.

        Returns
        -------
        pydicom.dataelem.DataElement
            The DataElement corresponding to `key`, if present in one of the
            directory records.
        """
        if isinstance(key, BaseTag):
            tag = key
        else:
            tag = Tag(key)

        for record in self._records.values():
            if tag in record.record:
                return record.record[tag]

        raise KeyError(tag)

    def load(self):
        from pydicom.filereader import dcmread

        return dcmread(self.path)

    @property
    def path(self) -> str:
        """Return the path to the SOP Instance referenced by the record.

        Raises
        ------
        AttributeError
            If the record doesn't reference a SOP Instance.
        """
        return os.fspath(
            Path(self.file_set.path) / Path(*self.ReferencedFileID)
        )

    @property
    def SOPClassUID(self):
        return self.ReferencedSOPClassUIDInFile

    @property
    def SOPInstanceUID(self):
        return self.ReferencedSOPInstanceUIDInFile

    @property
    def TransferSyntaxUID(self):
        return self.ReferencedTransferSyntaxUIDInFile


class FileSet:
    """Representation of a DICOM :dcm:`File-set<part10/chapter_8.html>`."""
    def __init__(self, ds: Optional[Dataset] = None) -> None:
        """Create a new File-set.

        Parameters
        ----------
        ds : pydicom.dataset.Dataset, optional
            If loading an existing File-set, this is its DICOMDIR dataset.
        """
        # The relationship between instances
        self._tree = {}
        # The instances belonging to the File-set
        self._instances = []
        self._dicomdir = ds or self._create_dicomdir()

        if ds:
            self._parse()

    def _create_dicomdir(self) -> Dataset:
        """Return a new DICOMDIR dataset."""
        ds = Dataset()
        # TODO: Placeholder, will be updated on writing/updating
        ds.filename = 'DICOMDIR'

        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
        ds.file_meta.MediaStorageSOPClassUID = MediaStorageDirectoryStorage

        # Type 2, VR CS, VM 1
        ds.FileSetID = None

        return ds

    @property
    def ID(self) -> Union[str, None]:
        """Return the File-set ID (if available) or ``None``."""
        return self._dicomdir.FileSetID

    @ID.setter
    def ID(self, val: Union[str, None]) -> None:
        """Set the File-set ID."""
        if val is None or 0 <= len(val) <= 16:
            self._dicomdir.FileSetID = val

    @property
    def UID(self) -> UID:
        """Return the File-set UID."""
        return self._dicomdir.file_meta.MediaStorageSOPInstanceUID

    @UID.setter
    def UID(self, uid: UID) -> None:
        """Set the File-set UID.

        Parameters
        ----------
        uid : pydicom.uid.UID
            The UID to use as the new File-set UID.
        """
        self._dicomdir.file_meta.MediaStorageSOPInstanceUID = uid

    def __iter__(self) -> Generator[FileInstance, None, None]:
        """Yield all the SOP Instances in the File-set.

        Yields
        ------
        pydicom.dataset.Dataset
            A SOP Instance from the File-set.
        """
        yield from self._instances

    def find(self, **kwargs) -> List[FileInstance]:
        """Return matching instances in the File-set

        Parameters
        ----------
        kwargs

        Returns
        -------
        list of pydicom.dicomdir.FileInstance
            A list of matching instances.
        """
        def match(instance, **kwargs):
            for kw, val in kwargs.items():
                try:
                    assert instance[kw].value == val
                except (AssertionError, AttributeError):
                    return False

            return True

        matches = []
        for instance in self:
            if match(instance, **kwargs):
                matches.append(instance)

        return matches

    def __len__(self) -> int:
        """Return the number of SOP Instances in the File-set."""
        return len(self._instances)

    def _parse(self) -> None:
        """Parse the records in the DICOMDIR.

        Build up the File instances in the File-set.
        """
        # Build up relationship tree for efficient traversing
        tree = {}

        def build_branch(record):
            """Recurse through a record, creating a FileInstance."""
            if not record.children:
                # If no children we are at the end of the branch
                instance = FileInstance(self)
                # PRIVATE records are not unique in traversal
                if record.record_type == "PRIVATE":
                    key = record.key
                else:
                    key = record.record_type
                instance._records[key] = record
                parent = record.parent
                while parent:
                    if parent.record_type == "PRIVATE":
                        key = parent.key
                    else:
                        key = parent.record_type
                    instance._records[key] = parent
                    parent = parent.parent  # Move up one level

                self._instances.append(instance)

                return instance

            branch = {}
            for child in record.children:
                branch[child.key] = build_branch(child)

            return branch

        # First record
        for record in self._dicomdir.root:
            tree[record.key] = build_branch(record)

        self._tree = tree

    @property
    def path(self) -> str:
        """Return the absolute path to the File-set root directory as
        :class:`str`.
        """
        return os.fspath(Path(self._dicomdir.filename).resolve().parent)

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
            f"  Root directory: {self.path}",
        ]

        if self._tree:
            s.append("")
            s.extend(prettify(self._tree))

        return '\n'.join(s)
