# test.py
"""Temporary test file for pydicom development; will change over revisions
as test various things
"""
# Copyright (c) 2012 Darcy Mason
# This file is part of pydicom, relased under an MIT-style license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com
#

import dicom
# dicom.debug()

from dicom.valuerep import DS, MultiString
from dicom.multival import MultiValue

# print("\n\nTry creating MultiValue directly")
s = r"1.2000\2.30000"
m = MultiString(s, DS)

# print "m=", m
# print "type(m) = ", type(m)
# print "type(m[0]) = ", type(m[0])
# print "m[0].original_string", m[0].original_string


filename = "rtplan.dcm"
print("\n\nTest reading rtplan.dcm and keeping original string for multival DS")
print("---------")
print("First read a file with DS as default float-derived class")
ds = dicom.read_file(filename)
dr = ds.DoseReferenceSequence[0]
drpc0 = dr.DoseReferencePointCoordinates[0]
print("Value of original_string: ".format(drpc0.original_string))
print("Value of Instance of dose ref pt coord 0: {0:s}".format(str(drpc0)))

print("---------\nChange to DS decimal and read same file again")
import dicom.config
dicom.config.DS_decimal()

ds = dicom.read_file(filename)
dr = ds.DoseReferenceSequence[0]
drpc0 = dr.DoseReferencePointCoordinates[0]
print("Value of Instance of dose ref pt coord 0: {0:s}".format(str(drpc0)))
