# misc.py
"""Miscellaneous helper functions"""
# Copyright (c) 2009 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom
import os.path

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


def is_dicom(file):
    """Boolean specifying if file is a proper DICOM file.

    This function is a pared down version of read_preamble meant for a fast return.
    The file is read for a proper preamble ('DICM'), returning True if so,
    and False otherwise. This is a conservative approach.

    Parameters
    ----------
    file : str
        The path to the file.

    See Also
    --------
    filereader.read_preamble
    filereader.read_partial
    """
    # TODO: add a force parameter maybe?
    if not os.path.isfile(file):
        raise IOError("File passed was not a valid file")
        # TODO: error is only in Py3; what's a better Py2/3 error?
    fp = open(file, 'rb')
    preamble = fp.read(0x80)
    magic = fp.read(4)
    if magic == b"DICM":
        return True
    else:
        return False
