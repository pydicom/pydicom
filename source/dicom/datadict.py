# datadict.py
"""Access dicom dictionary information"""
# Copyright 2008, Darcy Mason
# This file is part of pydicom.
#
# pydicom is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# pydicom is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License (license.txt) for more details

# The actual python dict is in _dicom_dictionary.py.

from dicom.tag import Tag
from dicom._dicom_dict import DicomDictionary  # the actual dict of tag: (VR, VM, name, isRetired)
from dicom._dicom_dict import RepeatersDictionary # those with tags like "(50xx, 0005)"

# Generate mask dict for checking repeating groups etc.
# Map a true bitwise mask to the DICOM mask with "x"'s in it.
masks = {}
for mask_x in RepeatersDictionary:
    # mask1 is XOR'd to see that all bits are equal (XOR result = 0 if so, except for location of "x"'s where can be different,
    #      so AND those out with 0 bits at the "we don't care" location using mask2
    mask1 = long(mask_x.replace("x", "0"),16)
    mask2 = long("".join(["F0"[c=="x"] for c in mask_x]),16)
    # masks[long(mask_x.replace("x", "F"),16)] = mask_x
    masks[mask_x] = (mask1, mask2)

# For shorter naming of dicom member elements, put an entry here
#   (longer naming can also still be used)
# The descriptive name must start with the long version (not replaced if internal)
shortNames = [("BeamLimitingDevice", "BLD"),
              ("RTBeamLimitingDevice", "RTBLD"),
              ("ControlPoint", "CP"),
              ("Referenced", "Refd")
             ]

def mask_match(tag):
    for mask_x, (mask1, mask2) in masks.items():
        if (tag ^ mask1) & mask2 == 0:
            return mask_x
    return None
    
def get_entry(tag):
    """Return the tuple (VR, VM, name, isRetired) from the DICOM dictionary
    
    If the entry is not in the main dictionary, check the masked ones,
    e.g. repeating groups like 50xx, etc.
    """
    tag = Tag(tag)
    try:
        return DicomDictionary[tag]
    except KeyError:
        mask_x = mask_match(tag)
        if mask_x:
            return RepeatersDictionary[mask_x]
        else:
            raise KeyError, "Tag %s not found in DICOM dictionary" % Tag(tag)
        
def dictionaryDescription(tag):
    """Return the descriptive text for the given dicom tag."""
    return get_entry(tag)[2]

def dictionaryVM(tag):
    """Return the dicom value multiplicity for the given dicom tag."""
    return get_entry(tag)[1]

def dictionaryVR(tag):
    """Return the dicom value representation for the given dicom tag."""
    return get_entry(tag)[0]

def dictionaryHasTag(tag):
    """Return True if the dicom dictionary has an entry for the given tag."""
    return DicomDictionary.has_key(tag)

import string
normTable = string.maketrans('','')

def CleanName(tag):
    """Return the dictionary descriptive text string but without bad characters.
    
    Used for e.g. *named tags* of Dataset instances.
    
    """
    tag = Tag(tag)  # make sure is not an int
    if not DicomDictionary.has_key(tag): # can't name it - not in dictionary
        if tag.element == 0:             #  (unless is implied group length versions < 3)
            return "GroupLength"
        else:
            return ""
    s = dictionaryDescription(tag)    # Descriptive name in dictionary
    # remove blanks and nasty characters
    s = s.translate(normTable, r""" !@#$%^&*(),;:.?\|{}[]+-="'/""")
    if dictionaryVR(tag) == "SQ":
        if s[-8:] == "Sequence": s = s[:-8]+"s" # e.g. "BeamSequence" becomes "Beams"
        if s[-2:] == "ss": s = s[:-1]
        if s[-6:] == "Studys": s = s[:-2]+"ies"
        if s[-2:] == "xs": s = s[:-1] + "es" # e.g. Boxs -> Boxes
    return s

# Provide for the 'reverse' lookup. Given clean name, what is the tag?
NameDict = dict([(CleanName(tag), Tag(tag)) for tag in DicomDictionary])

def short_name(name):
    """Return a short *named tag* for the corresponding long version.
    
    Return a blank string if there is no short version of the name.
    
    """
    for longname, shortname in shortNames:
        if name.startswith(longname):
            return name.replace(longname, shortname)
    return ""
def long_name(name):
    """Return a long *named tag* for the corresponding short version.
    
    Return a blank string if there is no long version of the name.
    
    """
    
    for longname, shortname in shortNames:
        if name.startswith(shortname):
            return name.replace(shortname, longname)
    return ""

def TagForName(name):
    """Return the dicom tag corresponding to name, or None if none exist."""
    if name in NameDict:  # the usual case
        return NameDict[name]
    
    # check if is short-form of a valid name
    longname = long_name(name)
    if longname:
        return NameDict.get(longname, None)
    return None

def AllNamesForTag(tag):
    """Return a list of all (long and short) attribute names for the tag"""
    longname = CleanName(tag)
    shortname = short_name(longname)
    names = [longname]
    if shortname:
        names.append(shortname)
    return names
    