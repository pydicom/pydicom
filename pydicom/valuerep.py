# valuerep.py
"""Special classes for DICOM value representations (VR)"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

from decimal import Decimal
import dicom.config
from dicom.multival import MultiValue
from dicom import in_py3

import logging
logger = logging.getLogger('pydicom')

default_encoding = "iso8859"  # can't import from charset or get circular import

# For reading/writing data elements, these ones have longer explicit VR format
extra_length_VRs = ('OB', 'OW', 'OF', 'SQ', 'UN', 'UT')

# VRs that can be affected by character repertoire in (0008,0005) Specific Character Set
# See PS-3.5 (2011), section 6.1.2 Graphic Characters
text_VRs = ('SH', 'LO', 'ST', 'LT', 'UT')  # and PN, but it is handled separately.

import re

match_string = b''.join([
    b'(?P<single_byte>',
    b'(?P<family_name>[^=\^]*)',
    b'\^?(?P<given_name>[^=\^]*)',
    b'\^?(?P<middle_name>[^=\^]*)',
    b'\^?(?P<name_prefix>[^=\^]*)',
    b'\^?(?P<name_suffix>[^=\^]*)',
    b')',
    b'=?(?P<ideographic>[^=]*)',
    b'=?(?P<phonetic>[^=]*)$'])

match_string_uni = re.compile(match_string.decode('iso8859'))
match_string_bytes = re.compile(match_string)


class DSfloat(float):
    """Store values for DICOM VR of DS (Decimal String) as a float.

    If constructed from an empty string, return the empty string,
    not an instance of this class.

    """
    __slots__ = 'original_string'

    def __init__(self, val):
        """Store the original string if one given, for exact write-out of same
        value later.
        """
        # ... also if user changes a data element value, then will get
        # a different object, becuase float is immutable.

        if isinstance(val, (str, unicode)):
            self.original_string = val
        elif isinstance(val, (DSfloat, DSdecimal)) and hasattr(val, 'original_string'):
            self.original_string = val.original_string

    def __str__(self):
        if hasattr(self, 'original_string'):
            return self.original_string
        else:
            return super(DSfloat, self).__str__()

    def __repr__(self):
        return "'" + str(self) + "'"


class DSdecimal(Decimal):
    """Store values for DICOM VR of DS (Decimal String).
    Note: if constructed by an empty string, returns the empty string,
    not an instance of this class.
    """
    __slots__ = 'original_string'

    def __new__(cls, val):
        """Create an instance of DS object, or return a blank string if one is
        passed in, e.g. from a type 2 DICOM blank value.

        :param val: val must be a string or a number type which can be
                   converted to a decimal
        """
        # Store this value here so that if the input string is actually a valid
        # string but decimal.Decimal transforms it to an invalid string it will
        # still be initialized properly
        enforce_length = dicom.config.enforce_valid_values
        # DICOM allows spaces around the string, but python doesn't, so clean it
        if isinstance(val, (str, unicode)):
            val = val.strip()
            # If the input string is actually invalid that we relax the valid
            # value constraint for this particular instance
            if len(val) <= 16:
                enforce_length = False
        if val == '':
            return val
        if isinstance(val, float) and not dicom.config.allow_DS_float:
            msg = ("DS cannot be instantiated with a float value, unless "
                   "config.allow_DS_float is set to True. It is recommended to "
                   "convert to a string instead, with the desired number of digits, "
                   "or use Decimal.quantize and pass a Decimal instance.")
            raise TypeError(msg)
        if not isinstance(val, Decimal):
            val = super(DSdecimal, cls).__new__(cls, val)
        if len(str(val)) > 16 and enforce_length:
            msg = ("DS value representation must be <= 16 characters by DICOM "
                   "standard. Initialize with a smaller string, or set config.enforce_valid_values "
                   "to False to override, "
                   "or use Decimal.quantize() and initialize with a Decimal instance.")
            raise OverflowError(msg)
        return val

    def __init__(self, val):
        """Store the original string if one given, for exact write-out of same
        value later. E.g. if set '1.23e2', Decimal would write '123', but DS
        will use the original
        """
        # ... also if user changes a data element value, then will get
        # a different Decimal, as Decimal is immutable.
        if isinstance(val, (str, unicode)):
            self.original_string = val
        elif isinstance(val, (DSfloat, DSdecimal)) and hasattr(val, 'original_string'):
            self.original_string = val.original_string

    def __str__(self):
        if hasattr(self, 'original_string') and len(self.original_string) <= 16:
            return self.original_string
        else:
            return super(DSdecimal, self).__str__()

    def __repr__(self):
        return "'" + str(self) + "'"

# CHOOSE TYPE OF DS
if dicom.config.use_DS_decimal:
    DSclass = DSdecimal
else:
    DSclass = DSfloat


def DS(val):
    """Factory function for creating DS class instances.
    Checks for blank string; if so, return that. Else calls DSfloat or DSdecimal
    to create the class instance. This avoids overriding __new__ in DSfloat
    (which carries a time penalty for large arrays of DS).
    Similarly the string clean and check can be avoided and DSfloat called
    directly if a string has already been processed.
    """
    if isinstance(val, (str, unicode)):
        val = val.strip()
    if val == '':
        return val
    return DSclass(val)


class IS(int):
    """Derived class of int. Stores original integer string for exact rewriting
    of the string originally read or stored.
    """
    if not in_py3:
        __slots__ = 'original_string'
    # Unlikely that str(int) will not be the same as the original, but could happen
    # with leading zeros.

    def __new__(cls, val):
        """Create instance if new integer string"""
        if isinstance(val, (str, unicode)) and val.strip() == '':
            return ''
        newval = super(IS, cls).__new__(cls, val)
        # check if a float or Decimal passed in, then could have lost info,
        # and will raise error. E.g. IS(Decimal('1')) is ok, but not IS(1.23)
        if isinstance(val, (float, Decimal)) and newval != val:
            raise TypeError("Could not convert value to integer without loss")
        # Checks in case underlying int is >32 bits, DICOM does not allow this
        if (newval < -2 ** 31 or newval >= 2 ** 31) and dicom.config.enforce_valid_values:
            message = "Value exceeds DICOM limits of -2**31 to (2**31 - 1) for IS"
            raise OverflowError(message)
        return newval

    def __init__(self, val):
        # If a string passed, then store it
        if isinstance(val, (str, unicode)):
            self.original_string = val
        elif isinstance(val, IS) and hasattr(val, 'original_string'):
            self.original_string = val.original_string

    def __repr__(self):
        if hasattr(self, 'original_string'):
            return "'" + self.original_string + "'"
        else:
            return "'" + int.__str__(self) + "'"


def MultiString(val, valtype=str):
    """Split a bytestring by delimiters if there are any

    val -- DICOM bytestring to split up
    valtype -- default str, but can be e.g. UID to overwrite to a specific type
    """
    # Remove trailing blank used to pad to even length
    # 2005.05.25: also check for trailing 0, error made in PET files we are converting

    if val and (val.endswith(' ') or val.endswith('\x00')):
        val = val[:-1]
    splitup = val.split("\\")

    if len(splitup) == 1:
        val = splitup[0]
        return valtype(val) if val else val
    else:
        return MultiValue(valtype, splitup)


class PersonName3(object):
    def __init__(self, val, encodings=default_encoding):
        if isinstance(val, PersonName3):
            val = val.original_string

        self.original_string = val

        self.encodings = self._verify_encodings(encodings)
        self.parse(val)

    def parse(self, val):
        if isinstance(val, bytes):
            matchstr = match_string_bytes
        else:
            matchstr = match_string_uni

        matchobj = re.match(matchstr, val)

        self.__dict__.update(matchobj.groupdict())

        groups = matchobj.groups()
        self.components = [groups[i] for i in (0, -2, -1)]

    def __eq__(self, other):
        return self.original_string == other

    def __ne__(self, other):
        return not self == other

    def __str__(self):
        return self.original_string.__str__()

    def __repr__(self):
        return self.original_string.__repr__()

    def decode(self, encodings=None):
        encodings = self._verify_encodings(encodings)

        from dicom.charset import clean_escseq
        if not isinstance(self.components[0], bytes):
            comps = self.components
        else:
            comps = [clean_escseq(comp.decode(enc), encodings)
                     for comp, enc in zip(self.components, encodings)]

        while len(comps) and not comps[-1]:
            comps.pop()

        return PersonName3('='.join(comps), encodings)

    def encode(self, encodings=None):
        encodings = self._verify_encodings(encodings)

        if isinstance(self.components[0], bytes):
            comps = self.components
        else:
            comps = [C.encode(enc) for C, enc in zip(self.components, encodings)]

        # Remove empty elements from the end
        while len(comps) and not comps[-1]:
            comps.pop()

        return b'='.join(comps)

    def family_comma_given(self):
        return self.formatted('%(family_name)s, %(given_name)s')

    def formatted(self, format_str):
        if isinstance(self.original_string, bytes):
            return format_str % self.decode(default_encoding).__dict__
        else:
            return format_str % self.__dict__

    def _verify_encodings(self, encodings):
        if encodings is None:
            return self.encodings

        if not isinstance(encodings, list):
            encodings = [encodings] * 3

        if len(encodings) == 2:
            encodings.append(encodings[1])

        return encodings


class PersonNameBase(object):
    """Base class for Person Name classes"""

    def __init__(self, val):
        """Initialize the PN properties"""
        # Note normally use __new__ on subclassing an immutable, but here we just want
        #    to do some pre-processing for properties
        # PS 3.5-2008 section 6.2 (p.28)  and 6.2.1 describes PN. Briefly:
        #  single-byte-characters=ideographic characters=phonetic-characters
        # (each with?):
        #   family-name-complex^Given-name-complex^Middle-name^name-prefix^name-suffix
        self.parse()

    def formatted(self, format_str):
        """Return a formatted string according to the format pattern

        Use "...%(property)...%(property)..." where property is one of
           family_name, given_name, middle_name, name_prefix, name_suffix
        """
        return format_str % self.__dict__

    def parse(self):
        """Break down the components and name parts"""
        self.components = self.split("=")
        nComponents = len(self.components)
        self.single_byte = self.components[0]
        self.ideographic = ''
        self.phonetic = ''
        if nComponents > 1:
            self.ideographic = self.components[1]
        if nComponents > 2:
            self.phonetic = self.components[2]

        if self.single_byte:
            name_string = self.single_byte + "^^^^"  # in case missing trailing items are left out
            parts = name_string.split("^")[:5]
            self.family_name, self.given_name, self.middle_name = parts[:3]
            self.name_prefix, self.name_suffix = parts[3:]
        else:
            (self.family_name, self.given_name, self.middle_name,
                self.name_prefix, self.name_suffix) = ('', '', '', '', '')


class PersonName(PersonNameBase, bytes):
    """Human-friendly class to hold VR of Person Name (PN)

    Name is parsed into the following properties:
    single-byte, ideographic, and phonetic components (PS3.5-2008 6.2.1)
    family_name,
    given_name,
    middle_name,
    name_prefix,
    name_suffix

    """
    def __new__(cls, val):
        """Return instance of the new class"""
        # Check if trying to convert a string that has already been converted
        if isinstance(val, PersonName):
            return val
        return super(PersonName, cls).__new__(cls, val)

    def encode(self, *args):
        """Dummy method to mimic py2 str behavior in py3 bytes subclass"""
        # This greatly simplifies the write process so all objects have the
        # "encode" method
        return self

    def family_comma_given(self):
        """Return name as 'Family-name, Given-name'"""
        return self.formatted("%(family_name)s, %(given_name)s")
    # def __str__(self):
        # return str(self.byte_string)
        # XXX need to process the ideographic or phonetic components?
    # def __len__(self):
        # return len(self.byte_string)


class PersonNameUnicode(PersonNameBase, unicode):
    """Unicode version of Person Name"""

    def __new__(cls, val, encodings):
        """Return unicode string after conversion of each part
        val -- the PN value to store
        encodings -- a list of python encodings, generally found
                 from dicom.charset.python_encodings mapping
                 of values in DICOM data element (0008,0005).
        """
        from dicom.charset import clean_escseq  # in here to avoid circular import

        # Make the possible three character encodings explicit:
        if not isinstance(encodings, list):
            encodings = [encodings] * 3
        if len(encodings) == 2:
            encodings.append(encodings[1])
        components = val.split(b"=")
        # Remove the first encoding if only one component is present
        if (len(components) == 1):
            del encodings[0]

        comps = [clean_escseq(C.decode(enc), encodings)
                 for C, enc in zip(components, encodings)]
        new_val = u"=".join(comps)

        return unicode.__new__(cls, new_val)

    def __init__(self, val, encodings):
        self.encodings = self._verify_encodings(encodings)
        PersonNameBase.__init__(self, val)

    def _verify_encodings(self, encodings):
        """Checks the encoding to ensure proper format"""
        if encodings is None:
            return self.encodings

        if not isinstance(encodings, list):
            encodings = [encodings] * 3

        if len(encodings) == 2:
            encodings.append(encodings[1])

        return encodings

    def encode(self, encodings):
        """Encode the unicode using the specified encoding"""
        encodings = self._verify_encodings(encodings)

        components = self.split('=')

        comps = [C.encode(enc) for C, enc in zip(components, encodings)]

        # Remove empty elements from the end
        while len(comps) and not comps[-1]:
            comps.pop()

        return '='.join(comps)

    def family_comma_given(self):
        """Return name as 'Family-name, Given-name'"""
        return self.formatted("%(family_name)u, %(given_name)u")
