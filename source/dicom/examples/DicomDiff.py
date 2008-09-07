# DicomDiff.py
"""Show the difference between two dicom files.
"""
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

usage = """
Usage:
python DicomDiff.py file1 file2

Results printed in python difflib form - indicated by start of each line:
' ' blank means lines the same
'-' means in file1 but "removed" in file2
'+' means not in file1, but "added" in file2
('?' lines from difflib removed - no use here)
"""


import sys


# only used as a script
if len(sys.argv) != 3:
    print usage
    sys.exit()

from dicom.filereader import ReadFile
datasets = ReadFile(sys.argv[1]), \
           ReadFile(sys.argv[2])

# diflib compare functions require a list of lines, each terminated with newline character
# massage the string representation of each dicom dataset into this form:
rep = []
for dataset in datasets:
    lines = str(dataset).split("\n")
    lines = [line + "\n" for line in lines]  # add the newline to end
    rep.append(lines)

import difflib
diff = difflib.Differ()
for line in diff.compare(rep[0], rep[1]):
    if line[0] != "?":
        print line



    
