# Copyright 2008-2017 pydicom authors. See LICENSE file for details.
"""Utility functions to help with testing."""

from re import compile

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


def assert_warns_regex(type_warn, message, func, *args, **kwargs):
    """Test a warning against an expected warning.

    Only tests that the first `type_warn` warning fired matches the expected
    warning.

    Parameters
    ----------
    type_warn : Warning
        The expected warning.
    message : str
        A string that will be used as a regex pattern to match against the
        actual warning message. If using the actual expected message don't
        forget to escape any regex special characters like '|', '(', ')', etc.
    func : callable
        The function that is expected to fire the warning.
    args
        The callable function `func`'s arguments.
    kwargs
        The callable function `func`'s keyword arguments.

    Raises
    ------
    AssertionError
        If the regex pattern in `message` doesn't match the actual warning.
    """
    with pytest.warns(None) as wrnrecord:
        func(*args, **kwargs)

    wrn = wrnrecord.pop(type_warn)
    regex = compile(message)
    if regex.search(str(wrn.message)) is None:
        msg = "Pattern '{}' not found in warnings".format(message)
        raise AssertionError(msg)
