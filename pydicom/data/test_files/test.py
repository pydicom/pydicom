# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Temporary test file for pydicom development; will change over revisions
as test various things
"""

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
                series_name = "Series {0.SeriesNumber}: {0.SeriesDescription} ({1} image{2})".format(series, image_count, plural)  # noqa
                print(series_name)
