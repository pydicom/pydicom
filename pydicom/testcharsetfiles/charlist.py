# charlist.py
"""List summary info for the test files in the charset directory"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

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
        ds = dicom.read_file(name)
        ds.decode()
        files_info.append((name, ds.SpecificCharacterSet, ds.PatientsName))

    # Show the information
    format = "%-16s %-40s %s"
    logging.info(format % ("Filename", "Character Sets", "Patient's Name"))
    logging.info(format % ("--------", "--------------", "--------------"))
    for file_info in files_info:
        logging.info(format % file_info)

    if "chrFrenMulti.dcm" in names:
        logging.info("\nOther\n=====")
        logging.info(
            "chrFrenMulti.dcm is a modified version of chrFren.dcm"
            " with multi-valued PN and LO for testing decoding"
        )
