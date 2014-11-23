# datadict.py
# -*- coding: utf-8 -*-
"""Access dicom dictionary information"""

# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com
#

import logging
logger = logging.getLogger("pydicom")
from dicom.tag import Tag
from dicom._dicom_dict import DicomDictionary  # the actual dict of {tag: (VR, VM, name, is_retired, keyword), ...}
from dicom._dicom_dict import RepeatersDictionary  # those with tags like "(50xx, 0005)"
from dicom._private_dict import private_dictionaries
import warnings
from dicom import in_py3

# Generate mask dict for checking repeating groups etc.
# Map a true bitwise mask to the DICOM mask with "x"'s in it.
masks = {}
for mask_x in RepeatersDictionary:
    # mask1 is XOR'd to see that all non-"x" bits are identical (XOR result = 0 if bits same)
    #      then AND those out with 0 bits at the "x" ("we don't care") location using mask2
    mask1 = long(mask_x.replace("x", "0"), 16)
    mask2 = long("".join(["F0"[c == "x"] for c in mask_x]), 16)
    masks[mask_x] = (mask1, mask2)

# For shorter naming of dicom member elements, put an entry here
#   (longer naming can also still be used)
# The descriptive name must start with the long version (not replaced if internal)
shortNames = [
    ("BeamLimitingDevice", "BLD"),
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
    """Return the tuple (VR, VM, name, is_retired, keyword) from the DICOM dictionary

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
            raise KeyError("Tag {0} not found in DICOM dictionary".format(tag))


def dictionary_description(tag):
    """Return the descriptive text for the given dicom tag."""
    return get_entry(tag)[2]


def dictionaryVM(tag):
    """Return the dicom value multiplicity for the given dicom tag."""
    return get_entry(tag)[1]


def dictionaryVR(tag):
    """Return the dicom value representation for the given dicom tag."""
    return get_entry(tag)[0]


def dictionary_has_tag(tag):
    """Return True if the dicom dictionary has an entry for the given tag."""
    return (tag in DicomDictionary)


def dictionary_keyword(tag):
    """Return the official DICOM standard (since 2011) keyword for the tag"""
    return get_entry(tag)[4]

# Set up a translation table for "cleaning" DICOM descriptions
#    for backwards compatibility pydicom < 0.9.7 (before DICOM keywords)
# Translation is different with unicode - see .translate() at
#        http://docs.python.org/library/stdtypes.html#string-methods
chars_to_remove = r""" !@#$%^&*(),;:.?\|{}[]+-="'’/"""
if in_py3:  # i.e. unicode strings
    translate_table = dict((ord(char), None) for char in chars_to_remove)
else:
    import string
    translate_table = string.maketrans('', '')


def keyword_for_tag(tag):
    """Return the DICOM keyword for the given tag. Replaces old CleanName()
    method using the 2011 DICOM standard keywords instead.

    Will return GroupLength for group length tags,
    and returns empty string ("") if the tag doesn't exist in the dictionary.
    """
    try:
        return dictionary_keyword(tag)
    except KeyError:
        return ""


def CleanName(tag):
    """Return the dictionary descriptive text string but without bad characters.

    Used for e.g. *named tags* of Dataset instances (before DICOM keywords were
    part of the standard)

    """
    tag = Tag(tag)
    if tag not in DicomDictionary:
        if tag.element == 0:    # 0=implied group length in DICOM versions < 3
            return "GroupLength"
        else:
            return ""
    s = dictionary_description(tag)    # Descriptive name in dictionary
    # remove blanks and nasty characters
    if in_py3:
        s = s.translate(translate_table)
    else:
        s = s.translate(translate_table, chars_to_remove)

    # Take "Sequence" out of name (pydicom < 0.9.7)
    # e..g "BeamSequence"->"Beams"; "ReferencedImageBoxSequence"->"ReferencedImageBoxes"
    # 'Other Patient ID' exists as single value AND as sequence so check for it and leave 'Sequence' in
    if dictionaryVR(tag) == "SQ" and not s.startswith("OtherPatientIDs"):
        if s.endswith("Sequence"):
            s = s[:-8] + "s"
            if s.endswith("ss"):
                s = s[:-1]
            if s.endswith("xs"):
                s = s[:-1] + "es"
            if s.endswith("Studys"):
                s = s[:-2] + "ies"
    return s

# Provide for the 'reverse' lookup. Given clean name, what is the tag?
logger.debug("Reversing DICOM dictionary so can look up tag from a name...")
NameDict = dict([(CleanName(tag), tag) for tag in DicomDictionary])
keyword_dict = dict([(dictionary_keyword(tag), tag) for tag in DicomDictionary])


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


def tag_for_name(name):
    """Return the dicom tag corresponding to name, or None if none exist."""
    if name in keyword_dict:  # the usual case
        return keyword_dict[name]
    # If not an official keyword, check the old style pydicom names
    if name in NameDict:
        tag = NameDict[name]
        msg = ("'%s' as tag name has been deprecated; use official DICOM keyword '%s'"
               % (name, dictionary_keyword(tag)))
        warnings.warn(msg, DeprecationWarning)
        return tag

    # check if is short-form of a valid name
    longname = long_name(name)
    if longname:
        return NameDict.get(longname, None)
    return None


def all_names_for_tag(tag):
    """Return a list of all (long and short) names for the tag"""
    longname = keyword_for_tag(tag)
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


def private_dictionary_description(tag, private_creator):
    """Return the descriptive text for the given dicom tag."""
    return get_private_entry(tag, private_creator)[2]


def private_dictionaryVM(tag, private_creator):
    """Return the dicom value multiplicity for the given dicom tag."""
    return get_private_entry(tag, private_creator)[1]


def private_dictionaryVR(tag, private_creator):
    """Return the dicom value representation for the given dicom tag."""
    return get_private_entry(tag, private_creator)[0]
