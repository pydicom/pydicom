# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Module for pydicom exception classes"""


class InvalidDicomError(Exception):
    """Exception that is raised when the the file does not seem
    to be a valid dicom file, usually when the four characters
    "DICM" are not present at position 128 in the file.
    (According to the dicom specification, each dicom file should
    have this.)

    To force reading the file (because maybe it is a dicom file without
    a header), use dcmread(..., force=True).
    """

    def __init__(self, *args):
        if not args:
            args = ('The specified file is not a valid DICOM file.', )
        Exception.__init__(self, *args)
