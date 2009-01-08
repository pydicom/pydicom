# charlist.py
"""List summary infor for the test files in the charset directory"""
#
# Copyright 2008, Darcy Mason
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

import logging
logging.basicConfig(level=logging.INFO,
                    format='%(message)s')

if __name__ == "__main__":
    from glob import glob
    import dicom
    
    # Get list of all DICOM files
    names = glob("*.dcm")
    
    # Collect summary information from the files
    files_info = []
    for name in names:
        ds = dicom.ReadFile(name)
        files_info.append((name, ds.SpecificCharacterSet, ds.PatientsName))
    
    # Show the information
    format = "%-13s %-40s %-r" # r in Python >=2.0, uses repr()
    logging.info(format % ("Filename", "Character Sets", "Patient's Name"))
    logging.info(format % ("--------", "--------------", "--------------"))
    for file_info in files_info:
        logging.info(format % file_info)