# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Handle alternate character sets for character strings."""
import re
import warnings

from pydicom import compat, config
from pydicom.valuerep import PersonNameUnicode, text_VRs, TEXT_VR_DELIMS
from pydicom.compat import in_py2

# default encoding if no encoding defined - corresponds to ISO IR 6 / ASCII
default_encoding = "iso8859"

# Map DICOM Specific Character Set to python equivalent
python_encoding = {

    # default character set for DICOM
    '': default_encoding,

    # alias for latin_1 too (iso_ir_6 exists as an alias to 'ascii')
    'ISO_IR 6': default_encoding,
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

# these encodings cannot be used with code extensions
# see DICOM Standard, Part 3, Table C.12-5
# and DICOM Standard, Part 5, Section 6.1.2.5.4, item d
STAND_ALONE_ENCODINGS = ('ISO_IR 192', 'GBK', 'GB18030')

# the escape character used to mark the start of escape sequences
ESC = b'\x1b'

# Map Python encodings to escape sequences as defined in PS3.3 in tables
# C.12-3 (single-byte) and C.12-4 (multi-byte character sets).
CODES_TO_ENCODINGS = {
    ESC + b'(B': default_encoding,  # used to switch to ASCII G0 code element
    ESC + b'-A': 'latin_1',
    ESC + b')I': 'shift_jis',  # switches to ISO-IR 13
    ESC + b'(J': 'shift_jis',  # switches to ISO-IR 14 (shift_jis handles both)
    ESC + b'$B': 'iso2022_jp',
    ESC + b'-B': 'iso8859_2',
    ESC + b'-C': 'iso8859_3',
    ESC + b'-D': 'iso8859_4',
    ESC + b'-F': 'iso_ir_126',
    ESC + b'-G': 'iso_ir_127',
    ESC + b'-H': 'iso_ir_138',
    ESC + b'-L': 'iso_ir_144',
    ESC + b'-M': 'iso_ir_148',
    ESC + b'-T': 'iso_ir_166',
    ESC + b'$)C': 'euc_kr',
    ESC + b'$(D': 'iso-2022-jp',
    ESC + b'$)A': 'iso_ir_58',
}

ENCODINGS_TO_CODES = {v: k for k, v in CODES_TO_ENCODINGS.items()}

# Multi-byte character sets except Korean are handled by Python.
# To decode them, the escape sequence shall be preserved in the input byte
# string, and will be removed during decoding by Python.
handled_encodings = ('iso2022_jp',
                     'iso-2022-jp',
                     'iso_ir_58')


def decode_string(value, encodings, delimiters):
    """Convert a raw byte string into a unicode string using the given
    list of encodings.

    Parameters
    ----------
    value : byte string
        The raw string as encoded in the DICOM tag value.
    encodings : list
        The encodings needed to decode the string as a list of Python
        encodings, converted from the encodings in Specific Character Set.
    delimiters: set of int (Python 3) or characters (Python 2)
        A set of characters or character codes, each of which resets the
        encoding in `byte_str`.

    Returns
    -------
    text type
        The decoded unicode string. If the value could not be decoded,
        and `config.enforce_valid_values` is not set, a warning is issued,
        and the value is decoded using the first encoding with replacement
        characters, resulting in data loss.

    Raises
    ------
    UnicodeDecodeError
        If `config.enforce_valid_values` is set and `value` could not be
        decoded with the given encodings.
    """
    # shortcut for the common case - no escape sequences present
    if ESC not in value:
        try:
            return value.decode(encodings[0])
        except UnicodeError:
            if config.enforce_valid_values:
                raise
            warnings.warn(u"Failed to decode byte string with encoding {} - "
                          u"using replacement characters in decoded "
                          u"string".format(encodings[0]))
            return value.decode(encodings[0], errors='replace')

    # Each part of the value that starts with an escape sequence is decoded
    # separately. If it starts with an escape sequence, the
    # corresponding encoding is used, otherwise (e.g. the first part if it
    # does not start with an escape sequence) the first encoding.
    # See PS3.5, 6.1.2.4 and 6.1.2.5 for the use of code extensions.
    #
    # The following regex splits the value into these parts, by matching
    # the substring until the first escape character, and subsequent
    # substrings starting with an escape character.
    regex = b'(^[^\x1b]+|[\x1b][^\x1b]*)'
    fragments = re.findall(regex, value)

    # decode each byte string fragment with it's corresponding encoding
    # and join them all together
    return u''.join([_decode_fragment(fragment, encodings, delimiters)
                     for fragment in fragments])


def _decode_fragment(byte_str, encodings, delimiters):
    """Decode a byte string encoded with a single encoding.
    If `byte_str` starts with an escape sequence, the encoding corresponding
    to this sequence is used for decoding if present in `encodings`,
    otherwise the first value in encodings.
    If a delimiter occurs inside the string, it resets the encoding to the
    first encoding in case of single-byte encodings.

    Parameters
    ----------
    byte_str : bytes
        The raw string to be decoded.
    encodings: list of str
        The list of Python encodings as converted from the values in the
        Specific Character Set tag.
    delimiters: set of int (Python 3) or characters (Python 2)
        A set of characters or character codes, each of which resets the
        encoding in `byte_str`.

    Returns
    -------
    text type
        The decoded unicode string. If the value could not be decoded,
        and `config.enforce_valid_values` is not set, a warning is issued,
        and the value is decoded using the first encoding with replacement
        characters, resulting in data loss.

    Raises
    ------
    UnicodeDecodeError
        If `config.enforce_valid_values` is set and `value` could not be
        decoded with the given encodings.

    Reference
    ---------
    * DICOM Standard Part 5, Sections 6.1.2.4 and 6.1.2.5
    * DICOM Standard Part 3, Anex C.12.1.1.2
    """
    try:
        if byte_str.startswith(ESC):
            return _decode_escaped_fragment(byte_str, encodings, delimiters)
        # no escape sequence - use first encoding
        return byte_str.decode(encodings[0])
    except UnicodeError:
        if config.enforce_valid_values:
            raise
        warnings.warn(u"Failed to decode byte string with encodings: {} - "
                      u"using replacement characters in decoded "
                      u"string".format(', '.join(encodings)))
        return byte_str.decode(encodings[0], errors='replace')


def _decode_escaped_fragment(byte_str, encodings, delimiters):
    """Decodes a byte string starting with an escape sequence.
    See `_decode_fragment` for parameter description and more information.
    """
    # all 4-character escape codes start with one of two character sets
    seq_length = 4 if byte_str.startswith((b'\x1b$(', b'\x1b$)')) else 3
    encoding = CODES_TO_ENCODINGS.get(byte_str[:seq_length], '')
    if encoding in encodings or encoding == default_encoding:
        if encoding in handled_encodings:
            # Python strips the escape sequences for this encoding.
            # Any delimiters must be handled correctly by `byte_str`.
            return byte_str.decode(encoding)
        else:
            # Python doesn't know about the escape sequence -
            # we have to strip it before decoding
            byte_str = byte_str[seq_length:]

            # If a delimiter occurs in the string, it resets the encoding.
            # The following returns the first occurrence of a delimiter in
            # the byte string, or None if it does not contain any.
            index = next((index for index, ch in enumerate(byte_str)
                          if ch in delimiters), None)
            if index is not None:
                # the part of the string after the first delimiter
                # is decoded with the first encoding
                return (byte_str[:index].decode(encoding) +
                        byte_str[index:].decode(encodings[0]))
            # No delimiter - use the encoding defined by the escape code
            return byte_str.decode(encoding)

    # unknown escape code - use first encoding
    msg = u"Found unknown escape sequence in encoded string value"
    if config.enforce_valid_values:
        raise ValueError(msg)
    warnings.warn(msg + u" - using encoding {}".format(encodings[0]))
    return byte_str.decode(encodings[0], errors='replace')


def encode_string(value, encodings):
    """Convert a unicode string into a byte string using the given
    list of encodings.

    Parameters
    ----------
    value : text type
        The unicode string as presented to the user.
    encodings : list
        The encodings needed to encode the string as a list of Python
        encodings, converted from the encodings in Specific Character Set.

    Returns
    -------
    byte string
        The encoded string. If the value could not be encoded with any of
        the given encodings, and `config.enforce_valid_values` is not set, a
        warning is issued, and the value is encoded using the first
        encoding with replacement characters, resulting in data loss.

    Raises
    ------
    UnicodeEncodeError
        If `config.enforce_valid_values` is set and `value` could not be
        encoded with the given encodings.
    """
    for i, encoding in enumerate(encodings):
        try:
            encoded = value.encode(encoding)
            if i > 0 and encoding not in handled_encodings:
                return ENCODINGS_TO_CODES.get(encoding, b'') + encoded
            return encoded
        except UnicodeError:
            continue
    else:
        # if we have more than one encoding, we retry encoding by splitting
        # `value` into chunks that can be encoded with one of the encodings
        if len(encodings) > 1:
            try:
                return _encode_string_parts(value, encodings)
            except ValueError:
                pass
        # all attempts failed - raise or warn and encode with replacement
        # characters
        if config.enforce_valid_values:
            # force raising a valid UnicodeEncodeError
            value.encode(encodings[0])

        warnings.warn("Failed to encode value with encodings: {} - using "
                      "replacement characters in encoded string"
                      .format(', '.join(encodings)))
        return value.encode(encodings[0], errors='replace')


def _encode_string_parts(value, encodings):
    """Convert a unicode string into a byte string using the given
    list of encodings.
    This is invoked if `encode_string` failed to encode `value` with a single
    encoding. We try instead to use different encodings for different parts
    of the string, using the encoding that can encode the longest part of
    the rest of the string as we go along.

    Parameters
    ----------
    value : text type
        The unicode string as presented to the user.
    encodings : list
        The encodings needed to encode the string as a list of Python
        encodings, converted from the encodings in Specific Character Set.

    Returns
    -------
    byte string
        The encoded string, including the escape sequences needed to switch
        between different encodings.

    Raises
    ------
    ValueError
        If `value` could not be encoded with the given encodings.

    """
    encoded = bytearray()
    unencoded_part = value
    while unencoded_part:
        # find the encoding that can encode the longest part of the rest
        # of the string still to be encoded
        max_index = 0
        best_encoding = None
        for encoding in encodings:
            try:
                unencoded_part.encode(encoding)
                # if we get here, the whole rest of the value can be encoded
                best_encoding = encoding
                max_index = len(unencoded_part)
                break
            except UnicodeError as e:
                if e.start > max_index:
                    # e.start is the index of first character failed to encode
                    max_index = e.start
                    best_encoding = encoding
        # none of the given encodings can encode the first character - give up
        if best_encoding is None:
            raise ValueError()

        # encode the part that can be encoded with the found encoding
        encoded_part = unencoded_part[:max_index].encode(best_encoding)
        if best_encoding not in handled_encodings:
            encoded += ENCODINGS_TO_CODES.get(best_encoding, b'')
        encoded += encoded_part
        # set remaining unencoded part of the string and handle that
        unencoded_part = unencoded_part[max_index:]
    # unencoded_part is empty - we are done, return the encoded string
    return encoded


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
    """Converts DICOM encodings into corresponding python encodings.
    Handles some common spelling mistakes and issues a warning in this case.
    Handled stand-alone encodings: if they are the first encodings,
    additional encodings are ignored, if they are not the first encoding,
    they are ignored. In both cases, a warning is issued.

    Parameters
    ----------
    encodings : list of str
        The list of encodings as read from Specific Character Set.

    Returns
    -------
    list of str
        The list of Python encodings corresponding to the DICOM encodings.
        If conversion fails, `encodings` is returned unchanged, assuming
        that it already has been converted to Python encodings.
    """

    # If a list if passed, we don't want to modify the list in place so copy it
    encodings = encodings[:]

    if isinstance(encodings, compat.string_types):
        encodings = [encodings]
    elif not encodings[0]:
        encodings[0] = 'ISO_IR 6'

    try:
        py_encodings = [python_encoding[x] for x in encodings]

    except KeyError:
        # check for some common mistakes in encodings
        patched_encodings = []
        patched = {}
        for x in encodings:
            # check for spelling errors, but exclude the correct spelling
            # standard encodings
            if re.match('^ISO[^_]IR', x) is not None:
                patched[x] = 'ISO_IR' + x[6:]
                patched_encodings.append(patched[x])
            # encodings with code extensions
            elif re.match('^(?=ISO.2022.IR.)(?!ISO 2022 IR )', x) is not None:
                patched[x] = 'ISO 2022 IR ' + x[12:]
                patched_encodings.append(patched[x])
            else:
                patched_encodings.append(x)
        # fallback: assume that it is already a python encoding
        py_encodings = encodings
        if patched:
            try:
                encodings = patched_encodings
                py_encodings = [python_encoding[x] for x in encodings]
                for old, new in patched.items():
                    warnings.warn("Incorrect value for Specific Character Set "
                                  "'{}' - assuming '{}'".format(old, new),
                                  stacklevel=2)
            except KeyError:
                pass
        # if patching failed at this point, the original encodings
        # will be returned, assuming that they are already Python encodings;
        # otherwise, a LookupError will be raised in the using code

    # handle illegal stand-alone encodings
    if len(encodings) > 1:
        if encodings[0] in STAND_ALONE_ENCODINGS:
            warnings.warn("Value '{}' for Specific Character Set does not "
                          "allow code extensions, ignoring: {}"
                          .format(encodings[0], ', '.join(encodings[1:])),
                          stacklevel=2)
            py_encodings = py_encodings[:1]
        else:
            for i, encoding in reversed(list(enumerate(encodings[1:]))):
                if encoding in STAND_ALONE_ENCODINGS:
                    warnings.warn(
                        "Value '{}' cannot be used as code extension, "
                        "ignoring it".format(encoding),
                        stacklevel=2)
                    del py_encodings[i + 1]

    return py_encodings


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
    # PN is special case as may have 3 components with different chr sets
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
