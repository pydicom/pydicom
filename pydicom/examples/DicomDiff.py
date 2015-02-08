# DicomDiff.py
"""Show the difference between two dicom files.
"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

from __future__ import print_function

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
import pydicom
import difflib

# only used as a script
if len(sys.argv) != 3:
    print(usage)
    sys.exit()

datasets = (pydicom.read_file(sys.argv[1], force=True),
            pydicom.read_file(sys.argv[2], force=True))

# diflib compare functions require a list of lines, each terminated with newline character
# massage the string representation of each dicom dataset into this form:
rep = []
for dataset in datasets:
    lines = str(dataset).split("\n")
    lines = [line + "\n" for line in lines]  # add the newline to end
    rep.append(lines)


diff = difflib.Differ()
for line in diff.compare(rep[0], rep[1]):
    if line[0] != "?":
        print(line)
