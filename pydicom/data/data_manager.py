# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Management of pydicom's data files.


External Data Sources
---------------------

*pydicom* can also search third-party data sources for matching data. To do so
your project should register itself in it's `setup.py` file. For example, a
project named "mydata" with it's interface class ``MyInterface``:

.. codeblock: python

    from setuptools import setup

    setup(
        ...,
        entry_points={
            "pydicom.data.external_sources": "mydata" = mydata:MyInterface",
        },
    )

The interface class should have two methods:

* ``get_path(name: str, dtype: int) -> str`` - returns the absolute path to the
  first file with a filename `name` or raises a ``ValueError`` if no
  matching file found.
* ``get_paths(pattern: str, dtype: int) -> List[str]`` - returns a list of
  absolute paths to filenames matching `pattern`.

Where `name` is the name of the filename to search for, `dtype` is an int
that indicates the type of data to search for and should be one of the
following:

* ``0`` - DICOM dataset
* ``1`` - Character set file
* ``2`` - Palette file
* ``3`` - DICOMDIR file
* ``4`` - JPEG file

And lastly, `pattern` is a str used with :func:`fnmatch.filter` to filter
against when searching.

For a real-life example of an external data source you can look at the
`pydicom-data <https://github.com/pydicom/pydicom-data>`_ repository.
"""

from enum import IntEnum
import fnmatch
import os
from os.path import abspath, dirname, join
from pkg_resources import iter_entry_points
from typing import Dict, List

from pydicom.fileutil import path_from_pathlike

from . import download


DATA_ROOT = abspath(dirname(__file__))


class DataTypes(IntEnum):
    """Constants for data types."""
    DATASET = 0
    CHARSET = 1
    PALETTE = 2
    DICOMDIR = 3
    JPEG = 4


def get_external_sources() -> Dict:
    """Return a :class:`dict` of external data source interfaces.

    Returns
    -------
    dict
        A dict of ``{'source name': <interface class instance>}``.
    """
    entry_point = "pydicom.data.external_sources"
    return {val.name: val.load()() for val in iter_entry_points(entry_point)}


EXTERNAL_DATA_SOURCES = get_external_sources()


def online_test_file_dummy_paths() -> Dict[str, str]:
    filenames = list(download.get_url_map().keys())

    test_files_root = join(DATA_ROOT, 'test_files')

    dummy_path_map = {
        join(test_files_root, filename): filename
        for filename in filenames
    }

    return dummy_path_map


# TODO: Union of str and PathLike
def get_files(
    base: str, pattern: str, dtype: int = DataTypes.DATASET
) -> List[str]:
    """Return all files from a set of sources.

    First searches the local *pydicom* data store, then any locally available
    external sources, and finally will search the files available in the
    pydicom/pydicom-data repository.

    .. versionchange: 2.1

        Added the `dtype` keyword parameter.

    Parameters
    ----------
    base : str or PathLike
        Base directory to recursively search.
    pattern : str
        A string pattern to filter the files. Default is "*" and it will return
        all files.
    dtype : int, optional
        The type of data to search for when using an external source, one of:

        * ``0`` - DICOM dataset
        * ``1`` - Character set file
        * ``2`` - Palette file
        * ``3`` - DICOMDIR file
        * ``4`` - JPEG file

    Returns
    -------
    files : list of str
        The list of filenames matched.
    """
    base = path_from_pathlike(base)
    # if the user forgot to add them
    pattern = "*" + pattern + "*"

    # Search locally
    files = []
    for root, _, filenames in os.walk(base):
        for filename in filenames:
            filename_filter = fnmatch.filter([join(root, filename)], pattern)
            if filename_filter:
                files.append(filename_filter[0])

    # Search external sources
    for source in EXTERNAL_DATA_SOURCES.values():
        files.extend(source.get_paths(pattern, dtype))

    # Search http://github.com/pydicom/pydicom-data or local cache
    # To preserve backwards compatibility filter the downloaded files
    # as if they are stored within DATA_ROOT/test_files/*.dcm
    dummy_online_file_path_map = online_test_file_dummy_paths()
    dummy_online_file_path_filtered = fnmatch.filter(
        dummy_online_file_path_map.keys(), join(base, pattern)
    )
    download_names = [
        str(dummy_online_file_path_map[dummy_path])
        for dummy_path in dummy_online_file_path_filtered
    ]

    real_online_file_paths = []
    if download.check_network():
        for filename in download_names:
            try:
                real_online_file_paths.append(
                    str(download.data_path_with_download(filename))
                )
            except Exception as exc:
                pass

    files += real_online_file_paths

    return files


def get_palette_files(pattern: str = "*") -> List[str]:
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

    files = get_files(base=data_path, pattern=pattern, dtype=DataTypes.PALETTE)
    files = [filename for filename in files if not filename.endswith('.py')]

    return files


def get_testdata_file(name: str) -> str:
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
    # Check pydicom local
    data_path = join(DATA_ROOT, 'test_files')
    for root, _, filenames in os.walk(data_path):
        for filename in filenames:
            if filename == name:
                return os.path.join(root, filename)

    # Check external data sources
    for source in EXTERNAL_DATA_SOURCES.values():
        try:
            return source.get_path(name, dtype=DataTypes.DATASET)
        except ValueError:
            pass

    # Try online
    for filename in download.get_url_map().keys():
        if filename == name:
            try:
                return str(download.data_path_with_download(filename))
            except Exception as exc:
                pass


get_dataset = get_testdata_file


def get_testdata_files(pattern: str = "*") -> List[str]:
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

    files = get_files(base=data_path, pattern=pattern, dtype=DataTypes.DATASET)
    files = [filename for filename in files if not filename.endswith('.py')]

    return files


def get_charset_files(pattern: str = "*") -> List[str]:
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

    files = get_files(base=data_path, pattern=pattern, dtype=DataTypes.CHARSET)
    files = [filename for filename in files if not filename.endswith('.py')]

    return files
