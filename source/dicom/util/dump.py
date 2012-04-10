# dump.py
"""Utility functions for seeing contents of files, etc, to debug writing and reading"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

from io import BytesIO

def PrintCharacter(ordchr):
    """Return a printable character, or '.' for non-printable ones."""
    if 31 < ordchr < 126 and ordchr != 92:
        return chr(ordchr)
    else:
        return '.'


def filedump(filename, StartAddress=0, StopAddress=None):
    """Dump out the contents of a file to a standard hex dump 16 bytes wide"""
    fp = file(filename, 'rb')
    return hexdump(fp, StartAddress, StopAddress)

def datadump(data):
    StopAddress = len(data) + 1
    fp = BytesIO(data)
    print hexdump(fp, 0, StopAddress)

def hexdump(file_in, StartAddress=0, StopAddress=None, showAddress=True):
    """Return a formatted string of hex bytes and characters in data.

    This is a utility function for debugging file writing.

    file_in -- a file-like object to get the bytes to show from"""

    str_out = BytesIO()
    byteslen = 16*3-1 # space taken up if row has a full 16 bytes
    blanks = ' ' * byteslen

    file_in.seek(StartAddress)
    data = True   # dummy to start the loop
    while data:
        if StopAddress and file_in.tell() > StopAddress:
            break
        if showAddress:
            str_out.write("%04x : " % file_in.tell())  # address at start of line
        data = file_in.read(16)
        if not data:
            break
        row = [ord(x) for x in data]  # need ord twice below so convert once
        byte_string = ' '.join(["%02x" % x for x in row])  # string of two digit hex bytes
        str_out.write(byte_string)
        str_out.write(blanks[:byteslen-len(byte_string)])  # if not 16, pad
        str_out.write('  ')
        str_out.write(''.join([PrintCharacter(x) for x in row]))  # character rep of bytes
        str_out.write("\n")

    return str_out.getvalue()

def PrettyPrint(ds, indent=0, indentChars="   "):
    """Print a dataset directly, with indented levels.

    This is just like Dataset._PrettyStr, but more useful for debugging as it
    prints each item immediately rather than composing a string, making it
    easier to immediately see where an error in processing a dataset starts.

    """

    strings = []
    indentStr = indentChars * indent
    nextIndentStr = indentChars *(indent+1)
    for data_element in ds:
        if data_element.VR == "SQ":   # a sequence
            new_str = indentStr + str(data_element.tag) + "  %s   %i item(s) ---- " % ( data_element.name, len(data_element.value))
            print new_str
            for dataset in data_element.value:
                PrettyPrint(dataset, indent+1)
                print nextIndentStr + "---------"
        else:
            print indentStr + repr(data_element)


if __name__ == "__main__":
    import sys
    filename = sys.argv[1]
    StartAddress = 0
    StopAddress = None
    if len(sys.argv) > 2:  # then have start address
        StartAddress = eval(sys.argv[2])
    if len(sys.argv) > 3:
        StopAddress = eval(sys.argv[3])

    print filedump(filename, StartAddress, StopAddress)
