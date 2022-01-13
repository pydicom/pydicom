# Copyright 2008-2022 pydicom authors. See LICENSE file for details.
"""Utility functions for JPEG (ISO/IEC 10918-1) compressed pixel data."""

from struct import Struct
from typing import Dict, Any, Tuple


_UNPACK_UINT = Struct(">H").unpack
_UNPACK_UCHAR = Struct("B").unpack


# 0xFFEO to 0xFFEF
_APP_MARKERS = {bytes([255, x]) for x in range(224, 240)}
# 0xFFC0 to 0xFFC3, 0xFFC5 to 0xFFC7, 0xFFC9 to 0xFFCF
_sof_markers = [bytes([255, x]) for x in range(192, 208)]
_sof_markers.remove(b"\xFF\xC4")
_sof_markers.remove(b"\xFF\xC8")
_SOF_MARKERS = {x for x in _sof_markers}
_MISC_MARKERS = {
    b"\xFF\xFE",  # COM
    b"\xFF\xCC",  # DAC
    b"\xFF\xDE",  # DHP
    b"\xFF\xC4",  # DHT
    b"\xFF\xDB",  # DQT
    b"\xFF\xDD",  # DRI
}
_MARKERS = _APP_MARKERS | _SOF_MARKERS | _MISC_MARKERS


def _find_marker(src: bytes, idx: int = 0) -> Tuple[bytes, int]:
    """Find and return the next JPEG segment marker.

    This function will only work if `idx` is before the SOS marker.

    Parameters
    ----------
    src : bytes
        The JPEG codestream to search.
    idx : int
        The starting offset for the search.

    Returns
    -------
    Tuple[bytes, int]
        If a marker was found, its value and offset.

    Raises
    ------
    ValueError
        If no markers were found before the end of the data.
    """
    # ISO/IEC 10918-1, Section B.1.1.2:
    #   Any marker may optionally be preceded by any number of 0xFF fill bytes
    if src[idx] != 255:
        raise ValueError(f"No JPEG marker found at offset {idx}")

    msg = f"No JPEG markers found after offset {idx}"

    eof = len(src) - 2
    while src[idx] == 255 and idx <= eof:
        if src[idx + 1] == 255:
            idx += 1
            continue

        break

    if idx == eof:
        raise ValueError(msg)

    return src[idx : idx + 2], idx


def _get_bit(b: bytes, idx: int) -> int:
    """Return the value of the bit at `index` of `byte`.

    Parameters
    ----------
    b : bytes
        The value to process.
    idx : int
        The index of the bit to return, where index ``0`` is the most
        significant bit and index ``7`` is the least significant.

    Returns
    -------
    int
        The value of the bit (0 or 1) at `idx`.
    """
    return b[0] >> (7 - idx) & 1


def parse_jpeg(src: bytes) -> Dict[str, Any]:
    """Return a dict containing JPEG 10918-1 image parameters.

    .. versionadded:: 2.3

    Parameters
    ----------
    src : bytes
        The JPEG (ISO/IEC 10918-1) codestream to be parsed.

    Returns
    -------
    Dict[str, Any]
        A dict containing parameters for the JPEG codestream, or an empty
        dict if unable to parse the data. Keys are:

        * ``"SOF"``: a :class:`dict` of the SOF marker segment, with keys

            * ``"SOFn"``: :class:`bytes` - the codestream's SOFn marker
            * ``"P"``: :class:`int` - the sample precision in bits
            * ``"Y"``: :class:`int` - the maximum number of lines in the image
            * ``"X"``: :class:`int` - the maximum number of samples per line
            * ``"Nf"``: :class:`int` - the number of components in the frame
            * ``"Components"``: List[Tuple[int, int, int]] - the component ID,
              horizontal sampling factor and vertical sampling factor for each
              component
        * ``"APPn"``: a :class:`dict` of APP marker segments present in the
          codestream, as ``{APPn (bytes): APi, application data (bytes)}``
        * ``"COM"``: :clas:`bytes` - the COM marker segment contents, if
          present
    """
    try:
        # First marker must be the SOI marker - if not then wrong format
        marker, idx = _find_marker(src)
        if marker != b"\xFF\xD8":
            return {}

        d: Dict[str, Any] = {}

        # Any of the following marker segments **may** be present in any order
        # and with no limit on the number of segments:
        #   DQT, DHT, DAC, DRI, COM, APP
        # Then DHP will be present if hierarchical mode, otherwise absent
        # Then SOF marker
        marker, idx = _find_marker(src, idx + 2)
        while marker in _MARKERS:
            length = _UNPACK_UINT(src[idx + 2 : idx + 4])[0] - 2

            if marker in _APP_MARKERS:
                # Parse APP marker - Section B.2.4.6
                app = d.setdefault("APPn", {})
                app[marker] = src[idx + 4 : idx + 4 + length]
            elif marker == b"\xFF\xFE":
                d["COM"] = src[idx + 4 : idx + 4 + length]
            elif marker in _SOF_MARKERS:
                # Parse SOF frame header - Section B.2.2
                # SOF | Lf | P |  Y |  X | Nf | Components |
                #  16 | 16 | 8 | 16 | 16 |  8 |     Nf * 3 | bits
                #   0 |  2 | 4 |  5 |  7 |  9 |         10 |offset
                sof = d.setdefault("SOF", {})
                # SOF marker
                sof["SOFn"] = marker
                # Sample precision in bits
                sof["P"] = _UNPACK_UCHAR(src[idx + 4 : idx + 5])[0]
                # Number of lines
                sof["Y"] = _UNPACK_UINT(src[idx + 5 : idx + 7])[0]
                # Number of samples per line
                sof["X"] = _UNPACK_UINT(src[idx + 7 : idx + 9])[0]
                # Number of image components
                sof["Nf"] = _UNPACK_UCHAR(src[idx + 9 : idx + 10])[0]

                sof["Components"] = []
                idx += 10
                for _ in range(sof["Nf"]):
                    # Ci | Hi | Vi | Tqi
                    #  8 |  4 |  4 |   8 | bits
                    #  0 |       1 |   2 | offset
                    # Ci, component ID
                    c_id = src[idx : idx + 1]
                    # Hi and Vi, horizontal and vertical sampling factors
                    h_samples, v_samples = _split_byte(src[idx + 1 : idx + 2])
                    idx += 3

                    sof["Components"].append((c_id, h_samples, v_samples))

                return d

            marker, idx = _find_marker(src, idx + 4 + length)
    except:
        pass

    return {}


def _split_byte(b: bytes) -> Tuple[int, int]:
    """Return the 8-bit `byte` as two 4-bit unsigned integers.

    Parameters
    ----------
    b : bytes
        The byte to split, if more than one byte is supplied only the first
        will be split.

    Returns
    -------
    2-tuple of int
        The (4 most significant, 4 least significant) bits of `byte` as ``(int,
        int)``.
    """
    return b[0] >> 4, 0b00001111 & b[0]
