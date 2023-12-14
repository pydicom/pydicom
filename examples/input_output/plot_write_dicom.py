"""
================
Write DICOM data
================

This example shows how to write a DICOM file from scratch using pydicom. This
example does not produce a DICOM standards compliant file as written, you will
have to change UIDs to valid values and add all required DICOM data elements.

"""

# authors : Darcy Mason, Guillaume Lemaitre <g.lemaitre58@gmail.com>
# license : MIT

import datetime
from pathlib import Path
import tempfile

import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import UID, ExplicitVRLittleEndian


print("Setting dataset values...")
ds = Dataset()
ds.PatientName = "Test^Firstname"
ds.PatientID = "123456"
# Set creation date/time
dt = datetime.datetime.now()
ds.ContentDate = dt.strftime("%Y%m%d")
ds.ContentTime = dt.strftime("%H%M%S.%f")  # long format with micro seconds

print("Setting file meta information...")
# Populate required values for file meta information
file_meta = FileMetaDataset()
file_meta.MediaStorageSOPClassUID = UID("1.2.840.10008.5.1.4.1.1.2")
file_meta.MediaStorageSOPInstanceUID = UID("1.2.3")
file_meta.ImplementationClassUID = UID("1.2.3.4")
file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

# Add the file meta information
ds.file_meta = file_meta

path = Path(tempfile.NamedTemporaryFile(suffix=".dcm").name)
print(f"Writing dataset to: {path}")
ds.save_as(path, enforce_file_format=True)

# reopen the data just for checking
print(f"Load dataset from: {path} ...")
ds = pydicom.dcmread(path)
print(ds)

# remove the created file
print(f"Deleting file: {path} ...")
path.unlink()
