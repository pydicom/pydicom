# values.py
"""Functions for converting values of DICOM data elements to proper python types
"""
# Copyright (c) 2010-2012 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

from struct import unpack, calcsize

from pydicom import config  # don't import datetime_conversion directly
from pydicom import compat
from pydicom.compat import in_py2
import pydicom.valuerep  # don't import DS directly as can be changed by config
from pydicom.valuerep import MultiString, DA, DT, TM
from pydicom.config import logger
if not in_py2:
    from pydicom.valuerep import PersonName3 as PersonName
else:
    from pydicom.valuerep import PersonName  # NOQA

from pydicom.multival import MultiValue
import pydicom.uid
from pydicom.tag import Tag, TupleTag
from pydicom.filereader import read_sequence
from io import BytesIO
from pydicom.charset import default_encoding, text_VRs


def convert_tag(byte_string, is_little_endian, offset=0):
    if is_little_endian:
        struct_format = "<HH"
    else:
        struct_format = ">HH"
    return TupleTag(unpack(struct_format, byte_string[offset:offset + 4]))


def convert_AE_string(byte_string, is_little_endian, struct_format=None,
                      encoding=default_encoding):
    """Read a byte string for a VR of 'AE'.

    Elements with VR of 'AE' have non-significant leading and trailing spaces.
    """
    if not in_py2:
        byte_string = byte_string.decode(encoding)
    byte_string = byte_string.strip()
    return byte_string


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


def _DA_from_byte_string(byte_string):
    byte_string = byte_string.rstrip()
    length = len(byte_string)
    if length != 8 and length != 0:
        logger.warn("Expected length to be 8, got length %d", length)
    return DA(byte_string)


def convert_DA_string(byte_string, is_little_endian, struct_format=None):
    """Read and return a DA value"""
    if config.datetime_conversion:
        if not in_py2:
            byte_string = byte_string.decode(default_encoding)
        splitup = byte_string.split("\\")
        if len(splitup) == 1:
            return _DA_from_byte_string(splitup[0])
        else:
            return MultiValue(_DA_from_byte_string, splitup)
    else:
        return convert_string(byte_string, is_little_endian, struct_format)


def convert_DS_string(byte_string, is_little_endian, struct_format=None):
    """Read and return a DS value or list of values"""
    if not in_py2:
        byte_string = byte_string.decode(default_encoding)
    # Below, go directly to DS class instance rather than factory DS,
    # but need to ensure last string doesn't have blank padding (use strip())
    return MultiString(byte_string.strip(), valtype=pydicom.valuerep.DSclass)


def _DT_from_byte_string(byte_string):
    byte_string = byte_string.rstrip()
    length = len(byte_string)
    if length < 4 or length > 26:
        logger.warn("Expected length between 4 and 26, got length %d", length)
    return DT(byte_string)


def convert_DT_string(byte_string, is_little_endian, struct_format=None):
    """Read and return a DT value"""
    if config.datetime_conversion:
        if not in_py2:
            byte_string = byte_string.decode(default_encoding)
        splitup = byte_string.split("\\")
        if len(splitup) == 1:
            return _DT_from_byte_string(splitup[0])
        else:
            return MultiValue(_DT_from_byte_string, splitup)
    else:
        return convert_string(byte_string, is_little_endian, struct_format)


def convert_IS_string(byte_string, is_little_endian, struct_format=None):
    """Read and return an IS value or list of values"""
    if not in_py2:
        byte_string = byte_string.decode(default_encoding)
    return MultiString(byte_string, valtype=pydicom.valuerep.IS)


def convert_numbers(byte_string, is_little_endian, struct_format):
    """Convert `byte_string` to a value, depending on `struct_format`.

    Given an encoded DICOM Element value, use `struct_format` and the endianness
    of the data to decode it.

    Parameters
    ----------
    byte_string : bytes
        The raw byte data to decode.
    is_little_endian : bool
        The encoding of `byte_string`.
    struct_format : str
        The type of data encoded in `byte_string`.

    Returns
    -------
    str
        If there is no encoded data in `byte_string` then an empty string will
        be returned.
    value
        If `byte_string` encodes a single value then it will be returned.
    list
        If `byte_string` encodes multiple values then a list of the decoded
        values will be returned.
    """
    endianChar = '><'[is_little_endian]
    bytes_per_value = calcsize("=" + struct_format)  # "=" means use 'standard' size, needed on 64-bit systems.
    length = len(byte_string)
    if length % bytes_per_value != 0:
        logger.warn("Expected length to be even multiple of number size")
    format_string = "%c%u%c" % (endianChar, length // bytes_per_value, struct_format)
    value = unpack(format_string, byte_string)
    if len(value) == 0:  # if the number is empty, then return the empty string rather than empty list
        return ''
    elif len(value) == 1:
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

    if encoding and not in_py2:
        args = (encoding,)
    else:
        args = ()

    # We would like to return string literals
    if not in_py2:
        valtype = lambda x: PersonName(x, *args).decode()
    else:
        valtype = lambda x: PersonName(x, *args)

    if len(splitup) == 1:
        return valtype(splitup[0])
    else:
        return MultiValue(valtype, splitup)


def convert_string(byte_string, is_little_endian, struct_format=None, encoding=default_encoding):
    """Read and return a string or strings"""
    if not in_py2:
        byte_string = byte_string.decode(encoding)
    return MultiString(byte_string)


def convert_single_string(byte_string, is_little_endian, struct_format=None,
                          encoding=default_encoding):
    """Read and return a single string (backslash character does not split)"""
    if not in_py2:
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


def _TM_from_byte_string(byte_string):
    byte_string = byte_string.rstrip()
    length = len(byte_string)
    if (length < 2 or length > 16) and length != 0:
        logger.warn("Expected length between 2 and 16, got length %d", length)
    return TM(byte_string)


def convert_TM_string(byte_string, is_little_endian, struct_format=None):
    """Read and return a TM value"""
    if config.datetime_conversion:
        if not in_py2:
            byte_string = byte_string.decode(default_encoding)
        splitup = byte_string.split("\\")
        if len(splitup) == 1:
            return _TM_from_byte_string(splitup[0])
        else:
            return MultiValue(_TM_from_byte_string, splitup)
    else:
        return convert_string(byte_string, is_little_endian, struct_format)


def convert_UI(byte_string, is_little_endian, struct_format=None):
    """Read and return a UI values or values"""
    # Strip off 0-byte padding for even length (if there)
    if not in_py2:
        byte_string = byte_string.decode(default_encoding)
    if byte_string and byte_string.endswith('\0'):
        byte_string = byte_string[:-1]
    return MultiString(byte_string, pydicom.uid.UID)


def convert_UN(byte_string, is_little_endian, struct_format=None):
    """Return a byte string for a VR of 'UN' (unknown)"""
    return byte_string


def convert_UR_string(byte_string, is_little_endian, struct_format=None,
                      encoding=default_encoding):
    """Read a byte string for a VR of 'UR'

    Elements with VR of 'UR' shall not be multi-valued and trailing spaces shall
    be ignored.
    """
    if not in_py2:
        byte_string = byte_string.decode(encoding)
    byte_string = byte_string.rstrip()
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
    if isinstance(encoding, compat.string_types):
        encoding = [encoding, ] * 3

    byte_string = raw_data_element.value
    is_little_endian = raw_data_element.is_little_endian
    is_implicit_VR = raw_data_element.is_implicit_VR

    # Not only two cases. Also need extra info if is a raw sequence
    # Pass the encoding to the converter if it is a specific VR
    try:
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
    except ValueError:
        if config.enforce_valid_values:
            # The user really wants an exception here
            raise
        logger.debug('unable to translate tag %s with VR %s' % (raw_data_element.tag, VR))
        for convert_vr in convert_retry_VR_order:
            vr = convert_vr
            converter = converters[vr]
            if vr == VR:
                continue
            try:
                value = convert_value(vr, raw_data_element, encoding)
                break
            except Exception:
                pass
            else:
                logger.debug('converted tag %s with VR %s' % (raw_data_element.tag, vr))
                value = raw_data_element.value
    return value

convert_retry_VR_order = [
    'SH', 'UL', 'SL', 'US', 'SS', 'FL', 'FD', 'OF', 'OB', 'UI', 'DA', 'TM',
    'PN', 'IS', 'DS', 'LT', 'SQ', 'UN', 'AT', 'OW', 'DT', 'UT', ]
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
    'OD': convert_OBvalue,
    'OL': convert_OBvalue,
    'UI': convert_UI,
    'SH': convert_string,
    'DA': convert_DA_string,
    'TM': convert_TM_string,
    'CS': convert_string,
    'PN': convert_PN,
    'LO': convert_string,
    'IS': convert_IS_string,
    'DS': convert_DS_string,
    'AE': convert_AE_string,
    'AS': convert_string,
    'LT': convert_single_string,
    'SQ': convert_SQ,
    'UC': convert_string,
    'UN': convert_UN,
    'UR': convert_UR_string,
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
    'DT': convert_DT_string,
    'UT': convert_single_string,
}
if __name__ == "__main__":
    pass
