# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Special classes for DICOM value representations (VR)"""

import datetime
#from datetime import (date, datetime, time, timedelta, timezone)
from decimal import Decimal
import re
import sys
from typing import (
    TypeVar, Type, Tuple, Optional, List, Dict, Union, Any
)
import warnings

# don't import datetime_conversion directly
from pydicom import config
from pydicom.multival import MultiValue
from pydicom.uid import UID


# Types
_DA = TypeVar("_DA", bound="DA")
_DT = TypeVar("_DT", bound="DT")
_TM = TypeVar("_TM", bound="TM")
_IS = TypeVar("_IS", bound="IS")
_DSfloat = TypeVar("_DSfloat", bound="DSfloat")
_DSdecimal = TypeVar("_DSdecimal", bound="DSdecimal")
_PersonName = TypeVar("_PersonName", bound="PersonName")


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


class _DateTimeBase:
    """Base class for DT, DA and TM element sub-classes."""
    # Add pickling support for the mutable additions
    def __getstate__(self) -> Dict[str, Any]:
        return self.__dict__.copy()

    def __setstate__(self, state: Dict[str, Any]) -> None:
        self.__dict__.update(state)

    def __reduce__(self) -> Union[str, Tuple[Any, ...]]:
        return super().__reduce__() + (self.__getstate__(),)

    def __reduce_ex__(self, protocol: int) -> Union[str, Tuple[Any, ...]]:
        return self.__reduce__()

    def __str__(self) -> str:
        if hasattr(self, 'original_string'):
            return self.original_string

        return super().__str__()

    def __repr__(self) -> str:
        return f'"{str(self)}"'


class DA(_DateTimeBase, datetime.date):
    """Store value for an element with VR **DA** as :class:`datetime.date`.

    Note that the :class:`datetime.date` base class is immutable.
    """
    def __new__(cls: Type[_DA], val: Union[str, _DA]) -> Optional[_DA]:
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
            if val == '':
                return None  # empty date

            if len(val) == 8:
                year = int(val[0:4])
                month = int(val[4:6])
                day = int(val[6:8])
                return super().__new__(cls, year, month, day)

            if len(val) == 10 and val[4] == '.' and val[7] == '.':
                # ACR-NEMA Standard 300, predecessor to DICOM
                # for compatibility with a few old pydicom example files
                year = int(val[0:4])
                month = int(val[5:7])
                day = int(val[8:10])
                return super().__new__(cls, year, month, day)

            try:
                return super().__new__(cls, val)
            except TypeError as exc:
                raise ValueError(
                    f"Unable to convert '{val}' to 'DA' object"
                ) from exc

        if isinstance(val, datetime.date):
            return super().__new__(cls, val.year, val.month, val.day)

        return super().__new__(cls, val)

    def __init__(self, val: Union[str, _DA, None]) -> None:
        """Create a new **DA** element value."""
        if isinstance(val, str):
            self.original_string = val
        elif isinstance(val, DA) and hasattr(val, 'original_string'):
            self.original_string = val.original_string


class DT(_DateTimeBase, datetime.datetime):
    """Store value for an element with VR **DT** as :class:`datetime.datetime`.

    Note that the :class:`datetime.datetime` base class is immutable.
    """
    _regex_dt = re.compile(r"((\d{4,14})(\.(\d{1,6}))?)([+-]\d{4})?")

    @staticmethod
    def _utc_offset(value: str) -> datetime.timezone:
        """Return the UTC Offset suffix as a :class:`datetime.timezone`.

        Parameters
        ----------
        value : str
            The value of the UTC offset suffix, such as ``'-1000'`` or
            ``'+0245'``.

        Returns
        -------
        datetime.timezone
        """
        # Format is &ZZXX, & = '+' or '-', ZZ is hours, XX is minutes
        hour = int(value[1:3]) * 60  # Convert hours to minutes
        minute = int(value[3:5])  # In minutes
        offset = (hour + minute) * 60  # Convert minutes to seconds
        offset = -offset if value[0] == '-' else offset

        return datetime.timezone(datetime.timedelta(seconds=offset),name=value)

    def __new__(cls: Type[_DT], val: Union[str, _DT]) -> Optional[_DT]:
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
            if val == '':
                return None

            match = cls._regex_dt.match(val)
            if not match or len(val) > 26:
                try:
                    return super().__new__(cls, val)
                except TypeError as exc:
                    raise ValueError(
                        f"Unable to convert '{val}' to 'DT' object"
                    ) from exc

            dt_match = match.group(2)
            args = [
                int(dt_match[0:4]),  # year
                1 if len(dt_match) < 6 else int(dt_match[4:6]),  # month
                1 if len(dt_match) < 8 else int(dt_match[6:8]),  # day
                0 if len(dt_match) < 10 else int(dt_match[8:10]),  # hour
                0 if len(dt_match) < 12 else int(dt_match[10:12]),  # minute
                0 if len(dt_match) < 14 else int(dt_match[12:14]),  # second
            ]
            # microsecond
            if len(dt_match) >= 14 and match.group(4):
                args.append(int(match.group(4).rstrip().ljust(6, '0')))
            else:
                args.append(0)

            # Timezone offset
            tz_match = match.group(5)
            args.append(cls._utc_offset(tz_match) if tz_match else None)

            return super().__new__(cls, *args)

        if isinstance(val, datetime.datetime):
            return super().__new__(
                cls,
                val.year,
                val.month,
                val.day,
                val.hour,
                val.minute,
                val.second,
                val.microsecond,
                val.tzinfo
            )

        return super().__new__(cls, val)

    def __init__(self, val: Union[str, _DT]) -> None:
        if isinstance(val, str):
            self.original_string = val
        elif isinstance(val, DT) and hasattr(val, 'original_string'):
            self.original_string = val.original_string


class TM(_DateTimeBase, datetime.time):
    """Store value for an element with VR **TM** as :class:`datetime.time`.

    Note that the :class:`datetime.time` base class is immutable.
    """
    _regex_tm = re.compile(r"(\d{2,6})(\.(\d{1,6}))?")

    def __new__(cls: Type[_TM], val: Union[str, _TM]) -> Optional[_TM]:
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
            if val == '':
                return None  # empty time

            match = cls._regex_tm.match(val)
            if not match or len(val) > 14:
                try:
                    return super().__new__(cls, val)
                except TypeError as exc:
                    raise ValueError(
                        f"Unable to convert {val} to 'TM' object"
                    ) from exc

            tm_match = match.group(1)
            hour = int(tm_match[0:2])
            minute = 0 if len(tm_match) < 4 else int(tm_match[2:4])
            second = 0 if len(tm_match) < 6 else int(tm_match[4:6])

            microsecond = 0
            if len(tm_match) >= 6 and match.group(3):
                microsecond = int(match.group(3).rstrip().ljust(6, '0'))

            return super().__new__(cls, hour, minute, second, microsecond)

        if isinstance(val, datetime.time):
            return super().__new__(
                cls, val.hour, val.minute, val.second, val.microsecond
            )

        return super().__new__(cls, val)

    def __init__(self, val: Union[str, _TM]) -> None:
        if isinstance(val, str):
            self.original_string = val
        elif isinstance(val, TM) and hasattr(val, 'original_string'):
            self.original_string = val.original_string


class DSfloat(float):
    """Store value for an element with VR **DS** as :class:`float`.

    If constructed from an empty string, return the empty string,
    not an instance of this class.

    """
    def __init__(self, val: Union[str, int, float, _DSfloat]) -> None:
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

    def __str__(self) -> str:
        if hasattr(self, 'original_string'):
            return self.original_string

        # Issue #937 (Python 3.8 compatibility)
        return repr(self)[1:-1]

    def __repr__(self) -> str:
        return f'"{super().__repr__()}"'


class DSdecimal(Decimal):
    """Store value for an element with VR **DS** as :class:`decimal.Decimal`.

    Notes
    -----
    If constructed from an empty string, returns the empty string, not an
    instance of this class.
    """
    def __new__(
        cls: Type[_DSdecimal],
        val: Union[str, int, float, _DSdecimal]
    ) -> Optional[_DSdecimal]:
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
                return None

        if isinstance(val, float) and not config.allow_DS_float:
            msg = (
                "'DS' cannot be instantiated with a float value unless "
                "'config.allow_DS_float' is set to True. You should convert "
                "the value to a string with the desired number of digits, "
                "or use 'Decimal.quantize()' and pass a 'Decimal' instance."
            )
            raise TypeError(msg)

        if not isinstance(val, Decimal):
            val = super().__new__(cls, val)

        if len(str(val)) > 16 and enforce_length:
            msg = (
                "Values for elements with a VR of 'DS' values must be <= 16 "
                "characters long. Use a smaller string, set "
                "'config.enforce_valid_values' to False to override the "
                "length check, or use 'Decimal.quantize()' and initialize "
                "with a 'Decimal' instance."
            )
            raise OverflowError(msg)

        return val

    def __init__(self, val: Union[str, int, float, _DSdecimal]) -> None:
        """Store the original string if one given, for exact write-out of same
        value later. E.g. if set ``'1.23e2'``, :class:`~decimal.Decimal` would
        write ``'123'``, but :class:`DS` will use the original.
        """
        # ... also if user changes a data element value, then will get
        # a different Decimal, as Decimal is immutable.
        has_str = hasattr(val, 'original_string')
        if isinstance(val, str):
            self.original_string = val
        elif isinstance(val, (DSfloat, DSdecimal)) and has_str:
            self.original_string = val.original_string

    def __str__(self) -> str:
        has_str = hasattr(self, 'original_string')
        if has_str and len(self.original_string) <= 16:
            return self.original_string

        return super().__str__()

    def __repr__(self) -> str:
        return f'"{str(self)}"'


# CHOOSE TYPE OF DS
if config.use_DS_decimal:
    DSclass = DSdecimal
else:
    DSclass = DSfloat


def DS(val: Union[None, str]) -> Union[str, None, DSfloat, DSdecimal]:
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

    def __new__(
        cls: Type[_IS], val: Union[None, str, int, float, Decimal]
    ) -> Union[None, str, _IS]:
        """Create instance if new integer string"""
        if val is None:
            return val

        if isinstance(val, str) and val.strip() == '':
            return ''

        newval = super().__new__(cls, val)
        # check if a float or Decimal passed in, then could have lost info,
        # and will raise error. E.g. IS(Decimal('1')) is ok, but not IS(1.23)
        if isinstance(val, (float, Decimal)) and newval != val:
            raise TypeError("Could not convert value to integer without loss")

        # Checks in case underlying int is >32 bits, DICOM does not allow this
        check_newval = (newval < -2 ** 31 or newval >= 2 ** 31)
        if check_newval and config.enforce_valid_values:
            raise OverflowError(
                "Elements with a VR of IS must have a value between -2**31 "
                "and (2**31 - 1). Set 'config.enforce_valid_values' to False "
                "to override the value check"
            )

        return newval

    def __init__(self, val: Union[str, _IS]) -> None:
        # If a string passed, then store it
        if isinstance(val, str):
            self.original_string = val
        elif isinstance(val, IS) and hasattr(val, 'original_string'):
            self.original_string = val.original_string

    def __str__(self) -> str:
        if hasattr(self, 'original_string'):
            return self.original_string

        # Issue #937 (Python 3.8 compatibility)
        return repr(self)[1:-1]

    def __repr__(self) -> str:
        return f'"{super().__repr__()}"'


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
    """Representation of the value for an element with VR **PN**."""
    # Is this supposed to be mutable or immutable?
    def __new__(
        cls: Type[_PersonName], *args, **kwargs
    ) -> Union[None, _PersonName]:
        # Handle None value by returning None instead of a PersonName object
        if len(args) and args[0] is None:
            return None

        return super().__new__(cls)

    def __init__(
        self,
        val: Union[bytes, str, "PersonName"],
        encodings: Optional[List[str]] = None,
        original_string: Optional[str] = None
    ) -> None:
        """Create a new ``PersonName``.

        Parameters
        ----------
        val: str, bytes, PersonName
            The value to use for the **PN** element.
        encodings: list of str, optional
            A list of the encodings used for the value.
        original_string: str, optional
            When creating a ``PersonName`` using a decoded string, this is the
            original encoded value.
        """
        self.original_string: Union[None, str, bytes] = None
        self._components = None

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
        self.encodings: List[str] = _verify_encodings(encodings)
        self._dict = {}

    def _create_dict(self) -> Dict[str, str]:
        """Creates a dictionary of person name group and component names.

        Used exclusively for `formatted` for backwards compatibility.
        """
        parts = [
            'family_name', 'given_name', 'middle_name', 'name_prefix',
            'name_suffix', 'ideographic', 'phonetic'
        ]
        return {c: getattr(self, c, '') for c in parts}

    @property
    def components(self) -> List[str]:
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

    def _name_part(self, i) -> str:
        """Return the `i`th part of the name."""
        try:
            return self.components[0].split('^')[i]
        except IndexError:
            return ''

    @property
    def family_name(self) -> str:
        """Return the first (family name) group of the alphabetic person name
        representation as a unicode string

        .. versionadded:: 1.2
        """
        return self._name_part(0)

    @property
    def given_name(self) -> str:
        """Return the second (given name) group of the alphabetic person name
        representation as a unicode string

        .. versionadded:: 1.2
        """
        return self._name_part(1)

    @property
    def middle_name(self) -> str:
        """Return the third (middle name) group of the alphabetic person name
        representation as a unicode string

        .. versionadded:: 1.2
        """
        return self._name_part(2)

    @property
    def name_prefix(self) -> str:
        """Return the fourth (name prefix) group of the alphabetic person name
        representation as a unicode string

        .. versionadded:: 1.2
        """
        return self._name_part(3)

    @property
    def name_suffix(self) -> str:
        """Return the fifth (name suffix) group of the alphabetic person name
        representation as a unicode string

        .. versionadded:: 1.2
        """
        return self._name_part(4)

    @property
    def ideographic(self) -> str:
        """Return the second (ideographic) person name component as a
        unicode string

        .. versionadded:: 1.2
        """
        try:
            return self.components[1]
        except IndexError:
            return ''

    @property
    def phonetic(self) -> str:
        """Return the third (phonetic) person name component as a
        unicode string

        .. versionadded:: 1.2
        """
        try:
            return self.components[2]
        except IndexError:
            return ''

    def __eq__(self, other: object) -> bool:
        """Return ``True`` if `other` equals the current name."""
        return str(self) == other

    def __ne__(self, other: object) -> bool:
        """Return ``True`` if `other` doesn't equal the current name."""
        return not self == other

    def __str__(self) -> str:
        """Return a string representation of the name."""
        return '='.join(self.components).__str__()

    def __next__(self) -> str:
        """Return the next character in the name."""
        # Get next character or stop iteration
        if self._i < self._rep_len:
            c = self._str_rep[self._i]
            self._i += 1
            return c

        raise StopIteration

    def __iter__(self) -> str:
        """Iterate through the name."""
        # Get string rep. and length, initialize index counter
        self._str_rep = self.__str__()
        self._rep_len = len(self._str_rep)
        self._i = 0
        return self

    def __contains__(self, x: str) -> bool:
        """Return ``True`` if `x` is in the name."""
        return x in self.__str__()

    def __repr__(self) -> str:
        """Return a representation of the name."""
        return '='.join(self.components).__repr__()

    def __hash__(self) -> int:
        """Return a hash of the name."""
        return hash(self.components)

    def decode(self, encodings: Optional[List[str]] = None) -> _PersonName:
        """Return the patient name decoded by the given `encodings`.

        Parameters
        ----------
        encodings : list of str, optional
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

    def encode(
        self, encodings: Optional[List[str]] = None
    ) -> bytes:
        """Return the patient name decoded by the given `encodings`.

        Parameters
        ----------
        encodings : list of str, optional
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

    def family_comma_given(self) -> str:
        """Return the name as "Family, Given"."""
        return self.formatted('%(family_name)s, %(given_name)s')

    def formatted(self, format_str: str) -> str:
        """Return the name as a :class:`str` formatted using `format_str`."""
        return format_str % self._create_dict()

    def __bool__(self) -> bool:
        """Return ``True`` if the name is not empty."""
        if self.original_string is None:
            return (
                bool(self._components)
                and (
                    len(self._components) > 1 or bool(self._components[0])
                )
            )

        return bool(self.original_string)


# Alias old class names for backwards compat in user code
def __getattr__(name):
    if name == "PersonNameUnicode":
        warnings.warn(
            "'PersonNameUnicode' is deprecated and will be removed in "
            "pydicom v2.2, use 'PersonName' instead",
            DeprecationWarning
        )
        return globals()['PersonName']

    raise AttributeError(f"module {__name__} has no attribute {name}")


if sys.version_info[:2] < (3, 7):
    PersonNameUnicode = PersonName
