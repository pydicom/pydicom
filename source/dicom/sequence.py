# sequence.py
"""Hold the Sequence class, which stores a dicom sequence (list of Datasets)"""
#
# Copyright 2004, Darcy Mason
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

from dicom.attribute import Attribute

class Sequence(list):
    """Slightly modified python list to print nicely"""
    def __str__(self):
        lines = [str(x) for x in self]
        return "[" + "".join(lines) + "]"
    
    def __repr__(self):
        formatstr = "<%(classname)s, length %(count)d, at %(id)X>"
        return   formatstr % {'classname':self.__class__.__name__, 'id':id(self), 'count':len(self)}
    
