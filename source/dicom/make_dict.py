# make_dict.py
"""Reformat a dicom dictionary file to Python syntax"""
#
# Copyright 2004, Darcy Mason
# This file is part of pydicom.
#
# pydicom is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# pydicom is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License (license.txt) for more details 

# Create a file to associate dicom tags with descriptive info

# Read from DICOM-dict.txt found at www.openhealth.org/ASTM
#    CHANGES:
#      -(modified (0018,6011) in that file to put "Sequence" at end of string)
#      -removed "(formerly Image)" from Content Date and others like it
# and converted to Python dictionary syntax
# This should only ever need to be run once, (and has already been)
#     unless a new Dicom-dict.txt becomes available

dict_filename = "_dicom_dictionary.py"

import re
pattern = p=r'\((?P<grp>\w*),(?P<elem>\w*)\).*VR=\"(?P<vr>.*?)\".*VM=\"(?P<vm>.*?)\"'
pattern += r'.*NAME=\"(?P<name>.*?)\"'
compile = re.compile(pattern, re.I)

fp = file("DICOM-dict.txt", 'rt')
lines = fp.readlines()
fp.close()

outlines = []
for line in lines:
    match = compile.search(line)
    # don't store the 0x..xx groups - want to read a real number
    if "x" not in match.group('grp') and "x" not in match.group('elem'):
        outlines.append("""0x%s%s: ('%s', '%s', "%s")""" % match.groups())

fp = file(dict_filename, 'wt')

fp.write("# %s\n# Created by make_dict.py program\n" % dict_filename)
fp.write("\n")
fp.write("DicomDictionary = {\n")

fp.write(",\n".join(outlines))
fp.write("}")
fp.close()
         
print "Finished creating python file containing the dicom dictionary"

