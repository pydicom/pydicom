# DicomInfo.py
"""
Read a DICOM file and print some or all of its values.

Usage:  python DicomInfo.py imagefile [-v]

-v (optional): Verbose mode, prints all DICOM data elements

Without the -v option, a few of the most common dicom file
data elements are printed: some info about the patient and about
the image.

"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

from __future__ import print_function

import sys
import dicom

# check command line arguments make sense
if not 1 < len(sys.argv) < 4:
    print(__doc__)
    sys.exit()

# read the file
filename = sys.argv[1]
dataset = dicom.read_file(filename)

# Verbose mode:
if len(sys.argv) == 3:
    if sys.argv[2] == "-v":  # user asked for all info
        print(dataset)
    else:  # unknown command argument
        print(__doc__)
    sys.exit()

# Normal mode:
print()
print("Filename.........:", filename)
print("Storage type.....:", dataset.SOPClassUID)
print()

pat_name = dataset.PatientName
display_name = pat_name.family_name + ", " + pat_name.given_name
print("Patient's name...:", display_name)
print("Patient id.......:", dataset.PatientID)
print("Modality.........:", dataset.Modality)
print("Study Date.......:", dataset.StudyDate)

if 'PixelData' in dataset:
    rows = int(dataset.Rows)
    cols = int(dataset.Columns)
    print("Image size.......: {rows:d} x {cols:d}, {size:d} bytes".format(
        rows=rows, cols=cols, size=len(dataset.PixelData)))
    if 'PixelSpacing' in dataset:
        print("Pixel spacing....:", dataset.PixelSpacing)

# use .get() if not sure the item exists, and want a default value if missing
print("Slice location...:", dataset.get('SliceLocation', "(missing)"))
