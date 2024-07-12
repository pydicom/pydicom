# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Hold DicomFile class, which does basic I/O for a dicom file."""

from io import BytesIO
import os
from struct import Struct
from types import TracebackType
from typing import TYPE_CHECKING, cast, Any, TypeVar, Protocol

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable


ExitException = tuple[
    type[BaseException] | None, BaseException | None, TracebackType | None
]
Self = TypeVar("Self", bound="DicomIO")


class ReadableBuffer(Protocol):
    def read(self, size: int = ..., /) -> bytes: ...  # pragma: no cover

    def seek(self, offset: int, whence: int = ..., /) -> int: ...  # pragma: no cover

    def tell(self) -> int: ...  # pragma: no cover


class WriteableBuffer(Protocol):
    def seek(self, offset: int, whence: int = ..., /) -> int: ...  # pragma: no cover

    def tell(self) -> int: ...  # pragma: no cover

    def write(
        self, b: bytes | bytearray | memoryview, /
    ) -> int: ...  # pragma: no cover


class DicomIO:
    """Wrapper for managing buffer-like objects used when reading or writing
    DICOM datasets.
    """

    def __init__(self, buffer: ReadableBuffer | WriteableBuffer) -> None:
        """Create a new ``DicomIO`` instance.

        Parameters
        ----------
        buffer : buffer-like object
            A buffer-like object that implements:

            * ``seek()`` and ``tell()`` methods with the same signatures as
              :meth:`io.IOBase.seek` and :meth:`io.IOBase.tell`
            * a ``read()`` method with the same signature as
              :meth:`io.RawIOBase.read` if it supports reading data from
              itself, and/or
            * a ``write()`` method with the same signature as
              :meth:`io.RawIOBase.write` if it supports writing data to itself

            If `buffer` supports reading it can be used with
            :func:`~pydicom.filereader.dcmread` as the source to decode a DICOM
            dataset from, and if it supports writing it can be used with
            :func:`~pydicom.filewriter.dcmwrite` as the destination for the
            encoded DICOM dataset.
        """
        # Data packers/unpackers
        self._us_unpacker: Callable[[bytes], tuple[Any, ...]]
        self._us_packer: Callable[[int], bytes]
        self._ul_unpacker: Callable[[bytes], tuple[Any, ...]]
        self._ul_packer: Callable[[int], bytes]
        self._tag_unpacker: Callable[[bytes], tuple[Any, ...]]
        self._tag_packer: Callable[[int, int], bytes]

        # Store the encoding method
        self._implicit_vr: bool
        self._little_endian: bool

        # The buffer-like object being wrapped
        self._buffer = buffer

        # The filename associated with the buffer-like
        self._name: str | None = getattr(self._buffer, "name", None)

        # It's more efficient to replace the existing class methods
        #   instead of wrapping them
        if hasattr(buffer, "read"):
            self.read = buffer.read

        if hasattr(buffer, "write"):
            self.write = buffer.write

        if hasattr(buffer, "close"):
            self.close = buffer.close

        # seek() and tell() are always required
        self.seek = buffer.seek
        self.tell = buffer.tell

    def close(self, *args: Any, **kwargs: Any) -> Any:
        """Close the buffer (if possible)"""
        pass

    def __enter__(self: Self) -> Self:
        return self

    def __exit__(self, *exc_info: ExitException) -> None:
        self.close()

    @property
    def is_little_endian(self) -> bool:
        """Get/set the endianness for encoding/decoding, ``True`` for little
        endian and ``False`` for big endian.
        """
        if not hasattr(self, "_little_endian"):
            raise AttributeError(
                f"{type(self).__name__}.is_little_endian' has not been set"
            )

        return self._little_endian

    @is_little_endian.setter
    def is_little_endian(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError(f"'{type(self).__name__}.is_little_endian' must be bool")

        self._little_endian = value

        endianness = "><"[value]
        self._us_packer = Struct(f"{endianness}H").pack
        self._us_unpacker = Struct(f"{endianness}H").unpack
        self._ul_packer = Struct(f"{endianness}L").pack
        self._ul_unpacker = Struct(f"{endianness}L").unpack
        self._tag_packer = Struct(f"{endianness}2H").pack
        self._tag_unpacker = Struct(f"{endianness}2H").unpack

    @property
    def is_implicit_VR(self) -> bool:
        """Get/set the VR mode for encoding/decoding. ``True`` for implicit VR
        and ``False`` for explicit VR.
        """
        if not hasattr(self, "_implicit_vr"):
            raise AttributeError(
                f"{type(self).__name__}.is_implicit_VR' has not been set"
            )

        return self._implicit_vr

    @is_implicit_VR.setter
    def is_implicit_VR(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError(f"'{type(self).__name__}.is_implicit_VR' must be bool")

        self._implicit_vr = value

    @property
    def name(self) -> str | None:
        """Return the value of the :attr:`~pydicom.filebase.DicomIO.parent`'s
        ``name`` attribute, or ``None`` if no such attribute.
        """
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    def parent(self) -> ReadableBuffer | WriteableBuffer:
        """Return the buffer object being wrapped."""
        return self._buffer

    def read(self, size: int = -1, /) -> bytes:
        """Read up to `size` bytes from the buffer and return them. If `size`
        is unspecified, all bytes until EOF are returned.

        Fewer than `size` bytes may be returned if the operating system call
        returns fewer than `size` bytes.
        """
        raise TypeError(
            f"'{type(self).__name__}' cannot be used with "
            f"'{type(self._buffer).__name__}': object has no read() method"
        )

    def read_exact(self, length: int, nr_retries: int = 3) -> bytes:
        """Return `length` bytes read from the buffer.

        Parameters
        ----------
        length : int
            The number of bytes to be read. If ``None`` (default) then read all
            the bytes available.
        nr_retries : int, optional
            The number of tries to read data when the number of bytes read
            from the buffer is less than `length`. Default ``3``.

        Returns
        -------
        bytes
            The read data.

        Raises
        ------
        EOFError
            If unable to read `length` bytes.
        """
        bytes_read = self.read(length)
        if len(bytes_read) == length:
            return bytes_read

        # Use a bytearray because concatenating bytes is expensive
        bytes_read = bytearray(bytes_read)
        attempts = 0
        while (num_bytes := len(bytes_read)) < length and attempts < nr_retries:
            bytes_read += self.read(length - num_bytes)
            attempts += 1

        if num_bytes == length:
            return bytes(bytes_read)

        raise EOFError(
            f"Unexpected end of file. Read {num_bytes} bytes of {length} "
            f"expected starting at position 0x{self.tell() - num_bytes:x}"
        )

    def read_tag(self) -> tuple[int, int]:
        """Return a DICOM tag value read from the buffer."""
        return cast(
            tuple[int, int],
            self._tag_unpacker(self.read_exact(4)),
        )

    def read_UL(self) -> int:
        """Return a UL value read from the buffer."""
        return cast(int, self._ul_unpacker(self.read(4))[0])

    def read_US(self) -> int:
        """Return a US value read from the buffer."""
        return cast(int, self._us_unpacker(self.read(2))[0])

    def seek(self, offset: int, whence: int = os.SEEK_SET, /) -> int:
        """Change the buffer position to the given byte `offset`, relative to
        the position indicated by `whence` and return the new absolute position.
        """
        raise NotImplementedError()  # pragma: no cover

    def tell(self) -> int:
        """Return the current stream position of the buffer"""
        raise NotImplementedError()  # pragma: no cover

    def write(self, b: bytes | bytearray | memoryview, /) -> int:
        """Write the bytes-like object `b` to the buffer and return the number
        of bytes written.
        """
        raise TypeError(
            f"'{type(self).__name__}' cannot be used with "
            f"'{type(self._buffer).__name__}': object has no write() method"
        )

    def write_tag(self, tag: int) -> None:
        """Write a DICOM tag to the buffer."""
        self.write(self._tag_packer(tag >> 16, tag & 0xFFFF))

    def write_UL(self, val: int) -> None:
        """Write a UL value to the buffer."""
        self.write(self._ul_packer(val))

    def write_US(self, val: int) -> None:
        """Write a US value to the buffer."""
        self.write(self._us_packer(val))


class DicomFileLike(DicomIO):
    """Wrapper for file-likes to simplify encoding/decoding DICOM datasets.

    See Also
    --------
    :class:`~pydicom.filebase.DicomIO`
    :class:`~pydicom.filebase.DicomBytesIO`
    """

    pass


def DicomFile(*args: Any, **kwargs: Any) -> DicomFileLike:
    """Return an opened :class:`~pydicom.filebase.DicomFileLike` from a file-like."""
    return DicomFileLike(open(*args, **kwargs))


class DicomBytesIO(DicomIO):
    """Wrapper for :class:`io.BytesIO` to simplify encoding/decoding DICOM datasets.

    See Also
    --------
    :class:`~pydicom.filebase.DicomIO`
    :class:`~pydicom.filebase.DicomFileLike`
    """

    def __init__(self, initial_bytes: bytes | bytearray | memoryview = b"") -> None:
        """Create a new DicomBytesIO instance.

        Parameters
        ----------
        buffer : bytes | bytearray | memoryview, optional
            The buffer to write to or read from, default is an empty buffer.
        """
        buffer = BytesIO(initial_bytes)
        super().__init__(buffer)

        self.getvalue = buffer.getvalue
