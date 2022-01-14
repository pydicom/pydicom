# Copyright 2008-2022 pydicom authors. See LICENSE file for details.
"""Utility functions for JPEG 2000 (ISO/IEC 15444-1) compressed pixel data."""

from struct import unpack
from typing import Dict, Any, List


def _as_str(src: bytes, cutoff: int = 32) -> str:
    """Return bytes as a formatted str."""
    return " ".join([f"{b:02X}" for b in src[:cutoff]])


def debug_jpeg2k(src: bytes) -> List[str]:
    """Return JPEG 2000 debugging information.

    Parameters
    ----------
    src : bytes
        The JPEG 2000 codestream.

    Returns
    -------
    list of str
    """
    s = []

    if src[0:2] != b"\xff\x4f":
        s.append("No SOI (FF 4F) marker found @ offset 0")
        s.append(f"  {_as_str(src)}")
        return s

    s.append("SOI (FF 4F) marker found @ offset 0")

    # SIZ segment
    if src[2:4] != b"\xff\x51":
        s.append("No SIZ (FF 51) marker found @ offset 2")
        s.append(f"  {_as_str(src)}")
        return s

    s.append("SIZ (FF 51) segment @ offset 2")
    xsiz, ysiz = unpack(">2I", src[8:16])
    s.append(f"  Rows: {ysiz}")
    s.append(f"  Columns: {xsiz}")

    csiz = unpack(">H", src[40:42])[0]
    s.append(f"  Components:")
    idx = 42
    for ii in range(csiz):
        ssiz = src[idx]
        idx += 3
        if ssiz & 0x80:
            s.append(f"    {ii}: signed, precision {(ssiz & 0x7F) + 1}")
        else:
            s.append(f"    {ii}: unsigned, precision {ssiz + 1}")

    # COD segment
    if src[idx:idx + 2] != b"\xFF\x52":
        s.append(f"No COD (FF 52) marker found @ offset {idx}")
        s.append(f"  {_as_str(src[idx:])}")
        return s

    s.append(f"COD (FF 52) segment found @ offset {idx}")

    # COD: SGcod
    mct = ["none", "applied"][src[idx + 8]]
    s.append(f"  Multiple component transform: {mct}")

    # COD: SPcod
    transform = ["9-7 irreversible", "5-3 reversible"][src[idx + 13]]
    s.append(f"  Wavelet transform: {transform}")

    return s


def parse_jpeg2k(src: bytes) -> Dict[str, Any]:
    """Return a dict containing JPEG 2000 component parameters.

    .. versionadded:: 2.1

    Parameters
    ----------
    src : bytes
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
        if src[0:2] != b"\xff\x4f":
            return {}

        # SIZ is required to be the second marker - Figure A-3 in 15444-1
        if src[2:4] != b"\xff\x51":
            return {}

        # See 15444-1 A.5.1 for format of the SIZ box and contents
        ssiz = src[42]
        if ssiz & 0x80:
            return {"precision": (ssiz & 0x7F) + 1, "is_signed": True}

        return {"precision": ssiz + 1, "is_signed": False}
    except (IndexError, TypeError):
        pass

    return {}
