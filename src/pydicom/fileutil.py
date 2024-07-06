# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Functions for reading to certain bytes, e.g. delimiters."""

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from io import BufferedIOBase
import os
from struct import pack, unpack
from typing import BinaryIO, cast

from pydicom.misc import size_in_bytes
from pydicom.tag import TupleTag, Tag, SequenceDelimiterTag, ItemTag, BaseTag
from pydicom.datadict import dictionary_description
from pydicom.filebase import ReadableBuffer, WriteableBuffer

from pydicom.config import logger, settings


PathType = str | bytes | os.PathLike


def absorb_delimiter_item(
    fp: BinaryIO, is_little_endian: bool, delimiter: BaseTag
) -> None:
    """Read (and ignore) undefined length sequence or item terminators."""
    if is_little_endian:
        struct_format = "<HHL"
    else:
        struct_format = ">HHL"
    group, elem, length = unpack(struct_format, fp.read(8))
    tag = TupleTag((group, elem))
    if tag != delimiter:
        logger.warn(
            "Did not find expected delimiter "
            f"'{dictionary_description(delimiter)}', instead found "
            f"{tag} at file position 0x{fp.tell() - 8:X}"
        )
        fp.seek(fp.tell() - 8)
        return

    logger.debug(
        "%04x: Found Delimiter '%s'", fp.tell() - 8, dictionary_description(delimiter)
    )

    if length == 0:
        logger.debug("%04x: Read 0 bytes after delimiter", fp.tell() - 4)
    else:
        logger.debug(
            "%04x: Expected 0x00000000 after delimiter, found 0x%x",
            fp.tell() - 4,
            length,
        )


def find_bytes(
    fp: BinaryIO, bytes_to_find: bytes, read_size: int = 128, rewind: bool = True
) -> int | None:
    """Read in the file until a specific byte sequence found.

    Parameters
    ----------
    fp : file-like
        The file-like to search.
    bytes_to_find : bytes
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


def read_undefined_length_value(
    fp: BinaryIO,
    is_little_endian: bool,
    delimiter_tag: BaseTag,
    defer_size: int | float | None = None,
    read_size: int = 1024 * 8,
) -> bytes | None:
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
    delimiter : bytes or None
        The file delimiter.

    Raises
    ------
    EOFError
        If EOF is reached before delimiter found.
    """
    data_start = fp.tell()
    defer_size = size_in_bytes(defer_size)

    # It's common for an undefined length value item to be an
    # encapsulated pixel data as defined in PS3.5 section A.4.
    # Attempt to parse the data under that assumption, since the method
    #  1. is proof against coincidental embedded sequence delimiter tags
    #  2. avoids accumulating any data in memory if the element is large
    #     enough to be deferred
    #  3. does not double-accumulate data (in chunks and then joined)
    #
    # Unfortunately, some implementations deviate from the standard and the
    # encapsulated pixel data-parsing algorithm fails. In that case, we fall
    # back to a method of scanning the entire element value for the
    # sequence delimiter, as was done historically.
    if delimiter_tag == SequenceDelimiterTag:
        was_value_found, value = _try_read_encapsulated_pixel_data(
            fp, is_little_endian, defer_size
        )
        if was_value_found:
            return value

    search_rewind = 3

    if is_little_endian:
        bytes_format = b"<HH"
    else:
        bytes_format = b">HH"
    bytes_to_find = pack(bytes_format, delimiter_tag.group, delimiter_tag.elem)

    found = False
    eof = False
    value_chunks = []
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
                value_chunks.append(new_bytes)
            fp.seek(chunk_start + index + 4)  # rewind to end of delimiter
            length = fp.read(4)
            if length != b"\0\0\0\0":
                msg = (
                    "Expected 4 zero bytes after undefined length delimiter"
                    " at pos {0:04x}"
                )
                logger.error(msg.format(fp.tell() - 4))
        elif eof:
            fp.seek(data_start)
            raise EOFError(
                f"End of file reached before delimiter {delimiter_tag!r} found"
            )
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


def _try_read_encapsulated_pixel_data(
    fp: BinaryIO,
    is_little_endian: bool,
    defer_size: float | int | None = None,
) -> tuple[bool, bytes | None]:
    """Attempt to read an undefined length value item as if it were
    encapsulated pixel data as defined in PS3.5 section A.4.

    On success, the file will be set to the first byte after the delimiter
    and its following four zero bytes. If unsuccessful, the file will be left
    in its original position.

    Parameters
    ----------
    fp : file-like
        The file-like to read.
    is_little_endian : bool
        ``True`` if the file transfer syntax is little endian, else ``False``.
    defer_size : int or None, optional
        Size to avoid loading large elements in memory. See
        :func:`~pydicom.filereader.dcmread` for more parameter info.

    Returns
    -------
    bool, bytes
        Whether or not the value was parsed properly and, if it was,
        the value.
    """

    if is_little_endian:
        tag_format = b"<HH"
        length_format = b"<L"
    else:
        tag_format = b">HH"
        length_format = b">L"

    sequence_delimiter_bytes = pack(
        tag_format, SequenceDelimiterTag.group, SequenceDelimiterTag.elem
    )
    item_bytes = pack(tag_format, ItemTag.group, ItemTag.elem)

    data_start = fp.tell()
    byte_count = 0
    while True:
        tag_bytes = fp.read(4)
        if len(tag_bytes) < 4:
            # End of file reached while scanning.
            # Maybe the sequence delimiter is missing or or maybe we read past
            # it due to an inaccurate length indicator for an element
            logger.debug(
                "End of input encountered while parsing undefined length "
                "value as encapsulated pixel data. Unable to find tag at "
                "position 0x%x. Falling back to byte by byte scan.",
                fp.tell() - len(tag_bytes),
            )
            fp.seek(data_start)
            return (False, None)
        byte_count += 4

        if tag_bytes == sequence_delimiter_bytes:
            break

        if tag_bytes == item_bytes:
            length_bytes = fp.read(4)
            if len(length_bytes) < 4:
                # End of file reached while scanning.
                # Maybe the sequence delimiter is missing or or maybe we read
                # past it due to an inaccurate length indicator for an element
                logger.debug(
                    "End of input encountered while parsing undefined length "
                    "value as encapsulated pixel data. Unable to find length "
                    "for tag %s at position 0x%x. Falling back to byte by "
                    "byte scan.",
                    ItemTag,
                    fp.tell() - len(length_bytes),
                )
                fp.seek(data_start)
                return (False, None)
            byte_count += 4
            length = unpack(length_format, length_bytes)[0]

            try:
                fp.seek(length, os.SEEK_CUR)
            except OverflowError:
                logger.debug(
                    "Too-long length %04x for tag %s at position 0x%x found "
                    "while parsing undefined length value as encapsulated "
                    "pixel data. Falling back to byte-by-byte scan.",
                    length,
                    ItemTag,
                    fp.tell() - 8,
                )
                fp.seek(data_start)
                return (False, None)
            byte_count += length
        else:
            logger.debug(
                "Unknown tag bytes %s at position 0x%x found "
                "while parsing undefined length value as encapsulated "
                "pixel data. Falling back to byte-by-byte scan.",
                tag_bytes.hex(),
                fp.tell() - 4,
            )
            fp.seek(data_start)
            return (False, None)

    length = fp.read(4)
    if length != b"\0\0\0\0":
        msg = "Expected 4 zero bytes after undefined length delimiter at pos {0:04x}"
        logger.debug(msg.format(fp.tell() - 4))

    if defer_size is not None and defer_size <= byte_count:
        value = None
    else:
        fp.seek(data_start)
        value = fp.read(byte_count - 4)

    fp.seek(data_start + byte_count + 4)
    return (True, value)


def find_delimiter(
    fp: BinaryIO,
    delimiter: BaseTag,
    is_little_endian: bool,
    read_size: int = 128,
    rewind: bool = True,
) -> int | None:
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
        struct_format, delimiter.elem
    )

    return find_bytes(fp, bytes_to_find, read_size=read_size, rewind=rewind)


def length_of_undefined_length(
    fp: BinaryIO,
    delimiter: BaseTag,
    is_little_endian: bool,
    read_size: int = 128,
    rewind: bool = True,
) -> int | None:
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
    delimiter_pos = find_delimiter(fp, delimiter, is_little_endian, rewind=rewind)
    if delimiter_pos is not None:
        return delimiter_pos - data_start

    return None


def path_from_pathlike(
    file_object: PathType | BinaryIO | ReadableBuffer | WriteableBuffer,
) -> str | BinaryIO:
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
    """
    try:
        return os.fspath(file_object)  # type: ignore[arg-type]
    except TypeError:
        return cast(BinaryIO, file_object)


def _unpack_tag(b: bytes, endianness: str) -> BaseTag:
    return TupleTag(cast(tuple[int, int], unpack(f"{endianness}HH", b)))


def check_buffer(buffer: BufferedIOBase) -> None:
    """Raise an exception if `buffer` is not usable as an element value.

    Parameters
    ----------
    buffer : io.BufferedIOBase
        The buffer to check, must be :meth:`~io.IOBase.readable`,
        :meth:`~io.IOBase.seekable` and not be :attr:`io.IOBase.closed`.
    """
    if not isinstance(buffer, BufferedIOBase):
        raise TypeError("the buffer must inherit from 'io.BufferedIOBase'")

    if buffer.closed:
        raise ValueError("the buffer has been closed")

    # readable() covers read(), seekable() covers seek() and tell()
    if not buffer.readable() or not buffer.seekable():
        raise ValueError("the buffer must be readable and seekable")


@contextmanager
def reset_buffer_position(buffer: BufferedIOBase) -> Generator[int, None, None]:
    """Yields the initial position of the buffer and return to that position on exiting
    the context.

    Parameters
    ----------
    buffer : io.BufferedIOBase
        The buffer to use.

    Yields
    ------
    int
        The initial position of the buffer.
    """
    check_buffer(buffer)

    initial_offset = buffer.tell()
    yield initial_offset

    buffer.seek(initial_offset)


def read_buffer(
    buffer: BufferedIOBase, *, chunk_size: int | None = None
) -> Iterator[bytes]:
    """Read data from `buffer`.

    The buffer is NOT returned to its starting position.

    Parameters
    ----------
    buffer : io.BufferedIOBase
        The buffer to read from.
    chunk_size : int, optional
        The amount of bytes to read per iteration (default 8192). Fewer bytes may be
        yielded if there is insufficient remaining data in `buffer`.

    Yields
    -------
    bytes
        Data read from the buffer of length up to the specified chunk_size.
    """
    chunk_size = settings.buffered_read_size if chunk_size is None else chunk_size
    if chunk_size <= 0:
        raise ValueError(
            f"Invalid 'chunk_size' value '{chunk_size}', must be greater than 0"
        )

    check_buffer(buffer)
    while chunk := buffer.read(chunk_size):
        if chunk:
            yield chunk


def buffer_length(buffer: BufferedIOBase) -> int:
    """Return the total length of the buffer.

    Parameters
    ----------
    buffer : io.BufferedIOBase
        The buffer to return the remaining length for.

    Returns
    -------
    int
        The total length of the buffer.
    """
    with reset_buffer_position(buffer):
        return buffer.seek(0, os.SEEK_END)


def buffer_remaining(buffer: BufferedIOBase) -> int:
    """Return the remaining length of the buffer with respect to the current position.

    Parameters
    ----------
    buffer : io.BufferedIOBase
        The buffer to return the remaining length for.

    Returns
    -------
    int
        The remaining length of the buffer from the current position.
    """
    with reset_buffer_position(buffer) as current_offset:
        return buffer.seek(0, os.SEEK_END) - current_offset


def buffer_equality(
    buffer: BufferedIOBase,
    other: bytes | bytearray | BufferedIOBase,
) -> bool:
    """Return ``True`` if `buffer` and `other` are equal, ``False`` otherwise."""
    if not isinstance(other, bytes | bytearray | BufferedIOBase):
        return False

    # Avoid reading the entire buffer object into memory
    with reset_buffer_position(buffer):
        buffer.seek(0)
        if isinstance(other, bytes | bytearray):
            start = 0
            for data in read_buffer(buffer):
                nr_read = len(data)
                if other[start : start + nr_read] != data:
                    return False

                start += nr_read

            return len(other) == start

        if buffer_length(buffer) != buffer_length(other):
            return False

        with reset_buffer_position(other):
            other.seek(0)
            for data_a, data_b in zip(read_buffer(buffer), read_buffer(other)):
                if data_a != data_b:
                    return False

        return True
