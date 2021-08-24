"""Value Representation (VR) configuration.

dataelem.DataElement.repval()
filewriter.correct_ambiguous_vr_element() -> if elem.VR.is_ambiguous:
filewriter.writers ?
values.converters ?
"""

from enum import Enum, unique
from itertools import chain

from pydicom._dicom_dict import DicomDictionary, RepeatersDictionary


# VRs from Table 6.2-1 in Part 5
_VR = {
    "AE", "AS", "AT", "CS", "DA", "DS", "DT", "FD", "FL", "IS",
    "LO", "LT", "OB", "OD", "OF", "OL", "OW", "OV", "PN", "SH",
    "SL", "SQ", "SS", "ST", "SV", "TM", "UC", "UI", "UL", "UN",
    "UR", "US", "UT", "UV",
}
# Ambiguous VRs from Tables 6-1, 7-1 and 8-1 in Part 6
#AMBIGUOUS_VR = {"US or SS or OW", "US or SS", "US or OW", "OB or OW"}


@unique
class VR(str, Enum):
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
    US_SS_OW = "US or SS or OW"
    US_SS = "US or SS"
    US_OW = "US or OW"
    OB_OW = "OB or OW"


    # standard = {
    #     AE, AS, AT, CS, DA, DS, DT, FD, FL, IS, LO, LT, OB, OD, OF,
    #     OL, OW, OV, PN, SH, SL, SQ, SS, ST, SV, TM, UC, UI, UL, UN,
    #     UR, US, UT, UV
    # }
    # ambiguous = {US_SS_OW, US_SS, US_OW, OB_OW}
    # all = standard | ambiguous

    @classmethod
    def standard(cls):
        # VRs from Table 6.2-1 in Part 5
        return {
            cls.AE, cls.AS, cls.AT, cls.CS, cls.DA, cls.DS, cls.DT,
            cls.FD, cls.FL, cls.IS, cls.LO, cls.LT, cls.OB, cls.OD,
            cls.OF, cls.OL, cls.OW, cls.OV, cls.PN, cls.SH, cls.SL,
            cls.SQ, cls.SS, cls.ST, cls.SV, cls.TM, cls.UC, cls.UI,
            cls.UL, cls.UN, cls.UR, cls.US, cls.UT, cls.UV,
        }

    @classmethod
    def ambiguous(cls):
        # Ambiguous VRs from Tables 6-1, 7-1 and 8-1 in Part 6
        return {cls.US_SS_OW, cls.US_SS, cls.US_OW, cls.OB_OW}

    @classmethod
    def all(cls):
        return cls.standard | cls.ambiguous


# VRs from Table 6.2-1 in Part 5
#STANDARD_VR = VR.standard()
# Ambiguous VRs from Tables 6-1, 7-1 and 8-1 in Part 6
#AMBIGUOUS_VR = VR.ambiguous()
#AMBIGUOUS_TAGS = {
#    kk: [] for
#}

# Ensure we have all possible VRs accounted for
_elements = chain(DicomDictionary.values(), RepeatersDictionary.values())
_reference = {v[0] for v in _elements} - {"NONE"}
_missing = ", ".join(list(_reference - VR.all()))
if _missing:
    raise RuntimeError(f"Missing configuration for {_missing}")





# Corresponding Python built-in for each VR
#   For some VRs this is more a "fallback" class-like behavioural definition
#   than actual, and note that some VRs such as IS and DS are present in
#   multiple sets
BYTES_VR = {VR.OB, VR.OD, VR.OF, VR.OL, VR.OW, VR.OV, VR.UN}
FLOAT_VR = {VR.DS, VR.FD, VR.FL}
INT_VR = {VR.AT, VR.IS, VR.SL, VR.SS, VR.SV, VR.UL, VR.US, VR.UV}
LIST_VR = {VR.SQ}
STR_VR = {
    VR.AE, VR.AS, VR.CS, VR.DA, VR.DS, VR.DT, VR.IS, VR.LO, VR.LT, VR.PN,
    VR.SH, VR.ST, VR.TM, VR.UC, VR.UI, VR.UR, VR.UT,
}

_missing = ", ".join(
    list(VR.standard() - (BYTES_VR | FLOAT_VR | INT_VR | LIST_VR | STR_VR))
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
EXPLICIT_VR_LENGTH_32 = VR.standard - EXPLICIT_VR_LENGTH_16
