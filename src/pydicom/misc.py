# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Miscellaneous helper functions"""

import logging
from itertools import groupby
from pathlib import Path
import warnings


LOGGER = logging.getLogger("pydicom")


_size_factors = {
    "kb": 1000,
    "mb": 1000 * 1000,
    "gb": 1000 * 1000 * 1000,
    "kib": 1024,
    "mib": 1024 * 1024,
    "gib": 1024 * 1024 * 1024,
}


def size_in_bytes(expr: int | float | str | None) -> None | float | int:
    """Return the number of bytes for `defer_size` argument in
    :func:`~pydicom.filereader.dcmread`.
    """
    if expr is None or expr == float("inf"):
        return None

    if isinstance(expr, int | float):
        return expr

    try:
        return int(expr)
    except ValueError:
        pass

    value, unit = ("".join(g) for k, g in groupby(expr, str.isalpha))
    if unit.lower() in _size_factors:
        return float(value) * _size_factors[unit.lower()]

    raise ValueError(f"Unable to parse length with unit '{unit}'")


def is_dicom(file_path: str | Path) -> bool:
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
    with open(file_path, "rb") as fp:
        fp.read(128)  # preamble
        return fp.read(4) == b"DICM"


def warn_and_log(
    msg: str, category: type[Warning] | None = None, stacklevel: int = 1
) -> None:
    """Send warning message `msg` to the logger.

    Parameters
    ----------
    msg : str
        The warning message.
    category : type[Warning] | None, optional
        The warning category class, defaults to ``UserWarning``.
    stacklevel : int, optional
        The stack level to refer to, relative to where `warn_and_log` is used.
    """
    LOGGER.warning(msg)
    warnings.warn(msg, category, stacklevel=stacklevel + 1)
