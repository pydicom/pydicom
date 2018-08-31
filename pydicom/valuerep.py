# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Special classes for DICOM value representations (VR)"""

from copy import deepcopy
from decimal import Decimal
import re

from datetime import (date, datetime, time, timedelta)

# don't import datetime_conversion directly
from pydicom import config
from pydicom import compat
from pydicom.multival import MultiValue
from pydicom.util.fixes import timezone

# can't import from charset or get circular import
default_encoding = "iso8859"

# For reading/writing data elements,
# these ones have longer explicit VR format
# Taken from PS3.5 Section 7.1.2
extra_length_VRs = ('OB', 'OD', 'OF', 'OL', 'OW', 'SQ', 'UC', 'UN', 'UR', 'UT')

# VRs that can be affected by character repertoire
# in (0008,0005) Specific Character Set
# See PS-3.5 (2011), section 6.1.2 Graphic Characters
# and PN, but it is handled separately.
text_VRs = ('SH', 'LO', 'ST', 'LT', 'UC', 'UT')

match_string = b''.join([
    b'(?P<single_byte>', br'(?P<family_name>[^=\^]*)',
    br'\^?(?P<given_name>[^=\^]*)', br'\^?(?P<middle_name>[^=\^]*)',
    br'\^?(?P<name_prefix>[^=\^]*)', br'\^?(?P<name_suffix>[^=\^]*)', b')',
    b'=?(?P<ideographic>[^=]*)', b'=?(?P<phonetic>[^=]*)$'
])

match_string_uni = re.compile(match_string.decode('iso8859'))
match_string_bytes = re.compile(match_string)


class DA(date):
    """Store value for DICOM VR DA (Date) as datetime.date.

    Note that the datetime.date base class is immutable.

    """
    __slots__ = ['original_string']

    def __getstate__(self):
        return dict((slot, getattr(self, slot)) for slot in self.__slots__
                    if hasattr(self, slot))

    def __setstate__(self, state):
        for slot, value in state.items():
            setattr(self, slot, value)

    def __reduce__(self):
        return super(DA, self).__reduce__() + (self.__getstate__(),)

    def __reduce_ex__(self, protocol):
        return super(DA, self).__reduce__() + (self.__getstate__(),)

    def __new__(cls, val):
        """Create an instance of DA object.

        Raise an exception if the string cannot be parsed or the argument
        is otherwise incompatible.

        :param val: val must be a string conformant to the DA definition
        in the DICOM Standard PS 3.5-2011
        """
        if isinstance(val, (str, compat.string_types)):
            if len(val) == 8:
                year = int(val[0:4])
                month = int(val[4:6])
                day = int(val[6:8])
                val = super(DA, cls).__new__(cls, year, month, day)
            elif len(val) == 10 and val[4] == '.' and val[7] == '.':
                # ACR-NEMA Standard 300, predecessor to DICOM
                # for compatibility with a few old pydicom example files
                year = int(val[0:4])
                month = int(val[5:7])
                day = int(val[8:10])
                val = super(DA, cls).__new__(cls, year, month, day)
            elif val == '':
                val = None  # empty date
            else:
                try:
                    val = super(DA, cls).__new__(cls, val)
                except TypeError:
                    raise ValueError("Cannot convert to datetime: '%s'" %
                                     (val))
        elif isinstance(val, date):
            val = super(DA, cls).__new__(cls, val.year, val.month, val.day)
        else:
            val = super(DA, cls).__new__(cls, val)
        return val

    def __init__(self, val):
        if isinstance(val, (str, compat.string_types)):
            self.original_string = val
        elif isinstance(val, DA) and hasattr(val, 'original_string'):
            self.original_string = val.original_string

    def __str__(self):
        if hasattr(self, 'original_string'):
            return self.original_string
        else:
            return super(DA, self).__str__()

    def __repr__(self):
        return "\"" + str(self) + "\""


class DT(datetime):
    """Store value for DICOM VR DT (DateTime) as datetime.datetime.

    Note that the datetime.datetime base class is immutable.

    """
    __slots__ = ['original_string']
    _regex_dt = re.compile(r"((\d{4,14})(\.(\d{1,6}))?)([+-]\d{4})?")

    def __getstate__(self):
        return dict((slot, getattr(self, slot)) for slot in self.__slots__
                    if hasattr(self, slot))

    def __setstate__(self, state):
        for slot, value in state.items():
            setattr(self, slot, value)

    def __reduce__(self):
        return super(DT, self).__reduce__() + (self.__getstate__(),)

    def __reduce_ex__(self, protocol):
        return super(DT, self).__reduce__() + (self.__getstate__(),)

    @staticmethod
    def _utc_offset(offset, name):
        return timezone(timedelta(seconds=offset), name)

    def __new__(cls, val):
        """Create an instance of DT object.

        Raise an exception if the string cannot be parsed or the argument
        is otherwise incompatible.

        :param val: val must be a string conformant to the DT definition
        in the DICOM Standard PS 3.5-2011
        """
        if isinstance(val, (str, compat.string_types)):
            match = DT._regex_dt.match(val)
            if match and len(val) <= 26:
                dt_match = match.group(2)
                year = int(dt_match[0:4])
                if len(dt_match) < 6:
                    month = 1
                else:
                    month = int(dt_match[4:6])
                if len(dt_match) < 8:
                    day = 1
                else:
                    day = int(dt_match[6:8])
                if len(dt_match) < 10:
                    hour = 0
                else:
                    hour = int(dt_match[8:10])
                if len(dt_match) < 12:
                    minute = 0
                else:
                    minute = int(dt_match[10:12])
                if len(dt_match) < 14:
                    second = 0
                    microsecond = 0
                else:
                    second = int(dt_match[12:14])
                    ms_match = match.group(4)
                    if ms_match:
                        microsecond = int(ms_match.rstrip().ljust(6, '0'))
                    else:
                        microsecond = 0
                tz_match = match.group(5)
                if tz_match:
                    offset1 = int(tz_match[1:3]) * 60
                    offset2 = int(tz_match[3:5])
                    offset = (offset1 + offset2) * 60
                    if tz_match[0] == '-':
                        offset = -offset
                    tzinfo = cls._utc_offset(offset, tz_match)
                else:
                    tzinfo = None
                val = super(DT,
                            cls).__new__(cls, year, month, day, hour, minute,
                                         second, microsecond, tzinfo)
            else:
                try:
                    val = super(DT, cls).__new__(cls, val)
                except TypeError:
                    raise ValueError("Cannot convert to datetime: '%s'" %
                                     (val))
        elif isinstance(val, datetime):
            val = super(DT, cls).__new__(cls, val.year, val.month, val.day,
                                         val.hour, val.minute, val.second,
                                         val.microsecond, val.tzinfo)
        else:
            val = super(DT, cls).__new__(cls, val)
        return val

    def __init__(self, val):
        if isinstance(val, (str, compat.string_types)):
            self.original_string = val
        elif isinstance(val, DT) and hasattr(val, 'original_string'):
            self.original_string = val.original_string

    def __str__(self):
        if hasattr(self, 'original_string'):
            return self.original_string
        else:
            return super(DT, self).__str__()

    def __repr__(self):
        return "\"" + str(self) + "\""


class TM(time):
    """Store value for DICOM VR of TM (Time) as datetime.time.

    Note that the datetime.time base class is immutable.

    """
    __slots__ = ['original_string']
    _regex_tm = re.compile(r"(\d{2,6})(\.(\d{1,6}))?")

    def __getstate__(self):
        return dict((slot, getattr(self, slot)) for slot in self.__slots__
                    if hasattr(self, slot))

    def __setstate__(self, state):
        for slot, value in state.items():
            setattr(self, slot, value)

    def __reduce__(self):
        return super(TM, self).__reduce__() + (self.__getstate__(),)

    def __reduce_ex__(self, protocol):
        return super(TM, self).__reduce__() + (self.__getstate__(),)

    def __new__(cls, val):
        """Create an instance of TM object from a string.

        Raise an exception if the string cannot be parsed or the argument
        is otherwise incompatible.

        :param val: val must be a string conformant to the TM definition
        in the DICOM Standard PS 3.5-2011
        """
        if isinstance(val, (str, compat.string_types)):
            match = TM._regex_tm.match(val)
            if match and len(val) <= 16:
                tm_match = match.group(1)
                hour = int(tm_match[0:2])
                if len(tm_match) < 4:
                    minute = 0
                else:
                    minute = int(tm_match[2:4])
                if len(tm_match) < 6:
                    second = 0
                    microsecond = 0
                else:
                    second = int(tm_match[4:6])
                    ms_match = match.group(3)
                    if ms_match:
                        microsecond = int(ms_match.rstrip().ljust(6, '0'))
                    else:
                        microsecond = 0
                val = super(TM, cls).__new__(cls, hour, minute, second,
                                             microsecond)
            elif val == '':
                val = None  # empty time
            else:
                try:
                    val = super(TM, cls).__new__(cls, val)
                except TypeError:
                    raise ValueError("Cannot convert to datetime: '%s" % (val))
        elif isinstance(val, time):
            val = super(TM, cls).__new__(cls, val.hour, val.minute, val.second,
                                         val.microsecond)
        else:
            val = super(TM, cls).__new__(cls, val)
        return val

    def __init__(self, val):
        if isinstance(val, (str, compat.string_types)):
            self.original_string = val
        elif isinstance(val, TM) and hasattr(val, 'original_string'):
            self.original_string = val.original_string

    def __str__(self):
        if hasattr(self, 'original_string'):
            return self.original_string
        else:
            return super(TM, self).__str__()

    def __repr__(self):
        return "\"" + str(self) + "\""


class DSfloat(float):
    """Store values for DICOM VR of DS (Decimal String) as a float.

    If constructed from an empty string, return the empty string,
    not an instance of this class.

    """
    __slots__ = ['original_string']

    def __getstate__(self):
        return dict((slot, getattr(self, slot)) for slot in self.__slots__
                    if hasattr(self, slot))

    def __setstate__(self, state):
        for slot, value in state.items():
            setattr(self, slot, value)

    def __init__(self, val):
        """Store the original string if one given, for exact write-out of same
        value later.
        """
        # ... also if user changes a data element value, then will get
        # a different object, because float is immutable.

        has_attribute = hasattr(val, 'original_string')
        if isinstance(val, (str, compat.text_type)):
            self.original_string = val
        elif isinstance(val, (DSfloat, DSdecimal)) and has_attribute:
            self.original_string = val.original_string

    def __str__(self):
        if hasattr(self, 'original_string'):
            return self.original_string
        else:
            return super(DSfloat, self).__str__()

    def __repr__(self):
        return "\"" + str(self) + "\""


class DSdecimal(Decimal):
    """Store values for DICOM VR of DS (Decimal String).
    Note: if constructed by an empty string, returns the empty string,
    not an instance of this class.
    """
    __slots__ = ['original_string']

    def __getstate__(self):
        return dict((slot, getattr(self, slot)) for slot in self.__slots__
                    if hasattr(self, slot))

    def __setstate__(self, state):
        for slot, value in state.items():
            setattr(self, slot, value)

    def __new__(cls, val):
        """Create an instance of DS object, or return a blank string if one is
        passed in, e.g. from a type 2 DICOM blank value.

        :param val: val must be a string or a number type which can be
                   converted to a decimal
        """
        # Store this value here so that if the input string is actually a valid
        # string but decimal.Decimal transforms it to an invalid string it will
        # still be initialized properly
        enforce_length = config.enforce_valid_values
        # DICOM allows spaces around the string,
        # but python doesn't, so clean it
        if isinstance(val, (str, compat.text_type)):
            val = val.strip()
            # If the input string is actually invalid that we relax the valid
            # value constraint for this particular instance
            if len(val) <= 16:
                enforce_length = False
        if val == '':
            return val
        if isinstance(val, float) and not config.allow_DS_float:
            msg = ("DS cannot be instantiated with a float value, "
                   "unless config.allow_DS_float is set to True. "
                   "It is recommended to convert to a string instead, "
                   "with the desired number of digits, or use "
                   "Decimal.quantize and pass a Decimal instance.")
            raise TypeError(msg)
        if not isinstance(val, Decimal):
            val = super(DSdecimal, cls).__new__(cls, val)
        if len(str(val)) > 16 and enforce_length:
            msg = ("DS value representation must be <= 16 "
                   "characters by DICOM standard. Initialize with "
                   "a smaller string, or set config.enforce_valid_values "
                   "to False to override, or use Decimal.quantize() and "
                   "initialize with a Decimal instance.")
            raise OverflowError(msg)
        return val

    def __init__(self, val):
        """Store the original string if one given, for exact write-out of same
        value later. E.g. if set '1.23e2', Decimal would write '123', but DS
        will use the original
        """
        # ... also if user changes a data element value, then will get
        # a different Decimal, as Decimal is immutable.
        if isinstance(val, (str, compat.text_type)):
            self.original_string = val
        elif isinstance(val, (DSfloat, DSdecimal)) and hasattr(val, 'original_string'):  # noqa
            self.original_string = val.original_string

    def __str__(self):
        if hasattr(self, 'original_string') and len(self.original_string) <= 16:  # noqa
            return self.original_string
        else:
            return super(DSdecimal, self).__str__()

    def __repr__(self):
        return "\"" + str(self) + "\""


# CHOOSE TYPE OF DS
if config.use_DS_decimal:
    DSclass = DSdecimal
else:
    DSclass = DSfloat


def DS(val):
    """Factory function for creating DS class instances.
    Checks for blank string; if so, return that.
    Else calls DSfloat or DSdecimal to create the class
    instance. This avoids overriding __new__ in DSfloat
    (which carries a time penalty for large arrays of DS).
    Similarly the string clean and check can be avoided
    and DSfloat called directly if a string has already
    been processed.
    """
    if isinstance(val, (str, compat.text_type)):
        val = val.strip()
    if val == '' or val is None:
        return ''
    return DSclass(val)


class IS(int):
    """Derived class of int. Stores original integer
    string for exact rewriting
    of the string originally read or stored.
    """
    if compat.in_py2:
        __slots__ = ['original_string']

        # Unlikely that str(int) will not be the
        # same as the original, but could happen
        # with leading zeros.

        def __getstate__(self):
            return dict((slot, getattr(self, slot)) for slot in self.__slots__
                        if hasattr(self, slot))

        def __setstate__(self, state):
            for slot, value in state.items():
                setattr(self, slot, value)

    def __new__(cls, val):
        """Create instance if new integer string"""
        if val is None:
            return ''
        if isinstance(val, (str, compat.text_type)) and val.strip() == '':
            return ''
        # Overflow error in Python 2 for integers too large
        # while calling super(IS). Fall back on the regular int
        # casting that will automatically convert the val to long
        # if needed.
        try:
            newval = super(IS, cls).__new__(cls, val)
        except OverflowError:
            newval = int(val)
        # check if a float or Decimal passed in, then could have lost info,
        # and will raise error. E.g. IS(Decimal('1')) is ok, but not IS(1.23)
        if isinstance(val, (float, Decimal)) and newval != val:
            raise TypeError("Could not convert value to integer without loss")
        # Checks in case underlying int is >32 bits, DICOM does not allow this
        check_newval = (newval < -2 ** 31 or newval >= 2 ** 31)
        if check_newval and config.enforce_valid_values:
            dcm_limit = "-2**31 to (2**31 - 1) for IS"
            message = "Value exceeds DICOM limits of %s" % (dcm_limit)
            raise OverflowError(message)
        return newval

    def __init__(self, val):
        # If a string passed, then store it
        if isinstance(val, (str, compat.text_type)):
            self.original_string = val
        elif isinstance(val, IS) and hasattr(val, 'original_string'):
            self.original_string = val.original_string

    def __repr__(self):
        if hasattr(self, 'original_string'):
            return "\"" + self.original_string + "\""
        else:
            return "\"" + int.__str__(self) + "\""


def MultiString(val, valtype=str):
    """Split a bytestring by delimiters if there are any

    val -- DICOM bytestring to split up
    valtype -- default str, but can be e.g.
    UID to overwrite to a specific type
    """
    # Remove trailing blank used to pad to even length
    # 2005.05.25: also check for trailing 0, error made
    # in PET files we are converting

    if val and (val.endswith(' ') or val.endswith('\x00')):
        val = val[:-1]
    splitup = val.split("\\")

    if len(splitup) == 1:
        val = splitup[0]
        return valtype(val) if val else val
    else:
        return MultiValue(valtype, splitup)


def _verify_encodings(encodings):
    """Checks the encoding to ensure proper format"""
    if encodings is not None and not isinstance(encodings, list):
        return [encodings]

    return encodings


def _decode_personname(components, encodings):
    """Return a list of decoded person name components."""
    from pydicom.charset import decode_string

    if isinstance(components[0], compat.text_type):
        comps = components
    else:
        comps = [decode_string(comp, encodings)
                 for comp in components]
    # Remove empty elements from the end to avoid trailing '='
    while len(comps) and not comps[-1]:
        comps.pop()
    return comps


def _encode_personname(components, encodings):
    if not compat.in_py2 and isinstance(components[0], bytes):
        comps = components
    else:
        comps = [
            C.encode(enc) for C, enc in zip(components, encodings)
        ]

    # Remove empty elements from the end
    while len(comps) and not comps[-1]:
        comps.pop()

    return b'='.join(comps)


class PersonName3(object):
    def __init__(self, val, encodings=None):
        if isinstance(val, PersonName3):
            encodings = val.encodings
            val = val.original_string

        self.original_string = val

        self.encodings = _verify_encodings(encodings) or [default_encoding]
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

    # For python 3, any override of __cmp__ or __eq__
    # immutable requires explicit redirect of hash
    # function to the parent class See
    # See http://docs.python.org/
    #  dev/3.0/reference/datamodel.html#object.__hash__
    __hash__ = object.__hash__

    def decode(self, encodings=None):
        encodings = _verify_encodings(encodings) or self.encodings
        comps = _decode_personname(self.components, encodings)
        return PersonName3(u'='.join(comps), encodings)

    def encode(self, encodings=None):
        encodings = _verify_encodings(encodings) or self.encodings
        return _encode_personname(self.components, encodings)

    def family_comma_given(self):
        return self.formatted('%(family_name)s, %(given_name)s')

    def formatted(self, format_str):
        if isinstance(self.original_string, bytes):
            return format_str % self.decode(default_encoding).__dict__
        else:
            return format_str % self.__dict__


class PersonNameBase(object):
    """Base class for Person Name classes"""

    def __init__(self, val):
        """Initialize the PN properties"""
        # Note normally use __new__ on subclassing an immutable,
        # but here we just want to do some pre-processing
        # for properties PS 3.5-2008 section 6.2 (p.28)
        # and 6.2.1 describes PN. Briefly:
        # single-byte-characters=ideographic
        # characters=phonetic-characters
        # (each with?):
        #   family-name-complex
        #  ^Given-name-complex
        #  ^Middle-name^name-prefix^name-suffix
        self.parse()

    def formatted(self, format_str):
        """Return a formatted string according to the format pattern

        Use "...%(property)...%(property)..." where property
        is one of family_name, given_name,
                  middle_name, name_prefix,
                  name_suffix
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
            # in case missing trailing items are left out
            name_string = self.single_byte + "^^^^"
            parts = name_string.split("^")[:5]
            self.family_name, self.given_name, self.middle_name = parts[:3]
            self.name_prefix, self.name_suffix = parts[3:]
        else:
            (self.family_name, self.given_name, self.middle_name,
             self.name_prefix, self.name_suffix) = ('', '', '', '', '')


class PersonName(PersonNameBase, bytes):
    """Human-friendly class to hold VR of Person Name (PN)

    Name is parsed into the following properties:
    single-byte, ideographic, and phonetic components
    (PS3.5-2008 6.2.1)
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


class PersonNameUnicode(PersonNameBase, compat.text_type):
    """Unicode version of Person Name"""

    def __new__(cls, val, encodings):
        """Return unicode string after conversion of each part
        val -- the PN value to store
        encodings -- a list of python encodings, generally found
                 from pydicom.charset.python_encodings mapping
                 of values in DICOM data element (0008,0005).
        """
        encodings = _verify_encodings(encodings)
        comps = _decode_personname(val.split(b"="), encodings)
        new_val = u"=".join(comps)

        return compat.text_type.__new__(cls, new_val)

    def __init__(self, val, encodings):
        self.encodings = _verify_encodings(encodings)
        PersonNameBase.__init__(self, val)

    def __copy__(self):
        """Correctly copy object.
        Needed because of the overwritten __new__.
        """
        # no need to use the original encoding here - we just encode and
        # decode in utf-8 and set the original encoding later
        name = compat.text_type(self).encode('utf8')
        new_person = PersonNameUnicode(name, 'utf8')
        new_person.__dict__.update(self.__dict__)
        return new_person

    def __deepcopy__(self, memo):
        """Make correctly a deep copy of the object.
        Needed because of the overwritten __new__.
        """
        name = compat.text_type(self).encode('utf8')
        new_person = PersonNameUnicode(name, 'utf8')
        memo[id(self)] = new_person
        for k, v in self.__dict__.items():
            setattr(new_person, k, deepcopy(v, memo))
        return new_person

    def encode(self, encodings):
        """Encode the unicode using the specified encoding"""
        encodings = _verify_encodings(encodings) or self.encodings
        return _encode_personname(self.split('='), encodings)

    def family_comma_given(self):
        """Return name as 'Family-name, Given-name'"""
        return self.formatted("%(family_name)u, %(given_name)u")
