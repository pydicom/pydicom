# errors.py
"""Module for pydicom exception classes"""
#
# Copyright (c) 2013 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com
#


class InvalidDicomError(Exception):
    """Exception that is raised when the the file does not seem
    to be a valid dicom file, usually when the four characters
    "DICM" are not present at position 128 in the file.
    (According to the dicom specification, each dicom file should
    have this.)

    To force reading the file (because maybe it is a dicom file without
    a header), use read_file(..., force=True).
    """
    def __init__(self, *args):
        if not args:
            args = ('The specified file is not a valid DICOM file.',)
        Exception.__init__(self, *args)
