# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Module for DicomDir class."""
import warnings

from pydicom import config
from pydicom.errors import InvalidDicomError
from pydicom.dataset import FileDataset


class DicomDir(FileDataset):
    """Hold a DICOMDIR dataset read from file.

    Derived from :class:`~pydicom.dataset.FileDataset`, but additional methods
    are available, specific to the Directory structure
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
            class_uid = file_meta.MediaStorageSOPClassUID
            if not class_uid.name == "Media Storage Directory Storage":
                msg = "SOP Class is not Media Storage Directory (DICOMDIR)"
                raise InvalidDicomError(msg)
        if is_implicit_VR or not is_little_endian:
            msg = ('Invalid transfer syntax for DICOMDIR - '
                   'Explicit Little Endian expected.')
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
            while ('OffsetOfTheNextDirectoryRecord' in current_record and
                   current_record.OffsetOfTheNextDirectoryRecord):
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
            offset = record.seq_item_tell
            map_offset_to_record[offset] = record
        # logging.debug("Record offsets: " + map_offset_to_record.keys())

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
