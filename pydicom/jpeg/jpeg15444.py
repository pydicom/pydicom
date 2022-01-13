# Copyright 2008-2022 pydicom authors. See LICENSE file for details.
"""Utility functions for JPEG 2000 (ISO/IEC 15444-1) compressed pixel data."""

from typing import Dict, Any


def parse_jpeg2k(codestream: bytes) -> Dict[str, Any]:
    """Return a dict containing JPEG 2000 component parameters.

    .. versionadded:: 2.1

    Parameters
    ----------
    codestream : bytes
        The JPEG 2000 (ISO/IEC 15444-1) codestream to be parsed.

    Returns
    -------
    dict
        A dict containing parameters for the first component sample in the
        JPEG 2000 `codestream`, or an empty dict if unable to parse the data.
        Available parameters are ``{"precision": int, "is_signed": bool}``.
    """
    try:
        # First 2 bytes must be the SOC marker - if not then wrong format
        if codestream[0:2] != b"\xff\x4f":
            return {}

        # SIZ is required to be the second marker - Figure A-3 in 15444-1
        if codestream[2:4] != b"\xff\x51":
            return {}

        # See 15444-1 A.5.1 for format of the SIZ box and contents
        ssiz = codestream[42]
        if ssiz & 0x80:
            return {"precision": (ssiz & 0x7F) + 1, "is_signed": True}

        return {"precision": ssiz + 1, "is_signed": False}
    except (IndexError, TypeError):
        pass

    return {}
