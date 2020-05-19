# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Tests for the TravisCI testing environments.

The current pydicom testing environments are as follows:

* conda:
  * Python 3.5, 3.6, 3.7:
    * no additional packages
    * numpy
    * numpy, gdcm (newest and v2.8.4)
    * numpy, pillow (jpg, jpg2k)
    * numpy, jpeg-ls
    * numpy, pillow (jpg, jpg2k), jpeg-ls
    * numpy, pillow (jpg, jpg2k), jpeg-ls, gdcm
    * As with 2.7
  * Python 3.7:
    * numpy, pillow (jpg)
* pypy
  * Python 3.5:
    * no additional packages
    * numpy
* ubuntu


Environmental variables
-----------------------
DISTRIB: conda, pypy, ubuntu
PYTHON_VERSION: 3.5, 3.6, 3.7
NUMPY: true, false
PILLOW: jpeg, both, false
JPEG_LS: false, true
GDCM: false, true, old
"""
import os
import platform
import sys

import pytest


def get_envar(envar):
    """Return the value of the environmental variable `envar`.

    Parameters
    ----------
    envar : str
        The environmental variable to check for.

    Returns
    -------
    str or None
        If the envar is present then return its value otherwise returns None.
    """
    if envar in os.environ:
        return os.environ.get(envar)

    return None


IN_TRAVIS = get_envar("TRAVIS") == 'true'


@pytest.mark.skipif(not IN_TRAVIS, reason="Tests not running in Travis")
class TestBuilds:
    """Tests for the testing builds in Travis CI."""
    def test_distribution(self):
        """Test that the distribution is correct."""
        distrib = get_envar('DISTRIB')
        if not distrib:
            raise RuntimeError("No 'DISTRIB' envar has been set")

        if distrib == 'conda':
            # May not be robust
            assert os.path.exists(os.path.join(sys.prefix, 'conda-meta'))
            assert "CPython" in platform.python_implementation()
        elif distrib == 'pypy':
            assert 'PyPy' in platform.python_implementation()
        elif distrib == 'ubuntu':
            assert "CPython" in platform.python_implementation()
        else:
            raise NotImplementedError("Unknown 'DISTRIB' value")

    def test_python_version(self):
        """Test that the python version is correct."""
        version = get_envar('PYTHON_VERSION')
        if not version:
            raise RuntimeError("No 'PYTHON_VERSION' envar has been set")

        version = tuple([int(vv) for vv in version.split('.')])
        assert version[:2] == sys.version_info[:2]

    def test_numpy(self):
        """Test that numpy is absent/present."""
        have_np = get_envar('NUMPY')
        if not have_np:
            raise RuntimeError("No 'NUMPY' envar has been set")

        if have_np == 'true':
            try:
                import numpy
            except ImportError:
                pytest.fail("NUMPY is true but numpy is not importable")
        elif have_np == 'false':
            with pytest.raises(ImportError):
                import numpy
        else:
            raise NotImplementedError(
                "Unknown 'NUMPY' value of '{}'".format(have_np)
            )

    def test_pillow(self):
        """Test that pillow is absent/present with the correct plugins."""
        have_pillow = get_envar('PILLOW')
        if not have_pillow:
            raise RuntimeError("No 'PILLOW' envar has been set")

        if have_pillow == 'both':
            try:
                from PIL import features
            except ImportError:
                pytest.fail("PILLOW is both but PIL is not importable")

            assert features.check_codec("jpg")
            assert features.check_codec("jpg_2000")
        elif have_pillow == 'jpeg':
            try:
                from PIL import features
            except ImportError:
                pytest.fail("PILLOW is both but PIL is not importable")

            assert features.check_codec("jpg")
            assert not features.check_codec("jpg_2000")
        elif have_pillow == 'false':
            with pytest.raises(ImportError):
                import PIL
        else:
            raise NotImplementedError(
                "Unknown 'PILLOW' value of '{}'".format(have_pillow)
            )

    def test_jpegls(self):
        """Test that jpeg-ls is absent/present."""
        have_jpegls = get_envar('JPEG_LS')
        if not have_jpegls:
            raise RuntimeError("No 'JPEG_LS' envar has been set")

        if have_jpegls == 'true':
            try:
                import jpeg_ls
            except ImportError:
                pytest.fail("JPEG_LS is true but jpeg_ls is not importable")
        elif have_jpegls == 'false':
            with pytest.raises(ImportError):
                import jpeg_ls
        else:
            raise NotImplementedError(
                "Unknown 'JPEG_LS' value of '{}'".format(have_jpegls)
            )

    def test_gdcm(self):
        """Test that gdcm is absent/present."""
        have_gdcm = get_envar('GDCM')
        if not have_gdcm:
            raise RuntimeError("No 'GDCM' envar has been set")

        if have_gdcm == 'true':
            try:
                import gdcm
            except ImportError:
                pytest.fail("GDCM is true but gdcm is not importable")
        elif have_gdcm == 'false':
            with pytest.raises(ImportError):
                import gdcm
        elif have_gdcm == 'old':
            try:
                import gdcm
            except ImportError:
                pytest.fail("GDCM is 'old' but gdcm is not importable")
            assert gdcm.Version_GetVersion() == '2.8.4'
        else:
            raise NotImplementedError(
                "Unknown 'GDCM' value of '{}'".format(have_gdcm)
            )
