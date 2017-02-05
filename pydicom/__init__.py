# __init__.py for Dicom package
"""pydicom package -- easily handle DICOM files. See Quick Start below.

Copyright (c) 2008-2014 Darcy Mason
This file is part of pydicom, released under a modified MIT license.
   See the file license.txt included with this distribution, also
   available at https://github.com/darcymason/pydicom

-----------
Quick Start
-----------
1. A simple program to read a dicom file, modify a value, and write to a new file::
    from pydicom import dicomio
    dataset = dicomio.read_file("file1.dcm")
    dataset.PatientName = 'anonymous'
    dataset.save_as("file2.dcm")

2. See the files in the examples directory that came with this package for more
examples, including some interactive sessions.

3. Learn the methods of the Dataset class; that is the one you will
work with most directly.

4. Questions and comments can be directed to the pydicom google group:
http://groups.google.com/group/pydicom

5. Bugs and other issues can be reported in the issue tracker:
https://github.com/darcymason/pydicom/issues
"""

import sys
if sys.version_info < (2, 6, 0):
    raise ImportError("pydicom > 0.9.7 requires python 2.6 or later")



# pre-pydicom 1.0, read_file and write_file were imported here.
# Continue to do so, but with deprecation warning
def read_file(*args, **kwargs):
    global read_file
    from pydicom.dicomio import read_file
    return read_file(*args, **kwargs)

def write_file(*args, **kwargs):
    global write_file
    from pydicom.dicomio import write_file
    return write_file(*args, **kwargs)

__version__ = "1.0.0a1"
__version_info__ = (1, 0, 0, 'alpha', 0)
