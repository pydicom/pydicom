# Copyright pydicom authors 2019. See LICENSE file for details
"""
======================================
Show working with memory-based dataset
======================================

Show how to write a DICOM dataset into a byte array and to read
it back from a byte array. This can be helpful for example if working with
datasets saved as blobs in a database.

"""


from io import BytesIO

from pydicom import dcmread, dcmwrite
from pydicom.filebase import DicomFileLike

print(__doc__)

usage = "Usage: python memory_dataset.py dicom_filename"


def write_dataset_to_bytes(dataset):
    # create a buffer
    with BytesIO() as buffer:
        # create a DicomFileLike object that has some properties of DataSet
        memory_dataset = DicomFileLike(buffer)
        # write the dataset to the DicomFileLike object
        dcmwrite(memory_dataset, dataset)
        # to read from the object, you have to rewind it
        memory_dataset.seek(0)
        # read the contents as bytes
        return memory_dataset.read()


def adapt_dataset_from_bytes(blob):
    # you can just read the dataset from the byte array
    dataset = dcmread(BytesIO(blob))
    # do some interesting stuff
    dataset.is_little_endian = False
    dataset.PatientName = 'Bond^James'
    dataset.PatientID = '007'
    return dataset


class DummyDataBase:
    def __init__(self):
        self._blobs = {}

    def save(self, name, blob):
        self._blobs[name] = blob

    def load(self, name):
        return self._blobs.get(name)


if __name__ == '__main__':
    import sys

    if len(sys.argv) != 2:
        print("Please supply a dicom file name:\n")
        print(usage)
        sys.exit(-1)
    file_path = sys.argv[1]
    db = DummyDataBase()

    # Convert a dataset to a byte array:
    # - read the dataset from a file
    dataset = dcmread(file_path)
    print(dataset)
    # - convert the dataset to bytes
    ds_bytes = write_dataset_to_bytes(dataset)
    # - save the bytes in some storage
    db.save('dataset', ds_bytes)

    # Convert a byte array to a dataset:
    # - get the bytes from storage
    read_bytes = db.load('dataset')
    # - convert the bytes into a dataset and do something interesting with it
    read_dataset = adapt_dataset_from_bytes(read_bytes)
    print(read_dataset)
    # - you can write your dataset to a file if wanted
    dcmwrite(file_path + '_new', read_dataset)
