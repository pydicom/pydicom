# datadict.py
# -*- coding: utf-8 -*-
"""Access dicom dictionary information"""

# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom
#

from pydicom.config import logger
from pydicom.tag import Tag
from pydicom._dicom_dict import DicomDictionary  # the actual dict of {tag: (VR, VM, name, is_retired, keyword), ...}
from pydicom._dicom_dict import RepeatersDictionary  # those with tags like "(50xx, 0005)"
from pydicom._private_dict import private_dictionaries
import warnings
from pydicom.compat import in_py2

# Generate mask dict for checking repeating groups etc.
# Map a true bitwise mask to the DICOM mask with "x"'s in it.
masks = {}
for mask_x in RepeatersDictionary:
    # mask1 is XOR'd to see that all non-"x" bits are identical (XOR result = 0 if bits same)
    #      then AND those out with 0 bits at the "x" ("we don't care") location using mask2
    mask1 = int(mask_x.replace("x", "0"), 16)
    mask2 = int("".join(["F0"[c == "x"] for c in mask_x]), 16)
    masks[mask_x] = (mask1, mask2)

    
def mask_match(tag):
    for mask_x, (mask1, mask2) in masks.items():
        if (tag ^ mask1) & mask2 == 0:
            return mask_x
    return None


def get_entry(tag):
    """Return the tuple (VR, VM, name, is_retired, keyword) from the DICOM dictionary

    If the entry is not in the main dictionary, check the masked ones,
    e.g. repeating groups like 50xx, etc.
    """
    # Note: tried the lookup with 'if tag in DicomDictionary' 
    #    and with DicomDictionary.get, instead of try/except
    #    Try/except was fastest using timeit if tag is valid (usual case)
    #    My test had 5.2 usec vs 8.2 for 'contains' test, vs 5.32 for dict.get
    tag = Tag(tag)
    try:
        return DicomDictionary[tag]
    except KeyError:
        mask_x = mask_match(tag)
        if mask_x:
            return RepeatersDictionary[mask_x]
        else:
            raise KeyError("Tag {0} not found in DICOM dictionary".format(tag))


def dictionary_VR(tag):
    """Return the dicom value representation for the given dicom tag."""
    return get_entry(tag)[0]


def dictionary_VM(tag):
    """Return the dicom value multiplicity for the given dicom tag."""
    return get_entry(tag)[1]


def dictionary_description(tag):
    """Return the descriptive text for the given dicom tag."""
    return get_entry(tag)[2]


def dictionary_keyword(tag):
    """Return the official DICOM standard (since 2011) keyword for the tag"""
    return get_entry(tag)[4]


def dictionary_has_tag(tag):
    """Return True if the dicom dictionary has an entry for the given tag."""
    return (tag in DicomDictionary)


def keyword_for_tag(tag):
    """Return the DICOM keyword for the given tag. 

    Will return GroupLength for group length tags,
    and returns empty string ("") if the tag doesn't exist in the dictionary.
    """
    try:
        return dictionary_keyword(tag)
    except KeyError:
        return ""

# Provide for the 'reverse' lookup. Given the keyword, what is the tag?
logger.debug("Reversing DICOM dictionary so can look up tag from a keyword...")
keyword_dict = dict([(dictionary_keyword(tag), tag) for tag in DicomDictionary])


def tag_for_keyword(keyword):
    """Return the dicom tag corresponding to keyword, or None if none exist."""
    return keyword_dict.get(keyword)


# PRIVATE DICTIONARY handling
# functions in analogy with those of main DICOM dict
def get_private_entry(tag, private_creator):
    """Return the tuple (VR, VM, name, is_retired) from a private dictionary"""
    tag = Tag(tag)
    try:
        private_dict = private_dictionaries[private_creator]
    except KeyError:
        raise KeyError("Private creator {0} not in private dictionary".format(private_creator))

    # private elements are usually agnostic for "block" (see PS3.5-2008 7.8.1 p44)
    # Some elements in _private_dict are explicit; most have "xx" for high-byte of element
    # Try exact key first, but then try with "xx" in block position
    try:
        dict_entry = private_dict[tag]
    except KeyError:
        #     so here put in the "xx" in the block position for key to look up
        group_str = "%04x" % tag.group
        elem_str = "%04x" % tag.elem
        key = "%sxx%s" % (group_str, elem_str[-2:])
        if key not in private_dict:
            raise KeyError("Tag {0} not in private dictionary for private creator {1}".format(key, private_creator))
        dict_entry = private_dict[key]
    return dict_entry


def private_dictionary_VR(tag, private_creator):
    """Return the dicom value representation for the given dicom tag."""
    return get_private_entry(tag, private_creator)[0]


def private_dictionary_VM(tag, private_creator):
    """Return the dicom value multiplicity for the given dicom tag."""
    return get_private_entry(tag, private_creator)[1]


def private_dictionary_description(tag, private_creator):
    """Return the descriptive text for the given dicom tag."""
    return get_private_entry(tag, private_creator)[2]


