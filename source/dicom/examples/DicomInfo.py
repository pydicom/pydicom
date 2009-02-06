# DicomInfo.py
"""
Read a DICOM file and print some or all of its values.

Usage:  python DicomInfo.py imagefile [-v]

-v (optional): Verbose mode, prints all DICOM data elements

Without the -v option, a few of the most common dicom file
data elements are printed: some info about the patient and about
the image.

"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import sys
from dicom.filereader import ReadFile

# check command line arguments make sense
if not 1 < len(sys.argv) < 4:
    print __doc__
    sys.exit()

# read the file
filename = sys.argv[1]
dataset = ReadFile(filename)

# Verbose mode:
if len(sys.argv) == 3:
    if sys.argv[2]=="-v": #user asked for all info
        print dataset
    else: # unknown command argument
        print __doc__
    sys.exit()

# Normal mode:
print
print "Filename.........:", filename
print "Storage type.....:", dataset.SOPClassUID
print

pat_name = dataset.PatientsName.split("^")
display_name = ", ".join(pat_name[:2])
print "Patient's name...:", display_name
print "Patient id.......:", dataset.PatientID
print "Modality.........:", dataset.Modality
print "Study Date.......:", dataset.StudyDate

# use either:
#     'name' in dataset
# or
#     hasattr(dataset, 'name')
# to check if a data element exists
if 'PixelData' in dataset:
    print "Image size.......: %i x %i, %i bytes" % (dataset.Rows, dataset.Columns, len(dataset.PixelData))
    if hasattr(dataset, 'PixelSpacing'):
        print "Pixel spacing....:", dataset.PixelSpacing

# use .get() if not sure the item exists, and want a default value if missing
print "Slice location...:", dataset.get('SliceLocation', "(missing)")
