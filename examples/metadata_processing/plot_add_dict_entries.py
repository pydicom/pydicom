"""
=============================================================
Add private dictionary items to the standard DICOM dictionary
=============================================================

This examples illustrates how to add private dictionary items to the DICOM
dictionary dynamically. This allows to add unknown private tags to a new dataset,
or reading private tags from an existing dataset not present in the pydicom
private dictionary.
"""

# authors : Darcy Mason and pydicom contributors
# license : MIT


from pydicom.datadict import add_private_dict_entries
from pydicom.dataset import Dataset

print(__doc__)

# Define items as (VR, VM, description, is_retired flag)
# Leave is_retired flag blank.
new_dict_items = {
    0x10011001: ("UL", "1", "Test One", ""),
    0x10011002: ("OB", "1", "Test Two", ""),
    0x10011003: ("UI", "1", "Test Three", ""),
}

# add the entries to the private dictionary, using the correct private creator string
add_private_dict_entries(private_creator="ACME 3.1", new_entries_dict=new_dict_items)

# Test that it is working
ds = Dataset()

ds.TestOne = 42
ds.TestTwo = "12345"
ds.TestThree = "1.2.3.4.5"

print(ds.top())
