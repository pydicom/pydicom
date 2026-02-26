"""
=======================================
Analyse differences between DICOM files
=======================================

This examples illustrates how to find the differences between two DICOM files.

"""

# authors : Guillaume Lemaitre <g.lemaitre58@gmail.com>
# license : MIT

import difflib

from pydicom import examples

print(__doc__)

# difflib compare functions require a list of lines, each terminated with
# newline character massage the string representation of each dicom dataset
# into this form:
rep = [
    [f"{line}\n" for line in str(ds).split("\n")]
    for ds in (examples.mr, examples.ct)
]


diff = difflib.Differ()
for line in diff.compare(rep[0], rep[1]):
    if line[0] != "?":
        print(line)
