# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""pydicom data manager"""

from .data_manager import get_charset_files
from .data_manager import get_testdata_files
from .data_manager import DATA_ROOT

__all__ = ['get_charset_files',
           'get_testdata_files']
