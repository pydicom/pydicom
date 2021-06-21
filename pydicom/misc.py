# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Miscellaneous helper functions"""

from pathlib import Path
from typing import Optional, Union


_size_factors = {
    "KB": 1000, "MiB": 1000 * 1000, "GiB": 1000 * 1000 * 1000,
    "KiB": 1024, "MiB": 1024 * 1024, "GiB": 1024 * 1024 * 1024,
}


def size_in_bytes(expr: Optional[str]) -> Union[None, float, int]:
    """Return the number of bytes for `defer_size` argument in
    :func:`~pydicom.filereader.dcmread`.
    """
    if expr is None or expr == float('inf'):
        return None

    try:
        return int(expr)
    except ValueError:
        pass

    unit = expr[-2:].upper()
    if unit in _size_factors.keys():
        return float(expr[:-2]) * _size_factors[unit]

    raise ValueError(f"Unable to parse length with unit '{unit}'")


def is_dicom(file_path: Union[str, Path]) -> bool:
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
        fp.read(128)  # preamble
        return fp.read(4) == b"DICM"
