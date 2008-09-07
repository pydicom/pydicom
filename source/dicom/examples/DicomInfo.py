# DicomInfo.py
"""
Read a dicom file and print some or all of its values.

Usage:  python DicomInfo.py imagefile [-v]

-v (optional): Verbose mode, prints all dicom attributes

Without the -v option, a few of the most common dicom file
attributes are printed: some info about the patient and about
the image.

"""

import sys
from dicom.filereader import ReadFile
from dicom.UIDs import SOP_name

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
print "Storage type.....:", SOP_name(dataset.SOPClassUID)
print

pat_name = dataset.PatientsName.split("^")
display_name = ", ".join(pat_name[:2])
print "Patient name.....:", display_name
print "Patient id.......:", dataset.PatientsID
print "Modality.........:", dataset.Modality
print "Study Date.......:", dataset.StudyDate

# use either:
#     'name' in dataset
# or
#     hasattr(dataset, 'name')
# to check if an attribute exists
if 'PixelData' in dataset:
    print "Image size.......: %i x %i, %i bytes" % (dataset.Rows, dataset.Columns, len(dataset.PixelData))
    if hasattr(dataset, 'PixelSpacing'):
        print "Pixel spacing....:", dataset.PixelSpacing

# use .get() if not sure the item exists, and want a default value if missing
print "Slice location...:", dataset.get('SliceLocation', "(missing)")
