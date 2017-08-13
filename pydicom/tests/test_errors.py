# Copyright 2008-2017 pydicom authors. See LICENSE file for details.
"""Tests for errors.py"""

import pytest

from pydicom.errors import InvalidDicomError


def assert_raises_regex(type_error, message, func, *args, **kwargs):
    """Taken from https://github.com/glemaitre/specio, BSD 3 license."""
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
