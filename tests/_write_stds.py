# Copyright 2008-2025 pydicom authors. See LICENSE file for details.
"""Test data for a couple of tests"""


# Test data: Implicit VR, little endian, SQ with defined lengths
impl_LE_deflen_std_hex = (
    b"10 00 10 00 "  # (0010,0010) Patient's Name
    b"0c 00 00 00 "  # length 12
    b"4e 61 6d 65 5e 50 61 74 69 65 6e 74 "  # "Name^Patient"
    b"20 00 13 00 "  # instance number with no value
    b"00 00 00 00 "  # length 0
    b"06 30 39 00 "  # (3006,0039) ROI Contour Sequence
    b"5a 00 00 00 "  # length 90
    b"fe ff 00 e0 "  # (FFFE,E000) Item Tag
    b"52 00 00 00 "  # length 82
    b"06 30 40 00 "  # (3006,0040)  Contour Sequence
    b"4a 00 00 00 "  # length 74
    b"fe ff 00 e0 "  # (FFFE,E000) Item Tag
    b"1a 00 00 00 "  # length 26
    b"06 30 48 00 "  # (3006,0048) Contour Number
    b"02 00 00 00 "  # length 2
    b"31 20 "  # "1 "
    b"06 30 50 00 "  # (3006,0050) Contour Data
    b"08 00 00 00 "  # length 8
    b"32 5c 34 5c 38 5c 31 36 "  # "2\4\8\16"
    b"fe ff 00 e0 "  # (FFFE,E000) Item Tag
    b"20 00 00 00 "  # length 32
    b"06 30 48 00 "  # (3006,0048) Contour Number
    b"02 00 00 00 "  # length 2
    b"32 20 "  # "2 "
    b"06 30 50 00 "  # (3006,0050) Contour Data
    b"0e 00 00 00 "  # length 14
    b"33 32 5c 36 34 5c 31 32 38 5c 31 39 36 20 "
    # "32\64\128\196 "
)
