"""
=====================
Read a DICOM File-set
=====================

This example shows how to read and interact with a DICOM File-set.

"""

from pathlib import Path
from tempfile import TemporaryDirectory
import warnings

from pydicom import dcmread
from pydicom.data import get_testdata_file
from pydicom.fileset import FileSet
from pydicom.uid import generate_uid

warnings.filterwarnings("ignore")

path = get_testdata_file('DICOMDIR')
# A File-set can be loaded from the path to its DICOMDIR dataset or the
#   dataset itself
fs = FileSet(path)  # or fs = FileSet(dcmread(path))

# A summary of the File-set's contents can be seen when printing
print(fs)
print()

# Iterating over the FileSet yields FileInstance objects
for instance in fs:
    # Load the corresponding SOP Instance dataset
    ds = instance.load()
    # Do something with each dataset

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

# We can remove and add instances to the File-set
fs.add(get_testdata_file("CT_small.dcm"))
fs.add(get_testdata_file("MR_small.dcm"))
result = fs.find(StudyDescription="'XR C Spine Comp Min 4 Views'")
fs.remove(result)

# To edit the elements in the DICOMDIR's File-set Identification Module
#   (Part 3, Annex F.3.2.1) use the following properties:
# (0004,1130) File-set ID
fs.ID = "MY FILESET"
# Change the File-set's UID
fs.UID = generate_uid()
# (0004,1141) File-set Descriptor File ID
fs.descriptor_file_id = "README"
# (0004,1142) Specific Character Set of File-set Descriptor File
fs.descriptor_character_set = "ISO_IR 100"

# Changes to the File-set are staged until write() is called
# Calling write() will update the File-set's directory structure to meet the
#   semantics used by pydicom File-sets (if required), add/remove instances and
#   and re-write the DICOMDIR file
# We don't do it here because it would overwrite your example data
# fs.write()

# Alternatively, the File-set can be copied to a new root directory
#   This will apply any staged changes while leaving the original FileSet
#   object unchanged
tdir = TemporaryDirectory()
new_fileset = fs.copy(tdir.name)
print(f"\nOriginal File-set still at {fs.path}")
root = Path(new_fileset.path)
print(f"File-set copied to {root} and contains the following files:")
# Note how the original File-set directory layout has been changed to
#   the structure used by pydicom
for p in sorted(root.glob('**/*')):
    if p.is_file():
        print(f"  {p.relative_to(root)}")
