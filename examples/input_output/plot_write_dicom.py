"""
================
Write DICOM data
================

This example shows how to write a DICOM file from scratch using pydicom. This
example does not produce a DICOM standards compliant file as written, you will
have to change UIDs to valid values and add all required DICOM data elements.

"""

# authors : Darcy Mason, Guillaume Lemaitre
# license : MIT

import os
import tempfile
import datetime

import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset

# Create a temporary filename
filename = tempfile.NamedTemporaryFile().name

print("Setting file meta information...")
# Populate required values for file meta information
file_meta = FileMetaDataset()
file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
file_meta.MediaStorageSOPInstanceUID = "1.2.3"
file_meta.ImplementationClassUID = "1.2.3.4"

print("Setting dataset values...")
# Create the FileDataset instance (intially no data elements)
ds = FileDataset(filename, {}, file_meta=file_meta)

# Add data elements -- not setting all required here. Check DICOM standard
ds.PatientName = "Test^Firstname"
ds.PatientID = "123456"
now = datetime.datetime.now()
ds.ContentDate = now.strftime("%Y%m%d")
ds.ContentTime = now.strftime("%H%M%S.%f")

# Set the transfer syntax
ds.is_little_endian = True
ds.is_implicit_VR = True

print("Writing test file", filename)
# write_like_original=False ensures proper DICOM format, preamble
ds.save_as(filename, write_like_original=False)
print("File saved.")

# reopen the data just for checking
print("Load file {} ...".format(filename))
ds = pydicom.dcmread(filename)
print(ds)

# remove the created file
print("Remove file {}".format(filename))
os.remove(filename)
