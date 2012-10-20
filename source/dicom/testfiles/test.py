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
print("\n\nTest using both DS as float (default) and switching to Decimal")
print("---------")
print("First read a file with DS as default float-derived class")
ds = dicom.read_file("CT_small.dcm")
print("Instance type of ds.SliceThickness: {0:s}".format(type(ds.SliceThickness)))

print("---------\nChange to DS decimal and read same file again")

import dicom.config
dicom.config.DS_decimal()

ds = dicom.read_file("CT_small.dcm")
print("Instance type of ds.SliceThickness: {0:s}".format(type(ds.SliceThickness)))