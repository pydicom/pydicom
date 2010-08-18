# datadict.py
"""Access dicom dictionary information"""
#
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com
#
import logging
logger = logging.getLogger("pydicom")
from dicom.tag import Tag
from dicom._dicom_dict import DicomDictionary  # the actual dict of {tag: (VR, VM, name, is_retired), tag:...}
from dicom._dicom_dict import RepeatersDictionary # those with tags like "(50xx, 0005)"
from dicom._private_dict import private_dictionaries

# Generate mask dict for checking repeating groups etc.
# Map a true bitwise mask to the DICOM mask with "x"'s in it.
masks = {}
for mask_x in RepeatersDictionary:
    # mask1 is XOR'd to see that all non-"x" bits are identical (XOR result = 0 if bits same)
    #      then AND those out with 0 bits at the "x" ("we don't care") location using mask2
    mask1 = long(mask_x.replace("x", "0"),16)
    mask2 = long("".join(["F0"[c=="x"] for c in mask_x]),16)
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
    """Return the tuple (VR, VM, name, is_retired) from the DICOM dictionary
    
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
    return (tag in DicomDictionary)

import string
normTable = string.maketrans('','')

def CleanName(tag):
    """Return the dictionary descriptive text string but without bad characters.
    
    Used for e.g. *named tags* of Dataset instances.
    
    """
    tag = Tag(tag)  
    if tag not in DicomDictionary: 
        if tag.element == 0:    # 0=implied group length in DICOM versions < 3
            return "GroupLength"
        else:
            return ""
    s = dictionaryDescription(tag)    # Descriptive name in dictionary
    # remove blanks and nasty characters
    s = s.translate(normTable, r""" !@#$%^&*(),;:.?\|{}[]+-="'/""")
    
    # Take "Sequence" out of name as more natural sounding
    # e..g "BeamSequence"->"Beams"; "ReferencedImageBoxSequence"->"ReferencedImageBoxes"
    # 'Other Patient ID' exists as single value AND as sequence so check for it and leave 'Sequence' in
    if dictionaryVR(tag) == "SQ" and not s.startswith("OtherPatientIDs"):
        if s[-8:] == "Sequence": 
            s = s[:-8]+"s"
        if s[-2:] == "ss":
            s = s[:-1]
        if s[-6:] == "Studys":
            s = s[:-2]+"ies"
        if s[-2:] == "xs":
            s = s[:-1] + "es"
    return s

# Provide for the 'reverse' lookup. Given clean name, what is the tag?
logger.debug("Reversing DICOM dictionary so can look up tag from a name...")
NameDict = dict([(CleanName(tag), tag) for tag in DicomDictionary])

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
    """Return a list of all (long and short) names for the tag"""
    longname = CleanName(tag)
    shortname = short_name(longname)
    names = [longname]
    if shortname:
        names.append(shortname)
    return names


# PRIVATE DICTIONARY handling 
# functions in analogy with those of main DICOM dict
def get_private_entry(tag, private_creator):
    """Return the tuple (VR, VM, name, is_retired) from a private dictionary"""
    tag = Tag(tag)
    try:
        private_dict = private_dictionaries[private_creator]
    except KeyError:
        raise KeyError, "Private creator '%s' not in private dictionary" % private_creator
    
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
            raise KeyError, "Tag %s not in private dictionary for private creator '%s'" % (key, private_creator)
        dict_entry = private_dict[key]
    return dict_entry
	
def private_dictionaryDescription(tag, private_creator):
    """Return the descriptive text for the given dicom tag."""
    return get_private_entry(tag, private_creator)[2]

def private_dictionaryVM(tag, private_creator):
    """Return the dicom value multiplicity for the given dicom tag."""
    return get_private_entry(tag, private_creator)[1]

def private_dictionaryVR(tag, private_creator):
    """Return the dicom value representation for the given dicom tag."""
    return get_private_entry(tag, private_creator)[0]