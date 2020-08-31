"""
=====================
Read a DICOM File-set
=====================

This example shows how to read and interact with a DICOM File-set.

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

# A summary of the File-set's contents can be seen when printing
print(fs)
print()

# Iterating over the FileSet yields FileInstance objects
for instance in fs:
    # Load the corresponding SOP Instance dataset
    ds = instance.load()
    break

# You can also access the File-set's Patient > Study > Series > Instance
#   hierarchy (assuming it contains suitable SOP Instances)
tree = fs.as_tree()
for patient_id in tree:
    for study_uid in tree[patient_id]:
        for series_uid in tree[patient_id][study_uid]:
            for instance in tree[patient_id][study_uid][series_uid]:
                ds = instance.load()
                break

# We can search the File-set
patient_ids = fs.find_values("PatientID")
for patient_id in patient_ids:
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
result = fs.find(SeriesInstanceUID=series_uid)
print(f"\nFound {len(result)} instances for SeriesInstanceUID={series_uid}")

# We can search the actual stored SOP Instances by using `load=True`
# This can be useful as the DICOMDIR's directory records only contain a
#   limited subset of the available elements, however its less efficient
result = fs.find(load=False, PhotometricInterpretation="MONOCHROME1")
result_load = fs.find(load=True, PhotometricInterpretation="MONOCHROME1")
print(
    f"Found {len(result)} instances with "
    f"PhotometricInterpretation='MONOCHROME1' without loading the stored "
    f"instances and {len(result_load)} instances with loading"
)
