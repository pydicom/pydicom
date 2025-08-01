# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Management of pydicom's data files.


External Data Sources
---------------------

*pydicom* can also search third-party data sources for matching data. To do so
your project should register its entry points in its `pyproject.toml` or `setup.py` file. For
example, a project named "mydata" using `setup.py` with the interface class ``MyInterface``
should register:

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

And lastly, `pattern` is a str used to filter files against when searching.

For a real-life example of an external data source you can look at the
`pydicom-data <https://github.com/pydicom/pydicom-data>`_ repository.
"""

from enum import IntEnum
import fnmatch
import os
from pathlib import Path
from typing import TYPE_CHECKING

from pydicom.data.download import (
    data_path_with_download,
    calculate_file_hash,
    get_cached_filehash,
    get_url_map,
    get_data_dir,
)
from pydicom.misc import warn_and_log

if TYPE_CHECKING:  # pragma: no cover
    from pydicom import Dataset


DATA_ROOT = os.fspath(Path(__file__).parent.resolve())
"""The absolute path to the pydicom/data directory."""


class DataTypes(IntEnum):
    """Constants for data types."""

    DATASET = 0
    CHARSET = 1
    PALETTE = 2
    DICOMDIR = 3
    JPEG = 4


def _check_data_hash(fpath: str) -> bool:
    """Return ``True`` if the SHA256 checksum of the file at ``fpath`` is OK.

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
    pydicom.data.download.NoHashFound
        If the file is missing from ``hashes.json``.
    """
    p = Path(fpath)
    ext_hash = calculate_file_hash(p)
    ref_hash = get_cached_filehash(p.name)

    return ext_hash == ref_hash


def get_external_sources() -> dict:
    """Return a :class:`dict` of external data source interfaces.

    Returns
    -------
    dict
        A dict of ``{'source name': <interface class instance>}``.
    """

    from importlib.metadata import entry_points

    # Prefer pydicom-data as the source
    sources = {
        vv.name: vv.load()()
        for vv in entry_points(group="pydicom.data.external_sources")
    }
    out = {}
    if "pydicom-data" in sources:
        out["pydicom-data"] = sources["pydicom-data"]

    out.update(sources)

    return out


_EXTERNAL_DATA_SOURCES: dict | None = None


def external_data_sources() -> dict:
    """Return the available external data sources - loaded once."""
    global _EXTERNAL_DATA_SOURCES
    if _EXTERNAL_DATA_SOURCES is None:
        _EXTERNAL_DATA_SOURCES = get_external_sources()
    return _EXTERNAL_DATA_SOURCES


def online_test_file_dummy_paths() -> dict[str, str]:
    """Return a :class:`dict` of dummy paths to the downloadable test files.

    Returns
    -------
    dict
        A dict of dummy paths to the test files available via download.
    """
    filenames = list(get_url_map().keys())

    test_files_root = os.path.join(DATA_ROOT, "test_files")

    dummy_path_map = {
        os.path.join(test_files_root, filename): filename for filename in filenames
    }

    return dummy_path_map


def fetch_data_files(data_dir: Path = get_data_dir()) -> None:
    """Download missing test files to the local cache.

    ..versionchanged:: 3.1

        Added the `data_dir` optional argument.

    Parameters
    ----------
    data_dir : pathlib.Path, optional
        The path to the data cache directory, defaults to the directory returned by
        :func:`~pydicom.data.download.get_data_dir`.
    """
    paths = {data_dir / fname: fname for fname in list(get_url_map().keys())}

    errors: dict[str, list[str]] = {}
    for p in paths:
        # Download missing files or files that don't match the hash
        try:
            data_path_with_download(p.name, data_dir=data_dir)
        except Exception as exc:
            filenames = errors.setdefault(f"{type(exc).__name__}: {exc}", [])
            filenames.append(p.name)

    if not errors:
        return

    msg = ["The following exception(s) occurred trying to download the data files"]
    for err, filenames in errors.items():
        err_msg = f"  '{err}' for " + ", ".join(filenames[:2])
        if len(filenames) > 2:
            err_msg += f" and {len(filenames) - 2} others"

        msg.append(err_msg)

    raise RuntimeError("\n".join(msg))


def get_files(
    base: str | os.PathLike, pattern: str = "**/*", dtype: int = DataTypes.DATASET
) -> list[str]:
    """Return all matching file paths from the available data sources.

    First searches the local *pydicom* data store, then any locally available
    external sources, and finally the files available in the
    pydicom/pydicom-data repository.

    .. versionchanged: 2.1

        Added the `dtype` keyword parameter, modified to search locally
        available external data sources and the pydicom/pydicom-data repository

    Parameters
    ----------
    base : str or os.PathLike
        Base directory to recursively search.
    pattern : str, optional
        The pattern to pass to :meth:`~pathlib.Path.glob`, default
        (``'**/*'``).
    dtype : int, optional
        The type of data to search for when using an external source, one of:

        * ``0`` - DICOM dataset
        * ``1`` - Character set file
        * ``2`` - Palette file
        * ``3`` - DICOMDIR file
        * ``4`` - JPEG file

    Returns
    -------
    list of str
        A list of absolute paths to matching files.
    """
    base = Path(base)

    # Search locally
    files = [os.fspath(m) for m in base.glob(pattern)]

    # Search external sources
    for lib, source in external_data_sources().items():
        fpaths = source.get_paths(pattern, dtype)
        if lib == "pydicom-data":
            # For pydicom-data, check the hash against hashes.json
            fpaths = [p for p in fpaths if _check_data_hash(p)]

        files.extend(fpaths)

    # Search https://github.com/pydicom/pydicom-data or local cache
    # To preserve backwards compatibility filter the downloaded files
    # as if they are stored within DATA_ROOT/test_files/*.dcm
    dummy_online_file_path_map = online_test_file_dummy_paths()
    dummy_online_file_path_filtered = fnmatch.filter(
        dummy_online_file_path_map.keys(), os.path.join(base, pattern)
    )
    download_names = [
        os.fspath(dummy_online_file_path_map[dummy_path])
        for dummy_path in dummy_online_file_path_filtered
    ]

    real_online_file_paths = []
    download_error = False
    for filename in download_names:
        try:
            real_online_file_paths.append(os.fspath(data_path_with_download(filename)))
        except Exception:
            download_error = True

    files += real_online_file_paths

    if download_error:
        warn_and_log(
            "One or more download failures occurred, the list of matching "
            "file paths may be incomplete"
        )

    return files


def get_palette_files(pattern: str = "**/*") -> list[str]:
    """Return a list of absolute paths to palettes with filenames matching
    `pattern`.

    Parameters
    ----------
    pattern : str, optional
        The pattern to pass to :meth:`~pathlib.Path.glob`, default
        (``'**/*'``).

    Returns
    -------
    list of str
        A list of absolute paths to matching files.
    """
    data_path = Path(DATA_ROOT) / "palettes"

    files = get_files(base=data_path, pattern=pattern, dtype=DataTypes.PALETTE)
    files = [filename for filename in files if not filename.endswith(".py")]

    return files


def get_testdata_file(
    name: str,
    read: bool = False,
    download: bool = True,
) -> "str | Dataset | None":
    """Return an absolute path to the first matching dataset with filename
    `name` that is found in a local or external pydicom datastore.

    First searches the local *pydicom* data store, then any locally available
    external sources, and finally the files available in the
    pydicom/pydicom-data repository.

    .. versionchanged:: 2.1

        Modified to search locally available external data sources and the
        pydicom/pydicom-data repository

    .. versionchanged:: 2.2

        Added the `read` keyword parameter.

    .. versionchanged:: 2.3

        Added the `download` keyword parameter.

    Parameters
    ----------
    name : str
        The full file name (without path)
    read : bool, optional
        If ``True`` then use :func:`~pydicom.filereader.dcmread` to read the
        file and return the corresponding
        :class:`~pydicom.dataset.FileDataset`. Default ``False``.
    download : bool, optional
        If ``True`` (default) download the file if missed locally.

    Returns
    -------
    str, pydicom.dataset.Dataset or None
        The absolute path of the file if found, the dataset itself if `read` is
        ``True``, or ``None`` if the file is not found.

    Raises
    ______
    ValueError
        If `name` is an absolute path.
    """

    path = _get_testdata_file(name=name, download=download)

    if read and path is not None:
        from pydicom.filereader import dcmread

        return dcmread(path, force=True)
    return path


def _get_testdata_file(name: str, download: bool = True) -> str | None:
    # Check pydicom local
    data_path = Path(DATA_ROOT) / "test_files"

    if Path(name).anchor:
        raise ValueError(
            f"'get_testdata_file' does not support absolute paths, as it only works"
            f" with internal pydicom test data - did you mean 'dcmread(\"{name}\")'?"
        )
    matches = [m for m in data_path.rglob(name)]
    if matches:
        return os.fspath(matches[0])

    # Check external data sources
    fpath: str | None
    for lib, source in external_data_sources().items():
        try:
            fpath = source.get_path(name, dtype=DataTypes.DATASET)
        except ValueError:
            fpath = None

        # For pydicom-data, check the hash against hashes.json
        if lib == "pydicom-data":
            if fpath and _check_data_hash(fpath):
                return fpath
        elif fpath:
            return fpath

    # Try online
    if download:
        for filename in get_url_map().keys():
            if filename != name:
                continue
            try:
                return os.fspath(data_path_with_download(filename))
            except Exception:
                warn_and_log(
                    f"A download failure occurred while attempting to "
                    f"retrieve {name}"
                )

    return None


def get_testdata_files(pattern: str = "**/*") -> list[str]:
    """Return a list of absolute paths to datasets with filenames matching
    `pattern`.

    Parameters
    ----------
    pattern : str, optional
        The pattern to pass to :meth:`~pathlib.Path.glob`, default
        (``'**/*'``).

    Returns
    -------
    list of str
        A list of absolute paths to matching files.

    Raises
    ______
    ValueError
        If `pattern` matches an absolute path.
    """
    if Path(pattern).anchor:
        raise ValueError(
            "'get_testdata_files' does not support absolute paths, as it only works"
            " with internal pydicom test data."
        )
    data_path = Path(DATA_ROOT) / "test_files"

    files = get_files(base=data_path, pattern=pattern, dtype=DataTypes.DATASET)
    files = [filename for filename in files if not filename.endswith(".py")]

    return files


def get_charset_files(pattern: str = "**/*") -> list[str]:
    """Return a list of absolute paths to charsets with filenames matching
    `pattern`.

    Parameters
    ----------
    pattern : str, optional
        The pattern to pass to :meth:`~pathlib.Path.glob`, default
        (``'**/*'``).

    Returns
    ----------
    list of str
        A list of absolute paths to matching files.
    """
    data_path = Path(DATA_ROOT) / "charset_files"

    files = get_files(base=data_path, pattern=pattern, dtype=DataTypes.CHARSET)
    files = [filename for filename in files if not filename.endswith(".py")]

    return files
