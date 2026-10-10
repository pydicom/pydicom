# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Module for pydicom exception classes"""

from typing import Any


class InvalidDicomError(Exception):
    """Exception that is raised when the the file does not appear to be DICOM.

    Usually raised when the "DICM" prefix is not present at position 128 in
    the file.

    To force reading the file (because maybe it is a DICOM file without
    a header), use ``dcmread(..., force=True)``.
    """

    def __init__(self, *args: Any) -> None:
        if not args:
            args = ("The specified file is not a valid DICOM file.",)
        Exception.__init__(self, *args)


class BytesLengthException(Exception):
    """Exception that is raised for an unexpected number of bytes."""

    pass


class UnknownVRError(NotImplementedError):
    """Exception that is raised when an element's encoded VR is not recognised.

    .. versionadded:: 3.1

    Subclasses :class:`NotImplementedError`, so code that already catches that
    is unaffected -- including :func:`~pydicom.filereader.read_dataset`, the
    implicit-VR retry inside :func:`~pydicom.filereader.read_file_meta_info`
    and :func:`~pydicom.util.fixer.fix_mismatch`.

    Its purpose is to let :func:`~pydicom.filereader.dcmread` translate *this*
    failure to :class:`InvalidDicomError` without also capturing unrelated
    ``NotImplementedError`` raised by callbacks registered through
    :mod:`pydicom.hooks`.

    To parse the offending element as **UN** rather than raise, set
    :attr:`~pydicom.config.convert_unknown_vr_to_UN` to ``True``.
    """

    pass
