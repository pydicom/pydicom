# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Unit tests for pydicom.data_manager"""

import json
import os
from os.path import basename
from pathlib import Path
import shutil

import pytest

from pydicom.data import (
    get_charset_files,
    get_testdata_files,
    get_palette_files,
    fetch_data_files,
)
from pydicom.data.data_manager import (
    DATA_ROOT,
    get_testdata_file,
    external_data_sources,
)
from pydicom.data import download
from pydicom.data.download import get_data_dir, calculate_file_hash, get_cached_filehash


EXT_PYDICOM = "pydicom-data" in external_data_sources()
if EXT_PYDICOM:
    DATA_SRC = external_data_sources()["pydicom-data"].data_path


@pytest.fixture
def download_failure():
    """Simulate a download failure."""
    download._SIMULATE_NETWORK_OUTAGE = True
    yield
    download._SIMULATE_NETWORK_OUTAGE = False


class TestGetData:
    def test_get_dataset(self):
        """Test the different functions to get lists of data files."""
        # The cached files downloaded from the pydicom-data repo
        cached_data_test_files = str(get_data_dir())

        # If pydicom-data is available locally
        ext_path = None
        if "pydicom-data" in external_data_sources():
            ext_path = os.fspath(external_data_sources()["pydicom-data"].data_path)

        # Test base locations
        charbase = os.path.join(DATA_ROOT, "charset_files")
        assert os.path.exists(charbase)

        testbase = os.path.join(DATA_ROOT, "test_files")
        assert os.path.exists(testbase)

        # Test file get
        chardata = get_charset_files()
        assert 15 < len(chardata)

        # Test that top level file is included
        bases = [basename(x) for x in chardata]

        # Test that subdirectory files included
        testdata = get_testdata_files()
        bases = [basename(x) for x in testdata]
        assert "2693" in bases
        assert 70 < len(testdata)

        # The files should be from their respective bases
        for x in testdata:
            # Don't check files from external sources other than pydicom-data
            if (
                testbase not in x
                and cached_data_test_files not in x
                and (ext_path not in x if ext_path else True)
            ):
                continue

            assert (
                testbase in x
                or cached_data_test_files in x
                or (ext_path in x if ext_path else False)
            )

        for x in chardata:
            assert charbase in x

    def test_get_dataset_pattern(self):
        """Test that pattern is working properly."""
        pattern = "CT_small*"
        filename = get_testdata_files(pattern)
        assert filename[0].endswith("CT_small.dcm")

        pattern = "chrX1*"
        filename = get_charset_files(pattern)
        assert filename[0].endswith("chrX1.dcm")

    def test_get_testdata_file(self):
        """Test that file name is working properly."""
        p = Path(get_testdata_file("DICOMDIR"))
        assert "DICOMDIR" == p.name.upper()

    def test_get_palette_files(self):
        """Test data_manager.get_palette_files."""
        palbase = os.path.join(DATA_ROOT, "palettes")
        assert os.path.exists(palbase)

        palettes = get_palette_files("*.dcm")
        assert 8 == len(palettes)

        for x in palettes:
            assert palbase in x

    def test_no_absolute_path_in_get_testdata_file(self):
        msg = (
            "'get_testdata_file' does not support absolute paths, "
            "as it only works with internal pydicom test data - "
            r"did you mean 'dcmread\(\"/foo/bar.dcm\"\)'?"
        )
        with pytest.raises(ValueError, match=msg):
            get_testdata_file("/foo/bar.dcm")

    def test_no_absolute_path_in_get_testdata_files(self):
        msg = (
            "'get_testdata_files' does not support absolute paths, as it only works "
            "with internal pydicom test data."
        )
        with pytest.raises(ValueError, match=msg):
            get_testdata_files("/foo/*.dcm")


@pytest.fixture
def data_fs(fs):
    # Note: when using pyfakefs you must use open() with externally defined
    # pathlib.Path instances (such as DATA_SRC), not Path.open()
    # Add the cache directory so it can be created on the GitHub runner
    (Path.home() / ".pydicom" / "data").mkdir(parents=True, exist_ok=True)

    # Add the installation test data directory
    fs.add_real_directory(Path(DATA_ROOT) / "test_files", read_only=False)

    # Add the JSON files
    fs.add_real_file(Path(DATA_ROOT) / "hashes.json")
    fs.add_real_file(Path(DATA_ROOT) / "urls.json")

    # Add the local user's cache
    fs.add_real_directory(get_data_dir(), read_only=False)

    # Add the external data source from pydicom-data (if available)
    if EXT_PYDICOM:
        fs.add_real_directory(DATA_SRC, read_only=False)

    yield fs


@pytest.mark.skipif(not EXT_PYDICOM, reason="pydicom-data not installed")
class TestExternalDataSource:
    """Tests for the external data sources."""

    def teardown_method(self):
        if "mylib" in external_data_sources():
            del external_data_sources()["mylib"]

    def as_posix(self, path):
        """Return `path` as a posix path"""
        return Path(path).as_posix()

    def test_get_testdata_file_local(self):
        """Test that local data path retrieved OK."""
        fpath = self.as_posix(get_testdata_file("CT_small.dcm"))
        assert "pydicom/data/test_files" in fpath

    def test_get_testdata_file_external(self):
        """Test that external data source preferred over cache."""
        fpath = self.as_posix(get_testdata_file("693_UNCI.dcm"))
        assert "data_store/data" in fpath

    def test_get_testdata_file_external_hash_mismatch(self, data_fs):
        """Test that the external source is not used when hash is not OK."""
        p = Path(DATA_SRC / "693_UNCI.dcm")
        with open(p, "wb") as f:
            f.write(b"\x00\x01")

        ext_hash = calculate_file_hash(p)
        ref_hash = get_cached_filehash(p.name)
        assert ext_hash != ref_hash
        fpath = self.as_posix(get_testdata_file(p.name))
        assert ".pydicom/data" in fpath

    def test_get_testdata_file_external_hash_match(self):
        """Test that external source is used when hash is OK."""
        p = Path(DATA_SRC / "693_UNCI.dcm")
        ext_hash = calculate_file_hash(p)
        ref_hash = get_cached_filehash(p.name)
        assert ext_hash == ref_hash
        fpath = self.as_posix(get_testdata_file(p.name))
        assert "data_store/data" in fpath

    def test_get_testdata_file_external_ignore_hash(self, data_fs):
        """Test that non-pydicom-data external source ignores hash check."""
        external_data_sources()["mylib"] = external_data_sources()["pydicom-data"]
        p = Path(DATA_SRC / "693_UNCI.dcm")
        with open(p, "wb") as f:
            f.write(b"\x00\x01")

        ext_hash = calculate_file_hash(p)
        ref_hash = get_cached_filehash(p.name)
        assert ext_hash != ref_hash
        fpath = self.as_posix(get_testdata_file(p.name))
        assert "data_store/data" in fpath

    def test_get_testdata_file_missing(self):
        """Test no such file available."""
        fname = "MY_MISSING_FILE.dcm"
        assert get_testdata_file(fname) is None

    def test_get_testdata_files_local(self):
        """Test that local data paths retrieved OK."""
        paths = get_testdata_files("CT_small*")
        assert 1 == len(paths)
        assert "pydicom/data/test_files" in self.as_posix(paths[0])

    def test_get_testdata_files_local_external_and_cache(self):
        """Test that local, external and cache paths retrieved OK."""
        paths = get_testdata_files("693*")
        assert 7 == len(paths)
        # Local preferred first
        assert "pydicom/data/test_files" in self.as_posix(paths[0])
        # External source preferred second
        assert "data_store/data" in self.as_posix(paths[1])
        # Cache source preferred last
        assert ".pydicom/data" in self.as_posix(paths[4])

    def test_get_testdata_files_hash_match(self):
        """Test that the external source is not used when hash is not OK."""
        p = Path(DATA_SRC / "693_UNCI.dcm")
        ext_hash = calculate_file_hash(p)
        ref_hash = get_cached_filehash(p.name)
        assert ext_hash == ref_hash
        fpaths = get_testdata_files("693_UNCI*")
        fpaths = [self.as_posix(p) for p in fpaths]
        assert 2 == len(fpaths)
        assert "data_store/data" in fpaths[0]
        assert ".pydicom/data" in fpaths[1]

    def test_get_testdata_files_hash_mismatch(self, data_fs):
        """Test that the external source is not used when hash is not OK."""
        p = Path(DATA_SRC / "693_UNCI.dcm")
        with open(p, "wb") as f:
            f.write(b"\x00\x01")

        ext_hash = calculate_file_hash(p)
        ref_hash = get_cached_filehash(p.name)
        assert ext_hash != ref_hash
        fpaths = get_testdata_files("693_UNCI*")
        fpaths = [self.as_posix(p) for p in fpaths]
        assert 1 == len(fpaths)
        assert ".pydicom/data" in fpaths[0]

    def test_get_testdata_files_external_ignore_hash(self, data_fs):
        """Test that non-pydicom-data external source ignores hash check."""
        external_data_sources()["mylib"] = external_data_sources()["pydicom-data"]
        p = Path(DATA_SRC / "693_UNCI.dcm")
        with open(p, "wb") as f:
            f.write(b"\x00\x01")

        ext_hash = calculate_file_hash(p)
        ref_hash = get_cached_filehash(p.name)
        assert ext_hash != ref_hash
        fpaths = get_testdata_files("693_UNCI*")
        fpaths = [self.as_posix(p) for p in fpaths]
        assert 2 == len(fpaths)
        assert "data_store/data" in fpaths[0]
        assert ".pydicom/data" in fpaths[1]


@pytest.mark.skipif(EXT_PYDICOM, reason="pydicom-data installed")
class TestDownload:
    """Tests for the download module."""

    def test_get_testdata_file_no_download(self, recwarn):
        """
        Test that `data_path_with_download`
        is not called when `download=False`.
        """
        assert get_testdata_file("693_UNCI.dcm", download=False) is None
        assert not recwarn.list

    def test_get_testdata_file_network_outage(self, download_failure):
        """Test a network outage when using get_testdata_file."""
        msg = r"A download failure occurred while attempting to retrieve 693_UNCI.dcm"
        with pytest.warns(UserWarning, match=msg):
            assert get_testdata_file("693_UNCI.dcm") is None

    def test_get_testdata_files_network_outage(self, download_failure):
        """Test a network outage when using get_testdata_files."""
        msg = (
            r"One or more download failures occurred, the list of matching "
            r"file paths may be incomplete"
        )
        with pytest.warns(UserWarning, match=msg):
            assert [] == get_testdata_files("693_UN*")


def test_fetch_data_files(data_fs):
    """Test fetch_data_files()."""
    # Remove a single file from the temporary cache
    cache = Path(get_data_dir())
    path = cache / "SC_rgb_expb.dcm"  # smallest file in cache
    if path.exists():
        path.unlink()

    assert not path.exists()
    fetch_data_files(data_dir=cache)
    assert path.exists()


def test_fetch_data_files_download_failure(download_failure):
    """Test fetch_data_files() with download failures."""
    msg = r"An error occurred downloading the following files:"
    with pytest.raises(RuntimeError, match=msg):
        fetch_data_files()


def test_hashes():
    """Test for duplicates in hashes.json."""
    # We can't have case mixes because windows filenames are case insensitive
    root = Path(DATA_ROOT)
    with open(root / "hashes.json") as f:
        filenames = json.load(f).keys()
        filenames = [name.lower() for name in filenames]
        assert len(set(filenames)) == len(filenames)


def test_urls():
    """Test for duplicates in urls.json."""
    # We can't have case mixes because windows filenames are case insensitive
    root = Path(DATA_ROOT)
    with open(root / "urls.json") as f:
        filenames = json.load(f).keys()
        filenames = [name.lower() for name in filenames]
        assert len(set(filenames)) == len(filenames)
