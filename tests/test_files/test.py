# test.py
"""Temporary test file for pydicom development; will change over revisions
as test various things
"""
# Copyright (c) 2013 Darcy Mason
# This file is part of pydicom, relased under an MIT-style license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom
#

import pydicom
# pydicom.debug()


if __name__ == "__main__":
    dcmdir = pydicom.read_dicomdir()
    for patrec in dcmdir.patient_records:
        print("Patient: {0.PatientID}: {0.PatientsName}".format(patrec))
        studies = patrec.children
        for study in studies:
            print("    Study {0.StudyID}: {0.StudyDate}:"
                  " {0.StudyDescription}".format(study))
            all_series = study.children
            for series in all_series:
                image_count = len(series.children)
                plural = ('', 's')[image_count > 1]
                print(" " * 8 + "Series {0.SeriesNumber}: {0.SeriesDescription}"
                      " ({1} image{2})".format(series, image_count, plural))
