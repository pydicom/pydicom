# fileutil.py
"""Functions for reading to certain bytes, e.g. delimiters"""
# Copyright (c) 2009 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

from struct import pack, unpack
from dicom.tag import TupleTag, Tag
from dicom.datadict import dictionaryDescription

import logging
logger = logging.getLogger('pydicom')

def absorb_delimiter_item(fp, is_little_endian, delimiter):
    """Read (and ignore) undefined length sequence or item terminators."""
    if is_little_endian:
        format = "<HHL"
    else:
        format = ">HHL"
    group, elem, length = unpack(format, fp.read(8))
    tag = TupleTag((group, elem))
    if tag != delimiter:
        logger.warn("Did not find expected delimiter '%s', instead found %s at file position 0x%x", dictionaryDescription(delimiter), str(tag), fp.tell()-8)    
        fp.seek(fp.tell()-8)
        return 
    logger.debug("%04x: Found Delimiter '%s'", fp.tell()-8, dictionaryDescription(delimiter))
    if length == 0:
        logger.debug("%04x: Read 0 bytes after delimiter", fp.tell()-4)
    else:
        logger.debug("%04x: Expected 0x00000000 after delimiter, found 0x%x", fp.tell()-4, length)

def find_bytes(fp, bytes_to_find, read_size=128, rewind=True):
    """Read in the file until a specific byte sequence found
	
    bytes_to_find -- a string containing the bytes to find. Must be in correct
                    endian order already
    read_size -- number of bytes to read at a time
	"""

    data_start = fp.tell()  
    search_rewind = len(bytes_to_find)-1
    
    found = False
    EOF = False
    while not found:
        chunk_start = fp.tell()
        bytes = fp.read(read_size) 
        if len(bytes) < read_size:
            # try again - if still don't get required amount, this is last block
            new_bytes = fp.read(read_size - len(bytes))
            bytes += new_bytes
            if len(bytes) < read_size:
                EOF = True # but will still check whatever we did get
        index = bytes.find(bytes_to_find)
        if index != -1:
            found = True
        elif EOF:
            if rewind:
                fp.seek(data_start)
            return None
        else:
            fp.seek(fp.tell()-search_rewind) # rewind a bit in case delimiter crossed read_size boundary
    # if get here then have found the byte string
    found_at = chunk_start + index
    if rewind:
        fp.seek(data_start)
    return found_at

def find_delimiter(fp, delimiter, is_little_endian, read_size=128, rewind=True):
    """Return file position where 4-byte delimiter is located.
    
    Return None if reach end of file without finding the delimiter.
    On return, file position will be where it was before this function,
    unless rewind argument is False.
    
    """
    format = "<H"
    if not is_little_endian:
        format = ">H"
    delimiter = Tag(delimiter)
    bytes_to_find = pack(format, delimiter.group) + pack(format, delimiter.elem)
    return find_bytes(fp, bytes_to_find, rewind=rewind)            
    
def length_of_undefined_length(fp, delimiter, is_little_endian, read_size=128, rewind=True):
    """Search through the file to find the delimiter, return the length of the data
    element value that the dicom file writer was too lazy to figure out for us.
    Return the file to the start of the data, ready to read it.
    Note the data element that the delimiter starts is not read here, the calling
    routine must handle that.
    delimiter must be 4 bytes long
    rewind == if True, file will be returned to position before seeking the bytes
    
    """
    chunk = 0
    data_start = fp.tell()
    delimiter_pos = find_delimiter(fp, delimiter, is_little_endian, rewind=rewind)
    length = delimiter_pos - data_start
    return length
    
def read_delimiter_item(fp, delimiter):
    """Read and ignore an expected delimiter.
    
    If the delimiter is not found or correctly formed, a warning is logged.
    """
    found = fp.read(4)
    if found != delimiter:
        logger.warn("Expected delimitor %s, got %s at file position 0x%x", Tag(delimiter), Tag(found), fp.tell()-4)
    length = fp.read_UL()
    if length != 0:
        logger.warn("Expected delimiter item to have length 0, got %d at file position 0x%x", length, fp.tell()-4)
    