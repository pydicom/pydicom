# add_dict_entries.py
"""Example script to add dictionary items to the 'standard' DICOM
dictionary dynamically

Not a recommended solution in general, but useful as a demonstration
or for in-house programs only, or to get around elements missing
from pydicom's DICOM dictionaries.

For private items, the proper way would be similar to ones in _private_dict.py,
where a block is reserved etc as specified in the DICOM standards.
"""
from __future__ import print_function

# D. Mason, 2013-01
from pydicom.datadict import DicomDictionary, NameDict, CleanName
from pydicom.dataset import Dataset

# Define items as (VR, VM, description, is_retired flag, keyword)
#   Leave is_retired flag blank.
new_dict_items = {
    0x10011001: ('UL', '1', "Test One", '', 'TestOne'),
    0x10011002: ('OB', '1', "Test Two", '', 'TestTwo'),
    0x10011003: ('UI', '1', "Test Three", '', 'TestThree'),
}

# Update the dictionary itself
DicomDictionary.update(new_dict_items)

# Update the reverse mapping from name to tag
new_names_dict = dict([(CleanName(tag), tag) for tag in
                       new_dict_items])
NameDict.update(new_names_dict)

# Test that it is working
ds = Dataset()  # or could get one from read_file, etc

ds.TestOne = 42
ds.TestTwo = '12345'
ds.TestThree = '1.2.3.4.5'

print(ds.top())
