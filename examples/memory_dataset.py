# Copyright pydicom authors 2019. See LICENSE file for details
"""
======================================
Show working with memory-based dataset
======================================

Show how to write a DICOM dataset into a byte array and to read
it back from a byte array. This can be helpful for example if working with
datasets saved as blobs in a database.

"""

from __future__ import print_function

from pydicom import dcmread, dcmwrite
from pydicom.filebase import DicomFileLike

print(__doc__)

usage = "Usage: python memory_dataset.py dicom_filename"

from io import BytesIO


def write_dataset_to_bytes(filepath):
    # read the dataset from a file
    dataset = dcmread(filepath)
    # create a buffer
    with BytesIO() as buffer:
        # create a DicomLike object that has some properties of DataSet
        memory_dataset = DicomFileLike(buffer)
        # write the dataset to the DicomLike object
        dcmwrite(memory_dataset, dataset)
        # to read from the object, you have to rewind it
        memory_dataset.seek(0)
        # read the contents as bytes
        return memory_dataset.read()


def read_dataset_from_bytes(blob):
    # you can just read the dataset from the byte array
    return dcmread(BytesIO(blob))


if __name__ == '__main__':
    import sys

    if len(sys.argv) != 2:
        print("Please supply a dicom file name:\n")
        print(usage)
        sys.exit(-1)
    ds_bytes = write_dataset_to_bytes(sys.argv[1])
    print(ds_bytes)
    ds = read_dataset_from_bytes(ds_bytes)
    print(ds)
