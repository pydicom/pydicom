"""
=========================================
Add items to the private DICOM dictionary
=========================================

This examples illustrates how to add private dictionary items to the DICOM
dictionary dynamically. This allows you to read private tags not present in
pydicom's private dictionary when loading an existing dataset.
"""

# authors : Darcy Mason and pydicom contributors
# license : MIT

import io

from pydicom import dcmread
from pydicom.datadict import add_private_dict_entries
from pydicom.dataset import Dataset
from pydicom.valuerep import VR

print(__doc__)

# create a dataset with some private tags for demonstration
# we create the dataset with Implicit VR Little Endian transfer syntax,
# so that the VR of the private tags will not be saved

ds = Dataset()
ds.is_implicit_VR = True
ds.is_little_endian = True

# add private tags by creating a new private block and add elements to it
block = ds.private_block(0x1001, "ACME 3.1", create=True)
block.add_new(0x01, VR.UL, 42)
block.add_new(0x02, VR.SH, "Hello World")
block.add_new(0x03, VR.UI, "1.2.3.4.5")

# write the dataset into a memory file and read it back
# this simulates reading from a normal DICOM file
fp = io.BytesIO()
ds.save_as(fp)
ds = dcmread(fp, force=True)

print("Output for unknown private tags:")
print(ds)

# Creates output:
# (1001,0010) Private Creator                     LO: 'ACME 3.1'
# (1001,1001) Private tag data                    UN: b'*\x00\x00\x00'
# (1001,1002) Private tag data                    UN: b'Hello World '
# (1001,1003) Private tag data                    UN: b'1.2.3.4.5\x00'


# Add the private tags to the private tag dictionary

# Define items as (VR, VM, description, is_retired flag)
# Leave is_retired flag blank.
new_dict_items = {
    0x10011001: ("UL", "1", "Test One", ""),
    0x10011002: ("SH", "1", "Test Two", ""),
    0x10011003: ("UI", "1", "Test Three", ""),
}

# add the entries to the private dictionary, using the correct private creator string
add_private_dict_entries(private_creator="ACME 3.1", new_entries_dict=new_dict_items)

# re-read the dataset for the new dictionary entries to be applied
ds = dcmread(fp, force=True)

print("\nOutput with registered private tags:")
print(ds)

# Creates output:
# (1001,0010) Private Creator                     LO: 'ACME 3.1'
# (1001,1001) [Test One]                          UL: 42
# (1001,1002) [Test Two]                          SH: 'Hello World'
# (1001,1003) [Test Three]                        UI: 1.2.3.4.5
