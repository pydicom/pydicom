# misc.py
"""Miscellaneous helper functions"""
# Copyright (c) 2009 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

_size_factors = dict(KB=1024, MB=1024 * 1024, GB=1024 * 1024 * 1024)


def size_in_bytes(expr):
    """Return the number of bytes for a defer_size argument to read_file()
    """
    try:
        return int(expr)
    except ValueError:
        unit = expr[-2:].upper()
        if unit in _size_factors.keys():
            val = float(expr[:-2]) * _size_factors[unit]
            return val
        else:
            raise ValueError("Unable to parse length with unit '{0:s}'".format(unit))
