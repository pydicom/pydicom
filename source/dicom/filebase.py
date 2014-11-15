# filebase.py
"""Hold DicomFile class, which does basic I/O for a dicom file."""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com
from __future__ import absolute_import

from dicom.tag import Tag
from struct import unpack, pack

from io import BytesIO
import logging
logger = logging.getLogger('pydicom')


class DicomIO(object):
    """File object which holds transfer syntax info and anything else we need."""

    max_read_attempts = 3  # number of times to read if don't get requested bytes
    defer_size = None      # default

    def __init__(self, *args, **kwargs):
        self._implicit_VR = True   # start with this by default

    def __del__(self):
        self.close()

    def read_le_tag(self):
        """Read and return two unsigned shorts (little endian) from the file."""
        bytes_read = self.read(4)
        if len(bytes_read) < 4:
            raise EOFError  # needed for reading "next" tag when at end of file
        return unpack(b"<HH", bytes_read)

    def read_be_tag(self):
        """Read and return two unsigned shorts (little endian) from the file."""
        bytes_read = self.read(4)
        if len(bytes_read) < 4:
            raise EOFError  # needed for reading "next" tag when at end of file
        return unpack(b">HH", bytes_read)

    def write_tag(self, tag):
        """Write a dicom tag (two unsigned shorts) to the file."""
        tag = Tag(tag)  # make sure is an instance of class, not just a tuple or int
        self.write_US(tag.group)
        self.write_US(tag.element)

    def read_leUS(self):
        """Return an unsigned short from the file with little endian byte order"""
        return unpack(b"<H", self.read(2))[0]

    def read_beUS(self):
        """Return an unsigned short from the file with big endian byte order"""
        return unpack(b">H", self.read(2))[0]

    def read_leUL(self):
        """Return an unsigned long read with little endian byte order"""
        return unpack(b"<L", self.read(4))[0]

    def read(self, length=None, need_exact_length=True):
        """Reads the required length, returns EOFError if gets less

        If length is None, then read all bytes
        """
        parent_read = self.parent_read  # super(DicomIO, self).read
        if length is None:
            return parent_read()  # get all of it
        bytes_read = parent_read(length)
        if len(bytes_read) < length and need_exact_length:
            # Didn't get all the desired bytes. Keep trying to get the rest. If reading across network, might want to add a delay here
            attempts = 0
            while attempts < self.max_read_attempts and len(bytes_read) < length:
                bytes_read += parent_read(length - len(bytes_read))
                attempts += 1
            if len(bytes_read) < length:
                start_pos = self.tell() - len(bytes_read)
                msg = "Unexpected end of file. "
                msg += "Read {0} bytes of {1} expected starting at position 0x{2:x}".format(len(bytes_read), length, start_pos)
                raise EOFError(msg)
        return bytes_read

    def write_leUS(self, val):
        """Write an unsigned short with little endian byte order"""
        self.write(pack(b"<H", val))

    def write_leUL(self, val):
        """Write an unsigned long with little endian byte order"""
        self.write(pack(b"<L", val))

    def write_beUS(self, val):
        """Write an unsigned short with big endian byte order"""
        self.write(pack(b">H", val))

    def write_beUL(self, val):
        """Write an unsigned long with big endian byte order"""
        self.write(pack(b">L", val))

    write_US = write_leUS   # XXX should we default to this?
    write_UL = write_leUL   # XXX "

    def read_beUL(self):
        """Return an unsigned long read with big endian byte order"""
        return unpack(b">L", self.read(4))[0]

    # Set up properties is_little_endian and is_implicit_VR
    # Big/Little Endian changes functions to read unsigned short or long, e.g. length fields etc
    @property
    def is_little_endian(self):
        return self._little_endian

    @is_little_endian.setter
    def is_little_endian(self, value):
        self._little_endian = value
        if value:  # Little Endian
            self.read_US = self.read_leUS
            self.read_UL = self.read_leUL
            self.write_US = self.write_leUS
            self.write_UL = self.write_leUL
            self.read_tag = self.read_le_tag
        else:      # Big Endian
            self.read_US = self.read_beUS
            self.read_UL = self.read_beUL
            self.write_US = self.write_beUS
            self.write_UL = self.write_beUL
            self.read_tag = self.read_be_tag

    @property
    def is_implicit_VR(self):
        return self._implicit_VR

    @is_implicit_VR.setter
    def is_implicit_VR(self, value):
        self._implicit_VR = value


class DicomFileLike(DicomIO):

    def __init__(self, file_like_obj):
        self.parent = file_like_obj
        self.parent_read = getattr(file_like_obj, "read", self.no_read)
        self.write = getattr(file_like_obj, "write", self.no_write)
        self.seek = getattr(file_like_obj, "seek", self.no_seek)
        self.tell = file_like_obj.tell
        self.close = file_like_obj.close
        self.name = getattr(file_like_obj, 'name', '<no filename>')

    def no_write(self, bytes_read):
        """Used for file-like objects where no write is available"""
        raise IOError("This DicomFileLike object has no write() method")

    def no_read(self, bytes_read):
        """Used for file-like objects where no read is available"""
        raise IOError("This DicomFileLike object has no read() method")

    def no_seek(offset, from_what):
        """Used for file-like objects where no seek is available"""
        raise IOError("This DicomFileLike object has no seek() method")


def DicomFile(*args, **kwargs):
    return DicomFileLike(open(*args, **kwargs))


def DicomBytesIO(*args, **kwargs):
    return DicomFileLike(BytesIO(*args, **kwargs))