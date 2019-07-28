# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Module for DicomDir class"""

from pydicom.errors import InvalidDicomError
from pydicom.dataset import FileDataset


class DicomDir(FileDataset):
    """Hold a DICOMDIR dataset read from file.

    Derived from FileDataset, but additional
    methods are available,
    specific to the Directory structure
    """

    def __init__(self, filename_or_obj, dataset, preamble=None, file_meta=None,
                 is_implicit_VR=True, is_little_endian=True):
        """Initialize a DICOMDIR dataset read from a DICOM file.

        Carries forward all the initialization from FileDataset class

        Parameters
        ----------
        filename_or_obj : str or None
            Full path and filename to the file of None if io.BytesIO.\
        dataset : dataset.Dataset
            Some form of dictionary, usually a Dataset from read_dataset().
        preamble : bytes
            The 128-byte DICOM preamble.
        file_meta : dataset.Dataset
            The file meta info dataset, as returned by _read_file_meta,
            or an empty dataset if no file meta information is in the file.
        is_implicit_VR : bool
            True if implicit VR transfer syntax used; False if explicit VR.
            Default is True.
        is_little_endian : bool
            True if little-endian transfer syntax used; False if big-endian.
            Default is True.
        """
        # Usually this class is created through filereader.read_partial,
        # and it checks class SOP, but in case of direct creation,
        # check here also
        if file_meta:
            class_uid = file_meta.MediaStorageSOPClassUID
            if not class_uid.name == "Media Storage Directory Storage":
                msg = "SOP Class is not Media Storage Directory (DICOMDIR)"
                raise InvalidDicomError(msg)
        FileDataset.__init__(
            self,
            filename_or_obj,
            dataset,
            preamble,
            file_meta,
            is_implicit_VR=is_implicit_VR,
            is_little_endian=is_little_endian)
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
            while current_record.OffsetOfTheNextDirectoryRecord:
                offset_of_next = current_record.OffsetOfTheNextDirectoryRecord
                sibling = map_offset_to_record[offset_of_next]
                sibling_list.append(sibling)
                current_record = sibling
            return sibling_list

        # Build the mapping from file offsets to records
        records = self.DirectoryRecordSequence
        map_offset_to_record = {}
        for record in records:
            offset = record.seq_item_tell
            map_offset_to_record[offset] = record
        # logging.debug("Record offsets: " + map_offset_to_record.keys())

        # Find the children of each record
        for record in records:
            child_offset = record.OffsetOfReferencedLowerLevelDirectoryEntity
            if child_offset:
                child = map_offset_to_record[child_offset]
                record.children = get_siblings(child, map_offset_to_record)
            else:
                record.children = []

        # Find the top-level records : siblings of the first record
        self.patient_records = get_siblings(records[0], map_offset_to_record)
