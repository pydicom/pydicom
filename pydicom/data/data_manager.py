# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""pydicom data manager"""

from os import walk
from os.path import abspath, dirname, join
import fnmatch

DATA_ROOT = abspath(dirname(__file__))


def get_files(base, pattern):
    """Return all files from a set of sources.

    Parameters
    ----------
    base : str
        Base directory to recursively search.

    pattern : str
        A string pattern to filter the files. Default is "*" and it will return
        all files.

    Returns
    -------
    files : list of str
        The list of filenames matched.
    """

    # if the user forgot to add them
    pattern = "*" + pattern + "*"

    files = []
    for root, dirnames, filenames in walk(base):
        for filename in filenames:
            filename_filter = fnmatch.filter([join(root, filename)],
                                             pattern)
            if len(filename_filter):
                files.append(filename_filter[0])

    return files


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
