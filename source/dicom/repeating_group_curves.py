# repeating_group_curves.py
"""Dicom dictionary elements for Repeating Group 50xx, dicom versions < 3.0."""

# This is made to resemble the format in _dicom_dictionary.py,
#   but with the element only, since we know the group is
#   an even number between 5000 and 501e.
CurveDictionary = {
0x0005: ('US', '1', "Curve Dimensions"),
0x0010: ('US', '1', "Number of Points"),
0x0020: ('CS', '1', "Type of Data"),
0x0022: ('LO', '1', "Curve Description"),
0x0030: ('SH', '1-n', "Axis Units"),
0x0040: ('SH', '1-n', "Axis Labels"),
0x0103: ('US', '1', "Data Value Representation"),
0x0104: ('US', '1-n', "Minimum Coordinate Value"),
0x0105: ('US', '1-n', "Maximum Coordinate Value"),
0x0106: ('SH', '1-n', "Curve Range"),
0x0110: ('US', '1-n', "Curve Data Descriptor"),
0x0112: ('US', '1', "Coordinate Start Value"),
0x0114: ('US', '1', "Coordinate Step Value"),
0x1001: ('CS', '1', "Curve Activation Layer"),
0x2000: ('US', '1', "Audio Type"),
0x2002: ('US', '1', "Audio Sample Format"),
0x2004: ('US', '1', "Number of Channels"),
0x2006: ('UL', '1', "Number of Samples"),
0x200A: ('UL', '1', "Total Time"),
0x200C: ('OW/OB', '1', "Audio Sample Data"),
0x200E: ('LT', '1', "Audio Comments"),
0x2500: ('LO', '1', "Curve Label"),
0x2600: ('SQ', '1', "Referenced Overlay Sequence"),
0x2610: ('US', '1', "Referenced Overlay Group"),
0x3000: ('OW/OB', '1', "Curve Data")
}
