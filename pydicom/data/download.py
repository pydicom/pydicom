# Copyright 2018-2020 pydicom authors. See LICENSE file for details.

import functools
import json
import os
import pathlib
import urllib.request
import warnings
import hashlib
import contextlib

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


def calculate_file_hash(filename):
    BLOCKSIZE = 65536
    hasher = hashlib.sha256()
    with open(str(filename), "rb") as f:
        buf = f.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(BLOCKSIZE)

    return hasher.hexdigest()


def get_config_dir():
    config_dir = pathlib.Path.home().joinpath(".pydicom")
    config_dir.mkdir(exist_ok=True)

    return config_dir


@retry.retry(urllib.error.HTTPError)
def download_with_progress(url, filepath):
    with DownloadProgressBar(
        unit="B", unit_scale=True, miniters=1, desc=url.split("/")[-1]
    ) as t:
        urllib.request.urlretrieve(url, filepath, reporthook=t.update_to)


def get_data_dir():
    data_dir = get_config_dir().joinpath("data")
    data_dir.mkdir(exist_ok=True)

    return data_dir


@functools.lru_cache()
def get_url_map():
    with open(str(HERE.joinpath("urls.json")), "r") as url_file:
        url_map = json.load(url_file)

    return url_map


def get_url(filename):
    url_map = get_url_map()

    try:
        url = url_map[filename]
    except KeyError:
        raise ValueError(
            "The file provided isn't within pydicom's urls.json record.")

    return url


def data_path_with_download(
        filename,
        check_hash=True,
        redownload_on_hash_mismatch=True,
        url=None):
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
                return data_path_with_download(filename, redownload_on_hash_mismatch=False)

            raise ValueError(
                "The file on disk does not match the recorded hash.")

    return filepath.resolve()


class NoHashFound(KeyError):
    pass


def get_cached_filehash(filename):
    with open(str(HERE.joinpath("hashes.json")), "r") as hash_file:
        hashes = json.load(hash_file)

    try:
        cached_filehash = hashes[filename]
    except KeyError:
        raise NoHashFound

    return cached_filehash


def data_file_hash_check(filename):
    filename = str(filename).replace(os.sep, "/")

    filepath = get_data_dir().joinpath(filename)
    calculated_filehash = calculate_file_hash(filepath)

    try:
        cached_filehash = get_cached_filehash(filename)
    except NoHashFound:
        warnings.warn("Hash not found in hashes.json. File will be updated.")
        with open(str(HERE.joinpath("hashes.json")), "r") as hash_file:
            hashes = json.load(hash_file)

        hashes[filename] = calculated_filehash

        with open(str(HERE.joinpath("hashes.json")), "w") as hash_file:
            json.dump(hashes, hash_file, indent=2, sort_keys=True)

        raise

    return cached_filehash == calculated_filehash

