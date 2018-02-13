# Copyright 2008-2017 pydicom authors. See LICENSE file for details.
"""Tests for errors.py"""

import pytest

from pydicom.errors import InvalidDicomError


def assert_raises_regex(type_error, message, func, *args, **kwargs):
    """Test a raised exception against an expected exception.

    Parameters
    ----------
    type_error : Exception
        The expected raised exception.
    message : str
        A string that will be used as a regex pattern to match against the
        actual exception message. If using the actual expected message don't
        forget to escape any regex special characters like '|', '(', ')', etc.
    func : callable
        The function that is expected to raise the exception.
    args
        The callable function `func`'s arguments.
    kwargs
        The callable function `func`'s keyword arguments.

    Notes
    -----
    Taken from https://github.com/glemaitre/specio, BSD 3 license.
    """
    with pytest.raises(type_error) as excinfo:
        func(*args, **kwargs)
    excinfo.match(message)


def test_message():
    """Test InvalidDicomError with a message"""
    def _test():
        raise InvalidDicomError('test msg')
    assert_raises_regex(InvalidDicomError, 'test msg', _test)


def test_no_message():
    """Test InvalidDicomError with no message"""
    def _test():
        raise InvalidDicomError
    assert_raises_regex(InvalidDicomError,
                        'The specified file is not a valid DICOM file.', _test)
