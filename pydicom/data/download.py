# Copyright 2020 pydicom authors. See LICENSE file for details.

# Copyright 2018-2019 Cancer Care Associates.
# Relicensed under pydicom LICENSE by Simon Biggs.

import contextlib
import functools
import hashlib
import json
import os
import pathlib
from typing import Dict, Optional
import urllib.request
import urllib.error
import warnings

from . import retry

try:
    import tqdm

    class DownloadProgressBar(tqdm.tqdm):
        def update_to(self, b=1, bsize=1, tsize=None):
            if tsize is not None:
                self.total = tsize
            self.update(b * bsize - self.n)

except ImportError:
    @contextlib.contextmanager
    def DownloadProgressBar(*args, **kwargs):
        try:
            class dummy:
                def update_to(*args, **kwargs):  # pylint: disable = no-method-argument
                    pass

            yield dummy
        finally:
            pass


HERE = pathlib.Path(__file__).resolve().parent
_SIMULATE_NETWORK_OUTAGE = False  # For testing network outages


def calculate_file_hash(fpath: pathlib.Path) -> str:
    """Return the SHA256 checksum for the file at `fpath`.

    Parameters
    ----------
    fpath : pathlib.Path
        The absolute path to the file that is to be checksummed.

    Returns
    -------
    str
        The SHA256 checksum of the file.
    """
    BLOCKSIZE = 65536
    hasher = hashlib.sha256()
    with open(fpath, "rb") as f:
        buf = f.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(BLOCKSIZE)

    return hasher.hexdigest()


def get_config_dir() -> str:
    """Return the path to the pydicom config directory, creating it if required

    The config directory will be named ``.pydicom`` and will be created in the
    local user's home directory.
    """
    config_dir = pathlib.Path.home().joinpath(".pydicom")
    config_dir.mkdir(exist_ok=True)

    return config_dir


@retry.retry(urllib.error.HTTPError)
def download_with_progress(url: str, fpath: pathlib.Path) -> None:
    """Download the file at `url` to `fpath` with a progress bar.

    Parameters
    ----------
    url : str
        The URL to download the file from.
    fpath : pathlib.Path
        The absolute path where the file will be written to.
    """
    with DownloadProgressBar(
        unit="B", unit_scale=True, miniters=1, desc=url.split("/")[-1]
    ) as t:
        urllib.request.urlretrieve(
            url, os.fspath(fpath), reporthook=t.update_to
        )


def get_data_dir() -> str:
    """Return the path to the cache directory, creating it if required."""
    data_dir = get_config_dir().joinpath("data")
    data_dir.mkdir(exist_ok=True)

    return data_dir


@functools.lru_cache()
def get_url_map() -> Dict[str, str]:
    """Return a dict containing the URL mappings from ``urls.json```."""
    with open(HERE / "urls.json", "r") as url_file:
        return json.load(url_file)


def get_url(filename: str) -> str:
    """Return the download URL corresponding to `filename`.

    The filename:URL mappings are located in the ``urls.json`` file.

    Parameters
    ----------
    filename : str
        The filename of the file to get the corresponding URL for.

    Returns
    -------
    str
        The download URL corresponding to `filename`.

    Raises
    ------
    ValueError
        If `filename` is not in the ``urls.json`` record.
    """
    # Convert filename to lowercase because windows filenames are
    #   case-insensitive
    urls = {k.lower(): v for k, v in get_url_map().items()}
    try:
        return urls[filename.lower()]
    except KeyError:
        raise ValueError(
            "The file provided isn't within pydicom's urls.json record."
        )


def data_path_with_download(
        filename: str,
        check_hash: bool = True,
        redownload_on_hash_mismatch: bool = True,
        url: Optional[str] = None
    ) -> pathlib.Path:
    """Return the absolute path to the cached file with `filename`.

    If the file isn't available in the cache then it will be downloaded.

    Parameters
    ----------
    filename : str
        The filename of the file to return the path to.
    check_hash : bool, optional
        ``True`` to perform a SHA256 checkum on the file, ``False`` otherwise.
    redownload_on_hash_mismatch : bool, optional
        ``True`` to redownload the file on checksum failure, ``False``
        otherwise.
    url : str, optional
        The file's corresponding download URL

    Returns
    -------
    pathlib.Path
        The absolute path to the file.
    """
    if _SIMULATE_NETWORK_OUTAGE:
        raise RuntimeError("No network!")

    filepath = get_data_dir().joinpath(filename)

    if check_hash and filepath.exists():
        try:
            get_cached_filehash(filename)
        except NoHashFound:
            filepath.unlink()  # Force a redownload

    if not filepath.exists():
        if url is None:
            url = get_url(filename)

        download_with_progress(url, filepath)

    if check_hash:
        try:
            hash_agrees = data_file_hash_check(filename)
        except NoHashFound:
            return filepath.resolve()

        if not hash_agrees:
            if redownload_on_hash_mismatch:
                filepath.unlink()
                return data_path_with_download(
                    filename, redownload_on_hash_mismatch=False
                )

            raise ValueError(
                "The file on disk does not match the recorded hash."
            )

    return filepath.resolve()


class NoHashFound(KeyError):
    pass


def get_cached_filehash(filename: str) -> str:
    """Return the SHA256 checksum of a cached file.

    Parameters
    ----------
    filename : str
        The filename of the cached file to calculate the checksum for.

    Returns
    -------
    str
        The SHA256 checksum of the cached file.
    """
    with open(HERE / "hashes.json", "r") as hash_file:
        hashes = json.load(hash_file)
        # Convert filenames to lowercase because windows filenames are
        #   case-insensitive
        hashes = {k.lower(): v for k, v in hashes.items()}

    try:
        return hashes[filename.lower()]
    except KeyError:
        raise NoHashFound


def data_file_hash_check(filename: str) -> bool:
    """Return ``True`` if the SHA256 checksum of the cached file is correct.

    Parameters
    ----------
    filename : str
        The filename of the cached file to check.

    Returns
    -------
    bool
        ``True`` if the cached file has the correct checksum, ``False``
        otherwise.
    """
    filename = os.fspath(filename)
    filepath = get_data_dir().joinpath(filename)
    calculated_filehash = calculate_file_hash(filepath)

    try:
        cached_filehash = get_cached_filehash(filename)
    except NoHashFound:
        warnings.warn("Hash not found in hashes.json. File will be updated.")
        with open(HERE / "hashes.json", "r") as hash_file:
            hashes = json.load(hash_file)

        hashes[filename] = calculated_filehash

        with open(HERE / "hashes.json", "w") as hash_file:
            json.dump(hashes, hash_file, indent=2, sort_keys=True)

        raise

    return cached_filehash == calculated_filehash
