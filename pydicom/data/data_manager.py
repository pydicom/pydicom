# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""pydicom data manager"""

import fnmatch
import os
from os.path import abspath, dirname, join

from pydicom.fileutil import path_from_pathlike

DATA_ROOT = abspath(dirname(__file__))


def get_files(base, pattern):
    """Return all files from a set of sources.

    Parameters
    ----------
    base : str or PathLike
        Base directory to recursively search.

    pattern : str
        A string pattern to filter the files. Default is "*" and it will return
        all files.

    Returns
    -------
    files : list of str
        The list of filenames matched.
    """

    base = path_from_pathlike(base)
    # if the user forgot to add them
    pattern = "*" + pattern + "*"

    files = []
    for root, _, filenames in os.walk(base):
        for filename in filenames:
            filename_filter = fnmatch.filter([join(root, filename)],
                                             pattern)
            if len(filename_filter):
                files.append(filename_filter[0])

    return files


def get_palette_files(pattern="*"):
    """Return palette data files from pydicom data root.

    .. versionadded:: 1.4

    Parameters
    ----------
    pattern : str, optional (default="*")
        A string pattern to filter the files

    Returns
    -------
    files : list of str
        The list of filenames matched.

    """
    data_path = join(DATA_ROOT, 'palettes')

    files = get_files(base=data_path, pattern=pattern)
    files = [filename for filename in files if not filename.endswith('.py')]

    return files


def get_testdata_file(name):
    """Return the first test data file path with the given name found under
    the pydicom test data root.

    .. versionadded:: 1.4

    Parameters
    ----------
    name : str
        The full file name (without path)

    Returns
    -------
    str, None
        The full path of the file if found, or ``None``.

    """
    data_path = join(DATA_ROOT, 'test_files')
    for root, _, filenames in os.walk(data_path):
        for filename in filenames:
            if filename == name:
                return os.path.join(root, filename)


def get_testdata_files(pattern="*"):
    """Return test data files from pydicom data root.

    Parameters
    ----------
    pattern : str, optional (default="*")
        A string pattern to filter the files

    Returns
    -------
    files : list of str
        The list of filenames matched.

    """

    data_path = join(DATA_ROOT, 'test_files')

    files = get_files(base=data_path, pattern=pattern)
    files = [filename for filename in files if not filename.endswith('.py')]

    return files


def get_charset_files(pattern="*"):
    """Return charset files from pydicom data root.

    Parameters
    ----------
    pattern : str, optional (default="*")
        A string pattern to filter the files

    Returns
    ----------
    files : list of str
        The list of filenames matched.

    """

    data_path = join(DATA_ROOT, 'charset_files')

    files = get_files(base=data_path, pattern=pattern)
    files = [filename for filename in files if not filename.endswith('.py')]

    return files
