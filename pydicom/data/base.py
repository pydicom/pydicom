"""pydicom data manager"""
#
# Copyright (c) 2008-2012 Darcy Mason
# Copyright (c) 2017 pydicom AUTHORS
# This file is part of pydicom, released under a modified MIT license.
#    See the file LICENSE included with this distribution, also
#    available at https://github.com/pydicom/pydicom
#

from os.path import abspath, dirname, join
from .utils import get_files


DATA_ROOT = abspath(dirname(__file__))


def get_testdata_files(pattern=None):
    """Return test data files from pydicom data root

    Parameters
    ----------
    pattern : string
            A string pattern to filter the files

    Returns
    ----------
    files : list of test data files

    """

    data_path = join(ROOT_PATH, 'test_files')
    return get_files(bases=data_path, pattern=pattern)


def get_charset_files(pattern=None):
    """Return charset files from pydicom data root

    Parameters
    ----------
    pattern : string
            A string pattern to filter the files

    Returns
    ----------
    files : list of charset data files

    """

    data_path = join(ROOT_PATH, 'charset_files')
    return get_files(bases=data_path, pattern=pattern)
