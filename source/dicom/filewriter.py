# filewriter.py
"""Write a dicom media file."""
#
# Copyright 2004,2008, Darcy Mason
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

from struct import pack

import logging
logger = logging.getLogger('pydicom')

from dicom.UID import ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian
from dicom.filebase import DicomFile
from dicom.datadict import dictionaryVR
from dicom.dataset import Dataset
from dicom.dataelem import DataElement
from dicom.tag import Tag, ItemTag, ItemDelimiterTag, SequenceDelimiterTag
from dicom.sequence import Sequence

def write_numbers(fp, data_element, format):
    """Write a "value" of type format from the dicom file.
    
    "Value" can be more than one number.
    
    format -- the character format as used by the struct module.
    
    """
    endianChar = '><'[fp.isLittleEndian]
    value = data_element.value
    if value == "":
        return  # don't need to write anything for empty string
    
    format_string = endianChar + format
    try:
        try:
            value.append   # works only if list, not if string or number
        except: # is a single value - the usual case
            fp.write(pack(format_string, value))
        else:
            for val in value:
                fp.write(pack(format_string, val))
    except Exception, e:
        raise IOError, "%s\nfor data_element:\n%s" % (str(e), str(data_element))

def write_OBvalue(fp, data_element):
    """Write a data_element with VR of 'other byte' (OB)."""
    fp.write(data_element.value)

def write_OWvalue(fp, data_element):
    """Write a data_element with VR of 'other word' (OW).
    
    Note: This **does not currently do the byte swapping** for Endian state.
    
    """    
    # XXX for now just write the raw bytes without endian swapping
    fp.write(data_element.value)

def write_UI(fp, data_element):
    """Write a data_element with VR of 'unique identifier' (UI)."""    
    write_String(fp, data_element, '\0') # pad with 0-byte to even length

def MultiString(val):
    """Put a string together with delimiter if has more than one value"""
    try:
        val.append  # will work for a list, but not for a string or number value
    except:
        return val
    else:
        return "\\".join(val)  # \ is escape chr, so "\\" gives single backslash

def write_String(fp, data_element, padding=' '):
    """Write a single or multivalued string."""
    val = MultiString(data_element.value)
    if len(val) % 2 != 0:
        val = val + padding   # pad to even length
    fp.write(val)

def write_NumberString(fp, data_element, padding = ' '):
    """Handle IS or DS VR - write a number stored as a string of digits."""
    val = MultiString(data_element.string_value) # use exact string value from file or set by user
    if len(val) % 2 != 0:
        val = val + padding   # pad to even length
    fp.write(val)
    
def WriteDataElement(fp, data_element):
    """Write the data_element to file fp according to dicom media storage rules."""
    fp.write_tag(data_element.tag)

    VR = data_element.VR
    if fp.isExplicitVR:
        fp.write(VR)
        if VR in ['OB', 'OW', 'OF', 'SQ', 'UT', 'UN']:
            fp.write_US(0)   # reserved 2 bytes
    if VR not in writers:
        raise NotImplementedError, "WriteDataElement: unknown Value Representation '%s'" % VR

    length_location = fp.tell() # save location for later.
    if fp.isExplicitVR and VR not in ['OB', 'OW', 'OF', 'SQ', 'UT', 'UN']:
        fp.write_US(0)  # Explicit VR length field is only 2 bytes
    else:
        fp.write_UL(0xFFFFFFFFL)   # will fill in real length value later if not undefined length item
    
    try:
        writers[VR][0] # if writer is a tuple, then need to pass a number format
    except TypeError:
        writers[VR](fp, data_element) # call the function to write that kind of item
    else:
        writers[VR][0](fp, data_element, writers[VR][1])
    #  print DataElement(tag, VR, value)
    
    isUndefinedLength = False
    if hasattr(data_element, "isUndefinedLength") and data_element.isUndefinedLength:
        isUndefinedLength = True
    location = fp.tell()
    fp.seek(length_location)
    if fp.isExplicitVR and VR not in ['OB', 'OW', 'OF', 'SQ', 'UT', 'UN']:
        fp.write_US(location - length_location - 2)  # 2 is length of US
    else:
        # write the proper length of the data_element back in the length slot, unless is SQ with undefined length.
        if not isUndefinedLength:
            fp.write_UL(location - length_location - 4)  # 4 is length of UL
    fp.seek(location)  # ready for next data_element
    if isUndefinedLength:
        fp.write_tag(SequenceDelimiterTag)
        fp.write_UL(0)  # 4-byte 'length' of delimiter data item
    
def WriteDataset(fp, dataset):
    """Write a Dataset dictionary to the file. Return the total length written."""
    fpStart = fp.tell()
    # data_elements must be written in tag order
    tags = dataset.keys()
    tags.sort()
    for tag in tags:
        WriteDataElement(fp, dataset[tag])

    return fp.tell() - fpStart

def WriteSequence(fp, data_element):
    """Write a dicom Sequence contained in data_element to the file fp."""
    # WriteDataElement has already written the VR='SQ' (if needed) and
    #    a placeholder for length"""
    sequence = data_element.value
    for dataset in sequence:
        WriteSequenceItem(fp, dataset)

def WriteSequenceItem(fp, dataset):
    """Write an item (dataset) in a dicom Sequence to the dicom file fp."""
    # see Dicom standard Part 5, p. 39 ('03 version)
    # This is similar to writing a data_element, but with a specific tag for Sequence Item
    fp.write_tag(ItemTag)   # marker for start of Sequence Item
    length_location = fp.tell() # save location for later.
    fp.write_UL(0xffffffffL)   # will fill in real value later if not undefined length
    WriteDataset(fp, dataset)
    if dataset.isUndefinedLengthSequenceItem:
        fp.write_tag(ItemDelimiterTag)
        fp.write_UL(0)  # 4-bytes 'length' field for delimiter item
    else: # we will be nice and set the lengths for the reader of this file
        location = fp.tell()
        fp.seek(length_location)
        fp.write_UL(location - length_location - 4)  # 4 is length of UL
        fp.seek(location)  # ready for next data_element

def write_UN(fp, data_element):
    """Write a byte string for an DataElement of value 'UN' (unknown)."""
    fp.write(data_element.value)

def write_ATvalue(fp, data_element):
    """Write a data_element tag to a file."""
    try:
        data_element.value[1]  # see if is multi-valued AT 
    except TypeError:
        tag = Tag(data_element.value)   # make sure is expressed as a Tag instance
        fp.write_tag(tag)
    else:
        for tag in data_element.value:
            fp.write_tag(tag)
            

def _WriteFileMetaInfo(fp, dataset):
    """Write the dicom group 2 dicom storage File Meta Information to the file.

    The file should already be positioned past the 128 byte preamble.
    Raises ValueError if the required data_elements (elements 2,3,0x10,0x12)
    are not in the dataset. If the dataset came from a file read with
    ReadFile(), then the required data_elements should already be there.
    """
    fp.write('DICM')

    # File meta info is always LittleEndian, Explicit VR. After will change these
    #    to the transfer syntax values set in the meta info
    fp.isLittleEndian = True
    fp.isExplicitVR = True

    # Extract only group 2 items (but not elem 0 = group length we need to calc)
    #   out of the dataset for file meta info
    meta_dataset = Dataset()
    meta_dataset.update(
        dict([(tag, data_element) for tag,data_element in dataset.items() if tag.group == 2 and tag.elem != 0])
        )
    
    if Tag((2,1)) not in meta_dataset:
        meta_dataset.AddNew((2,1), 'OB', "\0\1")   # file meta information version
    
    # Now check that required meta info tags are present:
    missing = []
    for element in [2, 3, 0x10, 0x12]:
        if Tag((2, element)) not in meta_dataset:
            missing.append(Tag((2, element)))
    if missing:
        raise ValueError, "Missing required tags %s for file meta information" % str(missing)
    
    group_length_tell = fp.tell()
    group_length = DataElement((2,0), 'UL', 0) # put 0 to start, write again later when length is known
    WriteDataElement(fp, group_length)  # write that one first - get it out of the way

    length = WriteDataset(fp, meta_dataset)
    location = fp.tell()
    fp.seek(group_length_tell)
    group_length = DataElement((2,0), 'UL', length) # now have real length
    WriteDataElement(fp, group_length)  # write the whole data_element
    fp.seek(location)

def WriteFile(filename, dataset, WriteLikeOriginal=True):
    """Store a Dataset to the filename specified.
    
    Set dataset.preamble if you want something other than 128 0-bytes.
    If the dataset was read from an existing dicom file, then its preamble
    was stored at read time. It is up to you to ensure the preamble is still
    correct for its purposes.
    If there is no Transfer Syntax tag in the dataset,
       Set dataset.isExplicitVR or .isImplicitVR, and .isLittleEndian or .isBigEndian,
       to determine the transfer syntax used to write the file.
    WriteLikeOriginal -- True if want to preserve the following for each sequence 
        within this dataset:
        - preamble -- if no preamble in read file, than not used here
        - dataset.hasFileMeta -- if writer did not do file meta information,
            then don't write here either
        - seq.isUndefinedLength -- if original had delimiters, write them now too,
            instead of the more sensible length characters
        - <dataset>.isUndefinedLengthSequenceItem -- for datasets that belong to a 
            sequence, write the undefined length delimiters if that is 
            what the original had
        Set WriteLikeOriginal = False to produce a "nicer" DICOM file for other readers,
            where all lengths are explicit.
    """

    fp = DicomFile(filename,'wb')
    
    # Decide whether to write DICOM preamble. Should always do so unless trying to mimic the original file read in
    if not dataset.preamble and not WriteLikeOriginal:
        preamble = "\0"*128
    else:
        preamble = dataset.preamble
    
    if preamble:
        fp.write(preamble)  # blank 128 byte preamble
    
    
    
    if 'TransferSyntaxUID' not in dataset:
        if dataset.isLittleEndian and not dataset.isExplicitVR:
            dataset.AddNew((2, 0x10), 'UI', ImplicitVRLittleEndian)
        elif dataset.isLittleEndian and dataset.isExplicitVR:
            dataset.AddNew((2, 0x10), 'UI', ExplicitVRLittleEndian)
        elif dataset.isBigEndian and dataset.isExplicitVR:
            dataset.AddNew((2, 0x10), 'UI', ExplicitVRBigEndian)
        else:
            raise NotImplementedError, "pydicom has not been verified for Big Endian with Implicit VR"
    
    if preamble:
        _WriteFileMetaInfo(fp, dataset)
    # Set file VR, endian. MUST BE AFTER META INFO (which changes to Explict LittleEndian)
    fp.isImplicitVR = not dataset.isExplicitVR
    fp.isLittleEndian = dataset.isLittleEndian
    
    no_group2_dataset = Dataset()
    no_group2_dataset.update(dict([(tag,data_element) for tag,data_element in dataset.items() if tag.group != 2]))
    
    WriteDataset(fp, no_group2_dataset)
    fp.close()
        
# Writers map a VR to the function to Write the value(s)
# for Write_numbers, the Writer maps to a tuple (function, number format (struct module style))
writers = {'UL':(write_numbers,'L'), 'SL':(write_numbers,'l'),
           'US':(write_numbers,'H'), 'SS':(write_numbers, 'h'),
           'FL':(write_numbers,'f'), 'FD':(write_numbers, 'd'),
           'OF':(write_numbers,'f'),
           'OB':write_OBvalue, 'UI':write_UI,
           'SH':write_String,  'DA':write_String, 'TM': write_String,
           'CS':write_String,  'PN':write_String, 'LO': write_String,
           'IS':write_NumberString,  'DS':write_NumberString, 'AE': write_String,
           'AS':write_String,
           'LT':write_String,
           'SQ':WriteSequence,
           'UN':write_UN,
           'AT':write_ATvalue,
           'ST':write_String,
           'OW':write_OWvalue,
           'US or SS':write_OWvalue,
           'OW/OB':write_OBvalue,
           'DT':write_String,
           'UT':write_String,
           } # note OW/OB depends on other items, which we don't know at write time

def ReplaceDataElementValue(filename, data_element, new_value):
    """Modify a dicom file data_element value 'in-place'.
    
    This function is no longer needed - instead, read a dicom file,
    modify data_elements, and write the file to a new (or same) filename.
    This is a more primitive function - it modifies the value in-place
    in the file. Therefore the length of new_value must be the same as
    the existing file data_element value. If not, ValueError is raised.
    
    """
    # if a text or byte string value, check if is same length
    #    XXX have I included all the right VRs here?
    #    XXX should use writers dict to write new_value properly
    if data_element.VR not in ['UL', 'SL', 'US', 'SS', 'FL', 'FD'] and \
      len(new_value) != len(data_element.value) + (len(data_element.value) % 2):
        raise ValueError, "New value is not the same length as existing one"
    fp = file(filename, 'r+b')
    print "File position", hex(data_element.file_tell)
    fp.seek(data_element.file_tell)  # start of the value field
    fp.write(new_value)
    fp.close()
