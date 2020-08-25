"""
=====================
Read a DICOM File-set
=====================

This example shows how to read a DICOM File-set.

"""

import os
from pathlib import Path

from pydicom import dcmread
from pydicom.data import get_testdata_file
from pydicom.dicomdir import FileSet

path = get_testdata_file('DICOMDIR')
ds = dcmread(path)
# Load an existing DICOM File-set using its DICOMDIR dataset
fs = FileSet(ds)
print(f'Root directory: {fs.path}\n')

# Find available patients
patients = fs.find_values("PatientID")
for patient_id in patients:
    # Returns a list of FileInstance, where each one represents an available
    #   SOP Instance with a matching *Patient ID*
    result = fs.find(PatientID=patient_id)
    print(
        f"PatientName={result[0].PatientName}, "
        f"PatientID={result[0].PatientID}"
    )

    # Search available studies
    study_uids = fs.find_values("StudyInstanceUID", instances=result)
    for study_uid in study_uids:
        result = fs.find(PatientID=patient_id, StudyInstanceUID=study_uid)
        print(
            f"  StudyDescription='{result[0].StudyDescription}', "
            f"StudyDate={result[0].StudyDate}"
        )

        # Search available series
        series_uids = fs.find_values("SeriesInstanceUID", instances=result)
        for series_uid in series_uids:
            result = fs.find(
                PatientID=patient_id,
                StudyInstanceUID=study_uid,
                SeriesInstanceUID=series_uid
            )
            plural = ['', 's'][len(result) > 1]

            print(
                f"    Modality={result[0].Modality} - "
                f"{len(result)} SOP Instance{plural}"
            )

# Of course you can just get the instances directly if you know what you want
series_uid = "1.3.6.1.4.1.5962.1.1.0.0.0.1196533885.18148.0.118"
for instance in fs.find(SeriesInstanceUID=series_uid):
    print(f"Reading SOP instance at {instance.path}")
    ds = instance.load()

# We can search the actual stored SOP Instances by using `load_instances=True`
# This can be useful as the DICOMDIR's directory records only contain a
#   limited subset of the available elements, however its less efficient
result = fs.find(
    SeriesDescription="ANGIO Projected from   C", load_instances=True
)
for instance in result:
    ds = instance.load()
