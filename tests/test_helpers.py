# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Helper functions for tests."""

import warnings
from contextlib import contextmanager
from collections.abc import Generator


@contextmanager
def assert_no_warning() -> Generator:
    """Assert that no warning is issued.
    Any warning will be handled as an error.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        yield
