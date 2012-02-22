# tag.py
#PZ 16 Feb 2012 no decode or unicode
"""Define Tag class to hold a dicom (group, element) tag"""
# Copyright (c) 2008, 2010 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com
import sys
if sys.hexversion >= 0x02060000 and sys.hexversion < 0x03000000: 
    inPy26 = True
    inPy3 = False
elif sys.hexversion >= 0x03000000: 
    inPy26 = False
    inPy3 = True
    long = int
    basestring = str

def Tag(arg, arg2=None):
    """Factory function for creating Tags in more general ways than the (gp, el)
    """
    if arg2 is not None:
        arg = (arg, arg2) # act as if was passed a single tuple
    if isinstance(arg, (tuple, list)):
        if len(arg) != 2:
#PZ http://www.python.org/dev/peps/pep-3109/          
            raise ValueError( "Tag must be an int or a 2-tuple")
#PZ no basestring in Py3 use str
        if isinstance(arg[0], basestring):
#PZ no basestring in Py3 use str
            if not isinstance(arg[1], basestring):
#PZ http://www.python.org/dev/peps/pep-3109/              
                raise ValueError( "Both arguments must be hex strings if one is")
            arg = (int(arg[0], 16), int(arg[1], 16))
        if arg[0] > 0xFFFF or arg[1] > 0xFFFF:
#PZ http://www.python.org/dev/peps/pep-3109/          
            raise OverflowError( "Groups and elements of tags must each be <=2 byte integers")
#PZ no long in Py3            
        long_value = long(arg[0])<<16 | arg[1]  # long needed for python <2.4 where shift could make int negative
#PZ no basestring in Py3 use str        
    elif isinstance(arg, basestring):
#PZ http://www.python.org/dev/peps/pep-3109/      
        raise ValueError( "Tags cannot be instantiated from a single string")
    else: # given a single number to use as a tag, as if (group, elem) already joined to a long
#PZ no long in Py3    
        long_value = long(hex(arg), 16) # needed in python <2.4 to avoid negative ints
#PZ http://www.python.org/dev/peps/pep-0237/         
        if long_value > 0xFFFFFFFF:
#PZ http://www.python.org/dev/peps/pep-3109/          
            raise OverflowError( "Tags are limited to 32-bit length; tag %r, long value %r" % (arg, long_value))
    return BaseTag(long_value)
    
#PZ no long in 3.0  
class BaseTag(long):
    """Class for storing the dicom (group, element) tag"""
    # Store the 4 bytes of a dicom tag as a python long (arbitrary length, not like C-language long).
    # NOTE: logic (in write_AT of filewriter at least) depends on this 
    #           NOT being a tuple, for checks if a value is a multi-value element
    # Using python int's may be different on different hardware platforms.
    # Simpler to deal with one number and separate to (group, element) when necessary.
    # Also can deal with python differences in handling ints starting in python 2.4,
    #   by forcing all inputs to a proper long where the differences go away
    
    # Override comparisons so can convert "other" to Tag as necessary
    # Changes this from __cmp__ to using __lt__ and __eq__ for python 3.
    #   See Ordering Comparisons at http://docs.python.org/dev/3.0/whatsnew/3.0.html
    
    def __lt__(self, other):
        # Allow comparisons to other longs or (group,elem) tuples directly.
        # So check if comparing with another Tag object; if not, create a temp one
        if not isinstance(other, BaseTag):
            try:
                other = Tag(other)
            except:
#PZ 3109
                raise TypeError( "Cannot compare Tag with non-Tag item")
#PZ no long in Py3                
        return long(self) < long(other)

    def __eq__(self, other):
        # Check if comparing with another Tag object; if not, create a temp one
        if not isinstance(other, BaseTag):
            try:
                other = Tag(other)
            except:
#PZ 3109            
                raise TypeError( "Cannot compare Tag with non-Tag item")
        # print "self %r; other %r" % (long(self), long(other))
#PZ no long in Py3        
        return long(self) == long(other)

    def __ne__(self, other):
        # Check if comparing with another Tag object; if not, create a temp one
        if not isinstance(other, BaseTag):
            try:
                other = Tag(other)
            except:
#PZ 3109            
                raise TypeError( "Cannot compare Tag with non-Tag item")
#PZ no long in Py3                
        return long(self) != long(other)

    
    # For python 3, any override of __cmp__ or __eq__ immutable requires
    #   explicit redirect of hash function to the parent class 
    #   See http://docs.python.org/dev/3.0/reference/datamodel.html#object.__hash__
#PZ no long in Py3    
    __hash__ = long.__hash__

#PZimplementing __str()__ makes it pass is_string like or +""     
#so is_stringlike must be changed
    def __str__(self):
        """String of tag value as (gggg, eeee)"""
        return "({0:04x}, {1:04x})".format(self.group, self.elem)

    __repr__= __str__
    # Property group
    def getGroup(self):
        return self >>16
    group = property(getGroup)

    # Property elem
    def getElem(self):
        return self & 0xffff
    elem  = property(getElem)
    element = elem
   
    # Property is_private
    def getis_private(self):
        """Private tags have an odd group number"""
        return self.group % 2 == 1
    is_private = property(getis_private)
    isPrivate = is_private  # for backwards compatibility

def TupleTag(group_elem):
    """Fast factory for BaseTag object with known safe (group, element) tuple"""
    # long needed for python <2.4 where shift could make int negative
#PZ no long in Py3    
    long_value = long(group_elem[0])<<16 | group_elem[1]  

    return BaseTag(long_value)

# Define some special tags:
# See PS 3.5-2008 section 7.5 (p.40)
ItemTag = TupleTag((0xFFFE, 0xE000)) # start of Sequence Item
ItemDelimiterTag = TupleTag((0xFFFE, 0xE00D)) # end of Sequence Item
SequenceDelimiterTag = TupleTag((0xFFFE,0xE0DD)) # end of Sequence of undefined length
