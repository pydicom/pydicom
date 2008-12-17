# anonymize.py
"""Read a dicom file (or directory of files), partially "anonymize" it (them), 
    by replacing Person names, patient id, optionally remove curves 
    and private tags, and write result to a new file (directory)
    This is an example only; use only as a starting point."""
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
OR
python anonymize.py originalsdirectory anonymizeddirectory
"""

# Use at your own risk!!
# Many more items need to be addressed for proper anonymizing
# In particular, note that pixel data could have confidential data "burned in"

import os, os.path

def anonymize(filename, output_filename, PersonName="anonymous",
              PatientID="id", RemoveCurves=True, RemovePrivate=True):
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
    dataset.PatientID = PatientID
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
    arg1, arg2 = sys.argv[1:]

    if os.path.isdir(arg1):
        in_dir = arg1
        out_dir = arg2
        if os.path.exists(out_dir):
            if not os.path.isdir(out_dir):
                raise IOError, "Input is directory; output name exists but is not a directory"
        else: # out_dir does not exist; create it.
            os.makedirs(out_dir)

        filenames = os.listdir(in_dir)
        for filename in filenames:
            if not os.path.isdir(os.path.join(in_dir, filename)):
                print filename + "...",
                anonymize(os.path.join(in_dir, filename), os.path.join(out_dir, filename))
                print "done\r",
    else: # first arg not a directory, assume two files given
        in_filename = arg1
        out_filename = arg2
        anonymize(in_filename, out_filename)
    print
    