# __init__.py for Dicom package
"""pydicom package -- easily handle DICOM files. See Quick Start below.

Copyright 2004, Darcy Mason
This file is part of pydicom.

pydicom is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

pydicom is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License (license.txt) for more details

-----------
Quick Start
-----------
1. Get and install Python (www.python.org). If you are on Windows, try the
(free) ActivePython distribution (www.activestate.com/Products/ActivePython).

2. Here is a very simple program to read a dicom file, modify a value, and
write the result to a new dicom file::
    import dicom
    dataset = dicom.ReadFile("file1.dcm")
    dataset.PatientsName = 'anonymous'
    dicom.WriteFile("file2.dcm", dataset)
    
3. See the files in the examples directory that came with this package,
in particular the capture of an interactive session.

4. Learn the methods of the Dataset class; that is the one you will
work with most directly.
"""
#

# For convenience, import the most common classes and functions into "dicom" namespace.
#   Thus can use
#        import dicom
#        dicom.ReadFile("a.dcm")

from filereader import ReadFile
from filewriter import WriteFile
#from dataset import Dataset
#from attribute import Attribute
#from tag import Tag