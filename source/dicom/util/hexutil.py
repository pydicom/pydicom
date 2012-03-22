# hexutil.py 
"""Miscellaneous utility routines relating to hex and byte strings"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

def hex2bytes(hex_string):
    """Return bytestring for a string of hex bytes separated by whitespace
    
    This is useful for creating specific byte sequences for testing, using
    python's implied concatenation for strings with comments allowed.
    Example:
        hex_string = (
         "08 00 32 10"     # (0008, 1032) SQ "Procedure Code Sequence"
         " 08 00 00 00"    # length 8
         " fe ff 00 e0"    # (fffe, e000) Item Tag
        )
        byte_string = hex2bytes(hex_string)
    Note in the example that all lines except the first must start with a space,
    alternatively the space could end the previous line.
    """
    return "".join((chr(int(x,16)) for x in hex_string.strip().split()))

def bytes2hex(byte_string):
    """Return a hex dump of the bytes given"""
    return " ".join(["{0:02x}".format(ord(b)) for b in byte_string])