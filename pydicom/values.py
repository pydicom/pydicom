# values.py
"""Functions for converting values of DICOM data elements to proper python types
"""
# Copyright (c) 2010-2012 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

from dicom import in_py3
from struct import unpack, calcsize
import logging
logger = logging.getLogger('pydicom')

# Because DS can be based on float or decimal, import whole module, not DS
#    directly, so it can be changed in user code and be updated here also
import dicom.valuerep
from dicom.valuerep import MultiString

if in_py3:
    from dicom.valuerep import PersonName3 as PersonName
else:
    from dicom.valuerep import PersonName  # NOQA

from dicom.multival import MultiValue
import dicom.UID
from dicom.tag import Tag, TupleTag
from dicom.filereader import read_sequence
from io import BytesIO
from dicom.charset import default_encoding, text_VRs


def convert_tag(byte_string, is_little_endian, offset=0):
    if is_little_endian:
        struct_format = "<HH"
    else:
        struct_format = ">HH"
    return TupleTag(unpack(struct_format, byte_string[offset:offset + 4]))


def convert_ATvalue(byte_string, is_little_endian, struct_format=None):
    """Read and return AT (tag) data_element value(s)"""
    length = len(byte_string)
    if length == 4:
        return convert_tag(byte_string, is_little_endian)
    # length > 4
    if length % 4 != 0:
        logger.warn("Expected length to be multiple of 4 for VR 'AT', "
                    "got length %d", length)
    return MultiValue(Tag, [convert_tag(byte_string, is_little_endian, offset=x)
                            for x in range(0, length, 4)])


def convert_DS_string(byte_string, is_little_endian, struct_format=None):
    """Read and return a DS value or list of values"""
    if in_py3:
        byte_string = byte_string.decode(default_encoding)
    # Below, go directly to DS class instance rather than factory DS,
    # but need to ensure last string doesn't have blank padding (use strip())
    return MultiString(byte_string.strip(), valtype=dicom.valuerep.DSclass)


def convert_IS_string(byte_string, is_little_endian, struct_format=None):
    """Read and return an IS value or list of values"""
    if in_py3:
        byte_string = byte_string.decode(default_encoding)
    return MultiString(byte_string, valtype=dicom.valuerep.IS)


def convert_numbers(byte_string, is_little_endian, struct_format):
    """Read a "value" of type struct_format from the dicom file. "Value" can be more than one number"""
    endianChar = '><'[is_little_endian]
    bytes_per_value = calcsize("=" + struct_format)  # "=" means use 'standard' size, needed on 64-bit systems.
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
    return convert_OBvalue(byte_string, is_little_endian)  # for now, Maybe later will have own routine


def convert_PN(byte_string, is_little_endian, struct_format=None, encoding=None):
    """Read and return string(s) as PersonName instance(s)"""

    # XXX - We have to replicate MultiString functionality here because we can't decode
    # easily here since that is performed in PersonNameUnicode
    if byte_string and (byte_string.endswith(b' ') or byte_string.endswith(b'\x00')):
        byte_string = byte_string[:-1]

    splitup = byte_string.split(b"\\")

    if encoding and in_py3:
        args = (encoding,)
    else:
        args = ()

    # We would like to return string literals
    if in_py3:
        valtype = lambda x: PersonName(x, *args).decode()
    else:
        valtype = lambda x: PersonName(x, *args)

    if len(splitup) == 1:
        return valtype(splitup[0])
    else:
        return MultiValue(valtype, splitup)


def convert_string(byte_string, is_little_endian, struct_format=None, encoding=default_encoding):
    """Read and return a string or strings"""
    if in_py3:
        byte_string = byte_string.decode(encoding)
    return MultiString(byte_string)


def convert_single_string(byte_string, is_little_endian, struct_format=None,
                          encoding=default_encoding):
    """Read and return a single string (backslash character does not split)"""
    if in_py3:
        byte_string = byte_string.decode(encoding)
    if byte_string and byte_string.endswith(' '):
        byte_string = byte_string[:-1]
    return byte_string


def convert_SQ(byte_string, is_implicit_VR, is_little_endian,
               encoding=default_encoding, offset=0):
    """Convert a sequence that has been read as bytes but not yet parsed."""
    fp = BytesIO(byte_string)
    seq = read_sequence(fp, is_implicit_VR, is_little_endian, len(byte_string),
                        encoding, offset)
    return seq


def convert_UI(byte_string, is_little_endian, struct_format=None):
    """Read and return a UI values or values"""
    # Strip off 0-byte padding for even length (if there)
    if in_py3:
        byte_string = byte_string.decode(default_encoding)
    if byte_string and byte_string.endswith('\0'):
        byte_string = byte_string[:-1]
    return MultiString(byte_string, dicom.UID.UID)


def convert_UN(byte_string, is_little_endian, struct_format=None):
    """Return a byte string for a VR of 'UN' (unknown)"""
    return byte_string


def convert_value(VR, raw_data_element, encoding=default_encoding):
    """Return the converted value (from raw bytes) for the given VR"""
    if VR not in converters:
        raise NotImplementedError("Unknown Value Representation '{0}'".format(VR))

    # Look up the function to convert that VR
    # Dispatch two cases: a plain converter, or a number one which needs a format string
    if isinstance(converters[VR], tuple):
        converter, num_format = converters[VR]
    else:
        converter = converters[VR]
        num_format = None

    # Ensure that encoding is in the proper 3-element format
    if isinstance(encoding, basestring):
        encoding = [encoding, ] * 3

    byte_string = raw_data_element.value
    is_little_endian = raw_data_element.is_little_endian
    is_implicit_VR = raw_data_element.is_implicit_VR

    # Not only two cases. Also need extra info if is a raw sequence
    # Pass the encoding to the converter if it is a specific VR
    if VR == 'PN':
        value = converter(byte_string, is_little_endian, encoding=encoding)
    elif VR in text_VRs:
        # Text VRs use the 2nd specified encoding
        value = converter(byte_string, is_little_endian, encoding=encoding[1])
    elif VR != "SQ":
        value = converter(byte_string, is_little_endian, num_format)
    else:
        value = convert_SQ(byte_string, is_implicit_VR, is_little_endian,
                           encoding, raw_data_element.value_tell)
    return value

# converters map a VR to the function to read the value(s).
# for convert_numbers, the converter maps to a tuple (function, struct_format)
#                        (struct_format in python struct module style)
converters = {
    'UL': (convert_numbers, 'L'),
    'SL': (convert_numbers, 'l'),
    'US': (convert_numbers, 'H'),
    'SS': (convert_numbers, 'h'),
    'FL': (convert_numbers, 'f'),
    'FD': (convert_numbers, 'd'),
    'OF': (convert_numbers, 'f'),
    'OB': convert_OBvalue,
    'UI': convert_UI,
    'SH': convert_string,
    'DA': convert_string,
    'TM': convert_string,
    'CS': convert_string,
    'PN': convert_PN,
    'LO': convert_string,
    'IS': convert_IS_string,
    'DS': convert_DS_string,
    'AE': convert_string,
    'AS': convert_string,
    'LT': convert_single_string,
    'SQ': convert_SQ,
    'UN': convert_UN,
    'AT': convert_ATvalue,
    'ST': convert_string,
    'OW': convert_OWvalue,
    'OW/OB': convert_OBvalue,  # note OW/OB depends on other items, which we don't know at read time
    'OB/OW': convert_OBvalue,
    'OW or OB': convert_OBvalue,
    'OB or OW': convert_OBvalue,
    'US or SS': convert_OWvalue,
    'US or OW': convert_OWvalue,
    'US or SS or OW': convert_OWvalue,
    'US\\US or SS\\US': convert_OWvalue,
    'DT': convert_string,
    'UT': convert_single_string,
}
if __name__ == "__main__":
    pass
