# Copyright 2008-2021 pydicom authors. See LICENSE file for details.
"""Value Representation (VR) configuration."""

from enum import Enum, unique
from itertools import chain

from pydicom._dicom_dict import DicomDictionary, RepeatersDictionary


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


# Standard VRs from Table 6.2-1 in Part 5
STANDARD_VR = {
    VR.AE, VR.AS, VR.AT, VR.CS, VR.DA, VR.DS, VR.DT, VR.FD, VR.FL, VR.IS,
    VR.LO, VR.LT, VR.OB, VR.OD, VR.OF, VR.OL, VR.OW, VR.OV, VR.PN, VR.SH,
    VR.SL, VR.SQ, VR.SS, VR.ST, VR.SV, VR.TM, VR.UC, VR.UI, VR.UL, VR.UN,
    VR.UR, VR.US, VR.UT, VR.UV,
}
# Ambiguous VRs from Tables 6-1, 7-1 and 8-1 in Part 6
AMBIGUOUS_VR = {VR.US_SS_OW, VR.US_SS, VR.US_OW, VR.OB_OW}


# Ensure we have all possible VRs accounted for
_elements = chain(DicomDictionary.values(), RepeatersDictionary.values())
_reference = {v[0] for v in _elements} - {"NONE"}
_missing = ", ".join(list(_reference - (STANDARD_VR | AMBIGUOUS_VR)))
if _missing:
    raise RuntimeError(f"VR configuration missing for {_missing}")


# Corresponding Python built-in for each VR
#   For some VRs this is more a "fallback" class-like behavioural definition
#   than actual, and note that some VRs such as IS and DS are present in
#   multiple sets
BYTES_VR = {VR.OB, VR.OD, VR.OF, VR.OL, VR.OV, VR.OW, VR.UN}
FLOAT_VR = {VR.DS, VR.FD, VR.FL}
INT_VR = {VR.AT, VR.IS, VR.SL, VR.SS, VR.SV, VR.UL, VR.US, VR.UV}
LIST_VR = {VR.SQ}
STR_VR = {
    VR.AE, VR.AS, VR.CS, VR.DA, VR.DS, VR.DT, VR.IS, VR.LO, VR.LT, VR.PN,
    VR.SH, VR.ST, VR.TM, VR.UC, VR.UI, VR.UR, VR.UT,
}

_missing = ", ".join(
    list(STANDARD_VR - (BYTES_VR | FLOAT_VR | INT_VR | LIST_VR | STR_VR))
)
if _missing:
    raise RuntimeError(f"Corresponding Python built-in missing for {_missing}")


# VRs that may have long values (more than 1024 characters)
LONG_VR = BYTES_VR | {VR.LT, VR.UC, VR.UT}
# These VRs may have backslash characters or encoded backslashes in the
#   value based off of the information in Table 6.2-1 in Part 5
# DataElements with ambiguous VRs may use `bytes` values and so are allowed
#   to have backslashes (except 'US or SS')
ALLOW_BACKSLASH = (
    {VR.LT, VR.ST, VR.UT, VR.US_SS_OW, VR.US_OW, VR.OB_OW} | BYTES_VR
)


# VRs that use 2 byte length fields for Explicit VR from Table 7.1-2 in Part 5
#   All other explicit VRs and all implicit VRs use 4 byte length fields
EXPLICIT_VR_LENGTH_16 = {
    VR.AE, VR.AS, VR.AT, VR.CS, VR.DA, VR.DS, VR.DT, VR.FL, VR.FD, VR.IS,
    VR.LO, VR.LT, VR.PN, VR.SH, VR.SL, VR.SS, VR.ST, VR.TM, VR.UI, VR.UL,
    VR.US,
}
EXPLICIT_VR_LENGTH_32 = STANDARD_VR - EXPLICIT_VR_LENGTH_16
