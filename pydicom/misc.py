# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Miscellaneous helper functions"""


_size_factors = dict(KB=1024, MB=1024 * 1024, GB=1024 * 1024 * 1024)


def size_in_bytes(expr):
    """Return the number of bytes for `defer_size` argument in
    :func:`~pydicom.filereader.dcmread`.
    """
    if expr is None or expr == float('inf'):
        return None
    try:
        return int(expr)
    except ValueError:
        unit = expr[-2:].upper()
        if unit in _size_factors.keys():
            val = float(expr[:-2]) * _size_factors[unit]
            return val
        else:
            raise ValueError(
                "Unable to parse length with unit '{0:s}'".format(unit))


def is_dicom(file_path):
    """Return ``True`` if the file at `file_path` is a DICOM file.

    This function is a pared down version of
    :func:`~pydicom.filereader.read_preamble` meant for a fast return. The
    file is read for a conformant preamble ('DICM'), returning
    ``True`` if so, and ``False`` otherwise. This is a conservative approach.

    Parameters
    ----------
    file_path : str
        The path to the file.

    See Also
    --------
    filereader.read_preamble
    filereader.read_partial
    """
    with open(file_path, 'rb') as fp:
        fp.read(0x80)  # preamble
        magic = fp.read(4)
    return magic == b"DICM"
