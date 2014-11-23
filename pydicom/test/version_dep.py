# version_dep.py
"""Holds test code that is dependent on certain python versions"""
# Copyright (c) 2009-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import warnings


def capture_warnings(function, *func_args, **func_kwargs):
    """Capture function result and warnings.
    """
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = function(*func_args, **func_kwargs)
        all_warnings = w
    return result, [str(warning.message) for warning in all_warnings]
