# Copyright 2008-2017 pydicom authors. See LICENSE file for details.
"""Tests for errors.py"""

import pytest

from pydicom.errors import InvalidDicomError
from .testing import assert_raises_regex


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
