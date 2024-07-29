# Copyright 2008-2021 pydicom authors. See LICENSE file for details.
"""Special classes for DICOM value representations (VR)"""

import datetime
from decimal import Decimal
from enum import Enum, unique
import re
from math import floor, isfinite, log10
from typing import Optional, Any, cast
from collections.abc import Callable, Sequence, Iterator

# don't import datetime_conversion directly
from pydicom import config
from pydicom.misc import warn_and_log


# can't import from charset or get circular import
default_encoding = "iso8859"

# Delimiters for text strings and person name that reset the encoding.
# See PS3.5, Section 6.1.2.5.3
# Note: We use character codes for Python 3
# because those are the types yielded if iterating over a byte string.

# Characters/Character codes for text VR delimiters: LF, CR, TAB, FF
TEXT_VR_DELIMS = {0x0D, 0x0A, 0x09, 0x0C}

# Character/Character code for PN delimiter: name part separator '^'
# (the component separator '=' is handled separately)
PN_DELIMS = {0x5E}

# maximum allowed value length for string VRs
# VRs with a maximum length of 2^32 (UR and UT) are not checked
MAX_VALUE_LEN = {
    "AE": 16,
    "CS": 16,
    "DS": 16,
    "IS": 12,
    "LO": 64,
    "LT": 10240,
    "SH": 16,
    "ST": 1024,
    "UI": 64,
}


def _range_regex(regex: str) -> str:
    """Compose a regex that allows ranges of the given regex,
    as defined for VRs DA, DT and TM in PS 3.4, C.2.2.2.5.
    """
    return rf"^{regex}$|^\-{regex} ?$|^{regex}\- ?$|^{regex}\-{regex} ?$"


# regular expressions to match valid values for some VRs
VR_REGEXES = {
    "AE": r"^[\x20-\x7e]*$",
    "AS": r"^\d\d\d[DWMY]$",
    "CS": r"^[A-Z0-9 _]*$",
    "DS": r"^ *[+\-]?(\d+|\d+\.\d*|\.\d+)([eE][+\-]?\d+)? *$",
    "IS": r"^ *[+\-]?\d+ *$",
    "DA": _range_regex(r"\d{4}(0[1-9]|1[0-2])([0-2]\d|3[01])"),
    "DT": _range_regex(
        r"\d{4}((0[1-9]|1[0-2])(([0-2]\d|3[01])(([01]\d|2[0-3])"
        r"([0-5]\d((60|[0-5]\d)(\.\d{1,6} ?)?)?)?)?)?)?([+-][01]\d\d\d)?"
    ),
    "TM": _range_regex(r"([01]\d|2[0-3])([0-5]\d((60|[0-5]\d)(\.\d{1,6} ?)?)?)?"),
    "UI": r"^(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*$",
    "UR": r"^[A-Za-z_\d:/?#\[\]@!$&'()*+,;=%\-.~]* *$",
}

STR_VR_REGEXES = {vr: re.compile(regex) for (vr, regex) in VR_REGEXES.items()}
BYTE_VR_REGEXES = {vr: re.compile(regex.encode()) for (vr, regex) in VR_REGEXES.items()}


def validate_type(
    vr: str, value: Any, types: type | tuple[type, type]
) -> tuple[bool, str]:
    """Checks for valid types for a given VR.

    Parameters
    ----------
    vr : str
        The value representation to validate against.
    value : Any
        The value to validate.
    types: Type or Tuple[Type]
        The type or tuple of types supported for the given VR.

    Returns
    -------
        A tuple of a boolean validation result and the error message.
    """
    if value is not None and not isinstance(value, types):
        return False, (
            f"A value of type '{type(value).__name__}' cannot be "
            f"assigned to a tag with VR {vr}."
        )
    return True, ""


def validate_vr_length(vr: str, value: Any) -> tuple[bool, str]:
    """Validate the value length for a given VR.

    Parameters
    ----------
    vr : str
        The value representation to validate against.
    value : Any
        The value to validate.

    Returns
    -------
        A tuple of a boolean validation result and the error message.
    """
    max_length = MAX_VALUE_LEN.get(vr, 0)
    if max_length > 0:
        value_length = len(value)
        if value_length > max_length:
            return False, (
                f"The value length ({value_length}) exceeds the "
                f"maximum length of {max_length} allowed for VR {vr}."
            )
    return True, ""


def validate_type_and_length(vr: str, value: Any) -> tuple[bool, str]:
    """Validate the correct type and the value length for a given VR.

    Parameters
    ----------
    vr : str
        The value representation to validate against.
    value : Any
        The value to validate.

    Returns
    -------
        A tuple of a boolean validation result and the error message.
    """
    valid, msg = validate_type(vr, value, (str, bytes))
    if not valid:
        return valid, msg
    return validate_vr_length(vr, value)


def validate_regex(vr: str, value: Any) -> tuple[bool, str]:
    """Validate the value for a given VR for allowed characters
    using a regular expression.

    Parameters
    ----------
    vr : str
        The value representation to validate against.
    value : Any
        The value to validate.

    Returns
    -------
        A tuple of a boolean validation result and the error message.
    """
    if value:
        regex: Any
        newline: str | int
        if isinstance(value, str):
            regex = STR_VR_REGEXES[vr]
            newline = "\n"
        else:
            regex = BYTE_VR_REGEXES[vr]
            newline = 10  # newline character
        if not re.match(regex, value) or value and value[-1] == newline:
            return False, f"Invalid value for VR {vr}: {value!r}."
    return True, ""


def validate_type_and_regex(vr: str, value: Any) -> tuple[bool, str]:
    """Validate that the value is of type :class:`str` or :class:`bytes`
    and that the value matches the VR-specific regular expression.

    Parameters
    ----------
    vr : str
        The value representation to validate against.
    value : Any
        The value to validate.

    Returns
    -------
        A tuple of a boolean validation result and the error message.
    """
    valid, msg = validate_type(vr, value, (str, bytes))
    if not valid:
        return valid, msg
    return validate_regex(vr, value)


def validate_date_time(vr: str, value: Any, date_time_type: type) -> tuple[bool, str]:
    """Checks for valid values for date/time related VRs.

    Parameters
    ----------
    vr : str
        The value representation to validate against.
    value : Any
        The value to validate.
    date_time_type: type
        The specific type supported for the given VR (additional to str/bytes).

    Returns
    -------
        A tuple of a boolean validation result and the error message.
    """

    if value and isinstance(value, date_time_type):
        return True, ""
    return validate_type_and_regex(vr, value)


def validate_length_and_type_and_regex(vr: str, value: Any) -> tuple[bool, str]:
    """Validate the value for a given VR for maximum length, for the correct
    value type, and for allowed characters using a regular expression.

    Parameters
    ----------
    vr : str
        The value representation to validate against.
    value : Any
        The value to validate.

    Returns
    -------
        A tuple of a boolean validation result and the error message.
    """
    valid, msg = validate_type(vr, value, (str, bytes))
    if not valid:
        return valid, msg
    is_valid_len, msg1 = validate_vr_length(vr, value)
    is_valid_expr, msg2 = validate_regex(vr, value)
    msg = " ".join([msg1, msg2]).strip()
    if msg:
        msg += (
            " Please see <https://dicom.nema.org/medical/dicom/current/output"
            "/html/part05.html#table_6.2-1> for allowed values for each VR."
        )
    return is_valid_len and is_valid_expr, msg


def validate_pn_component_length(vr: str, value: Any) -> tuple[bool, str]:
    """Validate the PN component value for the maximum length.

    Parameters
    ----------
    vr : str
        Ignored.
    value : str
        The value to validate.

    Returns
    -------
        A tuple of a boolean validation result and the error message.
    """
    if len(value) > 64:
        return False, (
            f"The PN component length ({len(value)}) exceeds the "
            f"maximum allowed length of 64."
        )
    return True, ""


def validate_pn(vr: str, value: Any) -> tuple[bool, str]:
    """Validate the value for VR PN for the maximum number of components
    and for the maximum length of each component.

    Parameters
    ----------
    vr : str
        Ignored.
    value : str
        The value to validate.

    Returns
    -------
        A tuple of a boolean validation result and the error message.
    """
    if not value or isinstance(value, PersonName):
        return True, ""
    valid, msg = validate_type(vr, value, (str, bytes))
    if not valid:
        return valid, msg
    components: Sequence[str | bytes]
    if isinstance(value, bytes):
        components = value.split(b"=")
    else:
        components = value.split("=")
    if len(components) > 3:
        return False, (
            f"The number of PN components length ({len(components)}) exceeds "
            f"the maximum allowed number of 3."
        )
    for comp in components:
        valid, msg = validate_pn_component_length("PN", comp)
        if not valid:
            return False, msg
    return True, ""


def validate_pn_component(value: str | bytes) -> None:
    """Validate the value of a single component of VR PN for maximum length.

    Parameters
    ----------
    value : str or bytes
        The component value to validate.

    Raises
    ------
    ValueError
        If the validation fails and the validation mode is set to
        `RAISE`.
    """
    validate_value(
        "PN",
        value,
        config.settings.writing_validation_mode,
        validate_pn_component_length,
    )


VALUE_LENGTH = {"US": 2, "SS": 2, "UL": 4, "SL": 4, "UV": 8, "SV": 8, "FL": 4, "FD": 8}


def validate_number(
    vr: str, value: Any, min_value: int, max_value: int
) -> tuple[bool, str]:
    """Validate the value for a numerical VR for type and allowed range.

    Parameters
    ----------
    vr : str
        The value representation to validate against.
    value : Any
        The value to validate.
    min_value : int
        The minimum allowed value.
    max_value : int
        The maximum allowed value.

    Returns
    -------
        A tuple of a boolean validation result and the error message.
    """
    valid, msg = validate_type(vr, value, (int, bytes))
    if not valid:
        return valid, msg
    if isinstance(value, int):
        if value < min_value or value > max_value:
            return False, (
                f"Invalid value: a value for a tag with VR {vr} must be "
                f"between {min_value} and {max_value}."
            )
    elif len(value) % VALUE_LENGTH[vr]:
        return False, (
            f"Invalid value length {len(value)}: the value length for a tag "
            f"with VR {vr} must be a multiple of {VALUE_LENGTH[vr]}."
        )
    return True, ""


VALIDATORS = {
    "AE": validate_length_and_type_and_regex,
    "AS": validate_type_and_regex,
    "CS": validate_length_and_type_and_regex,
    "DA": lambda vr, value: validate_date_time(vr, value, datetime.date),
    "DS": validate_length_and_type_and_regex,
    "DT": lambda vr, value: validate_date_time(vr, value, datetime.datetime),
    "FD": lambda vr, value: validate_type(vr, value, (float, int)),
    "FL": lambda vr, value: validate_type(vr, value, (float, int)),
    "IS": validate_length_and_type_and_regex,
    "LO": validate_type_and_length,
    "LT": validate_type_and_length,
    "OB": lambda vr, value: validate_type(vr, value, (bytes, bytearray)),
    "OD": lambda vr, value: validate_type(vr, value, (bytes, bytearray)),
    "OF": lambda vr, value: validate_type(vr, value, (bytes, bytearray)),
    "OL": lambda vr, value: validate_type(vr, value, (bytes, bytearray)),
    "OW": lambda vr, value: validate_type(vr, value, (bytes, bytearray)),
    "OV": lambda vr, value: validate_type(vr, value, (bytes, bytearray)),
    "PN": validate_pn,
    "SH": validate_type_and_length,
    "SL": lambda vr, value: validate_number(vr, value, -0x80000000, 0x7FFFFFFF),
    "SS": lambda vr, value: validate_number(vr, value, -0x8000, 0x7FFF),
    "ST": validate_type_and_length,
    "SV": lambda vr, value: validate_number(
        vr, value, -0x8000000000000000, 0x7FFFFFFFFFFFFFFF
    ),
    "TM": lambda vr, value: validate_date_time(vr, value, datetime.time),
    "UI": validate_length_and_type_and_regex,
    "UL": lambda vr, value: validate_number(vr, value, 0, 0xFFFFFFFF),
    "US": lambda vr, value: validate_number(vr, value, 0, 0xFFFF),
    "UR": validate_type_and_regex,
    "UV": lambda vr, value: validate_number(vr, value, 0, 0xFFFFFFFFFFFFFFFF),
}


def validate_value(
    vr: str,
    value: Any,
    validation_mode: int,
    validator: Callable[[str, Any], tuple[bool, str]] | None = None,
) -> None:
    """Validate the given value against the DICOM standard.

    Parameters
    ----------
    vr : str
        The VR of the tag the value is added to.
    value : Any
        The value to be validated.
    validation_mode : int
        Defines if values are validated and how validation errors are
        handled.
    validator : Callable or None
        Function that does the actual validation. If not given,
        the validator is taken from the VR-specific validator table instead.

    Raises
    ------
    ValueError
        If the validation fails and the validation mode is set to
        `RAISE`.
    """
    if validation_mode == config.IGNORE:
        return

    if value is not None:
        validator = validator or VALIDATORS.get(vr)
        if validator is not None:
            is_valid, msg = validator(vr, value)
            if not is_valid:
                if validation_mode == config.RAISE:
                    raise ValueError(msg)
                warn_and_log(msg)


@unique
class VR(str, Enum):
    """DICOM Data Element's Value Representation (VR)"""

    # Standard VRs from Table 6.2-1 in Part 5
    AE = "AE"
    AS = "AS"
    AT = "AT"
    CS = "CS"
    DA = "DA"
    DS = "DS"
    DT = "DT"
    FD = "FD"
    FL = "FL"
    IS = "IS"
    LO = "LO"
    LT = "LT"
    OB = "OB"
    OD = "OD"
    OF = "OF"
    OL = "OL"
    OW = "OW"
    OV = "OV"
    PN = "PN"
    SH = "SH"
    SL = "SL"
    SQ = "SQ"
    SS = "SS"
    ST = "ST"
    SV = "SV"
    TM = "TM"
    UC = "UC"
    UI = "UI"
    UL = "UL"
    UN = "UN"
    UR = "UR"
    US = "US"
    UT = "UT"
    UV = "UV"
    # Ambiguous VRs from Tables 6-1, 7-1 and 8-1 in Part 6
    US_SS_OW = "US or SS or OW"
    US_SS = "US or SS"
    US_OW = "US or OW"
    OB_OW = "OB or OW"

    def __str__(self) -> str:
        return str.__str__(self)


# Standard VRs from Table 6.2-1 in Part 5
STANDARD_VR = {
    VR.AE,
    VR.AS,
    VR.AT,
    VR.CS,
    VR.DA,
    VR.DS,
    VR.DT,
    VR.FD,
    VR.FL,
    VR.IS,
    VR.LO,
    VR.LT,
    VR.OB,
    VR.OD,
    VR.OF,
    VR.OL,
    VR.OW,
    VR.OV,
    VR.PN,
    VR.SH,
    VR.SL,
    VR.SQ,
    VR.SS,
    VR.ST,
    VR.SV,
    VR.TM,
    VR.UC,
    VR.UI,
    VR.UL,
    VR.UN,
    VR.UR,
    VR.US,
    VR.UT,
    VR.UV,
}
# Ambiguous VRs from Tables 6-1, 7-1 and 8-1 in Part 6
AMBIGUOUS_VR = {VR.US_SS_OW, VR.US_SS, VR.US_OW, VR.OB_OW}

# Character Repertoire for VRs
# Allowed character repertoire for str-like VRs, based off of the information
#   in Section 6.1.2 and Table 6.2-1 in Part 5
# Basic G0 set of ISO 646 (ISO-IR 6) only
DEFAULT_CHARSET_VR = {
    VR.AE,
    VR.AS,
    VR.CS,
    VR.DA,
    VR.DS,
    VR.DT,
    VR.IS,
    VR.TM,
    VR.UI,
    VR.UR,
}
# Basic G0 set of ISO 646 or extensible/replaceable by
#   (0008,0005) *Specific Character Set*
CUSTOMIZABLE_CHARSET_VR = {VR.LO, VR.LT, VR.PN, VR.SH, VR.ST, VR.UC, VR.UT}

# Corresponding Python built-in for each VR
#   For some VRs this is more a "fallback" class-like behavioural definition
#   than actual, and note that some VRs such as IS and DS are present in
#   multiple sets
BYTES_VR = {VR.OB, VR.OD, VR.OF, VR.OL, VR.OV, VR.OW, VR.UN}
FLOAT_VR = {VR.DS, VR.FD, VR.FL}
INT_VR = {VR.AT, VR.IS, VR.SL, VR.SS, VR.SV, VR.UL, VR.US, VR.UV}
LIST_VR = {VR.SQ}
STR_VR = DEFAULT_CHARSET_VR | CUSTOMIZABLE_CHARSET_VR

# These VRs may have backslash characters or encoded backslashes in the
#   value based off of the information in Table 6.2-1 in Part 5
# DataElements with ambiguous VRs may use `bytes` values and so are allowed
#   to have backslashes (except 'US or SS')
ALLOW_BACKSLASH = {VR.LT, VR.ST, VR.UT, VR.US_SS_OW, VR.US_OW, VR.OB_OW} | BYTES_VR

# VRs which may have a value more than 1024 bytes or characters long
#   Used to flag which values may need shortening during printing
LONG_VALUE_VR = {VR.LT, VR.UC, VR.UT} | BYTES_VR | AMBIGUOUS_VR

# VRs that use 2 byte length fields for Explicit VR from Table 7.1-2 in Part 5
#   All other explicit VRs and all implicit VRs use 4 byte length fields
EXPLICIT_VR_LENGTH_16 = {
    VR.AE,
    VR.AS,
    VR.AT,
    VR.CS,
    VR.DA,
    VR.DS,
    VR.DT,
    VR.FL,
    VR.FD,
    VR.IS,
    VR.LO,
    VR.LT,
    VR.PN,
    VR.SH,
    VR.SL,
    VR.SS,
    VR.ST,
    VR.TM,
    VR.UI,
    VR.UL,
    VR.US,
}
EXPLICIT_VR_LENGTH_32 = STANDARD_VR - EXPLICIT_VR_LENGTH_16

# VRs that are allowed to be buffers
BUFFERABLE_VRS = (BYTES_VR | {VR.OB_OW}) - {VR.UN}


class _DateTimeBase:
    """Base class for DT, DA and TM element sub-classes."""

    original_string: str

    # Add pickling support for the mutable additions
    def __getstate__(self) -> dict[str, Any]:
        return self.__dict__.copy()

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)

    def __reduce_ex__(self, protocol: int) -> tuple[Any, ...]:  # type: ignore[override]
        # Python 3.8 - protocol: SupportsIndex (added in 3.8)
        # datetime.time, and datetime.datetime return Tuple[Any, ...]
        # datetime.date doesn't define __reduce_ex__
        reduce_ex = cast(tuple[Any, ...], super().__reduce_ex__(protocol))
        return reduce_ex + (self.__getstate__(),)

    def __str__(self) -> str:
        if hasattr(self, "original_string"):
            return self.original_string

        return super().__str__()

    def __repr__(self) -> str:
        return f'"{self}"'


class DA(_DateTimeBase, datetime.date):
    """Store value for an element with VR **DA** as :class:`datetime.date`.

    Note that the :class:`datetime.date` base class is immutable.
    """

    def __new__(  # type: ignore[misc]
        cls: type["DA"], *args: Any, **kwargs: Any
    ) -> Optional["DA"]:
        """Create an instance of DA object.

        Raise an exception if the string cannot be parsed or the argument
        is otherwise incompatible.

        The arguments (``*args`` and ``**kwargs``) are either the ones
        inherited from :class:`datetime.date`, or the first argument is
        a string conformant to the DA definition in the DICOM Standard,
        Part 5, :dcm:`Table 6.2-1<part05/sect_6.2.html#table_6.2-1>`,
        or it is a :class:`datetime.date` object, or an object of type
        :class:`~pydicom.valuerep.DA`.
        """
        if not args or args[0] is None:
            return None

        val = args[0]
        if isinstance(val, str):
            if val.strip() == "":
                return None  # empty date

            if len(val) == 8:
                year = int(val[0:4])
                month = int(val[4:6])
                day = int(val[6:8])
                return super().__new__(cls, year, month, day)

            if len(val) == 10 and val[4] == "." and val[7] == ".":
                # ACR-NEMA Standard 300, predecessor to DICOM
                # for compatibility with a few old pydicom example files
                year = int(val[0:4])
                month = int(val[5:7])
                day = int(val[8:10])
                return super().__new__(cls, year, month, day)

        if isinstance(val, datetime.date):
            return super().__new__(cls, val.year, val.month, val.day)

        try:
            return super().__new__(cls, *args, **kwargs)
        except Exception as exc:
            raise ValueError(f"Unable to convert '{val}' to 'DA' object") from exc

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Create a new **DA** element value."""
        val = args[0]
        if isinstance(val, str):
            self.original_string = val
        elif isinstance(val, DA) and hasattr(val, "original_string"):
            self.original_string = val.original_string
        elif isinstance(val, datetime.date):
            self.original_string = f"{val.year}{val.month:02}{val.day:02}"


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
        offset = -offset if value[0] == "-" else offset

        return datetime.timezone(datetime.timedelta(seconds=offset), name=value)

    def __new__(  # type: ignore[misc]
        cls: type["DT"], *args: Any, **kwargs: Any
    ) -> Optional["DT"]:
        """Create an instance of DT object.

        Raise an exception if the string cannot be parsed or the argument
        is otherwise incompatible.

        The arguments (``*args`` and ``**kwargs``) are either the ones
        inherited from :class:`datetime.datetime`, or the first argument is
        a string conformant to the DT definition in the DICOM Standard,
        Part 5, :dcm:`Table 6.2-1<part05/sect_6.2.html#table_6.2-1>`,
        or it is a :class:`datetime.datetime` object, or an object of type
        :class:`~pydicom.valuerep.DT`.
        """
        if not args or args[0] is None:
            return None

        val = args[0]
        if isinstance(val, str):
            if val.strip() == "":
                return None

            match = cls._regex_dt.match(val)
            if not match or len(val) > 26:
                raise ValueError(
                    f"Unable to convert non-conformant value '{val}' to 'DT' object"
                )

            dt_match = match.group(2)
            args = (
                int(dt_match[0:4]),  # year
                1 if len(dt_match) < 6 else int(dt_match[4:6]),  # month
                1 if len(dt_match) < 8 else int(dt_match[6:8]),  # day
            )
            kwargs = {
                "hour": 0 if len(dt_match) < 10 else int(dt_match[8:10]),
                "minute": 0 if len(dt_match) < 12 else int(dt_match[10:12]),
                "second": 0 if len(dt_match) < 14 else int(dt_match[12:14]),
                "microsecond": 0,
            }
            if len(dt_match) >= 14 and match.group(4):
                kwargs["microsecond"] = int(match.group(4).rstrip().ljust(6, "0"))

            # Timezone offset
            tz_match = match.group(5)
            kwargs["tzinfo"] = cls._utc_offset(tz_match) if tz_match else None

            # DT may include a leap second which isn't allowed by datetime
            if kwargs["second"] == 60:
                warn_and_log(
                    "'datetime.datetime' doesn't allow a value of '60' for "
                    "the seconds component, changing to '59'"
                )
                kwargs["second"] = 59

            return super().__new__(cls, *args, **kwargs)

        if isinstance(val, datetime.datetime):
            return super().__new__(
                cls, *val.timetuple()[:6], val.microsecond, val.tzinfo
            )

        try:
            return super().__new__(cls, *args, **kwargs)
        except Exception as exc:
            raise ValueError(f"Unable to convert '{val}' to 'DT' object") from exc

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Create a new **DT** element value."""
        val = args[0]
        if isinstance(val, str):
            self.original_string = val
        elif isinstance(val, DT) and hasattr(val, "original_string"):
            self.original_string = val.original_string
        elif isinstance(val, datetime.datetime):
            self.original_string = (
                f"{val.year:04}{val.month:02}{val.day:02}"
                f"{val.hour:02}{val.minute:02}{val.second:02}"
            )
            # milliseconds are seldom used, add them only if needed
            if val.microsecond > 0:
                self.original_string += f".{val.microsecond:06}"

            if val.tzinfo is not None:
                # offset: Optional[datetime.timedelta]
                offset = val.tzinfo.utcoffset(val)
                if offset is not None:
                    offset_min = offset.days * 24 * 60 + offset.seconds // 60
                    sign = "+" if offset_min >= 0 else "-"
                    offset_min = abs(offset_min)
                    self.original_string += (
                        f"{sign}{offset_min // 60:02}{offset_min % 60:02}"
                    )


class TM(_DateTimeBase, datetime.time):
    """Store value for an element with VR **TM** as :class:`datetime.time`.

    Note that the :class:`datetime.time` base class is immutable.
    """

    _RE_TIME = re.compile(
        r"(?P<h>^([01][0-9]|2[0-3]))"
        r"((?P<m>([0-5][0-9]))"
        r"((?P<s>([0-5][0-9]|60))"
        r"(\.(?P<ms>([0-9]{1,6})?))?)?)?$"
    )

    def __new__(  # type: ignore[misc]
        cls: type["TM"], *args: Any, **kwargs: Any
    ) -> Optional["TM"]:
        """Create an instance of TM object from a string.

        Raise an exception if the string cannot be parsed or the argument
        is otherwise incompatible.

        The arguments (``*args`` and ``**kwargs``) are either the ones
        inherited from :class:`datetime.time`, or the first argument is
        a string conformant to the TM definition in the DICOM Standard,
        Part 5, :dcm:`Table 6.2-1<part05/sect_6.2.html#table_6.2-1>`,
        or it is a :class:`datetime.time` object, or an object of type
        :class:`~pydicom.valuerep.TM`.
        """
        if not args or args[0] is None:
            return None

        val = args[0]
        if isinstance(val, str):
            if val.strip() == "":
                return None  # empty time

            match = cls._RE_TIME.match(val)
            if not match:
                raise ValueError(
                    f"Unable to convert non-conformant value '{val}' to 'TM' object"
                )

            hour = int(match.group("h"))
            minute = 0 if match.group("m") is None else int(match.group("m"))
            second = 0 if match.group("s") is None else int(match.group("s"))

            if second == 60:
                warn_and_log(
                    "'datetime.time' doesn't allow a value of '60' for the "
                    "seconds component, changing to '59'"
                )
                second = 59

            microsecond = 0
            if match.group("ms"):
                microsecond = int(match.group("ms").rstrip().ljust(6, "0"))

            return super().__new__(cls, hour, minute, second, microsecond)

        if isinstance(val, datetime.time):
            return super().__new__(
                cls, val.hour, val.minute, val.second, val.microsecond
            )

        try:
            return super().__new__(cls, *args, **kwargs)
        except Exception as exc:
            raise ValueError(f"Unable to convert '{val}' to 'TM' object") from exc

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        val = args[0]
        if isinstance(val, str):
            self.original_string = val
        elif isinstance(val, TM) and hasattr(val, "original_string"):
            self.original_string = val.original_string
        elif isinstance(val, datetime.time):
            self.original_string = f"{val.hour:02}{val.minute:02}{val.second:02}"
            # milliseconds are seldom used, add them only if needed
            if val.microsecond > 0:
                self.original_string += f".{val.microsecond:06}"


def is_valid_ds(s: str) -> bool:
    """Check whether this string is a valid decimal string.

    Valid decimal strings must be 16 characters or fewer, and contain only
    characters from a limited set.

    Parameters
    ----------
    s: str
        String to test.

    Returns
    -------
    bool
        True if the string is a valid decimal string. Otherwise False.
    """
    return validate_length_and_type_and_regex("DS", s)[0]


def format_number_as_ds(val: float | Decimal) -> str:
    """Truncate a float's representation to give a valid Decimal String (DS).

    DICOM's decimal string (DS) representation is limited to strings with 16
    characters and a limited set of characters. This function represents a
    float that satisfies these constraints while retaining as much
    precision as possible. Some floats are represented using scientific
    notation to make more efficient use of the limited number of characters.

    Note that this will incur a loss of precision if the number cannot be
    represented with 16 characters. Furthermore, non-finite floats (infs and
    nans) cannot be represented as decimal strings and will cause an error to
    be raised.

    Parameters
    ----------
    val: float | Decimal
        The floating point value whose representation is required.

    Returns
    -------
    str
        String representation of the float satisfying the constraints of the
        decimal string representation.

    Raises
    ------
    ValueError
        If val does not represent a finite value

    """
    if not isinstance(val, float | Decimal):
        raise TypeError("'val' must be of type float or decimal.Decimal")
    if not isfinite(val):
        raise ValueError(
            f"Cannot encode non-finite floats as DICOM decimal strings. Got '{val}'"
        )

    valstr = str(val)

    # In the simple case, the default python string representation
    # will do
    if len(valstr) <= 16:
        return valstr

    # Decide whether to use scientific notation
    logval = log10(cast(float | Decimal, abs(val)))

    # Characters needed for '-' at start
    sign_chars = 1 if val < 0.0 else 0

    # Numbers larger than 1e14 cannot be correctly represented by truncating
    # their string representations to 16 chars, e.g pi * 10^13 would become
    # '314159265358979.', which may not be universally understood. This limit
    # is 1e13 for negative numbers because of the minus sign.
    # For negative exponents, the point of equal precision between scientific
    # and standard notation is 1e-4 e.g. '0.00031415926535' and
    # '3.1415926535e-04' are both 16 chars
    use_scientific = logval < -4 or logval >= (14 - sign_chars)

    if use_scientific:
        # In principle, we could have a number where the exponent
        # needs three digits to be represented (bigger than this cannot be
        # represented by floats). Due to floating point limitations
        # this is best checked for by doing the string conversion
        remaining_chars = 10 - sign_chars
        trunc_str = f"{val:.{remaining_chars}e}"
        if len(trunc_str) > 16:
            trunc_str = f"{val:.{remaining_chars - 1}e}"
        return trunc_str
    else:
        if logval >= 1.0:
            # chars remaining for digits after sign, digits left of '.' and '.'
            remaining_chars = 14 - sign_chars - int(floor(logval))
        else:
            remaining_chars = 14 - sign_chars
        return f"{val:.{remaining_chars}f}"


class DSfloat(float):
    """Store value for an element with VR **DS** as :class:`float`.

    If constructed from an empty string, return the empty string,
    not an instance of this class.

    Parameters
    ----------
    val: str | int | float | Decimal
        Value to store as a DS.
    auto_format: bool
        If True, automatically format the string representation of this
        number to ensure it satisfies the constraints in the DICOM standard.
        Note that this will lead to loss of precision for some numbers.

    """

    auto_format: bool

    def __new__(  # type: ignore[misc]
        cls: type["DSfloat"],
        val: None | str | int | float | Decimal,
        auto_format: bool = False,
        validation_mode: int | None = None,
    ) -> "str | DSfloat | None":
        if val is None:
            return val

        if isinstance(val, str) and val.strip() == "":
            return val

        return super().__new__(cls, val)

    def __init__(
        self,
        val: str | int | float | Decimal,
        auto_format: bool = False,
        validation_mode: int | None = None,
    ) -> None:
        """Store the original string if one given, for exact write-out of same
        value later.
        """
        if validation_mode is None:
            validation_mode = config.settings.reading_validation_mode

        self.original_string: str

        # ... also if user changes a data element value, then will get
        # a different object, because float is immutable.
        has_attribute = hasattr(val, "original_string")
        pre_checked = False
        if isinstance(val, str):
            self.original_string = val.strip()
        elif isinstance(val, DSfloat | DSdecimal):
            if val.auto_format:
                auto_format = True  # override input parameter
                pre_checked = True
            if has_attribute:
                self.original_string = val.original_string

        self.auto_format = auto_format
        if self.auto_format and not pre_checked:
            # If auto_format is True, keep the float value the same, but change
            # the string representation stored in original_string if necessary
            if hasattr(self, "original_string"):
                if not is_valid_ds(self.original_string):
                    self.original_string = format_number_as_ds(
                        float(self.original_string)
                    )
            else:
                self.original_string = format_number_as_ds(self)

        if validation_mode == config.RAISE and not self.auto_format:
            if len(str(self)) > 16:
                raise OverflowError(
                    "Values for elements with a VR of 'DS' must be <= 16 "
                    "characters long, but the float provided requires > 16 "
                    "characters to be accurately represented. Use a smaller "
                    "string, set 'config.settings.reading_validation_mode' to "
                    "'WARN' to override the length check, or "
                    "explicitly construct a DS object with 'auto_format' "
                    "set to True"
                )
            if not is_valid_ds(str(self)):
                # This will catch nan and inf
                raise ValueError(
                    f'Value "{self}" is not valid for elements with a VR of DS'
                )

    def __eq__(self, other: Any) -> Any:
        """Override to allow string equality comparisons."""
        if isinstance(other, str):
            return str(self) == other

        return super().__eq__(other)

    def __hash__(self) -> int:
        return super().__hash__()

    def __ne__(self, other: Any) -> Any:
        return not self == other

    def __str__(self) -> str:
        if hasattr(self, "original_string") and not self.auto_format:
            return self.original_string

        # Issue #937 (Python 3.8 compatibility)
        return repr(self)[1:-1]

    def __repr__(self) -> str:
        if hasattr(self, "original_string"):
            return f"'{self.original_string}'"

        return f"'{super().__repr__()}'"


class DSdecimal(Decimal):
    """Store value for an element with VR **DS** as :class:`decimal.Decimal`.

    Parameters
    ----------
    val: str | int | float | Decimal
        Value to store as a DS.
    auto_format: bool
        If True, automatically format the string representation of this
        number to ensure it satisfies the constraints in the DICOM standard.
        Note that this will lead to loss of precision for some numbers.

    Notes
    -----
    If constructed from an empty string, returns the empty string, not an
    instance of this class.

    """

    auto_format: bool

    def __new__(  # type: ignore[misc]
        cls: type["DSdecimal"],
        val: None | str | int | float | Decimal,
        auto_format: bool = False,
        validation_mode: int | None = None,
    ) -> "str | DSdecimal | None":
        """Create an instance of DS object, or return a blank string if one is
        passed in, e.g. from a type 2 DICOM blank value.

        Parameters
        ----------
        val : str or numeric
            A string or a number type which can be converted to a decimal.
        """
        if val is None:
            return val

        if isinstance(val, str) and val.strip() == "":
            return val

        if isinstance(val, float) and not config.allow_DS_float:
            raise TypeError(
                "'DS' cannot be instantiated with a float value unless "
                "'config.allow_DS_float' is set to True. You should convert "
                "the value to a string with the desired number of digits, "
                "or use 'Decimal.quantize()' and pass a 'Decimal' instance."
            )

        return super().__new__(cls, val)

    def __init__(
        self,
        val: str | int | float | Decimal,
        auto_format: bool = False,
        validation_mode: int | None = None,
    ) -> None:
        """Store the original string if one given, for exact write-out of same
        value later. E.g. if set ``'1.23e2'``, :class:`~decimal.Decimal` would
        write ``'123'``, but :class:`DS` will use the original.
        """
        if validation_mode is None:
            validation_mode = config.settings.reading_validation_mode

        self.original_string: str

        # ... also if user changes a data element value, then will get
        # a different Decimal, as Decimal is immutable.
        pre_checked = False
        if isinstance(val, str):
            self.original_string = val.strip()
        elif isinstance(val, DSfloat | DSdecimal):
            if val.auto_format:
                auto_format = True  # override input parameter
                pre_checked = True

            if hasattr(val, "original_string"):
                self.original_string = val.original_string

        self.auto_format = auto_format
        if self.auto_format and not pre_checked:
            # If auto_format is True, keep the float value the same, but change
            # the string representation stored in original_string if necessary
            if hasattr(self, "original_string"):
                if not is_valid_ds(self.original_string):
                    self.original_string = format_number_as_ds(
                        float(self.original_string)
                    )
            else:
                self.original_string = format_number_as_ds(self)

        if validation_mode != config.IGNORE:
            if len(repr(self).strip("'")) > 16:
                msg = (
                    "Values for elements with a VR of 'DS' values must be "
                    "<= 16 characters long. Use a smaller string, set "
                    "'config.settings.reading_validation_mode' to "
                    "'WARN' to override the length check, use "
                    "'Decimal.quantize()' and initialize "
                    "with a 'Decimal' instance, or explicitly construct a DS "
                    "instance with 'auto_format' set to True"
                )
                if validation_mode == config.RAISE:
                    raise OverflowError(msg)
                warn_and_log(msg)
            elif not is_valid_ds(repr(self).strip("'")):
                # This will catch nan and inf
                msg = f'Value "{self}" is not valid for elements with a VR of DS'
                if validation_mode == config.RAISE:
                    raise ValueError(msg)
                warn_and_log(msg)

    def __eq__(self, other: Any) -> Any:
        """Override to allow string equality comparisons."""
        if isinstance(other, str):
            return str(self) == other

        return super().__eq__(other)

    def __hash__(self) -> int:
        return super().__hash__()

    def __ne__(self, other: Any) -> Any:
        return not self == other

    def __str__(self) -> str:
        has_str = hasattr(self, "original_string")
        if has_str and len(self.original_string) <= 16:
            return self.original_string

        return super().__str__()

    def __repr__(self) -> str:
        if hasattr(self, "original_string"):
            return f"'{self.original_string}'"

        return f"'{self}'"


# CHOOSE TYPE OF DS
DSclass: Any
if config.use_DS_decimal:
    DSclass = DSdecimal
else:
    DSclass = DSfloat


def DS(
    val: None | str | int | float | Decimal,
    auto_format: bool = False,
    validation_mode: int | None = None,
) -> None | str | DSfloat | DSdecimal:
    """Factory function for creating DS class instances.

    Checks for blank string; if so, returns that, else calls :class:`DSfloat`
    or :class:`DSdecimal` to create the class instance. This avoids overriding
    ``DSfloat.__new__()`` (which carries a time penalty for large arrays of
    DS).

    Similarly the string clean and check can be avoided and :class:`DSfloat`
    called directly if a string has already been processed.
    """
    if val is None:
        return val

    if validation_mode is None:
        validation_mode = config.settings.reading_validation_mode

    if isinstance(val, str):
        if val.strip() == "":
            return val
        validate_value("DS", val, validation_mode)

    if config.use_DS_decimal:
        return DSdecimal(val, auto_format, validation_mode)

    return DSfloat(val, auto_format, validation_mode)


class ISfloat(float):
    """Store value for an element with VR **IS** as :class:`float`.

    Stores original integer string for exact rewriting of the string
    originally read or stored.

    Note: By the DICOM standard, IS can only be an :class:`int`,
    however, it is not uncommon to see float IS values.  This class
    is used if the config settings allow non-strict reading.

    Generally, use :class:`~pydicom.valuerep.IS` to create IS values,
    this is returned instead if the value cannot be represented as an
    :class:`int`.  See :class:`~pydicom.valuerep.IS` for details of the
    parameters and return values.
    """

    def __new__(  # type: ignore[misc]
        cls: type["ISfloat"],
        val: str | float | Decimal,
        validation_mode: int | None = None,
    ) -> float | str:
        if isinstance(val, str) and val.strip() == "":
            return ""

        return super().__new__(cls, val)

    def __init__(
        self, val: str | float | Decimal, validation_mode: int | None = None
    ) -> None:
        # If a string passed, then store it
        if isinstance(val, str):
            self.original_string = val.strip()
        elif isinstance(val, IS | ISfloat) and hasattr(val, "original_string"):
            self.original_string = val.original_string
        if validation_mode:
            msg = f'Value "{self}" is not valid for elements with a VR of IS'
            if validation_mode == config.WARN:
                warn_and_log(msg)
            elif validation_mode == config.RAISE:
                msg += "\nSet reading_validation_mode to WARN or IGNORE to bypass"
                raise TypeError(msg)


class IS(int):
    """Store value for an element with VR **IS** as :class:`int`.

    Stores original integer string for exact rewriting of the string
    originally read or stored.
    """

    def __new__(  # type: ignore[misc]
        cls: type["IS"],
        val: None | str | int | float | Decimal,
        validation_mode: int | None = None,
    ) -> "str | IS | ISfloat | None":
        """Create instance if new integer string"""
        if val is None:
            return val

        if validation_mode is None:
            validation_mode = config.settings.reading_validation_mode

        if isinstance(val, str):
            if val.strip() == "":
                return val
            validate_value("IS", val, validation_mode)

        try:
            newval: IS | ISfloat = super().__new__(cls, val)
        except ValueError:
            # accept float strings when no integer loss, e.g. "1.0"
            newval = super().__new__(cls, float(val))

        # If a float or Decimal was passed in, check for non-integer,
        # i.e. could lose info if converted to int
        # If so, create an ISfloat instead (if allowed by settings)
        if isinstance(val, float | Decimal | str) and newval != float(val):
            newval = ISfloat(val, validation_mode)

        # Checks in case underlying int is >32 bits, DICOM does not allow this
        if not -(2**31) <= newval < 2**31 and validation_mode == config.RAISE:
            raise OverflowError(
                "Elements with a VR of IS must have a value between -2**31 "
                "and (2**31 - 1). Set "
                "'config.settings.reading_validation_mode' to "
                "'WARN' to override the value check"
            )

        return newval

    def __init__(
        self, val: str | int | float | Decimal, validation_mode: int | None = None
    ) -> None:
        # If a string passed, then store it
        if isinstance(val, str):
            self.original_string = val.strip()
        elif isinstance(val, IS) and hasattr(val, "original_string"):
            self.original_string = val.original_string

    def __eq__(self, other: Any) -> Any:
        """Override to allow string equality comparisons."""
        if isinstance(other, str):
            return str(self) == other

        return super().__eq__(other)

    def __hash__(self) -> int:
        return super().__hash__()

    def __ne__(self, other: Any) -> Any:
        return not self == other

    def __str__(self) -> str:
        if hasattr(self, "original_string"):
            return self.original_string

        # Issue #937 (Python 3.8 compatibility)
        return repr(self)[1:-1]

    def __repr__(self) -> str:
        return f"'{super().__repr__()}'"


def _verify_encodings(encodings: str | Sequence[str] | None) -> tuple[str, ...] | None:
    """Checks the encoding to ensure proper format"""
    if encodings is None:
        return None

    if isinstance(encodings, str):
        return (encodings,)

    return tuple(encodings)


def _decode_personname(
    components: Sequence[bytes], encodings: Sequence[str]
) -> tuple[str, ...]:
    """Return a list of decoded person name components.

    Parameters
    ----------
    components : list of bytes
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
    from pydicom.charset import decode_bytes

    comps = [decode_bytes(c, encodings, PN_DELIMS) for c in components]

    # Remove empty elements from the end to avoid trailing '='
    while len(comps) and not comps[-1]:
        comps.pop()

    return tuple(comps)


def _encode_personname(components: Sequence[str], encodings: Sequence[str]) -> bytes:
    """Encode a list of text string person name components.

    Parameters
    ----------
    components : list of str
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
        groups = [encode_string(group, encodings) for group in comp.split("^")]
        encoded_comp = b"^".join(groups)
        encoded_comps.append(encoded_comp)

    # Remove empty elements from the end
    while len(encoded_comps) and not encoded_comps[-1]:
        encoded_comps.pop()
    return b"=".join(encoded_comps)


class PersonName:
    """Representation of the value for an element with VR **PN**."""

    def __new__(  # type: ignore[misc]
        cls: type["PersonName"], *args: Any, **kwargs: Any
    ) -> Optional["PersonName"]:
        if len(args) and args[0] is None:
            return None

        return super().__new__(cls)

    def __init__(
        self,
        val: "bytes | str | PersonName",
        encodings: Sequence[str] | None = None,
        original_string: bytes | None = None,
        validation_mode: int | None = None,
    ) -> None:
        """Create a new ``PersonName``.

        Parameters
        ----------
        val: str, bytes, PersonName
            The value to use for the **PN** element.
        encodings: list of str, optional
            A list of the encodings used for the value.
        original_string: bytes, optional
            When creating a ``PersonName`` using a decoded string, this is the
            original encoded value.

        Notes
        -----
        A :class:`PersonName` may also be constructed by specifying individual
        components using the :meth:`from_named_components` and
        :meth:`from_named_components_veterinary` class methods.
        """
        self.original_string: bytes
        self._components: tuple[str, ...] | None = None
        self.encodings: tuple[str, ...] | None
        if validation_mode is None:
            validation_mode = config.settings.reading_validation_mode
        self.validation_mode = validation_mode

        if isinstance(val, PersonName):
            encodings = val.encodings
            self.original_string = val.original_string
            self._components = tuple(str(val).split("="))
        elif isinstance(val, bytes):
            # this is the raw byte string - decode it on demand
            self.original_string = val
            validate_value("PN", val, validation_mode)
            self._components = None
        else:
            # val: str
            # `val` is the decoded person name value
            # `original_string` should be the original encoded value
            self.original_string = cast(bytes, original_string)
            # if we don't have the byte string at this point, we at least
            # validate the length of the string components
            validate_value(
                "PN", original_string if original_string else val, validation_mode
            )
            components = val.split("=")
            # Remove empty elements from the end to avoid trailing '='
            while len(components) and not components[-1]:
                components.pop()
            self._components = tuple(components)

            # if the encoding is not given, leave it as undefined (None)
        self.encodings = _verify_encodings(encodings)

    def _create_dict(self) -> dict[str, str]:
        """Creates a dictionary of person name group and component names.

        Used exclusively for `formatted` for backwards compatibility.
        """
        parts = [
            "family_name",
            "given_name",
            "middle_name",
            "name_prefix",
            "name_suffix",
            "ideographic",
            "phonetic",
        ]
        return {c: getattr(self, c, "") for c in parts}

    @property
    def components(self) -> tuple[str, ...]:
        """Returns up to three decoded person name components as a
        :class:`tuple` of :class:`str`.

        Returns
        -------
        Tuple[str, ...]
            The (alphabetic, ideographic, phonetic) components of the
            decoded person name. Any of the components may be absent.
        """
        if self._components is None:
            groups = self.original_string.split(b"=")
            encodings = self.encodings or [default_encoding]
            self._components = _decode_personname(groups, encodings)

        return self._components

    def _name_part(self, i: int) -> str:
        """Return the `i`th part of the name."""
        try:
            return self.components[0].split("^")[i]
        except IndexError:
            return ""

    @property
    def family_name(self) -> str:
        """Return the first (family name) group of the alphabetic person name
        representation as a unicode string
        """
        return self._name_part(0)

    @property
    def given_name(self) -> str:
        """Return the second (given name) group of the alphabetic person name
        representation as a unicode string
        """
        return self._name_part(1)

    @property
    def middle_name(self) -> str:
        """Return the third (middle name) group of the alphabetic person name
        representation as a unicode string
        """
        return self._name_part(2)

    @property
    def name_prefix(self) -> str:
        """Return the fourth (name prefix) group of the alphabetic person name
        representation as a unicode string
        """
        return self._name_part(3)

    @property
    def name_suffix(self) -> str:
        """Return the fifth (name suffix) group of the alphabetic person name
        representation as a unicode string
        """
        return self._name_part(4)

    @property
    def alphabetic(self) -> str:
        """Return the first (alphabetic) person name component as a
        unicode string
        """
        try:
            return self.components[0]
        except IndexError:
            return ""

    @property
    def ideographic(self) -> str:
        """Return the second (ideographic) person name component as a
        unicode string
        """
        try:
            return self.components[1]
        except IndexError:
            return ""

    @property
    def phonetic(self) -> str:
        """Return the third (phonetic) person name component as a
        unicode string
        """
        try:
            return self.components[2]
        except IndexError:
            return ""

    def __eq__(self, other: Any) -> Any:
        """Return ``True`` if `other` equals the current name."""
        return str(self) == other

    def __ne__(self, other: Any) -> Any:
        """Return ``True`` if `other` doesn't equal the current name."""
        return not self == other

    def __str__(self) -> str:
        """Return a string representation of the name."""
        return "=".join(self.components).__str__()

    def __iter__(self) -> Iterator[str]:
        """Iterate through the name."""
        yield from self.__str__()

    def __len__(self) -> int:
        """Return the length of the person name."""
        return len(self.__str__())

    def __contains__(self, x: Any) -> bool:
        """Return ``True`` if `x` is in the name."""
        return x in self.__str__()

    def __repr__(self) -> str:
        """Return a representation of the name."""
        return "=".join(self.components).__repr__()

    def __hash__(self) -> int:
        """Return a hash of the name."""
        return hash(self.components)

    def decode(self, encodings: Sequence[str] | None = None) -> "PersonName":
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
                self.components, self.encodings or [default_encoding]
            )
            # now that we have the byte length, we re-validate the value
            validate_value("PN", self.original_string, self.validation_mode)

        return PersonName(self.original_string, encodings)

    def encode(self, encodings: Sequence[str] | None = None) -> bytes:
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
            return _encode_personname(self.components, cast(Sequence[str], encodings))

        if self.original_string is None:
            # if the original encoding was not set, we set it now
            self.original_string = _encode_personname(
                self.components, encodings or [default_encoding]
            )

        return self.original_string

    def family_comma_given(self) -> str:
        """Return the name as "Family, Given"."""
        return f"{self.family_name}, {self.given_name}"

    def formatted(self, format_str: str) -> str:
        """Return the name as a :class:`str` formatted using `format_str`."""
        return format_str % self._create_dict()

    def __bool__(self) -> bool:
        """Return ``True`` if the name is not empty."""
        if not self.original_string:
            return bool(self.components) and (
                len(self.components) > 1 or bool(self.components[0])
            )

        return bool(self.original_string)

    @staticmethod
    def _encode_component_groups(
        alphabetic_group: Sequence[str | bytes],
        ideographic_group: Sequence[str | bytes],
        phonetic_group: Sequence[str | bytes],
        encodings: list[str] | None = None,
    ) -> bytes:
        """Creates a byte string for a person name from lists of parts.

        Each of the three component groups (alphabetic, ideographic, phonetic)
        are supplied as a list of components.

        Parameters
        ----------
        alphabetic_group: Sequence[str | bytes]
            List of components for the alphabetic group.
        ideographic_group: Sequence[str | bytes]
            List of components for the ideographic group.
        phonetic_group: Sequence[str | bytes]
            List of components for the phonetic group.
        encodings: list[str] | None
            A list of encodings used for the other input parameters.

        Returns
        -------
        bytes:
            Bytes string representation of the person name.

        Raises
        ------
        ValueError:
            If any of the input strings contain disallowed characters:
            '\\' (single backslash), '^', '='.
        """
        from pydicom.charset import encode_string, decode_bytes

        def enc(s: str) -> bytes:
            return encode_string(s, encodings or [default_encoding])

        def dec(s: bytes) -> str:
            return decode_bytes(s, encodings or [default_encoding], set())

        encoded_component_sep = enc("^")
        encoded_group_sep = enc("=")

        disallowed_chars = ["\\", "=", "^"]

        def standardize_encoding(val: str | bytes) -> bytes:
            # Return a byte encoded string regardless of the input type
            # This allows the user to supply a mixture of str and bytes
            # for different parts of the input
            if isinstance(val, bytes):
                val_enc = val
                val_dec = dec(val)
            else:
                val_enc = enc(val)
                val_dec = val

            # Check for disallowed chars in the decoded string
            for c in disallowed_chars:
                if c in val_dec:
                    raise ValueError(f"Strings may not contain the {c} character")

            # Return the encoded string
            return val_enc

        def make_component_group(components: Sequence[str | bytes]) -> bytes:
            encoded_components = [standardize_encoding(c) for c in components]
            joined_components = encoded_component_sep.join(encoded_components)
            return joined_components.rstrip(encoded_component_sep)

        component_groups: list[bytes] = [
            make_component_group(alphabetic_group),
            make_component_group(ideographic_group),
            make_component_group(phonetic_group),
        ]
        joined_groups: bytes = encoded_group_sep.join(component_groups)
        joined_groups = joined_groups.rstrip(encoded_group_sep)
        return joined_groups

    @classmethod
    def from_named_components(
        cls,
        family_name: str | bytes = "",
        given_name: str | bytes = "",
        middle_name: str | bytes = "",
        name_prefix: str | bytes = "",
        name_suffix: str | bytes = "",
        family_name_ideographic: str | bytes = "",
        given_name_ideographic: str | bytes = "",
        middle_name_ideographic: str | bytes = "",
        name_prefix_ideographic: str | bytes = "",
        name_suffix_ideographic: str | bytes = "",
        family_name_phonetic: str | bytes = "",
        given_name_phonetic: str | bytes = "",
        middle_name_phonetic: str | bytes = "",
        name_prefix_phonetic: str | bytes = "",
        name_suffix_phonetic: str | bytes = "",
        encodings: list[str] | None = None,
    ) -> "PersonName":
        """Construct a PersonName from explicit named components.

        The DICOM standard describes human names using five components:
        family name, given name, middle name, name prefix, and name suffix.
        Any component may be an empty string (the default) if not used.
        A component may contain multiple space-separated words if there
        are, for example, multiple given names, middle names, or titles.

        Additionally, each component may be represented in ideographic or
        phonetic form in addition to (or instead of) alphabetic form.

        For more information see the following parts of the DICOM standard:
        - :dcm:`Value Representations <part05/sect_6.2.html>`
        - :dcm:`PN Examples <part05/sect_6.2.html#sect_6.2.1.1>`
        - :dcm:`PN Precise semantics <part05/sect_6.2.html#sect_6.2.1.2>`

        Example
        -------
        A case with multiple given names and suffixes (DICOM standard,
        part 5, sect 6.2.1.1):

        >>> pn = PersonName.from_named_components(
                family_name='Adams',
                given_name='John Robert Quincy',
                name_prefix='Rev.',
                name_suffix='B.A. M.Div.'
            )

        A Korean case with phonetic and ideographic representations (PS3.5-2008
        section I.2 p. 108):

        >>> pn = PersonName.from_named_components(
                family_name='Hong',
                given_name='Gildong',
                family_name_ideographic='洪',
                given_name_ideographic='吉洞',
                family_name_phonetic='홍',
                given_name_phonetic='길동',
                encodings=[default_encoding, 'euc_kr']
            )

        Parameters
        ----------
        family_name: str | bytes
            Family name in alphabetic form.
        given_name: str | bytes
            Given name in alphabetic form.
        middle_name: str | bytes
            Middle name in alphabetic form.
        name_prefix: str | bytes
            Name prefix in alphabetic form, e.g. 'Mrs.', 'Dr.', 'Sr.', 'Rev.'.
        name_suffix: str | bytes
            Name prefix in alphabetic form, e.g. 'M.D.', 'B.A., M.Div.',
            'Chief Executive Officer'.
        family_name_ideographic: str | bytes
            Family name in ideographic form.
        given_name_ideographic: str | bytes
            Given name in ideographic form.
        middle_name_ideographic: str | bytes
            Middle name in ideographic form.
        name_prefix_ideographic: str | bytes
            Name prefix in ideographic form.
        name_suffix_ideographic: str | bytes
            Name suffix in ideographic form.
        family_name_phonetic: str | bytes
            Family name in phonetic form.
        given_name_phonetic: str | bytes
            Given name in phonetic form.
        middle_name_phonetic: str | bytes
            Middle name in phonetic form.
        name_prefix_phonetic: str | bytes
            Name prefix in phonetic form.
        name_suffix_phonetic: str | bytes
            Name suffix in phonetic form.
        encodings: list[str] | None
            A list of encodings used for the other input parameters.

        Returns
        -------
        PersonName:
            PersonName constructed from the supplied components.

        Notes
        -----
        Strings may not contain the following characters: '^', '=',
        or the backslash character.
        """
        alphabetic_group: list[str | bytes] = [
            family_name,
            given_name,
            middle_name,
            name_prefix,
            name_suffix,
        ]

        # Ideographic component group
        ideographic_group: list[str | bytes] = [
            family_name_ideographic,
            given_name_ideographic,
            middle_name_ideographic,
            name_prefix_ideographic,
            name_suffix_ideographic,
        ]

        # Phonetic component group
        phonetic_group: list[str | bytes] = [
            family_name_phonetic,
            given_name_phonetic,
            middle_name_phonetic,
            name_prefix_phonetic,
            name_suffix_phonetic,
        ]

        encoded_value: bytes = cls._encode_component_groups(
            alphabetic_group,
            ideographic_group,
            phonetic_group,
            encodings,
        )

        return cls(encoded_value, encodings=encodings)

    @classmethod
    def from_named_components_veterinary(
        cls,
        responsible_party_name: str | bytes = "",
        patient_name: str | bytes = "",
        responsible_party_name_ideographic: str | bytes = "",
        patient_name_ideographic: str | bytes = "",
        responsible_party_name_phonetic: str | bytes = "",
        patient_name_phonetic: str | bytes = "",
        encodings: list[str] | None = None,
    ) -> "PersonName":
        """Construct a PersonName from explicit named components following the
        veterinary usage convention.

        The DICOM standard describes names for veterinary use with two components:
        responsible party family name OR responsible party organization name,
        and patient name.
        Any component may be an empty string (the default) if not used.
        A component may contain multiple space-separated words if necessary.

        Additionally, each component may be represented in ideographic or
        phonetic form in addition to (or instead of) alphabetic form.

        For more information see the following parts of the DICOM standard:
        - :dcm:`Value Representations <part05/sect_6.2.html>`
        - :dcm:`PN Examples <part05/sect_6.2.html#sect_6.2.1.1>`
        - :dcm:`PN Precise semantics <part05/sect_6.2.html#sect_6.2.1.1>`

        Example
        -------

        A horse whose responsible organization is named "ABC Farms", and whose
        name is "Running On Water"

        >>> pn = PersonName.from_named_components_veterinary(
                responsible_party_name='ABC Farms',
                patient_name='Running on Water'
            )

        Parameters
        ----------
        responsible_party_name: str | bytes
            Name of the responsible party in alphabetic form. This may be
            either the family name of the responsible party, or the
            name of the responsible organization.
        patient_name: str | bytes
            Patient name in alphabetic form.
        responsible_party_name_ideographic: str | bytes
            Name of the responsible party in ideographic form.
        patient_name_ideographic: str | bytes
            Patient name in ideographic form.
        responsible_party_name_phonetic: str | bytes
            Name of the responsible party in phonetic form.
        patient_name_phonetic: str | bytes
            Patient name in phonetic form.
        encodings: list[str] | None
            A list of encodings used for the other input parameters

        Returns
        -------
        PersonName:
            PersonName constructed from the supplied components

        Notes
        -----
        Strings may not contain the following characters: '^', '=',
        or the backslash character.
        """
        alphabetic_group: list[str | bytes] = [
            responsible_party_name,
            patient_name,
        ]

        ideographic_group: list[str | bytes] = [
            responsible_party_name_ideographic,
            patient_name_ideographic,
        ]

        phonetic_group: list[str | bytes] = [
            responsible_party_name_phonetic,
            patient_name_phonetic,
        ]

        encoded_value: bytes = cls._encode_component_groups(
            alphabetic_group, ideographic_group, phonetic_group, encodings
        )

        return cls(encoded_value, encodings=encodings)
