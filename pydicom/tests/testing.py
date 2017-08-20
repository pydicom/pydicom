# Copyright 2008-2017 pydicom authors. See LICENSE file for details.
"""Test for encaps.py"""

import pytest


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
