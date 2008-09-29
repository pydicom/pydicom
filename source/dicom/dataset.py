# dataset.py
"""Class Dataset: A dictionary of Attributes, which in turn can have a Sequence of Datasets.

Overview of Dicom object model:
------------------------------
Dataset(derived class of Python's dict class)
    ---> contains Attribute instances (Attribute is a class with tag, VR, value)
             ==> the value can be a Sequence instance (Sequence is derived from Python's list),
                            or just a regular value like a number, string, etc.,
                            or a list of regular values, e.g. a 3d coordinate
                  --> Sequence's are a list of Datasets
   
"""
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

from sys import byteorder
sys_isLittleEndian = (byteorder == 'little')
from dicom.datadict import DicomDictionary, dictionaryVR
from dicom.datadict import TagForName, AllNamesForTag
from dicom.tag import Tag
from dicom.attribute import Attribute

haveNumpy = True
haveNumeric = True
try:
    import Numeric
except:
    haveNumeric = False
try:
    import numpy
except:
    haveNumpy = False

class Dataset(dict):
    """A Dataset is a collection (dictionary) of Dicom attribute instances.
    
    Example of two ways to retrieve or set values:
    (1) dataset[0x10, 0x10].value --> patient's name
    (2) dataset.PatientsName --> patient's name
    
    Example (2) is referred to as *Named tags* in this documentation.
    PatientsName is not actually a member of the object, but unknown member
    requests are checked against the dicom dictionary. If the name matches a
    DicomDictionary descriptive string, the corresponding tag is used
    to look up or set the attribute's value.
    
    Class Data
    ----------
    indentChars -- for string display, the characters used to indent for
            nested attributes (e.g. sequence items). Default is '   '.
    pixelFormats -- if Numeric module is available, map bits allocated
            to the Numeric typecode.
    """
    indentChars = "   "
    # In the following, the dictionary key is the number of BitsAllocated for image data
    if haveNumeric:
        NumericPixelFormats = {8: Numeric.UnsignedInt8, 16:Numeric.Int16, 32:Numeric.Int32}
    if haveNumpy:
        NumpyPixelFormats = {8: numpy.uint8, 16:numpy.int16, 32:numpy.int32}
        
    def Add(self, attribute):
        """Equivalent to dataset[attribute.tag] = attribute."""
        self[attribute.tag] = attribute
    def AddNew(self, tag, VR, value):
        """Create a new Attribute instance and add it to this Dataset."""
        attribute = Attribute(tag, VR, value)
        self[attribute.tag] = attribute   # use attribute.tag since Attribute verified it
    def attribute(self, name):
        """Return the full attribute instance for the given descriptive name.
        
        When using *named tags*, only the value is returned. If you want the
        whole attribute object, for example to change the attribute.VR,
        call this function with the name and the attribute instance is returned."""
        tag = TagForName(name)
        if tag:
            return self[tag]
        return None
    def __contains__(self, name):
        """Extend dict.__contains__() to handle *named tags*.
        
        This is called for code like: ``if 'SliceLocation' in dataset``.
        
        """
        if self._isString(name):
            tag = TagForName(name)
        else:
            try:
                tag = Tag(name)
            except:
                return 0
        if tag:
            return dict.__contains__(self, tag)
        else:
            return dict.__contains__(self, name) # will no doubt raise an exception
    def dir(self, *filters):
        """Return a list of some or all attribute names, in alphabetical order.
        
        Intended mainly for use in interactive Python sessions.
        
        filters -- 0 or more string arguments to the function
                if none provided, dir() returns all attribute names in this Dataset.
                Else dir() will return only those items with one of the strings
                somewhere in the name (case insensitive).
        
        """
        allnames = []
        for tag, attribute in self.items():
            allnames.extend(AllNamesForTag(tag))
        allnames = [x for x in allnames if x]  # remove blanks - tags without valid names (e.g. private tags)
        # Store found names in a dict, so duplicate names appear only once
        matches = {}
        for filter in filters:
            filter = filter.lower()
            match = [x for x in allnames if x.lower().find(filter) != -1]
            matches.update(dict([(x,1) for x in match]))
        if filters:
            names = matches.keys()
            names.sort()
            return names
        else:
            allnames.sort()
            return allnames
    def file_metadata(self):
        """Return a Dataset holding only meta information (group 2).
        
        Only makes sense if this dataset is a whole file dataset.
        
        """
        return GroupDataset(2)
    def get(self, key, default=None):
        """Extend dict.get() to handle *named tags*."""
        if self._isString(key):
            try:
                return getattr(self, key)
            except AttributeError:
                return default
        else: # is not a string, probably is a tag -> hand off to underlying dict
            return dict.get(self, key, default)
    def __getattr__(self, name):
        """Intercept requests for unknown Dataset python-attribute names.
        
        If the name matches a Dicom dictionary string (without blanks etc),
        then return the value for the attribute with the corresponding tag.
        
        """
        # __getattr__ only called if instance cannot find name in self.__dict__
        # So, if name is not a dicom string, then is an error
        tag = TagForName(name)
        if not tag or tag not in self:
            raise AttributeError, "Dataset does not have attribute '%s'." % name
        else:  # do have that dicom attribute
            return self[tag].value
    def __getitem__(self, key):
        """Operator for dataset[key] request."""
        return dict.__getitem__(self, Tag(key))
    def GroupDataset(self, group):
        """Return a Dataset containing only attributes of a certain group.
        
        group -- the group part of a dicom (group, element) tag.
        
        """
        ds = Dataset()
        ds.update(dict(
            [(tag,attr) for tag,attr in self.items() if tag.group==group]
                      ))
        return ds
    def has_key(self, key):
        """Extend dict.has_key() to handle *named tags*."""
        return self.__contains__(key)
    def _isString(self, name):
        """Return True if name is a string."""
        try:
            name + ""
        except TypeError:
            return 0
        else:
            return 1
    def PixelDataArray(self):
        """Return a NumPy or Numeric array of the pixel data.
        
        NumPy is the most recent numerical package for python. It is used if available.
        If not, and Numeric is available, that is used.
        
        Return a NumPy 2 or 3-D array object, or Numeric 2 or 3-D array object if NumPy unavailable.
        
        Raise TypeError if no pixel data in this dataset.
        Raise ImportError if cannot import numpy or Numeric.
        Raise NotImplementedError if SamplesPerPixel > 1. (not sure what to do with this).
        
        """
        if not 'PixelData' in self:
            raise TypeError, "No pixel data found in this dataset."

        if not haveNumeric and not haveNumpy:
            msg = "Either the Numpy package or Numeric package (http://sf/net/projects/numpy) is required\n"
            msg += " to use the PixelDataArray() method. Neither could be found on this system."
            raise ImportError, msg

#        if self.SamplesperPixel != 1:
#            raise NotImplementedError, "This code does not handle SamplesPerPixel > 1."

            # determine the type used for the array
        # XXX didn't have images to test all variations. Not sure if will always work.
        need_byteswap = (self.isLittleEndian != sys_isLittleEndian)

        if haveNumpy:
            format = self.NumpyPixelFormats[self.BitsAllocated]
            arr = numpy.fromstring(self.PixelData, format)
            # XXX byte swap - may later handle this in ReadFile!!?
            if need_byteswap:
                arr.byteswap(True)  # True = swap in-place, don't make a new copy
            # Note the following reshape operations return a new *view* onto arr, but don't copy the data
            if 'NumberofFrames' in self and self.NumberofFrames > 1:
                if self.SamplesperPixel > 1:
                    arr = arr.reshape(self.SamplesperPixel, self.NumberofFrames, self.Rows, self.Columns)
                else:
                    arr = arr.reshape(self.NumberofFrames, self.Rows, self.Columns)
            else:
                if self.SamplesperPixel > 1:
                    if self.BitsAllocated == 8:
                        arr = arr.reshape(self.SamplesperPixel, self.Rows, self.Columns)
                    else:
                        raise NotImplementedError, "This code only handles Samples Per Pixel > 1 if Bits Allocated = 8"
                else:
                    arr = arr.reshape(self.Rows, self.Columns)
        elif haveNumeric:
            format = self.NumericPixelFormats[self.BitsAllocated]
            arr = Numeric.fromstring(self.PixelData, format)
        
            # XXX byte swap - may later handle this in ReadFile!!?
            if need_byteswap:
                arr = arr.byteswapped()
            if 'NumberofFrames' in self and self.NumberofFrames > 1:
                arr = Numeric.reshape(arr,(self.NumberofFrames, self.Rows, self.Columns))
            else:
                arr = Numeric.reshape(arr, (self.Rows, self.Columns))
        return arr

    def top(self):
        """Show the DICOM tags, but only the top level; do not recurse into Sequences"""
        
        return self._PrettyStr(topLevelOnly=True)
        
    def _PrettyStr(self, indent=0, topLevelOnly=False):
        """Return a string of the attributes in this dataset, with indented levels.
        
        This private method is called by the __str__() method 
        for handling print statements or str(dataset), and the __repr__() method.
        It is also used by top, which is the reason for the topLevelOnly flag.
        This function recurses, with increasing indentation levels.
        
        """
        strings = []
        keylist = self.keys()
        keylist.sort()
        indentStr = self.indentChars * indent
        nextIndentStr = self.indentChars *(indent+1)
        for k in keylist:
            attr = self[k]
            if attr.VR == "SQ":   # a sequence
                strings.append(indentStr + str(attr.tag) + "  %s   %i item(s) ---- " % ( attr.description(),len(attr.value)))
                if not topLevelOnly:
                    for dataset in attr.value:
                        strings.append(dataset._PrettyStr(indent+1))
                        strings.append(nextIndentStr + "---------")
            else:
                strings.append(indentStr + repr(attr))
        return "\n".join(strings)
        
    def RemovePrivateTags(self):
        """Remove all Dicom private tags in this dataset and those contained within."""
        def RemoveCallback(dataset, attribute):
            """Internal method to use as callback to walk() method."""
            if attribute.tag.isPrivate:
                # can't del self[tag] - won't be right dataset on recursion
                del dataset[attribute.tag]  
        self.walk(RemoveCallback)

    def __setattr__(self, name, value):
        """Intercept any attempts to set a value for an instance attribute.
        
        If name is a dicom descriptive string (cleaned with CleanName),
        then set the corresponding tag and attribute.
        Else, set an instance (python) attribute as any other class would do.
        
        """
        tag = TagForName(name)
        if tag:  # successfully mapped name to a tag
            if tag not in self:  # don't have this tag yet->create the attribute instance
                VR = dictionaryVR(tag)
                attribute = Attribute(tag, VR, value)
            else:  # already have this attribute, just changing its value
                attribute = self[tag]
                attribute.value = value
            # Now have attribute - store it in this dict
            self[tag] = attribute
        else:  # name not in dicom dictionary - setting a non-dicom instance attribute
            # XXX note if user mis-spells a dicom attribute - no error!!!
            self.__dict__[name] = value  

    def __setitem__(self, key, value):
        """Operator for dataset[key]=value."""
        try:
            x = value.VR, value.tag, value.value  # check is an Attribute by its contents
        except AttributeError:
            raise TypeError, "Dataset contents must be Attribute instances.\n" + \
                  "To set an attribute value use attribute.value=val"
        if key != value.tag:
            raise ValueError, "attribute.tag must match the dictionary key"
        # Everything is okay - use base class (dict) to store the dicom Attribute
        dict.__setitem__(self, value.tag, value)

    def __str__(self):
        """Handle str(dataset)."""
        return self._PrettyStr()
        
    def update(self, dictionary):
        """Extend dict.update() to handle *named tags*."""
        for key, value in dictionary.items():
            if self._isString(key):
                setattr(self, key, value)
            else:
                self[Tag(key)] = value
    def walk(self, callback):
        """Call the given function for all dataset attributes (recurses).
        
        Go through all attributes, recursing into sequences and their datasets,
        calling the callback function at each attribute (including the SQ attribute).
        This can be used to perform an operation on certain types of attributes.
        For example, RemovePrivateTags() finds all private tags and deletes them.

        callback -- a callable method which takes two arguments: a dataset, and
                    an attribute belonging to that dataset.
        
        Attributes will come back in dicom order (by increasing tag number
        within their dataset)
        
        """
        keylist = self.keys()
        keylist.sort()
        for k in keylist:
            attribute = self[k]
            callback(self, attribute)  # self = this Dataset
            # 'k in self' below needed in case attribute was deleted in callback
            if k in self and attribute.VR == "SQ":  
                sequence = attribute.value
                for dataset in sequence:
                    dataset.walk(callback)
    def _getBigEndian(self):
        return not self.isLittleEndian
    def _setBigEndian(self, value):
        self.isLittleEndian = not value
    isBigEndian = property(_getBigEndian, _setBigEndian)
    
    
    __repr__ = __str__
