"""
Utilities to help with reading/writing from python's BufferedIOBase.
"""
from contextlib import contextmanager
from collections.abc import Generator

from io import BufferedIOBase
import os
from collections.abc import Iterator


def buffer_assertions(buffer: BufferedIOBase) -> None:
    """
    Asserts pre-conditions for working with a readable and seekable buffer.

    Parameters
    ----------
    buffer:
        The buffer to assert on.

    Raises
    ------
    AssertionError
        If the buffer is not seekable, readable, or is closed.
    """
    assert not buffer.closed, "The stream has been closed"
    assert buffer.readable(), "The stream is not readable"
    assert buffer.seekable(), "The buffer is not seekable"


@contextmanager
def reset_buffer_position(value: BufferedIOBase) -> Generator[int, None, None]:
    """
    Stores the current buffer position upon entering the context and then seeks back to the previously
    stored position upon exiting the context manager. Yields the starting stream position.

    Parameters
    ----------
    buffer:
        The buffer to restore the position of.

    Raises
    ------
    AssertionError
        If the buffer is not seekable, readable, or is closed.
    """
    buffer_assertions(value)

    startion_position = value.tell()
    yield startion_position
    value.seek(startion_position)


def read_bytes(value: BufferedIOBase, *, chunk_size: int = 8192) -> Iterator[bytes]:
    """Consume data from a buffered value. The value must be a buffer, the buffer must be
    readable, the buffer must be seekable, and the buffer must not be closed.

    NOTE: The buffer is NOT sought back to its starting position.

    Parameters
    ----------
    value:
        The buffer to read from. It must meet the required pre-conditions.
    chunk_size:
        The amount of bytes to read at a time. Less bytes may be read if there are less
        than the specified amount of bytes in the stream. Must be > 0. Default is 8192.

    Returns
    -------
    Iterator
        An iterator that yields bytes up to the specified chunk_size.

    Raises
    ------
    AssertionError
        If the buffer is not seekable, readable, or is closed.
    """
    assert chunk_size > 0, "chunk_size must be > 0: {chunk_size}"

    buffer_assertions(value)
    while chunk := value.read(chunk_size):
        if chunk:
            yield chunk


def buffer_length(value: BufferedIOBase) -> int:
    """
    Gets the length of the buffer with respect to the starting position of the buffer.

    Returns
    -------
    int
        The length of the buffer minus the starting position of the buffer.
    """
    with reset_buffer_position(value) as starting_position:
        value.seek(0, os.SEEK_END)
        return value.tell() - starting_position
