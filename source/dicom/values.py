# values.py
"""Functions for converting values of DICOM data elements to proper python types
"""
# Copyright (c) 2010-2012 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

from struct import unpack, calcsize, pack
import logging
logger = logging.getLogger('pydicom')

from dicom.valuerep import PersonName, MultiString
from dicom.multival import MultiValue
import dicom.UID
from dicom.tag import Tag, TupleTag, SequenceDelimiterTag
from dicom.datadict import dictionaryVR
from dicom.filereader import read_sequence
from cStringIO import StringIO
from dicom.valuerep import DS, IS

def convert_tag(byte_string, is_little_endian, offset=0):
    if is_little_endian:
        struct_format = b"<HH"
    else:
        struct_format = b">HH"
    return TupleTag(unpack(struct_format, byte_string[offset:offset+4]))
    
def convert_ATvalue(byte_string, is_little_endian, struct_format=None):
    """Read and return AT (tag) data_element value(s)"""
    length = len(byte_string)
    if length == 4:
        return convert_tag(byte_string, is_little_endian)
    # length > 4
    if length % 4 != 0:
        logger.warn("Expected length to be multiple of 4 for VR 'AT', got length %d at file position 0x%x", length, fp.tell()-4)
    return MultiValue(Tag,[convert_tag(byte_string, is_little_endian, offset=x) 
                        for x in range(0, length, 4)])

def convert_DS_string(byte_string, is_little_endian, struct_format=None):
    """Read and return a DS value or list of values"""
    return MultiString(byte_string, valtype=DS)

def convert_IS_string(byte_string, is_little_endian, struct_format=None):
    """Read and return an IS value or list of values"""
    return MultiString(byte_string, valtype=IS)
    
def convert_numbers(byte_string, is_little_endian, struct_format):
    """Read a "value" of type struct_format from the dicom file. "Value" can be more than one number"""
    endianChar = '><'[is_little_endian]
    bytes_per_value = calcsize("="+struct_format) # "=" means use 'standard' size, needed on 64-bit systems.
    length = len(byte_string)
    if length % bytes_per_value != 0:
        logger.warn("Expected length to be even multiple of number size")
    format_string = "%c%u%c" % (endianChar, length // bytes_per_value, struct_format) 
    value = unpack(format_string, byte_string)
    if len(value) == 1:
        return value[0]
    else:        
        return list(value)  # convert from tuple to a list so can modify if need to

def convert_OBvalue(byte_string, is_little_endian, struct_format=None):
    """Return the raw bytes from reading an OB value"""
    return byte_string
    
def convert_OWvalue(byte_string, is_little_endian, struct_format=None):
    """Return the raw bytes from reading an OW value rep
    
    Note: pydicom does NOT do byte swapping, except in 
    dataset.pixel_array function
    """
    return convert_OBvalue(byte_string, is_little_endian) # for now, Maybe later will have own routine

def convert_PN(byte_string, is_little_endian, struct_format=None):
    """Read and return string(s) as PersonName instance(s)"""
    return MultiString(byte_string, valtype=PersonName)

def convert_string(byte_string, is_little_endian, struct_format=None):
    """Read and return a string or strings"""
    return MultiString(byte_string)

def convert_single_string(byte_string, is_little_endian, struct_format=None):
    """Read and return a single string (backslash character does not split)"""
    if byte_string and byte_string.endswith(b' '):
        byte_string = byte_string[:-1]
    return byte_string

def convert_SQ(byte_string, is_implicit_VR, is_little_endian, offset=0):
    """Convert a sequence that has been read as bytes but not yet parsed."""
    fp = StringIO(byte_string)
    seq = read_sequence(fp, is_implicit_VR, is_little_endian, len(byte_string), offset)
    return seq
    
def convert_UI(byte_string, is_little_endian, struct_format=None):
    """Read and return a UI values or values"""
    # Strip off 0-byte padding for even length (if there)   
    if byte_string and byte_string.endswith(b'\0'):
        byte_string = byte_string[:-1]
    return MultiString(byte_string, dicom.UID.UID)

def convert_UN(byte_string, is_little_endian, struct_format=None):
    """Return a byte string for a VR of 'UN' (unknown)"""
    return byte_string 

def convert_value(VR, raw_data_element):
    """Return the converted value (from raw bytes) for the given VR"""
    tag = Tag(raw_data_element.tag)
    if VR not in converters:  
        raise NotImplementedError("Unknown Value Representation '{0}'".format(VR))

    # Look up the function to convert that VR
    # Dispatch two cases: a plain converter, or a number one which needs a format string
    if isinstance(converters[VR], tuple):
        converter, num_format = converters[VR]
    else:
        converter = converters[VR]
        num_format = None
    
    byte_string = raw_data_element.value
    is_little_endian = raw_data_element.is_little_endian
    is_implicit_VR = raw_data_element.is_implicit_VR
    
    # Not only two cases. Also need extra info if is a raw sequence
    if VR != "SQ":
        value = converter(byte_string, is_little_endian, num_format)
    else:
        value = convert_SQ(byte_string, is_implicit_VR, is_little_endian, raw_data_element.value_tell)
    return value

# converters map a VR to the function to read the value(s).
# for convert_numbers, the converter maps to a tuple (function, struct_format)
#                        (struct_format in python struct module style)
converters = {b'UL':(convert_numbers,b'L'), b'SL':(convert_numbers, b'l'),
           b'US':(convert_numbers,b'H'), b'SS':(convert_numbers, b'h'),
           b'FL':(convert_numbers,b'f'), b'FD':(convert_numbers, b'd'),
           b'OF':(convert_numbers, b'f'),
           b'OB':convert_OBvalue, b'UI':convert_UI,
           b'SH':convert_string,  b'DA':convert_string, b'TM': convert_string,
           b'CS':convert_string,  b'PN':convert_PN,     b'LO': convert_string,
           b'IS':convert_IS_string,  b'DS':convert_DS_string,
           b'AE': convert_string,
           b'AS':convert_string,
           b'LT':convert_single_string,
           b'SQ':convert_SQ,
           b'UN':convert_UN,
           b'AT':convert_ATvalue,
           b'ST':convert_string,
           b'OW':convert_OWvalue,
           b'OW/OB':convert_OBvalue,# note OW/OB depends on other items, which we don't know at read time
           b'OB/OW':convert_OBvalue,
           b'OW or OB': convert_OBvalue,
           b'OB or OW': convert_OBvalue,
           b'US or SS':convert_OWvalue,
           b'US or SS or OW':convert_OWvalue,          
           b'US\\US or SS\\US':convert_OWvalue,
           b'DT':convert_string,
           b'UT':convert_single_string,          
           } 
if __name__ == "__main__":
    pass