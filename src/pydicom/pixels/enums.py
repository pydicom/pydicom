from enum import Enum, unique


# TODO: Python 3.11 switch to StrEnum
@unique
class PhotometricInterpretation(str, Enum):
    """Values for (0028,0004) *Photometric Interpretation*"""

    # Standard Photometric Interpretations from C.7.6.3.1.2 in Part 3
    MONOCHROME1 = "MONOCHROME1"
    MONOCHROME2 = "MONOCHROME2"
    PALETTE_COLOR = "PALETTE COLOR"
    RGB = "RGB"
    YBR_FULL = "YBR_FULL"
    YBR_FULL_422 = "YBR_FULL_422"
    YBR_ICT = "YBR_ICT"
    YBR_RCT = "YBR_RCT"
    HSV = "HSV"  # Retired
    ARGB = "ARGB"  # Retired
    CMYK = "CMYK"  # Retired
    YBR_PARTIAL_422 = "YBR_PARTIAL_422"  # Retired
    YBR_PARTIAL_420 = "YBR_PARTIAL_420"  # Retired

    # TODO: no longer needed if StrEnum
    def __str__(self) -> str:
        return str.__str__(self)
