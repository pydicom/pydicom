"""Value Representation (VR) configuration.

dataelem.DataElement.repval()
filewriter.correct_ambiguous_vr_element() -> if elem.VR.is_ambiguous:
filewriter.writers ?
values.converters ?
"""
from itertools import chain

from pydicom._dicom_dict import DicomDictionary, RepeatersDictionary


# VRs from Table 6.2-1 in Part 5
VR = {
    "AE", "AS", "AT", "CS", "DA", "DS", "DT", "FD", "FL", "IS",
    "LO", "LT", "OB", "OD", "OF", "OL", "OW", "OV", "PN", "SH",
    "SL", "SQ", "SS", "ST", "SV", "TM", "UC", "UI", "UL", "UN",
    "UR", "US", "UT", "UV",
}
# Ambiguous VRs from Tables 6-1, 7-1 and 8-1 in Part 6
AMBIGUOUS_VR = {"US or SS or OW", "US or SS", "US or OW", "OB or OW"}

# Ensure we have all possible VRs accounted for
_elements = chain(DicomDictionary.values(), RepeatersDictionary.values())
_reference = {v[0] for v in _elements} - {"NONE"}
_missing = ", ".join(list(_reference - (VR | AMBIGUOUS_VR)))
if _missing:
    raise RuntimeError(f"Missing configuration for {_missing}")


# Corresponding Python built-in for each VR
#   For some VRs this is more a "fallback" class-like behavioural definition
#   than actual, and note that some VRs such as IS and DS are present in
#   multiple sets
BYTES_VR = {"OB", "OD", "OF", "OL", "OW", "OV", "UN"}
FLOAT_VR = {"DS", "FD", "FL"}
INT_VR = {"AT", "IS", "SL", "SS", "SV", "UL", "US", "UV"}
LIST_VR = {"SQ"}
STR_VR = {
    "AE", "AS", "CS", "DA", "DS", "DT", "IS", "LO", "LT", "PN",
    "SH", "ST", "TM", "UC", "UI", "UR", "UT",
}

_missing = (
    ", ".join(list(VR - (BYTES_VR | FLOAT_VR | INT_VR | LIST_VR | STR_VR)))
)
if _missing:
    raise RuntimeError(f"Missing corresponding Python built-in for {_missing}")


# Character Repertoire
# Allowed character repertoire for str-like VRs, based off of the information
#   in Section 6.1.2 and Table 6.2-1 in Part 5
CHARSET_VR = {
    # Basic G0 set of ISO 646 (ISO-IR 6) only
    "default": {"AE", "AS", "CS", "DA", "DS", "DT", "IS", "TM", "UI", "UR"},
    # Basic G0 set of ISO 646 or extensible/replaceable by
    #   (0008,0005) *Specific Character Set*
    "customizable": {"LO", "LT", "PN", "SH", "ST", "UC", "UT"},
    # These VRs may have backslash characters or encoded backslashes in the
    #   value based off of the information in Table 6.2-1 in Part 5
    # DataElements with ambiguous VRs may use `bytes` values and so are allowed
    #   to have backslashes until their ambiguity is resolved
    "backslash_allowed": {"LT", "ST", "UT"} | BYTES_VR | AMBIGUOUS_VR,
}

_missing = ", ".join(
    list(STR_VR - (CHARSET_VR["default"] | CHARSET_VR["customizable"]))
)
if _missing:
    raise RuntimeError(f"Missing character set configuration for {_missing}")


# VRs that use 2 byte length fields for Explicit VR from Table 7.1-2 in Part 5
#   All other explicit VRs and all implicit VRs use 4 byte length fields
EXPLICIT_VR_LENGTH_16 = {
    "AE", "AS", "AT", "CS", "DA", "DS", "DT", "FL", "FD", "IS", "LO", "LT",
    "PN", "SH", "SL", "SS", "ST", "TM", "UI", "UL", "US",
}
EXPLICIT_VR_LENGTH_32 = VR - EXPLICIT_VR_LENGTH_16
