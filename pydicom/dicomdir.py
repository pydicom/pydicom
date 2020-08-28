# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""DICOM File-set handling."""

from copy import deepcopy
import os
from pathlib import Path
from typing import Optional, Union, List, Generator, Any, Tuple
import uuid
import warnings

from pydicom import config
from pydicom.datadict import tag_for_keyword, dictionary_VR
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

            # Backwards compatibility only
            record.record.children = [ii.record for ii in record.children]

        self.root = []
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
        record : pydicom.dataset.Dataset
            The directory record dataset from the DICOMDIR's Media Storage
            Directory instance.
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
        """Return a string representation of the directory record."""
        ds = self.record

        s = []
        s.append(f"{self.record_type}")
        if self.record_type == "PATIENT":
            s.append(
                f": PatientID={ds.PatientID}, PatientName={ds.PatientName}"
            )
        elif self.record_type == "STUDY":
            s.append(f": StudyDate={ds.StudyDate}, StudyTime={ds.StudyTime}")
            if getattr(ds, "StudyDescription", None):
                s.append(f", StudyDescription={ds.StudyDescription}")
        elif self.record_type == "SERIES":
            s.append(
                f": Modality={ds.Modality}, SeriesNumber={ds.SeriesNumber}"
            )
        elif self.record_type == "IMAGE":
            s.append(f": SOPInstanceUID={self.key}")
        else:
            s.append(f": {self.key}")

        return ''.join(s)


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

    def add_record(self, record: DirectoryRecord) -> None:
        """Add a directory record to the FileInstance.

        Parameters
        ----------
        record : pydicom.dicomdir.DirectoryRecord
            The record to add.
        """
        # PRIVATE records are not unique in traversal
        if record.record_type == "PRIVATE":
            key = record.key
        else:
            key = record.record_type

        self._records[key] = record

    def __contains__(self, name: Union[str, int]) -> bool:
        """Return ``True`` if the DataElement with keyword or tag `name` is
        in one of the corresponding directory records.

        Parameters
        ----------
        name : str or int
            The element keyword or tag to search for.

        Returns
        -------
        bool
            ``True`` if the corresponding element is present, ``False``
            otherwise.
        """
        try:
            self[name]
        except KeyError:
            return False

        return True

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

    def load(self) -> Dataset:
        """Return the referenced instance as a
        :class:`~pydicom.dataset.Dataset`.
        """
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
        if self["ReferencedFileID"].VM > 1:
            path = Path(*self.ReferencedFileID)
        else:
            path = Path(self.ReferencedFileID)

        return os.fspath(Path(self.file_set.path) / path)

    @property
    def SOPClassUID(self) -> UID:
        """Return the *SOP Class UID* of the referenced instance."""
        return self.ReferencedSOPClassUIDInFile

    @property
    def SOPInstanceUID(self) -> UID:
        """Return the *SOP Instance UID* of the referenced instance."""
        return self.ReferencedSOPInstanceUIDInFile

    @property
    def TransferSyntaxUID(self) -> UID:
        """Return the *Transfer Syntax UID* of the referenced instance."""
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
            if "DirectoryRecordSequence" not in ds:
                raise ValueError(
                    "The supplied Dataset is not a DICOMDIR instance"
                )
            self._parse_tree()

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

    def find(self, load: bool = False, **kwargs) -> List[FileInstance]:
        """Return matching instances in the File-set

        **Limitations**

        * Only single value matching is supported so neither
          ``PatientID=['1234567', '7654321']`` or ``PatientID='1234567',
          PatientID='7654321'`` will work (although the first example will
          work if the *Patient ID* is actually multi-valued).
        * Repeating group and private elements cannot be used when searching.

        Parameters
        ----------
        load : bool, optional
            If ``True``, then load the SOP Instances belonging to the
            File-set and perform the search against their available elements.
            Otherwise (default) search only the elements available in the
            corresponding directory records (more efficient, but only a limited
            number of elements are available).
        **kwargs
            Search parameters, as element keyword=value (i.e.
            ``PatientID='1234567', StudyDescription="My study"``.

        Returns
        -------
        list of pydicom.dicomdir.FileInstance
            A list of matching instances.
        """
        has_elements = False

        def match(ds, **kwargs):
            if load:
                ds = instance.load()

            # Check that all query elements are present
            if all([kw in ds for kw in kwargs]):
                has_elements = True

            for kw, val in kwargs.items():
                try:
                    assert ds[kw].value == val
                except (AssertionError, KeyError):
                    return False

            return True

        matches = []
        for instance in self:
            if match(instance, **kwargs):
                matches.append(instance)

        if not load and not has_elements:
            warnings.warn(
                "None of the records in the DICOMDIR dataset contain all "
                "the query elements, consider using the 'load' parameter "
                "to expand the search to the corresponding SOP instances"
            )

        return matches

    def find_values(
            self,
            element: Union[str, int],
            instances: Optional[List[FileInstance]] = None,
            load: bool = False
        ) -> List[Any]:
        """Return a list of unique values for a given element.

        Parameters
        ----------
        element : str, int or Tag
            The keyword or tag of the element to search for.
        instances : list of pydicom.dicomdir.FileInstance, optional
            Search within the given instances. If not used then all available
            instances will be searched.
        load : bool, optional
            If ``True``, then load the SOP Instances belonging to the
            File-set and perform the search against their available elements.
            Otherwise (default) search only the elements available in the
            corresponding directory records (more efficient, but only a limited
            number of elements are available).

        Returns
        -------
        list of object
            A list of value(s) for the element available in the instances.
        """
        has_element = False
        results = []
        instances = instances or iter(self)
        for instance in instances:
            if load:
                instance = instance.load()

            if element not in instance:
                continue

            has_element = True
            val = instance[element].value
            # Not very efficient, but we can't use set
            if val not in results:
                results.append(val)

        if not load and not has_element:
            warnings.warn(
                "None of the records in the DICOMDIR dataset contain "
                "the query element, consider using the 'load' parameter "
                "to expand the search to the corresponding SOP instances"
            )

        return results

    @property
    def ID(self) -> Union[str, None]:
        """Return the File-set ID (if available) or ``None``."""
        return self._dicomdir.FileSetID

    @ID.setter
    def ID(self, val: Union[str, None]) -> None:
        """Set the File-set ID."""
        if val is None or 0 <= len(val) <= 16:
            self._dicomdir.FileSetID = val

    def __iter__(self) -> Generator[FileInstance, None, None]:
        """Yield all the SOP Instances in the File-set.

        Yields
        ------
        pydicom.dataset.Dataset
            A SOP Instance from the File-set.
        """
        yield from self._instances

    def __len__(self) -> int:
        """Return the number of SOP Instances in the File-set."""
        return len(self._instances)

    def _parse_tree(self) -> None:
        """Parse the records in the DICOMDIR.

        Build up the File instances in the File-set.
        """
        # Build up relationship tree for efficient traversing
        tree = {}

        def recurse_branch(record):
            """Recurse through a top-level directory record, creating a
            FileInstance for each of the SOP instances that are underneath.
            """
            # If no children we are at the end of the branch
            if not record.children:
                # Build up the FileInstance by traversing back to the root
                instance = FileInstance(self)
                instance.add_record(record)
                parent = record.parent
                while parent:
                    instance.add_record(parent)
                    parent = parent.parent  # Move up one level

                self._instances.append(instance)

                return instance

            # Recurse
            branch = {}
            for child in record.children:
                branch[child] = recurse_branch(child)

            return branch

        # Top-level records
        for record in self._dicomdir.root:
            tree[record] = recurse_branch(record)

        self._tree = tree

    @property
    def path(self) -> str:
        """Return the absolute path to the File-set root directory as
        :class:`str`.
        """
        return os.fspath(Path(self._dicomdir.filename).resolve().parent)

    def as_tree(self, hierarchy: Optional[List[str]] = None) -> dict:
        """Return a dict containing the File-set's SOP Instance hierarchy.

        .. warning::

            SOP Instances described using ``PRIVATE`` records are not
            supported and will not be included in the returned tree.

        Parameters
        ----------
        hierarchy : tuple of str, optional
            Create the tree using the given `hierarchy`, defaults to
            ``["PATIENT", "STUDY", "SERIES"]`` which returns a tree ordered
            as ``{PatientID: {StudyInstanceUID: SeriesInstanceUID:
            [FileInstance, ...]}}``.

        Returns
        -------
        dict
            A dict containing the hierarchy of SOP Instances.
        """
        tree = {}

        def build_branch(d, keys):
            if len(keys) == 1:
                return d.setdefault(keys[0], [])

            branch = d.setdefault(keys[0], {})
            return build_branch(branch, keys[1:])

        hierarchy = hierarchy or ['PATIENT', 'STUDY', 'SERIES']
        req = set(hierarchy)
        for instance in self:
            records = instance._records
            if not req.issubset(set(records)):
                continue

            instances_list = build_branch(
                tree,
                [records[rtype].key for rtype in hierarchy]
            )
            instances_list.append(instance)

        return tree

    def __str__(self) -> str:
        """Return a string representation of the FileSet."""
        def prettify(d, indent=0, indent_char='  '):
            """Return the record tree as a list of pretty strings

            Parameters
            ----------
            d : dict
                The record tree.
            indent : int, optional
                The current indent level, default ``0``.
            indent_char : str, optional
                The character(s) to use when indenting, default ``'  '``.

            Returns
            -------
            list of str
            """
            s = []
            for kk, vv in d.items():
                s.append(f"{indent_char * indent}{str(kk)}")
                if isinstance(vv, dict):
                    s.extend(prettify(vv, indent + 1))

            return s

        s = [
            "DICOM File-set",
            f"  Root directory: {self.path}",
            f"  File-set ID: {self.ID or '(no value available)'}",
            f"  File-set UID: {self.UID}",
        ]

        if self._tree:
            s.append("  Managed Instances:")
            s.extend(prettify(self._tree, indent=2))

        return '\n'.join(s)

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
