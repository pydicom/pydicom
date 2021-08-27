# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""List summary info for the test files in the charset directory"""

import logging
import os

import pydicom
from pydicom.data import get_charset_files


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger('charlist')

    # Get list of all DICOM files
    names = get_charset_files("*.dcm")

    # Collect summary information from the files
    files_info = []
    for name in names:
        ds = pydicom.dcmread(name)
        ds.decode()
        fname = os.path.basename(name)
        try:
            files_info.append((fname, ds.SpecificCharacterSet, ds.PatientName))
        except Exception:
            try:
                requested_seq = ds.RequestedProcedureCodeSequence[0]
                spec_charset = requested_seq.SpecificCharacterSet
                patient_name = requested_seq.PatientName
                files_info.append((fname,
                                   spec_charset,
                                   patient_name))
            except Exception:
                logger.warning("Trouble reading file %s", name)

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
