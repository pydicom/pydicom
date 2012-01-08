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

from dicom.valuerep import PersonName, MultiValue, MultiString
import dicom.UID
from dicom.tag import Tag, TupleTag, SequenceDelimiterTag
from dicom.datadict import dictionaryVR
from dicom.filereader import read_sequence
from cStringIO import StringIO
from dicom.valuerep import DS

def convert_tag(bytes, is_little_endian, offset=0):
    if is_little_endian:
        struct_format = "<HH"
    else:
        struct_format = ">HH"
    return TupleTag(unpack(struct_format, bytes[offset:offset+4]))
    
def convert_ATvalue(bytes, is_little_endian, struct_format=None):
    """Read and return AT (tag) data_element value(s)"""
    length = len(bytes)
    if length == 4:
        return convert_tag(bytes, is_little_endian)
    # length > 4
    if length % 4 != 0:
        logger.warn("Expected length to be multiple of 4 for VR 'AT', got length %d at file position 0x%x", length, fp.tell()-4)
    return MultiValue([convert_tag(bytes, is_little_endian, offset=x) 
                        for x in range(0, length, 4)])

def convert_numbers(bytes, is_little_endian, struct_format):
    """Read a "value" of type struct_format from the dicom file. "Value" can be more than one number"""
    endianChar = '><'[is_little_endian]
    bytes_per_value = calcsize("="+struct_format) # "=" means use 'standard' size, needed on 64-bit systems.
    length = len(bytes)
    if length % bytes_per_value != 0:
        logger.warn("Expected length to be even multiple of number size")
    format_string = "%c%u%c" % (endianChar, length // bytes_per_value, struct_format) 
    value = unpack(format_string, bytes)
    if len(value) == 1:
        return value[0]
    else:        
        return list(value)  # convert from tuple to a list so can modify if need to

def convert_OBvalue(bytes, is_little_endian, struct_format=None):
    """Return the raw bytes from reading an OB value"""
    return bytes
    
def convert_OWvalue(bytes, is_little_endian, struct_format=None):
    """Return the raw bytes from reading an OW value rep
    
    Note: pydicom does NOT do byte swapping, except in 
    dataset.pixel_array function
    """
    return convert_OBvalue(bytes, is_little_endian) # for now, Maybe later will have own routine

def convert_PN(bytes, is_little_endian, struct_format=None):
    """Read and return string(s) as PersonName instance(s)"""
    return MultiString(bytes, valtype=PersonName)

def convert_string(bytes, is_little_endian, struct_format=None):
    """Read and return a string or strings"""
    return MultiString(bytes)

def convert_number_string(bytes, is_little_endian, struct_format=None):
    """Read and return a DS or IS value or list of values"""
    return MultiString(bytes, valtype=DS)
    
def convert_single_string(bytes, is_little_endian, struct_format=None):
    """Read and return a single string (backslash character does not split)"""
    if bytes and bytes.endswith(' '):
        bytes = bytes[:-1]
    return bytes

def convert_SQ(bytes, is_implicit_VR, is_little_endian, offset=0):
    """Convert a sequence that has been read as bytes but not yet parsed."""
    fp = StringIO(bytes)
    seq = read_sequence(fp, is_implicit_VR, is_little_endian, len(bytes), offset)
    return seq
    
def convert_UI(bytes, is_little_endian, struct_format=None):
    """Read and return a UI values or values"""
    # Strip off 0-byte padding for even length (if there)
    if bytes and bytes.endswith('\0'):
        bytes = bytes[:-1]
    return MultiString(bytes, dicom.UID.UID)

def convert_UN(bytes, is_little_endian, struct_format=None):
    """Return a byte string for a VR of 'UN' (unknown)"""
    return bytes 

def convert_value(VR, raw_data_element):
    """Return the converted value (from raw bytes) for the given VR"""
    tag = Tag(raw_data_element.tag)
    if VR not in converters:
        raise NotImplementedError, "Unknown Value Representation '%s'" % VR

    # Look up the function to convert that VR
    # Dispatch two cases: a plain converter, or a number one which needs a format string
    if isinstance(converters[VR], tuple):
        converter, num_format = converters[VR]
    else:
        converter = converters[VR]
        num_format = None
    
    bytes = raw_data_element.value
    is_little_endian = raw_data_element.is_little_endian
    is_implicit_VR = raw_data_element.is_implicit_VR
    
    # Not only two cases. Also need extra info if is a raw sequence
    if VR != "SQ":
        value = converter(bytes, is_little_endian, num_format)
    else:
        value = convert_SQ(bytes, is_implicit_VR, is_little_endian, raw_data_element.value_tell)
    return value

# converters map a VR to the function to read the value(s).
# for convert_numbers, the converter maps to a tuple (function, struct_format)
#                        (struct_format in python struct module style)
converters = {'UL':(convert_numbers,'L'), 'SL':(convert_numbers,'l'),
           'US':(convert_numbers,'H'), 'SS':(convert_numbers, 'h'),
           'FL':(convert_numbers,'f'), 'FD':(convert_numbers, 'd'),
           'OF':(convert_numbers,'f'),
           'OB':convert_OBvalue, 'UI':convert_UI,
           'SH':convert_string,  'DA':convert_string, 'TM': convert_string,
           'CS':convert_string,  'PN':convert_PN,     'LO': convert_string,
           'IS':convert_number_string,  'DS':convert_number_string,
           'AE': convert_string,
           'AS':convert_string,
           'LT':convert_single_string,
           'SQ':convert_SQ,
           'UN':convert_UN,
           'AT':convert_ATvalue,
           'ST':convert_string,
           'OW':convert_OWvalue,
           'OW/OB':convert_OBvalue,# note OW/OB depends on other items, which we don't know at read time
           'OB/OW':convert_OBvalue,
           'OW or OB': convert_OBvalue,
           'OB or OW': convert_OBvalue,
           'US or SS':convert_OWvalue,
           'US or SS or OW':convert_OWvalue,
           'US\US or SS\US':convert_OWvalue,
           'DT':convert_string,
           'UT':convert_single_string,          
           } 
if __name__ == "__main__":
    pass