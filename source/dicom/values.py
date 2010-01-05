# values.py
"""Functions for converting values of DICOM data elements to proper python types
"""
# Copyright (c) 2010 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

from struct import unpack, calcsize, pack
import logging
logger = logging.getLogger('pydicom')

from dicom.valuerep import PersonName, MultiValue, MultiString
import dicom.UID
from dicom.tag import Tag, SequenceDelimiterTag
from dicom.datadict import dictionaryVR

def convert_tag(bytes, is_little_endian, offset=0):
    if is_little_endian:
        format = "<HH"
    else:
        format = ">HH"
    return Tag(unpack(format, bytes[offset:offset+4])[0])
    
def convert_ATvalue(bytes, is_little_endian, format=None):
    """Read and return AT (tag) data_element value(s)"""
    length = len(bytes)
    if length == 4:
        return convert_tag(bytes)
    # length > 4
    if length % 4 != 0:
        logger.warn("Expected length to be multiple of 4 for VR 'AT', got length %d at file position 0x%x", length, fp.tell()-4)
    return MultiValue([convert_tag(bytes, is_little_endian, offset=x) for x in range(0, length, 4)])

def convert_numbers(bytes, is_little_endian, format):
    """Read a "value" of type format from the dicom file. "Value" can be more than one number"""
    endianChar = '><'[is_little_endian]
    bytes_per_value = calcsize("="+format) # "=" means use 'standard' size, needed on 64-bit systems.
    length = len(bytes)
    format_string = "%c%u%c" % (endianChar, length/bytes_per_value, format) 
    value = unpack(format_string, bytes)
    if len(value) == 1:
        return value[0]
    else:        
        return list(value)  # convert from tuple to a list so can modify if need to

def convert_OBvalue(bytes, is_little_endian, format=None):
    """Return the raw bytes from reading an OB value"""
    return bytes
    
def convert_OWvalue(bytes, is_little_endian, format=None):
    """Return the raw bytes from reading an OW value rep
    
    Note: pydicom does NOT do byte swapping, except in 
    dataset.pixel_array function
    """
    return convert_OBvalue(bytes, is_little_endian) # for now, Maybe later will have own routine

def convert_PN(bytes, is_little_endian, format=None):
    """Read and return string(s) as PersonName instance(s)"""
    return MultiString(bytes, valtype=PersonName)

def convert_string(bytes, is_little_endian, format=None):
    """Read and return a string or strings"""
    return MultiString(bytes)

def convert_single_string(bytes, is_little_endian, format=None):
    """Read and return a single string (backslash character does not split)"""
    if bytes and bytes.endswith(' '):
        bytes = bytes[:-1]
    return bytes

def convert_UI(bytes, is_little_endian, format=None):
    """Read and return a UI values or values"""
    # Strip off 0-byte padding for even length (if there)
    if bytes and bytes.endswith('\0'):
        bytes = bytes[:-1]
    return MultiString(bytes, dicom.UID.UID)

def convert_UN(bytes, is_little_endian, format=None):
    """Return a byte string for a VR of 'UN' (unknown)"""
    return bytes 

def convert_value(VR, bytes, is_little_endian):
    if VR is None: # Can be if was implicit VR
        try:
            VR = dictionaryVR(tag)
        except KeyError:
            if tag.is_private:
                VR = 'OB'  # just read the bytes, no way to know what they mean
            elif tag.element == 0:  # group length tag implied in versions < 3.0
                VR = 'UL'
            else:
                raise KeyError, "Unknown DICOM tag %s - can't look up VR" % str(tag)
    if VR not in converters:
        raise NotImplementedError, "Unknown Value Representation '%s'" % VR

    # Look up the function to convert that VR
    # Dispatch two cases: a plain converter, or a number one which needs a format string
    if isinstance(converters[VR], tuple):
        converter, num_format = converters[VR]
    else:
        converter = converters[VR]
        num_format = None

    value = converter(bytes, is_little_endian, num_format)
    return value

# converters map a VR to the function to read the value(s).
# for convert_numbers, the converter maps to a tuple (function, number format (in python struct module style))
converters = {'UL':(convert_numbers,'L'), 'SL':(convert_numbers,'l'),
           'US':(convert_numbers,'H'), 'SS':(convert_numbers, 'h'),
           'FL':(convert_numbers,'f'), 'FD':(convert_numbers, 'd'),
           'OF':(convert_numbers,'f'),
           'OB':convert_OBvalue, 'UI':convert_UI,
           'SH':convert_string,  'DA':convert_string, 'TM': convert_string,
           'CS':convert_string,  'PN':convert_PN,     'LO': convert_string,
           'IS':convert_string,  'DS':convert_string, 'AE': convert_string,
           'AS':convert_string,
           'LT':convert_single_string,
           # 'SQ': convert_sequence added in filereader.py to avoid circular import
           'UN':convert_UN,
           'AT':convert_ATvalue,
           'ST':convert_string,
           'OW':convert_OWvalue,
           'OW/OB':convert_OBvalue,# note OW/OB depends on other items, which we don't know at read time
           'OB/OW':convert_OBvalue,
           'US or SS':convert_OWvalue,
           'US or SS or OW':convert_OWvalue,
           'US\US or SS\US':convert_OWvalue,
           'DT':convert_string,
           'UT':convert_single_string,          
           } 
