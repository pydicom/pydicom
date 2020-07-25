# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Management of pydicom's data files.


External Data Sources
---------------------

*pydicom* can also search third-party data sources for matching data. To do so
your project should register itself in it's `setup.py` file. For example, a
project named "mydata" with it's interface class ``MyInterface`` should
register:

.. codeblock: python

    from setuptools import setup

    setup(
        ...,
        entry_points={
            "pydicom.data.external_sources": "mydata = mydata:MyInterface",
        },
    )

The interface class should have, at a minimum, the following two methods:

* ``get_path(self, name: str, dtype: int) -> str`` - returns the absolute path
  to the first file with a filename `name` or raises a ``ValueError`` if no
  matching file found.
* ``get_paths(self, pattern: str, dtype: int) -> List[str]`` - returns a list
  of absolute paths to filenames matching `pattern`.

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
from pathlib import Path
from pkg_resources import iter_entry_points
from typing import Dict, List, Union
import warnings

from pydicom.data.download import (
    data_path_with_download, calculate_file_hash, get_cached_filehash,
    get_url_map
)
from pydicom.fileutil import path_from_pathlike


DATA_ROOT = abspath(dirname(__file__))


class DataTypes(IntEnum):
    """Constants for data types."""
    DATASET = 0
    CHARSET = 1
    PALETTE = 2
    DICOMDIR = 3
    JPEG = 4


def _check_pydicom_data_hash(fpath):
    """Return ``True`` if the SHA256 checksum of ``fpath`` is OK.

    Parameters
    ----------
    fpath : str
        The absolute path to the file to perform the checksum for.

    Returns
    -------
    bool
        ``True`` if the checksum matches those in ``hashes.json``, ``False``
        otherwise.

    Raises
    ------
    NoHashFound
        If the file is missing from ``hashes.json``.
    """
    p = Path(fpath)
    ext_hash = calculate_file_hash(p)
    ref_hash = get_cached_filehash(p.name)

    return ext_hash == ref_hash


def get_external_sources() -> Dict:
    """Return a :class:`dict` of external data source interfaces.

    Returns
    -------
    dict
        A dict of ``{'source name': <interface class instance>}``.
    """
    # Prefer pydicom-data as the source
    entry_point = "pydicom.data.external_sources"
    sources = {vv.name: vv.load()() for vv in iter_entry_points(entry_point)}
    out = {}
    if "pydicom-data" in sources:
        out["pydicom-data"] = sources["pydicom-data"]

    out.update(sources)

    return out


EXTERNAL_DATA_SOURCES = get_external_sources()


def online_test_file_dummy_paths() -> Dict[str, str]:
    filenames = list(get_url_map().keys())

    test_files_root = join(DATA_ROOT, 'test_files')

    dummy_path_map = {
        join(test_files_root, filename): filename
        for filename in filenames
    }

    return dummy_path_map


def get_files(
    base: Union[str, os.PathLike],
    pattern: str = "**/*",
    dtype: int = DataTypes.DATASET
) -> List[str]:
    """Return all matching file paths from the available data sources.

    First searches the local *pydicom* data store, then any locally available
    external sources, and finally the files available in the
    pydicom/pydicom-data repository.

    .. versionchanged: 2.1

        Added the `dtype` keyword parameter, modified to search locally
        available external data sources and the pydicom/pydicom-data repository

    Parameters
    ----------
    base : str or PathLike
        Base directory to recursively search.
    pattern : str, optional
        The pattern to pass to :meth:`Path.glob`, default (``'**/*'``).
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
    base = Path(path_from_pathlike(base))

    # Search locally
    files = [os.fspath(m) for m in base.glob(pattern)]

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
        os.fspath(dummy_online_file_path_map[dummy_path])
        for dummy_path in dummy_online_file_path_filtered
    ]

    real_online_file_paths = []
    download_error = False
    for filename in download_names:
        try:
            real_online_file_paths.append(
                os.fspath(data_path_with_download(filename))
            )
        except Exception as exc:
            download_error = True

    files += real_online_file_paths

    if download_error:
        warnings.warn(
            "One or more download failures occurred, the list of returned "
            "file paths may be incomplete"
        )

    return files


def get_palette_files(pattern: str = "**/*") -> List[str]:
    """Return a list of absolute paths to palettes with filenames matching
    `pattern`.

    .. versionadded:: 1.4

    Parameters
    ----------
    pattern : str, optional (default="**/*")
        The pattern to pass to :meth:`Path.glob`, default (``'**/*'``).

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
    """Return an absolute path to the first matching dataset with filename
    `name`.

    .. versionadded:: 1.4

    First searches the local *pydicom* data store, then any locally available
    external sources, and finally the files available in the
    pydicom/pydicom-data repository.

    .. versionchanged:: 2.1

        Modified to search locally available external data sources and the
        pydicom/pydicom-data repository

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
    for lib, source in EXTERNAL_DATA_SOURCES.items():
        try:
            fpath = source.get_path(name, dtype=DataTypes.DATASET)
        except ValueError:
            fpath = None

        # For pydicom-data, check the hash against hashes.json
        if lib == "pydicom-data":
            if fpath and _check_pydicom_data_hash(fpath):
                return fpath
        else:
            return fpath

    # Try online
    for filename in get_url_map().keys():
        if filename == name:
            try:
                return os.fspath(data_path_with_download(filename))
            except Exception as exc:
                pass


example_dataset_path = get_testdata_file


def get_testdata_files(pattern: str = "**/*") -> List[str]:
    """Return a list of absolute paths to datasets with filenames matching
    `pattern`.

    Parameters
    ----------
    pattern : str, optional (default="*")
        The pattern to pass to :meth:`Path.glob`, default (``'**/*'``).

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
    """Return a list of absolute paths to charsets with filenames matching
    `pattern`.

    Parameters
    ----------
    pattern : str, optional (default="*")
        The pattern to pass to :meth:`Path.glob`, default (``'**/*'``).

    Returns
    ----------
    files : list of str
        The list of filenames matched.

    """
    data_path = join(DATA_ROOT, 'charset_files')

    files = get_files(base=data_path, pattern=pattern, dtype=DataTypes.CHARSET)
    files = [filename for filename in files if not filename.endswith('.py')]

    return files
