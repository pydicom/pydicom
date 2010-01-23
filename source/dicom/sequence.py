# sequence.py
"""Hold the Sequence class, which stores a dicom sequence (list of Datasets)"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

from dicom.dataelem import DataElement

class Sequence(list):
    """Slightly modified python list to print nicely"""
    def __str__(self):
        lines = [str(x) for x in self]
        return "[" + "".join(lines) + "]"
    
    def __repr__(self):
        formatstr = "<%(classname)s, length %(count)d, at %(id)X>"
        return   formatstr % {'classname':self.__class__.__name__, 'id':id(self), 'count':len(self)}
    
