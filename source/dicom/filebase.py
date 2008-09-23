# filebase.py - part of dicom package
"""Hold DicomFile class, which does basic I/O for a dicom file."""
#
# Copyright 2004, 2008, Darcy Mason
# This file is part of pydicom.
#
# pydicom is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# pydicom is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License (license.txt) for more details 

from dicom.tag import Tag
from struct import unpack, pack

from StringIO import StringIO

# Use Boolean values if Python version has them, else make our own
try:
    True
except:
    False = 0; True = not False

class DicomIO(object):
    """File object which holds transfer syntax info and anything else we need."""
    def __init__(self, *args, **kwargs):
        self._ImplicitVR = True   # start with this by default
        
    def read_tag(self):
        """Read and return a dicom tag (two unsigned shorts) from the file."""
        return Tag((self.read_US(), self.read_US()))
    def write_tag(self, tag):
        """Write a dicom tag (two unsigned shorts) to the file."""
        tag = Tag(tag)  # make sure is an instance of class, not just a tuple or int
        self.write_US(tag.group)
        self.write_US(tag.element)
    def read_leUS(self):
        """Return an unsigned short from the file with little endian byte order"""
        bytes = self.read(2)
        if len(bytes) == 0: # needed for reading "next" tag when at end of file
            raise EOFError
        return unpack("<H", bytes)[0]
    
    def read_beUS(self):
        """Return an unsigned short from the file with big endian byte order"""
        bytes = self.read(2)
        if len(bytes) == 0: # needed for reading "next" tag when at end of file
            raise EOFError
        return unpack(">H", bytes)[0]
    
    def read_leUL(self):
        """Return an unsigned long read with little endian byte order"""
        return unpack("<L", self.read(4))[0]
    def write_leUS(self, val):
        """Write an unsigned short with little endian byte order"""
        self.write(pack("<H", val))
    def write_leUL(self, val):
        """Write an unsigned long with little endian byte order"""
        self.write(pack("<L", val))
    def write_beUS(self, val):
        """Write an unsigned short with big endian byte order"""
        self.write(pack(">H", val))
    def write_beUL(self, val):
        """Write an unsigned long with big endian byte order"""
        self.write(pack(">L", val))

    write_US = write_leUS   # XXX should we default to this?
    write_UL = write_leUL   # XXX "
    
    def read_beUL(self):
        """Return an unsigned long read with big endian byte order"""
        return unpack(">L", self.read(4))[0]

    # Set up properties BigEndian, LittleEndian, ImplicitVR, ExplicitVR.
    # Big/Little Endian changes functions to read unsigned short or long, e.g. length fields etc
    def _setLittleEndian(self, value):
        self._LittleEndian = value
        if value:  # LittleEndian
            self.read_US = self.read_leUS
            self.read_UL = self.read_leUL
            self.write_US = self.write_leUS
            self.write_UL = self.write_leUL
        else:      # BigEndian
            self.read_US = self.read_beUS
            self.read_UL = self.read_beUL
            self.write_US = self.write_beUS
            self.write_UL = self.write_beUL
        
    def _getLittleEndian(self):
        return self._LittleEndian
    def _setBigEndian(self, value):
        self.isLittleEndian = not value # note: must use self.isLittleEndian not self._LittleEndian
    def _getBigEndian(self):
        return not self.isLittleEndian
    def _getImplicitVR(self):
        return self._ImplicitVR
    def _setImplicitVR(self, value):
        self._ImplicitVR = value
    def _setExplicitVR(self, value):
        self.isImplicitVR = not value
    def _getExplicitVR(self):
        return not self.isImplicitVR
    
    isLittleEndian = property(_getLittleEndian, _setLittleEndian)
    isBigEndian =    property(_getBigEndian, _setBigEndian)
    isImplicitVR =   property(_getImplicitVR, _setImplicitVR)
    isExplicitVR =   property(_getExplicitVR, _setExplicitVR)

class DicomFile(DicomIO, file):
    def __init__(self, *args, **kwargs):
        """Extend file.__init__() to set default values."""
        file.__init__(self, *args, **kwargs)
        DicomIO.__init__(self, *args, **kwargs)

class DicomStringIO(DicomIO, StringIO):
    def __init__(self, *args, **kwargs):
        StringIO.__init__(self, *args, **kwargs)
        DicomIO.__init__(self, *args, **kwargs)
