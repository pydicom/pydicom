# anonymize.py
"""Read a dicom file, "anonymize" it, (replace Person names, patient id,
optionally remove curves and private tags,
and write result to a new file"""
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
python anonymize.py dicomfile.dcm outputfile.dcm
"""

# Use at your own risk!!
# Note that pixel data could have patient data "burned in" - this is not addressed here

import os, os.path

def anonymize(filename, output_filename, PersonName="anonymous",
              PatientsID="id", RemoveCurves=1, RemovePrivate=1):
    """Replace attributes with VR="PN" with PersonName etc."""
    def PN_callback(ds, attr):
        """Called from the dataset "walk" recursive function for all attributes."""
        if attr.VR == "PN":
            attr.value = PersonName
    def curves_callback(ds, attr):
        """Called from the dataset "walk" recursive function for all attributes."""
        if attr.tag.group & 0xFF00 == 0x5000:
            del ds[attr.tag]
        
    from dicom.filereader import ReadFile
    from dicom.filewriter import WriteFile    

    dataset = ReadFile(filename)
    dataset.walk(PN_callback)
    dataset.PatientsID = PatientsID
    if RemovePrivate:
        dataset.RemovePrivateTags()
    if RemoveCurves:
        dataset.walk(curves_callback)
    WriteFile(output_filename, dataset)
    
    

# Can run as a script:
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print usage
        sys.exit()

    # if a source directory is given, go through all files in directory.
    arg1, arg2 = sys.argv[1:]
    if os.path.isdir(arg1):
        filenames = os.listdir(arg1)
    if not os.path.exists(arg2):
        os.makedirs(arg2)
    for filename in filenames:
        if not os.path.isdir(os.path.join(arg1, filename)):
            print filename + "...",
            anonymize(os.path.join(arg1, filename), os.path.join(arg2, filename))
            print "done\r",
    else:
        anonymize(arg1, sys.argv[2])
    
    print
    