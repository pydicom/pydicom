# __init__.py for Dicom package
"""pydicom package -- easily handle DICOM files. See Quick Start below.

Copyright (c) 2008 Darcy Mason
This file is part of pydicom, released under a modified MIT license.
   See the file license.txt included with this distribution, also
   available at http://pydicom.googlecode.com

-----------
Quick Start
-----------
1. A simple program to read a dicom file, modify a value, and write to a new file::
    import dicom
    dataset = dicom.read_file("file1.dcm")
    dataset.PatientsName = 'anonymous'
    dataset.save_as("file2.dcm")
    
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

# For convenience, import the read_file and write_file functions (most used)  into the "dicom" namespace.
from filereader import read_file, ReadFile  # latter one for backwards compatibility; remove later
from filewriter import write_file, WriteFile # ditto

__version__ = "0.9.4-1"
__version_info__ = (0,9,4,1)

debugging = False

def debug(debug_on=True):
    global logger, debugging
    if debug_on:
        logger.setLevel(logging.DEBUG)
        debugging = True
    else:
        logger.setLevel(logging.WARNING)
        debugging = False
        
