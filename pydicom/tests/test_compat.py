# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Tests for dataset.py"""

import sys

import pytest

from pydicom.compat import *


def test_python_version():
    """Test that the correct python version is returned"""
    if sys.version_info[0] == 2:
        assert in_py2
        assert text_type == unicode
        assert string_types == (str, unicode)
    else:
        assert not in_py2
        assert text_type == str
        assert string_types == (str,)

    # Kinda redundant
    assert in_PyPy == ('PyPy' in sys.version)


def test_reraise():
    """Test reraising an exception works in both py2 and 3"""
    def raiser():
        raise ValueError('Some msg')

    with pytest.raises(ValueError) as exc:
        reraise(raiser())

    assert str(exc.value) == 'Some msg'
