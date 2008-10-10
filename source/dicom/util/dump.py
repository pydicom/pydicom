# dump.py
"""Utility functions for seeing contents of files, etc, to debug writing and reading"""

# Copyright 2008, Darcy Mason
# See pydicom license.txt for license information
from cStringIO import StringIO

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
    fp = StringIO(data)
    print hexdump(fp, 0, StopAddress)
    
def hexdump(file_in, StartAddress=0, StopAddress=None, showAddress=True):
    """Return a formatted string of hex bytes and characters in data.
    
    This is a utility function for debugging file writing.
    
    file_in -- a file-like object to get the bytes to show from"""

    str_out = StringIO()
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
        bytes = ' '.join(["%02x" % x for x in row])  # string of two digit hex bytes
        str_out.write(bytes)
        str_out.write(blanks[:byteslen-len(bytes)])  # if not 16, pad
        str_out.write('  ')
        str_out.write(''.join([PrintCharacter(x) for x in row]))  # character rep of bytes
        str_out.write("\n")
        
    return str_out.getvalue()
    
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
    