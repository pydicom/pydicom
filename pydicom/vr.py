
"""
Consolidate VR handling

dataelem.BINARY_VR_VALUES
dataelem.empty_value_for_VR
dataelem.DataElement.value setter
dataelem.DataElement._convert()
dataelem.DataElement.repval()
compat.text_type ?
compat.string_types ?
compat.char_types ?
compat.number_types ?
compat.int_type ?
jsonrep.BINARY_VR_VALUES
jsonrep.VRs_TO_BE_FLOATS
jsonrep.VRs_TO_BE_INTS
filewriter.correct_ambiguous_vr_element() -> if elem.VR.is_ambiguous:
filewriter.writers ?
valuerep.extra_length_VRs
valuerep.text_VRs
values.converters ?
"""


from typing import (
    Optional, Callable, Any, TypeVar, Type, Union, Tuple, MutableSequence,
    TYPE_CHECKING
)

if TYPE_CHECKING:  # pragma: no cover
    from pydicom.dataset import Dataset


# Unambiguous VRs from Table 6.2-1 in Part 5
_STANDARD_VR = {
    "AE", "AS", "AT", "CS", "DA", "DS", "DT", "FD", "FL", "IS", "LO",
    "LT", "OB", "OD", "OF", "OL", "OW", "OV", "PN", "SH", "SL", "SQ",
    "SS", "ST", "SV", "TM", "UC", "UI", "UL", "UN", "UR", "US", "UT",
    "UV",
},
# Ambiguous VRs from Tables 6-1, 7-1 and 8-1 in Part 6
_AMBIGUOUS_VR = {"US or SS or OW", "US or SS", "US or OW", "OB or OW"}
# All possible VRs used in Part 6 of the DICOM Standard
_ALL_VR = _STANDARD_VR | _AMBIGUOUS_VR
# These VRs may have backslash characters or encoded backslashes in the value
#   based off of the information in Table 6.2-1 in Part 5
_BACKSLASH_ALLOWED = {
    "LT", "OB", "OD", "OF", "OL", "OV", "OW", "ST", "UN", "UT",
    "OB or OW",  # "US or SS or OW", "US or OW",
}
# Allowed character repertoire for text-like VRs, based off of the information
#   in Table 6.2-1 in Part 5
_CHARACTER_REPERTOIRE = {
    # Basic G0 set of ISO 646 (ISO-IR 6) only
    "default": {"AE", "AS", "CS", "DA", "DS", "DT", "IS", "TM", "UI", "UR"},
    # Basic G0 set of ISO 646 or by (0008,0005) *Specific Character Set*
    "customizable": {"LO", "LT", "PN", "SH", "ST", "UC", "UT"},
}
# VRs that use 2 byte length fields for Explicit VR from Table 7.1-2 in Part 5
_EXPLICIT_VR_LENGTH_16 = {
    "AE", "AS", "AT", "CS", "DA", "DS", "DT", "FL", "FD", "IS", "LO", "LT",
    "PN", "SH", "SL", "SS", "ST", "TM", "UI", "UL", "US",
}
# VRs that use 4 byte length fields for Explicit VR
_EXPLICIT_VR_LENGTH_32 = _UNAMBIGUOUS - _EXP_VR_LENGTH_16


# Corresponding Python built-in for the corresponding VR
BYTES_VR = {"OB", "OD", "OF", "OL", "OW", "OV"}
INT_VR = {"IS", "SL", "SS", "SV", "UL", "US", "UV"}
FLOAT_VR = {"DS", "FD", "FL"}
STR_VR = {
    "AE", "AS", "CS", "DA", "DS", "DT", "IS", "LO", "LT", "PN", "SH", "ST",
    "TM", "UC", "UI", "UR", "UT",
}


_T = TypeVar("_T")

_VR_TYPES = {
    "AE": StrVRType,
    "AS": StrVRType,
    "AT": None,
    "CS": StrVRType,
    "DA": None,
    "DS": None,
    "DT": None,
    "FD": FloatVRType,
    "FL": FloatVRType,
    "IS": None,
    "LO": StrVRType,
    "LT": Optional[str],
    "OB": BytesVRType,
    "OD": BytesVRType,
    "OF": BytesVRType,
    "OL": BytesVRType,
    "OV": BytesVRType,
    "OW": BytesVRType,
    "PN": StrVRType,
    "SH": StrVRType,
    "SL": IntVRType,
    "SQ": MutableSequence["Dataset"],
    "SS": IntVRType,
    "ST": Optional[str],
    "SV": IntVRType,
    "TM": None,
    "UC": StrVRType,
    "UI": StrVRType,
    "UL": IntVRType,
    "UN": BytesVRType,
    "UR": Optional[str],
    "US": IntVRType,
    "UT": Optional[str],
    "UV": IntVRType,
}
StrVRType = Union[None, str, MutableSequence[str]]
FloatVRType = Union[None, float, MutableSequence[float]]
IntVRType = Union[None, int, MutableSequence[int]]
BytesVRType = Optional[bytes]


class VR(str):
    #def __init__(
    #    self,
    #    vr: str,
        #decoder: Optional[Callable[[bytes], Any]] = None,
        #encoder: Optional[Callable[[Any], bytes]] = None,
        #validator: Optional[Callable[[Any], bool]] = None,
    #) -> None:
        #self._vr = vr
        #self._validator = validator
        #self._decoder = decoder
        #self._encoder = encoder

    #def __repr__(self) -> str:
    #    return self._vr

    #def __str__(self) -> str:
    #    return self._vr

    @property
    def allow_backslash(self) -> bool:
        """Return ``True`` if the backslash character is allowed in the value,
        ``False`` otherwise.
        """
        return self in _BACKSLASH_ALLOWED

    @property
    def is_ambiguous(self) -> bool:
        """Return ``True`` if the VR is ambiguous, ``False`` otherwise."""
        return len(self) > 2

    @property
    def character_repertoire(self) -> Optional[str]:
        """

        """
        for k, v in _CHARACTER_REPERTOIRE.items():
            if self in v:
                return k

        return None

    def is_like(self, t: Union[Type[_T], Tuple[Type[_T], ...]]) -> bool:
        pass

    @property
    def set_types(self) -> Union[Type[_T], Tuple[Type[_T], ...]]:
        pass

    @property
    def stored_types(self) -> Type[_T]:
        pass

    @property
    def empty_type(self) -> Type[_T]:
        pass

    @property
    def is_known(self) -> bool:
        """Return ``True`` if the VR is known, ``False`` otherwise."""
        return self in _ALL

    @property
    def type_hint(self):
        if self in _VR_TYPES:
            return _VR_TYPES[self]

        return None


# FIXME: VR class instead?
VR_CONFIGURATION = {
    # All non-ambiguous VRs
    "all": (
        'AE', 'AS', 'AT', 'CS', 'DA', 'DS', 'DT', 'FD', 'FL', 'IS', 'LO',
        'LT', 'OB', 'OD', 'OF', 'OL', 'OW', 'OV', 'PN', 'SH', 'SL', 'SQ',
        'SS', 'ST', 'SV', 'TM', 'UC', 'UI', 'UL', 'UN', 'UR', 'US', 'UT',
        'UV',
    ),
    # All ambiguous VRs
    "ambiguous": ("US or SS or OW", "US or SS", "US or OW", "OB or OW"),
    # Valid types for setting values (excluding None)
    # AT can be set with keyword, int, List[int], Tuple[int, int]
    "set_types": {
        # FIXME: Invert? {"AE": (str,), "AT": (str, int, BaseTag)}?
        # Python types
        "bytes": ("OB", "OD", "OF", "OL", "OV", "OW", "UN", "OB or OW"),
        "str": (
            "AE", "AS", "AT", "CS", "DA", "DT", "DS", "IS", "LO", "LT", "PN",
            "SH", "ST", "TM", "UC", "UI", "UR", "UT",
        ),
        "int": ("AT", "IS", "SS", "SV", "UL", "US", "UV"),
        "float": ("DS", "FD", "FL"),
        "list": ("SQ",),
        # pydicom types
        "BaseTag": ("AT",),
        "DA": ("DA"),
        "DSfloat": ("DS",),
        "DSdecimal": ("DS",),
        "DT": ("DT"),
        "IS": ("IS",),
        "PersonName": ("PN",),
        "Sequence": ("SQ",),
        "TM": ("TM",),
        "UID": ("UI",),
    },
    # Valid types for stored values (excluding None)
    "stored_types" : {
        # Python types
        "bytes": ("OB", "OD", "OF", "OL", "OV", "OW", "UN", "OB or OW"),
        "str": (  # DS, IS, PN, UI if empty str (VM 0)
            "AE", "AS", "AT", "CS", "DA", "DT", "DS", "IS", "LO", "LT", "PN",
            "SH", "ST", "TM", "UC", "UI", "UR", "UT",
        ),
        "int": ("SS", "SV", "UL", "US", "UV"),
        "float": ("FD", "FL"),
        # pydicom types
        "BaseTag": ("AT",),
        "DA": ("DA"),
        "DSfloat": ("DS",),
        "DSdecimal": ("DS",),
        "DT": ("DT"),
        "IS": ("IS",),
        "PersonName": ("PN",),
        "Sequence": ("SQ",),
        "TM": ("TM",),
        "UID": ("UI",),
    }
    # VRs that allow backslashes in values (either encoded or unencoded)
    "allow_backslash": (
        "LT", "OB", "OD", "OF", "OL", "OV", "OW", "ST", "UN", "UT",
        "OB or OW",
    ),
    # Default Character Repertoire - Part 5, Section 6.1
    "character_repertoire": {
        # Basic G0 set of ISO 646 (ISO-IR 6) only
        "default": (
            "AE", "AS", "CS", "DA", "DS", "DT", "IS", "TM", "UI", "UR"
        ),
        # Basic G0 set of ISO 646 or by (0008,0005) *Specific Character Set*
        "customizable": ("LO", "LT", "PN", "SH", "ST", "UC", "UT"),
    }
}
# Check set(all + ambiguous) matches set(data_dict)
# Check set(values.converters) matches set(data_dict)
# Check set(filewriter.writes) matches set(data_dict)
