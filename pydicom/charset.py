# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Handle alternate character sets for character strings."""
import re
import warnings

from pydicom import compat
from pydicom.valuerep import PersonNameUnicode, text_VRs, TEXT_VR_DELIMS
from pydicom.compat import in_py2

# Map DICOM Specific Character Set to python equivalent
python_encoding = {

    # default character set for DICOM
    '': 'iso8859',

    # alias for latin_1 too (iso_ir_6 exists as an alias to 'ascii')
    'ISO_IR 6': 'iso8859',
    'ISO_IR 13': 'shift_jis',

    # these also have iso_ir_1XX aliases in python 2.7
    'ISO_IR 100': 'latin_1',
    'ISO_IR 101': 'iso8859_2',
    'ISO_IR 109': 'iso8859_3',
    'ISO_IR 110': 'iso8859_4',
    'ISO_IR 126': 'iso_ir_126',  # Greek
    'ISO_IR 127': 'iso_ir_127',  # Arabic
    'ISO_IR 138': 'iso_ir_138',  # Hebrew
    'ISO_IR 144': 'iso_ir_144',  # Russian
    'ISO_IR 148': 'iso_ir_148',  # Turkish
    'ISO_IR 166': 'iso_ir_166',  # Thai
    'ISO 2022 IR 6': 'iso8859',  # alias for latin_1 too
    'ISO 2022 IR 13': 'shift_jis',
    'ISO 2022 IR 87': 'iso2022_jp',
    'ISO 2022 IR 100': 'latin_1',
    'ISO 2022 IR 101': 'iso8859_2',
    'ISO 2022 IR 109': 'iso8859_3',
    'ISO 2022 IR 110': 'iso8859_4',
    'ISO 2022 IR 126': 'iso_ir_126',
    'ISO 2022 IR 127': 'iso_ir_127',
    'ISO 2022 IR 138': 'iso_ir_138',
    'ISO 2022 IR 144': 'iso_ir_144',
    'ISO 2022 IR 148': 'iso_ir_148',
    'ISO 2022 IR 149': 'euc_kr',
    'ISO 2022 IR 159': 'iso-2022-jp',
    'ISO 2022 IR 166': 'iso_ir_166',
    'ISO 2022 IR 58': 'iso_ir_58',
    'ISO_IR 192': 'UTF8',  # from Chinese example, 2008 PS3.5 Annex J p1-4
    'GB18030': 'GB18030',
    'ISO 2022 GBK': 'GBK',  # from DICOM correction CP1234
    'ISO 2022 58': 'GB2312',  # from DICOM correction CP1234
    'GBK': 'GBK',  # from DICOM correction CP1234
}

# the escape character used to mark the start of escape sequences
ESC = b'\x1b'

# Map Python encodings to escape sequences as defined in PS3.3 in tables
# C.12-3 (single-byte) and C.12-4 (multi-byte character sets).
escape_codes = {
    'iso8859': ESC + b'(B',  # used to switch to ASCII G0 code element
    'latin_1': ESC + b'-A',
    'shift_jis': ESC + b')I',
    'iso2022_jp': ESC + b'$B',
    'iso8859_2': ESC + b'-B',
    'iso8859_3': ESC + b'-C',
    'iso8859_4': ESC + b'-D',
    'iso_ir_126': ESC + b'-F',
    'iso_ir_127': ESC + b'-G',
    'iso_ir_138': ESC + b'-H',
    'iso_ir_144': ESC + b'-L',
    'iso_ir_148': ESC + b'-M',
    'iso_ir_166': ESC + b'-T',
    'euc_kr': ESC + b'$)C',
    'iso-2022-jp': ESC + b'$(D',
    'iso_ir_58': ESC + b'$)A',
}

default_encoding = "iso8859"


def decode_string(value, encodings, delims):
    """Convert a raw byte string into a unicode string using the given
    list of encodings.

    Parameters
    ----------
    value : byte string
        The raw string as encoded in the DICOM tag value.
    encodings : list
        The encodings needed to decode the string as a list of Python
        encodings, converted from the encodings in Specific Character Set.
    delims : byte string
        A string containing all characters that may cause the encoding of
        `value` to change.

    Returns
    -------
    text type
        The decoded string.
    """
    if ESC not in value:
        return value.decode(encodings[0])

    # multi-byte character sets except Korean are handled by Python encodings
    use_python_handling = value.startswith((escape_codes['iso2022_jp'],
                                            escape_codes['iso-2022-jp'],
                                            escape_codes['iso_ir_58']))

    if use_python_handling:
        values = [value]
    else:
        # Each part of the value that starts with an escape sequence
        # or a delimiter as defined in PS3.5, section 6.1.2.5.3 is decoded
        # separately. If it starts with an escape sequence, the
        # corresponding encoding is used, otherwise the first encoding.
        # See PS3.5, 6.1.2.4 and 6.1.2.5 for the use of code extensions.
        #
        # The following regex splits the value into these parts, by matching
        # substrings at line start not containing any of the delimiters,
        # and substrings starting with a delimiter and not containing other
        # delimiters.
        regex = b'(^[^' + delims + b']+|[' + delims + b'][^' + delims + b']*)'
        values = re.findall(regex, value)

    result = u''

    for part in values:
        if part.startswith(ESC):
            for enc in list(encodings) + ['iso8859']:
                if enc in escape_codes and part.startswith(escape_codes[enc]):
                    if use_python_handling:
                        # Python strips the escape sequences for this encoding
                        val = part.decode(enc)
                    else:
                        # Python doesn't know about the escape sequence -
                        # we have to strip it ourselves
                        val = part[len(escape_codes[enc]):].decode(enc)
                    break
            else:
                # unknown escape code - use first encoding (probably incorrect)
                val = part.decode(encodings[0])
        else:
            # if no escape code is given, the first encoding is used
            val = part.decode(encodings[0])
        result += val
    return result


# DICOM PS3.5-2008 6.1.1 (p 18) says:
#   default is ISO-IR 6 G0, equiv to common chr set of ISO 8859 (PS3.5 6.1.2.1)
#    (0008,0005)  value 1 can *replace* the default encoding...
#           for VRs of SH, LO, ST, LT, PN and UT (PS3.5 6.1.2.3)...
#           with a single-byte character encoding
#  if (0008,0005) is multi-valued, then value 1 (or default if blank)...
#           is used until code extension escape sequence is hit,
#          which can be at start of string, or after CR/LF, FF, or
#          in Person Name PN, after ^ or =
# NOTE also that 7.5.3 SEQUENCE INHERITANCE states that if (0008,0005)
#       is not present in a sequence item then it is inherited from its parent.


def convert_encodings(encodings):
    """Converts DICOM encodings into corresponding python encodings"""

    # If a list if passed, we don't want to modify the list in place so copy it
    encodings = encodings[:]

    if isinstance(encodings, compat.string_types):
        encodings = [encodings]
    elif not encodings[0]:
        encodings[0] = 'ISO_IR 6'

    try:
        encodings = [python_encoding[x] for x in encodings]

    except KeyError:
        # check for some common mistakes in encodings
        patched_encodings = []
        patched = {}
        for x in encodings:
            if re.match('^ISO[^_]IR', x):
                patched[x] = 'ISO_IR' + x[6:]
                patched_encodings.append(patched[x])
            else:
                patched_encodings.append(x)
        if patched:
            try:
                encodings = [python_encoding[x] for x in patched_encodings]
                for old, new in patched.items():
                    warnings.warn("Incorrect value for Specific Character Set "
                                  "'{}' - assuming '{}'".format(old, new),
                                  stacklevel=2)
            except KeyError:
                # assume that it is already a python encoding
                # otherwise, a LookupError will be raised in the using code
                pass

    return encodings


def decode(data_element, dicom_character_set):
    """Apply the DICOM character encoding to the data element

    data_element -- DataElement instance containing a value to convert
    dicom_character_set -- the value of Specific Character Set (0008,0005),
                    which may be a single value,
                    a multiple value (code extension), or
                    may also be '' or None.
                    If blank or None, ISO_IR 6 is used.

    """
    if not dicom_character_set:
        dicom_character_set = ['ISO_IR 6']

    encodings = convert_encodings(dicom_character_set)

    # decode the string value to unicode
    # PN is special case as may have 3 components with differenct chr sets
    if data_element.VR == "PN":
        if not in_py2:
            if data_element.VM == 1:
                data_element.value = data_element.value.decode(encodings)
            else:
                data_element.value = [
                    val.decode(encodings) for val in data_element.value
                ]
        else:
            if data_element.VM == 1:
                data_element.value = PersonNameUnicode(data_element.value,
                                                       encodings)
            else:
                data_element.value = [
                    PersonNameUnicode(value, encodings)
                    for value in data_element.value
                ]
    if data_element.VR in text_VRs:
        # You can't re-decode unicode (string literals in py3)
        if data_element.VM == 1:
            if isinstance(data_element.value, compat.text_type):
                return
            data_element.value = decode_string(data_element.value, encodings,
                                               TEXT_VR_DELIMS)
        else:

            output = list()

            for value in data_element.value:
                if isinstance(value, compat.text_type):
                    output.append(value)
                else:
                    output.append(decode_string(value, encodings,
                                                TEXT_VR_DELIMS))

            data_element.value = output
