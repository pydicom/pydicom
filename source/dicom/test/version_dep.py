# version_dep.py
"""Holds test code that is dependent on certain python versions"""
# Copyright (c) 2009 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

from __future__ import with_statement # so will compile under python 2.5 without error
import warnings

def capture_warnings(function, *func_args, **func_kwargs):
    """Capture and function result and warnings.
    For python > 2.5
    """
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = function(*func_args, **func_kwargs)
        all_warnings = w
    return result, [str(warning.message) for warning in all_warnings]
