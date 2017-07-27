"""pydicom data manager"""
#
# Copyright (c) 2008-2012 Darcy Mason
# Copyright (c) 2017 pydicom AUTHORS
# This file is part of pydicom, released under a modified MIT license.
#    See the file LICENSE included with this distribution, also
#    available at https://github.com/pydicom/pydicom
#

import fnmatch
import os

from .utils import get_files


def get_datadir():
    return os.path.abspath(os.path.dirname(__file__))


def get_testdata_base():
    return os.path.join(get_datadir(), 'test_files')


def get_charset_base():
    return os.path.join(get_datadir(), 'charset_files')


'''

Data get functions.

For each of the below, a complete list of files is returned.
Note the distinction between "get" (returning a list) and
what might be interpreted as reading in the files (load).
These functions serve to only provide the paths.

Optionally, the user can specify a pattern to filter by.

'''


def get_charset_files(pattern=None):
    charset_base = get_charset_base()
    return get_files(bases=charset_base,
                     pattern=pattern)


def get_testdata_files(pattern=None):
    testdata_base = get_testdata_base()
    return get_files(bases=testdata_base,
                     pattern=pattern)
