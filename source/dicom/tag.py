# tag.py
"""Define Tag class to hold a dicom (group, element) tag"""
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

class Tag(long):
    """Class for storing the dicom (group, element) tag"""
    def __new__(cls, arg):
        if isinstance(arg, tuple):
            if len(arg) != 2:
                raise ValueError, "Tag must be an int or a 2-tuple"
            return long.__new__(cls, arg[0]<<16 | arg[1])
        elif isinstance(arg, basestring):
            raise ValueError, "Tags cannot be instantiated from a string"
        else:
            if arg > 0xFFFFFFFF:
                raise OverflowError, "Tags are limited to 32-bit length"
            return long.__new__(cls, arg)
    def __cmp__(self, other):
        othertag=other
        if not isinstance(other, Tag):
            try:
                othertag = Tag(other)
            except:
                raise TypeError, "Cannot compare dicom Tag with non-Tag item"
        # Note that int's are negative if 0x80000000 or more but we want unsigned comparison
        # cheap trick: compare them by hex (fixed size) conversion to avoid negatives
        return cmp("%08x" % self, "%08x" % othertag) # XXX is there a better (faster) way?
        # return cmp(int(self),int(othertag))
    def __str__(self):
        """String of tag value as (gggg, eeee)"""
        return "(%04x, %04x)" % (self.group, self.elem)

    __repr__ = __str__
    
    # Property group
    def getGroup(self): 
        return int(("%08x" % self)[:4], 16) # use string rep to beat problems with negatives. Kludgy
    group = property(getGroup)

    # Property elem
    def getElem(self):
        return self & 0xffff
    elem  = property(getElem)
    element = elem
   
    # Property isPrivate
    def getIsPrivate(self):
        """Private tags have an odd group number"""
        return self.group % 2 == 1
    isPrivate = property(getIsPrivate)
    

if __name__ == "__main__":
    print "Basic tests of Tag class"
    tag = Tag(0x300a00b0)
    print "Initialized as Tag(0x300a00b0):"
    print tag, "group:", hex(tag.group), "element:", hex(tag.elem)
    print
    tag = Tag((0x300a, 0x00b0))
    print "Initialized as Tag((0x300a, 0x00b0)):"
    print tag, "group:", hex(tag.group), "element:", hex(tag.elem)
    print
    print "Comparisons:"
    print "tag==(0x300a, 0x00b0)...:", tag==(0x300a, 0x00b0)
    print "tag==Tag(0x300a00b0)....:", tag==Tag(0x300a00b0)
    print "tag==0x300a00b0.........:", tag==0x300a00b0
    