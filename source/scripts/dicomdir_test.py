# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Temporary test file for pydicom development; will change over revisions
as test various things
"""

from pydicom import dcmread
from pydicom.data import get_testdata_files
# pydicom.debug()


if __name__ == "__main__":
    testfiles = get_testdata_files('DICOMDIR')
    dcmdir = dcmread(testfiles[0])
    for patrec in dcmdir.patient_records:
        print("Patient: {0.PatientID}: {0.PatientName}".format(patrec))
        studies = patrec.children
        for study in studies:
            print(
                "    Study {0.StudyID}: {0.StudyDate}:"
                " {0.StudyDescription}".format(study)
            )
            all_series = study.children
            for series in all_series:
                image_count = len(series.children)
                plural = ('', 's')[image_count > 1]
                series_desc = getattr(series, 'SeriesDescription', '(none)')
                series_name = (
                    "Series {0.SeriesNumber}: {3} ({1} image{2})"
                    .format(series, image_count, plural, series_desc)
                )
                print(series_name)
