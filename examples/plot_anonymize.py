"""
====================
Anonymize DICOM data
====================

This example is starting point to anonymize DICOM data.

It shows how to read data and replace tags: person names, patient id,
optionally remove curves and private tags, and write the results in a new file.

"""

# authors : Guillaume Lemaitre <g.lemaitre58@gmail.com>
# license : MIT

from __future__ import print_function

import tempfile

import pydicom
from pydicom.data import get_testdata_files

print(__doc__)

###############################################################################
# Anonymize a single file
###############################################################################

filename = get_testdata_files('MR_small.dcm')[0]
dataset = pydicom.read_file(filename)

data_elements = ['PatientID',
                 'PatientBirthDate']
for de in data_elements:
    print(dataset.data_element(de))

###############################################################################
# We can define a callback function to find all tags corresponding to a person
# names inside the dataset. We can also define a callback function to remove
# curves tags.


def person_names_callback(dataset, data_element):
    if data_element.VR == "PN":
        data_element.value = "anonymous"


def curves_callback(dataset, data_element):
    if data_element.tag.group & 0xFF00 == 0x5000:
        del dataset[data_element.tag]


###############################################################################
# We can use the different callback function to iterate through the dataset but
# also some other tags such that patient ID, etc.

dataset.PatientID = "id"
dataset.walk(person_names_callback)
dataset.walk(curves_callback)

###############################################################################
# pydicom allows to remove private tags using ``remove_private_tags`` method

dataset.remove_private_tags()

###############################################################################
# Data elements of type 3 (optional) can be easily deleted using ``del`` or
# ``delattr``.

if 'OtherPatientIDs' in dataset:
    delattr(dataset, 'OtherPatientIDs')

if 'OtherPatientIDsSequence' in dataset:
    del dataset.OtherPatientIDsSequence

###############################################################################
# For data elements of type 2, this is possible to blank it by assigning a
# blank string.

tag = 'PatientBirthDate'
if tag in dataset:
    dataset.data_element(tag).value = '01011900'

##############################################################################
# Finally, this is possible to store the image

data_elements = ['PatientID',
                 'PatientBirthDate']
for de in data_elements:
    print(dataset.data_element(de))

output_filename = tempfile.NamedTemporaryFile().name
dataset.save_as(output_filename)

###############################################################################
# Anonymize several files from a directory
###############################################################################

###############################################################################
# This is possible to make the processing for a full directory
