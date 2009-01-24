# __init__.py for Dicom package
"""pydicom package -- easily handle DICOM files. See Quick Start below.

Copyright 2004, 2008, Darcy Mason
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
1. A simple program to read a dicom file, modify a value, and write to a new file::
    import dicom
    dataset = dicom.ReadFile("file1.dcm")
    dataset.PatientsName = 'anonymous'
    dataset.SaveAs("file2.dcm")
    
2. See the files in the examples directory that came with this package for more
examples, including some interactive sessions.

3. Learn the methods of the Dataset class; that is the one you will
work with most directly.

4. Questions/comments etc can be directed to the pydicom google group at
http://groups.google.com/group/pydicom
"""
# Set up logging system for the whole package. 
# In each module, set logger=logging.getLogger('pydicom')  and the same instance will be used by all
# At command line, turn on debugging for all pydicom functions with:
#        import dicom
#        dicom.debug()
#  Turn off debugging with
#       dicom.debug(False)
import logging
logger = logging.getLogger('pydicom')
handler = logging.StreamHandler()
# formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s", "%Y-%m-%d %H:%M") #'%(asctime)s %(levelname)s %(message)s'
formatter = logging.Formatter("%(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# For convenience, import the ReadFile and write_file functions (most used)  into the "dicom" namespace.
from filereader import read_file, ReadFile  # latter one for backwards compatibility; remove later
from filewriter import write_file, write_file # ditto

def debug(DebugOn=True):
    global logger
    if DebugOn:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)
        