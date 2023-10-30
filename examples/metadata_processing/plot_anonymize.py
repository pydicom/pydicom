"""
====================
Anonymize DICOM data
====================

This example is a starting point to anonymize DICOM data.

It shows how to read data and replace tags: person names, patient ID,
optionally remove curves and private tags, and write the results in a new file.

"""

###############################################################################
# Anonymize a single file
###############################################################################

# authors : Darcy Mason
#           Guillaume Lemaitre <g.lemaitre58@gmail.com>
# license : MIT

import tempfile

from pydicom import examples

ds = examples.mr

for keyword in ["PatientID", "PatientBirthDate"]:
    print(ds.data_element(keyword))

###############################################################################
# We can define a callback function to find all tags corresponding to a person
# names inside the dataset. We can also define a callback function to remove
# curves tags.


def person_names_callback(ds, elem):
    if elem.VR == "PN":
        elem.value = "anonymous"


def curves_callback(ds, elem):
    if elem.tag.group & 0xFF00 == 0x5000:
        del ds[elem.tag]


###############################################################################
# We can use the different callback function to iterate through the dataset but
# also some other tags such that patient ID, etc.

ds.PatientID = "id"
ds.walk(person_names_callback)
ds.walk(curves_callback)

###############################################################################
# pydicom allows to remove private tags using ``remove_private_tags`` method

ds.remove_private_tags()

###############################################################################
# Data elements of type 3 (optional) can be easily deleted using ``del`` or
# ``delattr``.

if "OtherPatientIDs" in ds:
    delattr(ds, "OtherPatientIDs")

if "OtherPatientIDsSequence" in ds:
    del ds.OtherPatientIDsSequence

###############################################################################
# For data elements of type 2, this is possible to blank it by assigning a
# blank string.

tag = "PatientBirthDate"
if tag in ds:
    ds.data_element(tag).value = "19000101"

##############################################################################
# Finally, this is possible to store the image

for keyword in ["PatientID", "PatientBirthDate"]:
    print(ds.data_element(keyword))

path = tempfile.NamedTemporaryFile().name
ds.save_as(path)
