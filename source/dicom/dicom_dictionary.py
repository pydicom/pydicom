# dicom_dictionary.py
"""Access dicom dictionary information"""
# Copyright 2004, Darcy Mason
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
from dicom._dicom_dictionary import DicomDictionary  # Note leading underscore
from dicom.tag import Tag

# Add Repeating Group info to dictionary (Dicom standard versions < 3.0)
from dicom.repeating_group_curves import CurveDictionary
for k,v in CurveDictionary.items():
    for group in range(0x5000, 0x5020, 2):
        DicomDictionary[Tag((group,k))] = v

# For shorter naming of dicom member elements, put an entry here
#   (longer naming can also still be used)
# The descriptive name must start with the long version (not replaced if internal)
shortNames = [("BeamLimitingDevice", "BLD"),
              ("RTBeamLimitingDevice", "RTBLD"),
              ("ControlPoint", "CP"),
              ("Referenced", "Refd")
             ]


def dictionaryDescription(tag):
    """Return the descriptive text for the given dicom tag."""
    return DicomDictionary[tag][2]

def dictionaryVR(tag):
    """Return the dicom value representation for the given dicom tag."""
    return DicomDictionary[tag][0]

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
            return "Group Length"
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
    