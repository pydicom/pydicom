# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Functions for reading to certain bytes, e.g. delimiters."""
import os
import pathlib
import sys
from struct import pack, unpack

from pydicom.misc import size_in_bytes
from pydicom.tag import TupleTag, Tag
from pydicom.datadict import dictionary_description

from pydicom.config import logger


def absorb_delimiter_item(fp, is_little_endian, delimiter):
    """Read (and ignore) undefined length sequence or item terminators."""
    if is_little_endian:
        struct_format = "<HHL"
    else:
        struct_format = ">HHL"
    group, elem, length = unpack(struct_format, fp.read(8))
    tag = TupleTag((group, elem))
    if tag != delimiter:
        msg = ("Did not find expected delimiter '%s'" %
               dictionary_description(delimiter))
        msg += ", instead found %s at file position 0x%x" % (
            str(tag), fp.tell() - 8)
        logger.warn(msg)
        fp.seek(fp.tell() - 8)
        return
    logger.debug("%04x: Found Delimiter '%s'", fp.tell() - 8,
                 dictionary_description(delimiter))
    if length == 0:
        logger.debug("%04x: Read 0 bytes after delimiter", fp.tell() - 4)
    else:
        logger.debug("%04x: Expected 0x00000000 after delimiter, found 0x%x",
                     fp.tell() - 4, length)


def find_bytes(fp, bytes_to_find, read_size=128, rewind=True):
    """Read in the file until a specific byte sequence found.

    Parameters
    ----------
    fp : file-like
        The file-like to search.
    bytes_to_find : str
        Contains the bytes to find. Must be in correct endian order already.
    read_size : int
        Number of bytes to read at a time.
    rewind : bool
        Flag to rewind file reading position.

    Returns
    -------
    found_at : int or None
        Position where byte sequence was found, else ``None``.
    """

    data_start = fp.tell()
    search_rewind = len(bytes_to_find) - 1

    found = False
    eof = False
    while not found:
        chunk_start = fp.tell()
        bytes_read = fp.read(read_size)
        if len(bytes_read) < read_size:
            # try again - if still don't get required amount,
            # this is the last block
            new_bytes = fp.read(read_size - len(bytes_read))
            bytes_read += new_bytes
            if len(bytes_read) < read_size:
                eof = True  # but will still check whatever we did get
        index = bytes_read.find(bytes_to_find)
        if index != -1:
            found = True
        elif eof:
            if rewind:
                fp.seek(data_start)
            return None
        else:
            # rewind a bit in case delimiter crossed read_size boundary
            fp.seek(fp.tell() - search_rewind)
    # if get here then have found the byte string
    found_at = chunk_start + index
    if rewind:
        fp.seek(data_start)
    else:
        fp.seek(found_at + len(bytes_to_find))
    return found_at


def read_undefined_length_value(fp,
                                is_little_endian,
                                delimiter_tag,
                                defer_size=None,
                                read_size=1024 * 8):
    """Read until `delimiter_tag` and return the value up to that point.

    On completion, the file will be set to the first byte after the delimiter
    and its following four zero bytes.

    Parameters
    ----------
    fp : file-like
        The file-like to read.
    is_little_endian : bool
        ``True`` if file transfer syntax is little endian, else ``False``.
    delimiter_tag : BaseTag
        Tag used as end marker for reading
    defer_size : int or None, optional
        Size to avoid loading large elements in memory. See
        :func:`~pydicom.filereader.dcmread` for more parameter info.
    read_size : int, optional
        Number of bytes to read at one time.

    Returns
    -------
    delimiter : str or None
        The file delimiter.

    Raises
    ------
    EOFError
        If EOF is reached before delimiter found.
    """
    data_start = fp.tell()
    search_rewind = 3

    if is_little_endian:
        bytes_format = b"<HH"
    else:
        bytes_format = b">HH"
    bytes_to_find = pack(bytes_format, delimiter_tag.group, delimiter_tag.elem)

    found = False
    eof = False
    value_chunks = []
    defer_size = size_in_bytes(defer_size)
    byte_count = 0  # for defer_size checks
    while not found:
        chunk_start = fp.tell()
        bytes_read = fp.read(read_size)
        if len(bytes_read) < read_size:
            # try again - if still don't get required amount,
            # this is the last block
            new_bytes = fp.read(read_size - len(bytes_read))
            bytes_read += new_bytes
            if len(bytes_read) < read_size:
                eof = True  # but will still check whatever we did get
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
                msg = ("Expected 4 zero bytes after undefined length delimiter"
                       " at pos {0:04x}")
                logger.error(msg.format(fp.tell() - 4))
        elif eof:
            fp.seek(data_start)
            raise EOFError("End of file reached before delimiter {0!r} found".
                           format(delimiter_tag))
        else:
            # rewind a bit in case delimiter crossed read_size boundary
            fp.seek(fp.tell() - search_rewind)
            # accumulate the bytes read (not including the rewind)
            new_bytes = bytes_read[:-search_rewind]
            byte_count += len(new_bytes)
            if defer_size is None or byte_count < defer_size:
                value_chunks.append(new_bytes)
    # if get here then have found the byte string
    if defer_size is not None and byte_count >= defer_size:
        return None
    else:
        return b"".join(value_chunks)


def find_delimiter(fp, delimiter, is_little_endian, read_size=128,
                   rewind=True):
    """Return file position where 4-byte delimiter is located.

    Parameters
    ----------
    delimiter : int
        The delimiter to search for.
    is_little_endian : bool
        ``True`` if little endian, ``False`` otherwise.
    read_size : int
        See :func:`find_bytes` for parameter info.
    rewind : bool
        Flag to rewind to initial position after searching.

    Returns
    -------
    int or None
        Returns ``None`` if end of file is reached without finding the
        delimiter, otherwise the byte offset to the delimiter.
    """
    struct_format = "<H"
    if not is_little_endian:
        struct_format = ">H"
    delimiter = Tag(delimiter)
    bytes_to_find = pack(struct_format, delimiter.group) + pack(
        struct_format, delimiter.elem)
    return find_bytes(fp, bytes_to_find, read_size=read_size, rewind=rewind)


def length_of_undefined_length(fp,
                               delimiter,
                               is_little_endian,
                               read_size=128,
                               rewind=True):
    """Search through the file to find the delimiter and return the length
    of the data element.

    Parameters
    ----------
    fp : file-like
        The file-like to read.
    delimiter :
        See :func:`find_delimiter` for parameter info.
    is_little_endian : bool
        ``True`` if little endian, ``False`` otherwise.
    read_size : int
        See :func:`find_bytes` for parameter info.
    rewind : bool
        Flag to rewind to initial position after searching.

    Returns
    -------
    int
        Byte offset to the delimiter.

    Notes
    -----
    Note the data element that the delimiter starts is not read here,
    the calling routine must handle that. Delimiter must be 4 bytes long.
    """
    data_start = fp.tell()
    delimiter_pos = find_delimiter(
        fp, delimiter, is_little_endian, rewind=rewind)
    length = delimiter_pos - data_start
    return length


def read_delimiter_item(fp, delimiter):
    """Read and ignore an expected delimiter.

    If the delimiter is not found or correctly formed, a warning is logged.
    """
    found = fp.read(4)
    if found != delimiter:
        logger.warn("Expected delimitor %s, got %s at file position 0x%x",
                    Tag(delimiter), Tag(found), fp.tell() - 4)
    length = fp.read_UL()
    if length != 0:
        logger.warn("Expected delimiter item to have length 0, "
                    "got %d at file position 0x%x", length, fp.tell() - 4)


def path_from_pathlike(file_object):
    """Returns the path if `file_object` is a path-like object, otherwise the
    original `file_object`.

    Parameters
    ----------
    file_object: str or PathLike or file-like

    Returns
    -------
    str or file-like
        the string representation of the given path object, or the object
        itself in case of an object not representing a path.

    ..note:

        ``PathLike`` objects have been introduced in Python 3.6. In Python 3.5,
        only objects of type :class:`pathlib.Path` are considered.
    """
    if sys.version_info < (3, 6):
        if isinstance(file_object, pathlib.Path):
            return str(file_object)
        return file_object
    try:
        return os.fspath(file_object)
    except TypeError:
        return file_object
