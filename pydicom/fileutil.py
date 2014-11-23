# fileutil.py
"""Functions for reading to certain bytes, e.g. delimiters"""
# Copyright (c) 2009-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

from struct import pack, unpack
from dicom.tag import TupleTag, Tag
from dicom.datadict import dictionary_description

import logging
logger = logging.getLogger('pydicom')


def absorb_delimiter_item(fp, is_little_endian, delimiter):
    """Read (and ignore) undefined length sequence or item terminators."""
    if is_little_endian:
        struct_format = "<HHL"
    else:
        struct_format = ">HHL"
    group, elem, length = unpack(struct_format, fp.read(8))
    tag = TupleTag((group, elem))
    if tag != delimiter:
        msg = "Did not find expected delimiter '%s'" % dictionary_description(delimiter)
        msg += ", instead found %s at file position 0x%x" % (str(tag), fp.tell() - 8)
        logger.warn(msg)
        fp.seek(fp.tell() - 8)
        return
    logger.debug("%04x: Found Delimiter '%s'", fp.tell() - 8, dictionary_description(delimiter))
    if length == 0:
        logger.debug("%04x: Read 0 bytes after delimiter", fp.tell() - 4)
    else:
        logger.debug("%04x: Expected 0x00000000 after delimiter, found 0x%x", fp.tell() - 4, length)


def find_bytes(fp, bytes_to_find, read_size=128, rewind=True):
    """Read in the file until a specific byte sequence found

    bytes_to_find -- a string containing the bytes to find. Must be in correct
                    endian order already
    read_size -- number of bytes to read at a time
    """

    data_start = fp.tell()
    search_rewind = len(bytes_to_find) - 1

    found = False
    EOF = False
    while not found:
        chunk_start = fp.tell()
        bytes_read = fp.read(read_size)
        if len(bytes_read) < read_size:
            # try again - if still don't get required amount, this is last block
            new_bytes = fp.read(read_size - len(bytes_read))
            bytes_read += new_bytes
            if len(bytes_read) < read_size:
                EOF = True  # but will still check whatever we did get
        index = bytes_read.find(bytes_to_find)
        if index != -1:
            found = True
        elif EOF:
            if rewind:
                fp.seek(data_start)
            return None
        else:
            fp.seek(fp.tell() - search_rewind)  # rewind a bit in case delimiter crossed read_size boundary
    # if get here then have found the byte string
    found_at = chunk_start + index
    if rewind:
        fp.seek(data_start)
    else:
        fp.seek(found_at + len(bytes_to_find))
    return found_at


def read_undefined_length_value(fp, is_little_endian, delimiter_tag, defer_size=None,
                                read_size=128):
    """Read until the delimiter tag found and return the value, ignore the delimiter

    fp -- a file-like object with read(), seek() functions
    is_little_endian -- True if file transfer syntax is little endian, else False
    read_size -- number of bytes to read at one time (default 128)

    On completion, the file will be set to the first byte after the delimiter and its
        following four zero bytes.
    If end-of-file is hit before the delimiter was found, raises EOFError
        """
    data_start = fp.tell()
    search_rewind = 3

    if is_little_endian:
        bytes_format = b"<HH"
    else:
        bytes_format = b">HH"
    bytes_to_find = pack(bytes_format, delimiter_tag.group, delimiter_tag.elem)

    found = False
    EOF = False
    value_chunks = []
    byte_count = 0  # for defer_size checks
    while not found:
        chunk_start = fp.tell()
        bytes_read = fp.read(read_size)
        if len(bytes_read) < read_size:
            # try again - if still don't get required amount, this is last block
            new_bytes = fp.read(read_size - len(bytes_read))
            bytes_read += new_bytes
            if len(bytes_read) < read_size:
                EOF = True  # but will still check whatever we did get
        index = bytes_read.find(bytes_to_find)
        if index != -1:
            found = True
            new_bytes = bytes_read[:index]
            byte_count += len(new_bytes)
            if defer_size is None or byte_count < defer_size:
                value_chunks.append(bytes_read[:index])
            fp.seek(chunk_start + index + 4)  # rewind to end of delimiter
            length = fp.read(4)
            if length != b"\0\0\0\0":
                msg = "Expected 4 zero bytes after undefined length delimiter at pos {0:04x}"
                logger.error(msg.format(fp.tell() - 4))
        elif EOF:
            fp.seek(data_start)
            raise EOFError("End of file reached before delimiter {0!r} found".format(delimiter_tag))
        else:
            fp.seek(fp.tell() - search_rewind)  # rewind a bit in case delimiter crossed read_size boundary
            # accumulate the bytes read (not including the rewind)
            new_bytes = bytes_read[:-search_rewind]
            byte_count += len(new_bytes)
            if defer_size is None or byte_count < defer_size:
                value_chunks.append(new_bytes)
    # if get here then have found the byte string
    if defer_size is not None and defer_size >= defer_size:
        return None
    else:
        return b"".join(value_chunks)


def find_delimiter(fp, delimiter, is_little_endian, read_size=128, rewind=True):
    """Return file position where 4-byte delimiter is located.

    Return None if reach end of file without finding the delimiter.
    On return, file position will be where it was before this function,
    unless rewind argument is False.

    """
    struct_format = "<H"
    if not is_little_endian:
        struct_format = ">H"
    delimiter = Tag(delimiter)
    bytes_to_find = pack(struct_format, delimiter.group) + pack(struct_format, delimiter.elem)
    return find_bytes(fp, bytes_to_find, rewind=rewind)


def length_of_undefined_length(fp, delimiter, is_little_endian, read_size=128, rewind=True):
    """Search through the file to find the delimiter, return the length of the data
    element.
    Return the file to the start of the data, ready to read it.
    Note the data element that the delimiter starts is not read here, the calling
    routine must handle that.
    delimiter must be 4 bytes long
    rewind == if True, file will be returned to position before seeking the bytes

    """
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
        logger.warn("Expected delimitor %s, got %s at file position 0x%x", Tag(delimiter), Tag(found), fp.tell() - 4)
    length = fp.read_UL()
    if length != 0:
        logger.warn("Expected delimiter item to have length 0, got %d at file position 0x%x", length, fp.tell() - 4)
