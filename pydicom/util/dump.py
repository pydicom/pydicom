# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Utility functions used in debugging writing and reading"""

from io import BytesIO
import pathlib.Path
from typing import Union, Optional, BinaryIO, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from pydicom.dataset import Dataset


def print_character(char: int) -> str:
    """Return a printable character, or '.' for non-printable ones."""
    if 31 < char < 126 and char != 92:
        return f"{char:02X}"

    return '.'


def filedump(
    filename: Union[str, pathlib.Path],
    start_address: int = 0,
    stop_address: Optional[int] = None,
) -> str:
    """Dump out the contents of a file to a
       standard hex dump 16 bytes wide"""

    with open(filename, 'rb') as f:
        return hexdump(f, start_address, stop_address)


def datadump(data: bytes) -> None:
    stop_address = len(data) + 1
    fp = BytesIO(data)
    print(hexdump(fp, 0, stop_address))


def hexdump(
    f: BinaryIO,
    start_address: int = 0,
    stop_address: Optional[int] = None,
    show_address: bool = True,
) -> str:
    """Return a formatted string of hex bytes and characters in data.

    This is a utility function for debugging file writing.

    file_in -- a file-like object to get the bytes to show from"""

    s = []
    # space taken up if row has a full 16 bytes
    byteslen = 16 * 3 - 1
    blanks = ' ' * byteslen

    f.seek(start_address)
    while True:
        if stop_address and f.tell() > stop_address:
            break

        if show_address:
            # address at start of line
            s.append(f"{f.tell():04X}")

        data = f.read(16)
        if not data:
            break

        # string of two digit hex bytes
        b = ' '.join([f"{x:02X}" for x in data])
        s.append(f"{b:<16}")  # if not 16, pad
        s.append('  ')

        # character repr of bytes
        s.append(''.join([print_character(x) for x in data]))
        s.append("\n")

    return ''.join(s)


def pretty_print(
    ds: "Dataset", indent: int = 0, indent_chars: str = "   "
) -> None:
    """Print a dataset directly, with indented levels.

    This is just like Dataset._pretty_str, but more useful for debugging as it
    prints each item immediately rather than composing a string, making it
    easier to immediately see where an error in processing a dataset starts.

    """

    indentStr = indent_chars * indent
    nextIndentStr = indent_chars * (indent + 1)
    for elem in ds:
        if elem.VR == "SQ":  # a sequence
            print(
                f"{indentStr}{elem.tag} {elem.name}  {elem.value:d} "
                "item(s) ---"
            )
            for dataset in elem.value:
                pretty_print(dataset, indent + 1)
                print(nextIndentStr + "---------")
        else:
            print(indentStr + repr(elem))


if __name__ == "__main__":
    import sys
    filename = sys.argv[1]
    start_address = 0
    stop_address = None
    if len(sys.argv) > 2:  # then have start address
        start_address = eval(sys.argv[2])
    if len(sys.argv) > 3:
        stop_address = eval(sys.argv[3])

    print(filedump(filename, start_address, stop_address))
