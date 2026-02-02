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


def _double_edits(keyword: str) -> set[str]:
    """Return candidates that are two edits away from `keyword`."""
    return set(e2 for e1 in _single_edits(keyword) for e2 in _single_edits(e1))


def find_keyword_candidates(
    keyword: str,
    allowed_edits: int = 1,
    max_candidates: None | int = 1,
) -> list[str]:
    """Generate possible spelling corrections for `keyword`.

    ..versionadded:: 3.1

    Parameters
    ----------
    keyword : str
        The misspelled element keyword to find candidates for.
    allowed_edits : int, optional
        The number of edits allowable when searching for candidates, default ``1``.
    max_candidates : int | None, optional
        The maximum number of candidates to return, default ``1``. If ``None`` then
        return all candidates.

    Returns
    -------
    list[str]
        The candidates for the keyword, may be an empty string if no candidates are
        found.
    """
    from pydicom.datadict import keyword_dict

    keywords = keyword_dict.keys()

    # Adapted from https://www.norvig.com/spell-correct.html
    candidates = [w for w in _single_edits(keyword) if w in keywords]
    if candidates and allowed_edits == 1:
        return sorted(candidates)[:max_candidates]

    candidates.extend([w for w in _double_edits(keyword) if w in keywords])
    if candidates:
        return sorted(list(set(candidates)))[:max_candidates]

    return []


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


def _single_edits(keyword: str) -> set[str]:
    """Return candidates that are a single edit away from `keyword`."""
    letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXY"
    splits = [(keyword[:i], keyword[i:]) for i in range(len(keyword) + 1)]
    deletes = [L + R[1:] for L, R in splits if R]
    transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1]
    replaces = [L + c + R[1:] for L, R in splits if R for c in letters]
    inserts = [L + c + R for L, R in splits for c in letters]
    return set(deletes + transposes + replaces + inserts)


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
