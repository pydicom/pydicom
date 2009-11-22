# readers.py
"""Functions for reading values of DICOM data elements"""
# Copyright (c) 2009 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

from struct import unpack, calcsize, pack
from dicom.fileutil import absorb_delimiter_item, length_of_undefined_length
from dicom.fileutil import read_delimiter_item
import logging
logger = logging.getLogger('pydicom')

from dicom.valuerep import PersonName, MultiValue, MultiString
import dicom.UID
from dicom.tag import Tag, SequenceDelimiterTag

def read_ATvalue(fp, length, format=None):
    """Read and return AT (tag) data_element value(s)"""
    if length == 4:
        return fp.read_tag()
    # length > 4
    if length % 4 != 0:
        logger.warn("Expected length to be multiple of 4 for VR 'AT', got length %d at file position 0x%x", length, fp.tell()-4)
    return MultiValue([fp.read_tag() for i in range(length / 4)])

def read_numbers(fp, length, format):
    """Read a "value" of type format from the dicom file. "Value" can be more than one number"""
    endianChar = '><'[fp.isLittleEndian]
    bytes_per_value = calcsize("="+format) # "=" means use 'standard' size, needed on 64-bit systems.
    data = fp.read(length)

    format_string = "%c%u%c" % (endianChar, length/bytes_per_value, format) 
    value = unpack(format_string, data)
    if len(value) == 1:
        return value[0]
    else:        
        return list(value)  # convert from tuple to a list so can modify if need to

def read_OBvalue(fp, length, format=None):
    """Return the raw bytes from reading an OB value"""
    isUndefinedLength = False
    if length == 0xffffffffL: # undefined length. PS3.6-2008 Tbl 7.1-1, then read to Sequence Delimiter Item
        isUndefinedLength = True
        length = length_of_undefined_length(fp, SequenceDelimiterTag)
    data = fp.read(length)
    # logger.debug("len(data): %d; length=%d", len(data), length)
    # logger.debug("OB before absorb: 0x%x", fp.tell())
    if isUndefinedLength:
        absorb_delimiter_item(fp, Tag(SequenceDelimiterTag))
    return data

def read_OWvalue(fp, length, format=None):
    """Return the raw bytes from reading an OW value rep
    
    Note: pydicom does NOT do byte swapping, except in 
    dataset.pixel_array function
    """
    return read_OBvalue(fp, length) # for now, Maybe later will have own routine

def read_PN(fp, length, format=None):
    """Read and return string(s) as PersonName instance(s)"""
    return MultiString(fp.read(length), valtype=PersonName)

def read_string(fp, length, format=None):
    """Read and return a string or strings"""
    return MultiString(fp.read(length))

def read_single_string(fp, length, format=None):
    """Read and return a single string (backslash character does not split)"""
    val = fp.read(length)
    if val and val.endswith(' '):
        val = val[:-1]
    return val

def read_UI(fp, length, format=None):
    """Read and return a UI values or values"""
    value = fp.read(length)
    # Strip off 0-byte padding for even length (if there)
    if value and value.endswith('\0'):
        value = value[:-1]
    return MultiString(value, dicom.UID.UID)

def read_UN(fp, length, format=None):
    """Return a byte string for an DataElement of value 'UN' (unknown)
    
    Raise NotImplementedError if length is 'Undefined Length'
    """
    if length == 0xFFFFFFFFL:
        raise NotImplementedError, "This code has not been tested for 'UN' with unknown length"
        # Below code is draft attempt to read undefined length
        delimiter = 0xFFFEE00DL
        length = length_of_undefined_length(fp, delimiter)
        data_value = fp.read(length)
        read_delimiter_item(fp, delimiter)
        return data_value
    else:
        return fp.read(length)
        
def read_VR(fp):
    """Return the two character Value Representation string"""
    return unpack("2s", fp.read(2))[0]

# Readers map a VR to the function to read the value(s).
# for read_numbers, the reader maps to a tuple (function, number format (in python struct module style))
readers = {'UL':(read_numbers,'L'), 'SL':(read_numbers,'l'),
           'US':(read_numbers,'H'), 'SS':(read_numbers, 'h'),
           'FL':(read_numbers,'f'), 'FD':(read_numbers, 'd'),
           'OF':(read_numbers,'f'),
           'OB':read_OBvalue, 'UI':read_UI,
           'SH':read_string,  'DA':read_string, 'TM': read_string,
           'CS':read_string,  'PN':read_PN,     'LO': read_string,
           'IS':read_string,  'DS':read_string, 'AE': read_string,
           'AS':read_string,
           'LT':read_single_string,
           # 'SQ': read_sequence added in filereader.py to avoid circular import
           'UN':read_UN,
           'AT':read_ATvalue,
           'ST':read_string,
           'OW':read_OWvalue,
           'OW/OB':read_OBvalue,# note OW/OB depends on other items, which we don't know at read time
           'OB/OW':read_OBvalue,
           'US or SS':read_OWvalue,
           'US or SS or OW':read_OWvalue,
           'US\US or SS\US':read_OWvalue,
           'DT':read_string,
           'UT':read_single_string,          
           } 
