# dump.py
"""Utility functions used in debugging writing and reading"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

from __future__ import print_function
from io import BytesIO


def print_character(ordchr):
    """Return a printable character, or '.' for non-printable ones."""
    if 31 < ordchr < 126 and ordchr != 92:
        return chr(ordchr)
    else:
        return '.'


def filedump(filename, start_address=0, stop_address=None):
    """Dump out the contents of a file to a standard hex dump 16 bytes wide"""
    fp = file(filename, 'rb')
    return hexdump(fp, start_address, stop_address)


def datadump(data):
    stop_address = len(data) + 1
    fp = BytesIO(data)
    print(hexdump(fp, 0, stop_address))


def hexdump(file_in, start_address=0, stop_address=None, showAddress=True):
    """Return a formatted string of hex bytes and characters in data.

    This is a utility function for debugging file writing.

    file_in -- a file-like object to get the bytes to show from"""

    str_out = BytesIO()
    byteslen = 16 * 3 - 1  # space taken up if row has a full 16 bytes
    blanks = ' ' * byteslen

    file_in.seek(start_address)
    data = True   # dummy to start the loop
    while data:
        if stop_address and file_in.tell() > stop_address:
            break
        if showAddress:
            str_out.write("%04x : " % file_in.tell())  # address at start of line
        data = file_in.read(16)
        if not data:
            break
        row = [ord(x) for x in data]  # need ord twice below so convert once
        byte_string = ' '.join(["%02x" % x for x in row])  # string of two digit hex bytes
        str_out.write(byte_string)
        str_out.write(blanks[:byteslen - len(byte_string)])  # if not 16, pad
        str_out.write('  ')
        str_out.write(''.join([print_character(x) for x in row]))  # character rep of bytes
        str_out.write("\n")

    return str_out.getvalue()


def pretty_print(ds, indent=0, indent_chars="   "):
    """Print a dataset directly, with indented levels.

    This is just like Dataset._pretty_str, but more useful for debugging as it
    prints each item immediately rather than composing a string, making it
    easier to immediately see where an error in processing a dataset starts.

    """

    indentStr = indent_chars * indent
    nextIndentStr = indent_chars * (indent + 1)
    for data_element in ds:
        if data_element.VR == "SQ":   # a sequence
            fmt_str = "{0:s}{1:s} {2:s}  {3:d} item(s) ---"
            new_str = fmt_str.format(indentStr, str(data_element.tag),
                                     data_element.name, len(data_element.value))
            print(new_str)
            for dataset in data_element.value:
                pretty_print(dataset, indent + 1)
                print(nextIndentStr + "---------")
        else:
            print(indentStr + repr(data_element))


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
