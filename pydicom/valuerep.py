# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Special classes for DICOM value representations (VR)"""
from copy import deepcopy
from decimal import Decimal
import re

from datetime import (date, datetime, time, timedelta, timezone)

# don't import datetime_conversion directly
from pydicom import config
from pydicom.multival import MultiValue

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

# Delimiters for text strings and person name that reset the encoding.
# See PS3.5, Section 6.1.2.5.3
# Note: We use character codes for Python 3
# because those are the types yielded if iterating over a byte string.

# Characters/Character codes for text VR delimiters: LF, CR, TAB, FF
TEXT_VR_DELIMS = {0x0d, 0x0a, 0x09, 0x0c}

# Character/Character code for PN delimiter: name part separator '^'
# (the component separator '=' is handled separately)
PN_DELIMS = {0xe5}


class DA(date):
    """Store value for an element with VR **DA** as :class:`datetime.date`.

    Note that the :class:`datetime.date` base class is immutable.
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

        Parameters
        ----------
        val : str
            A string conformant to the DA definition in the DICOM Standard,
            Part 5, :dcm:`Table 6.2-1<part05/sect_6.2.html#table_6.2-1>`.
        """
        if isinstance(val, str):
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
        if isinstance(val, str):
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
    """Store value for an element with VR **DT** as :class:`datetime.datetime`.

    Note that the :class:`datetime.datetime` base class is immutable.
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

        Parameters
        ----------
        val : str
            A string conformant to the DT definition in the DICOM Standard,
            Part 5, :dcm:`Table 6.2-1<part05/sect_6.2.html#table_6.2-1>`.
        """
        if isinstance(val, str):
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
        if isinstance(val, str):
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
    """Store value for an element with VR **TM** as :class:`datetime.time`.

    Note that the :class:`datetime.time` base class is immutable.
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

        Parameters
        ----------
        val : str
            A string conformant to the TM definition in the DICOM Standard,
            Part 5, :dcm:`Table 6.2-1<part05/sect_6.2.html#table_6.2-1>`.
        """
        if isinstance(val, str):
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
        if isinstance(val, str):
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
    """Store value for an element with VR **DS** as :class:`float`.

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
        if isinstance(val, str):
            self.original_string = val
        elif isinstance(val, (DSfloat, DSdecimal)) and has_attribute:
            self.original_string = val.original_string

    def __str__(self):
        if hasattr(self, 'original_string'):
            return self.original_string

        # Issue #937 (Python 3.8 compatibility)
        return repr(self)[1:-1]

    def __repr__(self):
        return '"{}"'.format(super(DSfloat, self).__repr__())


class DSdecimal(Decimal):
    """Store value for an element with VR **DS** as :class:`decimal.Decimal`.

    Notes
    -----
    If constructed from an empty string, returns the empty string, not an
    instance of this class.
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

        Parameters
        ----------
        val : str or numeric
            A string or a number type which can be converted to a decimal.
        """
        # Store this value here so that if the input string is actually a valid
        # string but decimal.Decimal transforms it to an invalid string it will
        # still be initialized properly
        enforce_length = config.enforce_valid_values
        # DICOM allows spaces around the string,
        # but python doesn't, so clean it
        if isinstance(val, str):
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
        value later. E.g. if set ``'1.23e2'``, :class:`~decimal.Decimal` would
        write ``'123'``, but :class:`DS` will use the original.
        """
        # ... also if user changes a data element value, then will get
        # a different Decimal, as Decimal is immutable.
        if isinstance(val, str):
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

    Checks for blank string; if so, returns that, else calls :class:`DSfloat`
    or :class:`DSdecimal` to create the class instance. This avoids overriding
    ``DSfloat.__new__()`` (which carries a time penalty for large arrays of
    DS).

    Similarly the string clean and check can be avoided and :class:`DSfloat`
    called directly if a string has already been processed.
    """
    if isinstance(val, str):
        val = val.strip()
    if val == '' or val is None:
        return val
    return DSclass(val)


class IS(int):
    """Store value for an element with VR **IS** as :class:`int`.

    Stores original integer string for exact rewriting of the string
    originally read or stored.
    """

    def __new__(cls, val):
        """Create instance if new integer string"""
        if val is None:
            return val
        if isinstance(val, str) and val.strip() == '':
            return ''

        newval = super(IS, cls).__new__(cls, val)

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
        if isinstance(val, str):
            self.original_string = val
        elif isinstance(val, IS) and hasattr(val, 'original_string'):
            self.original_string = val.original_string

    def __str__(self):
        if hasattr(self, 'original_string'):
            return self.original_string

        # Issue #937 (Python 3.8 compatibility)
        return repr(self)[1:-1]

    def __repr__(self):
        return '"{}"'.format(super(IS, self).__repr__())


def MultiString(val, valtype=str):
    """Split a bytestring by delimiters if there are any

    Parameters
    ----------
    val : bytes or str
        DICOM byte string to split up.
    valtype
        Default :class:`str`, but can be e.g. :class:`~pydicom.uid.UID` to
        overwrite to a specific type.

    Returns
    -------
    valtype or list of valtype
        The split value as `valtype` or a :class:`list` of `valtype`.
    """
    # Remove trailing blank used to pad to even length
    # 2005.05.25: also check for trailing 0, error made
    # in PET files we are converting

    while val and (val.endswith(' ') or val.endswith('\x00')):
        val = val[:-1]
    splitup = val.split("\\")

    if len(splitup) == 1:
        val = splitup[0]
        return valtype(val) if val else val
    else:
        return MultiValue(valtype, splitup)


def _verify_encodings(encodings):
    """Checks the encoding to ensure proper format"""
    if encodings is not None:
        if not isinstance(encodings, (list, tuple)):
            return encodings,
        return tuple(encodings)
    return encodings


def _decode_personname(components, encodings):
    """Return a list of decoded person name components.

    Parameters
    ----------
    components : list of byte string
        The list of the up to three encoded person name components
    encodings : list of str
        The Python encodings uses to decode `components`.

    Returns
    -------
    text type
        The unicode string representing the person name.
        If the decoding of some component parts is not possible using the
        given encodings, they are decoded with the first encoding using
        replacement characters for bytes that cannot be decoded.
    """
    from pydicom.charset import decode_string

    if isinstance(components[0], str):
        comps = components
    else:
        comps = [decode_string(comp, encodings, PN_DELIMS)
                 for comp in components]
    # Remove empty elements from the end to avoid trailing '='
    while len(comps) and not comps[-1]:
        comps.pop()
    return tuple(comps)


def _encode_personname(components, encodings):
    """Encode a list of text string person name components.

    Parameters
    ----------
    components : list of text type
        The list of the up to three unicode person name components
    encodings : list of str
        The Python encodings uses to encode `components`.

    Returns
    -------
    byte string
        The byte string that can be written as a PN DICOM tag value.
        If the encoding of some component parts is not possible using the
        given encodings, they are encoded with the first encoding using
        replacement bytes for characters that cannot be encoded.
    """
    from pydicom.charset import encode_string

    encoded_comps = []
    for comp in components:
        groups = [encode_string(group, encodings)
                  for group in comp.split('^')]
        encoded_comps.append(b'^'.join(groups))

    # Remove empty elements from the end
    while len(encoded_comps) and not encoded_comps[-1]:
        encoded_comps.pop()
    return b'='.join(encoded_comps)


class PersonName:
    def __new__(cls, *args, **kwargs):
        # Handle None value by returning None instead of a PersonName object
        if len(args) and args[0] is None:
            return None
        return super(PersonName, cls).__new__(cls)

    def __init__(self, val, encodings=None, original_string=None):
        if isinstance(val, PersonName):
            encodings = val.encodings
            self.original_string = val.original_string
            self._components = tuple(str(val).split('='))
        elif isinstance(val, bytes):
            # this is the raw byte string - decode it on demand
            self.original_string = val
            self._components = None
        else:
            # handle None `val` as empty string
            val = val or ''

            # this is the decoded string - save the original string if
            # available for easier writing back
            self.original_string = original_string
            components = val.split('=')
            # Remove empty elements from the end to avoid trailing '='
            while len(components) and not components[-1]:
                components.pop()
            self._components = tuple(components)

            # if the encoding is not given, leave it as undefined (None)
        self.encodings = _verify_encodings(encodings)
        self._dict = {}

    def _create_dict(self):
        """Creates a dictionary of person name group and component names.

        Used exclusively for `formatted` for backwards compatibility.
        """
        if not self._dict:
            for name in ('family_name', 'given_name', 'middle_name',
                         'name_prefix', 'name_suffix',
                         'ideographic', 'phonetic'):
                self._dict[name] = getattr(self, name, '')

    @property
    def components(self):
        """Returns up to three decoded person name components.

        .. versionadded:: 1.2

        The returned components represent the alphabetic, ideographic and
        phonetic representations as a list of unicode strings.
        """
        if self._components is None:
            groups = self.original_string.split(b'=')
            encodings = self.encodings or [default_encoding]
            self._components = _decode_personname(groups, encodings)

        return self._components

    def _name_part(self, i):
        try:
            return self.components[0].split('^')[i]
        except IndexError:
            return ''

    @property
    def family_name(self):
        """Return the first (family name) group of the alphabetic person name
        representation as a unicode string

        .. versionadded:: 1.2
        """
        return self._name_part(0)

    @property
    def given_name(self):
        """Return the second (given name) group of the alphabetic person name
        representation as a unicode string

        .. versionadded:: 1.2
        """
        return self._name_part(1)

    @property
    def middle_name(self):
        """Return the third (middle name) group of the alphabetic person name
        representation as a unicode string

        .. versionadded:: 1.2
        """
        return self._name_part(2)

    @property
    def name_prefix(self):
        """Return the fourth (name prefix) group of the alphabetic person name
        representation as a unicode string

        .. versionadded:: 1.2
        """
        return self._name_part(3)

    @property
    def name_suffix(self):
        """Return the fifth (name suffix) group of the alphabetic person name
        representation as a unicode string

        .. versionadded:: 1.2
        """
        return self._name_part(4)

    @property
    def ideographic(self):
        """Return the second (ideographic) person name component as a
        unicode string

        .. versionadded:: 1.2
        """
        try:
            return self.components[1]
        except IndexError:
            return ''

    @property
    def phonetic(self):
        """Return the third (phonetic) person name component as a
        unicode string

        .. versionadded:: 1.2
        """
        try:
            return self.components[2]
        except IndexError:
            return ''

    def __eq__(self, other):
        return str(self) == other

    def __ne__(self, other):
        return not self == other

    def __str__(self):
        return '='.join(self.components).__str__()

    def __repr__(self):
        return '='.join(self.components).__repr__()

    def __hash__(self):
        return hash(self.components)

    def decode(self, encodings=None):
        """Return the patient name decoded by the given `encodings`.

        Parameters
        ----------
        encodings : list of str
            The list of encodings used for decoding the byte string. If not
            given, the initial encodings set in the object are used.

        Returns
        -------
        valuerep.PersonName
            A person name object that will return the decoded string with
            the given encodings on demand. If the encodings are not given,
            the current object is returned.
        """
        # in the common case (encoding did not change) we decode on demand
        if encodings is None or encodings == self.encodings:
            return self
        # the encoding was unknown or incorrect - create a new
        # PersonName object with the changed encoding
        encodings = _verify_encodings(encodings)
        if self.original_string is None:
            # if the original encoding was not set, we set it now
            self.original_string = _encode_personname(
                self.components, self.encodings or [default_encoding])
        return PersonName(self.original_string, encodings)

    def encode(self, encodings=None):
        """Return the patient name decoded by the given `encodings`.

        Parameters
        ----------
        encodings : list of str
            The list of encodings used for encoding the unicode string. If
            not given, the initial encodings set in the object are used.

        Returns
        -------
        bytes
            The person name encoded with the given encodings as a byte string.
            If no encoding is given, the original byte string is returned, if
            available, otherwise each group of the patient name is encoded
            with the first matching of the given encodings.
        """
        encodings = _verify_encodings(encodings) or self.encodings

        # if the encoding is not the original encoding, we have to return
        # a re-encoded string (without updating the original string)
        if encodings != self.encodings and self.encodings is not None:
            return _encode_personname(self.components, encodings)
        if self.original_string is None:
            # if the original encoding was not set, we set it now
            self.original_string = _encode_personname(
                self.components, encodings or [default_encoding])
        return self.original_string

    def family_comma_given(self):
        return self.formatted('%(family_name)s, %(given_name)s')

    def formatted(self, format_str):
        self._create_dict()
        return format_str % self._dict

    def __bool__(self):
        if self.original_string is None:
            return (bool(self._components) and
                    (len(self._components) > 1 or bool(self._components[0])))
        return bool(self.original_string)


# Alias old class names for backwards compat in user code
PersonNameUnicode = PersonName = PersonName
