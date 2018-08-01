# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
# -*- coding: utf-8 -*-
"""Access dicom dictionary information"""

from pydicom.config import logger
from pydicom.tag import Tag, BaseTag

# the actual dict of {tag: (VR, VM, name, is_retired, keyword), ...}
from pydicom._dicom_dict import DicomDictionary

# those with tags like "(50xx, 0005)"
from pydicom._dicom_dict import RepeatersDictionary
from pydicom._private_dict import private_dictionaries
import warnings

# Generate mask dict for checking repeating groups etc.
# Map a true bitwise mask to the DICOM mask with "x"'s in it.
masks = {}
for mask_x in RepeatersDictionary:
    # mask1 is XOR'd to see that all non-"x" bits
    # are identical (XOR result = 0 if bits same)
    # then AND those out with 0 bits at the "x"
    # ("we don't care") location using mask2
    mask1 = int(mask_x.replace("x", "0"), 16)
    mask2 = int("".join(["F0" [c == "x"] for c in mask_x]), 16)
    masks[mask_x] = (mask1, mask2)


def mask_match(tag):
    for mask_x, (mask1, mask2) in masks.items():
        if (tag ^ mask1) & mask2 == 0:
            return mask_x
    return None


def add_dict_entry(tag, VR, keyword, description, VM='1', is_retired=''):
    """Update pydicom's DICOM dictionary with a new entry.

    Notes
    ----
    Dose not permanently update the dictionary,
    but only during run-time. Will replace an existing
    entry if the tag already exists in the dictionary.

    Parameters
    ----------
    tag : int
        The tag number for the new dictionary entry
    VR : str
        DICOM value representation
    description : str
        The descriptive name used in printing the entry.
        Often the same as the keyword, but with spaces between words.
    VM : str, optional
        DICOM value multiplicity. If not specified, then '1' is used.
    is_retired : str, optional
        Usually leave as blank string (default).
        Set to 'Retired' if is a retired data element.

    See Also
    --------
    pydicom.examples.add_dict_entry
        Example file which shows how to use this function
    add_dict_entries
        Update multiple values at once.

    Examples
    --------
    >>> from pydicom import Dataset
    >>> add_dict_entry(0x10011001, "UL", "TestOne", "Test One")
    >>> add_dict_entry(0x10011002, "DS", "TestTwo", "Test Two", VM='3')
    >>> ds = Dataset()
    >>> ds.TestOne = 'test'
    >>> ds.TestTwo = ['1', '2', '3']

    """
    new_dict_val = (VR, VM, description, is_retired, keyword)
    add_dict_entries({tag: new_dict_val})


def add_dict_entries(new_entries_dict):
    """Update pydicom's DICOM dictionary with new entries.

    Parameters
    ----------
    new_entries_dict : dict
        Dictionary of form:
        {tag: (VR, VM, description, is_retired, keyword),...}
        where parameters are as described in add_dict_entry

    See Also
    --------
    add_dict_entry
        Simpler function to add a single entry to the dictionary.

    Examples
    --------
    >>> from pydicom import Dataset
    >>> new_dict_items = {
    ...        0x10011001: ('UL', '1', "Test One", '', 'TestOne'),
    ...        0x10011002: ('DS', '3', "Test Two", '', 'TestTwo'),
    ... }
    >>> add_dict_entries(new_dict_items)
    >>> ds = Dataset()
    >>> ds.TestOne = 'test'
    >>> ds.TestTwo = ['1', '2', '3']

    >>> add_dict_entry(0x10011001, "UL", "TestOne", "Test One")
    >>> ds = Dataset()
    >>> ds.TestOne = 'test'
    """

    # Update the dictionary itself
    DicomDictionary.update(new_entries_dict)

    # Update the reverse mapping from name to tag
    new_names_dict = dict([(val[4], tag)
                           for tag, val in new_entries_dict.items()])
    keyword_dict.update(new_names_dict)


def get_entry(tag):
    """Return the tuple (VR, VM, name, is_retired, keyword)
    from the DICOM dictionary

    If the entry is not in the main dictionary,
    check the masked ones, e.g. repeating groups like 50xx, etc.
    """
    # Note: tried the lookup with 'if tag in DicomDictionary'
    # and with DicomDictionary.get, instead of try/except
    # Try/except was fastest using timeit if tag is valid (usual case)
    # My test had 5.2 usec vs 8.2 for 'contains' test, vs 5.32 for dict.get
    if not isinstance(tag, BaseTag):
        tag = Tag(tag)
    try:
        return DicomDictionary[tag]
    except KeyError:
        if not tag.is_private:
            mask_x = mask_match(tag)
            if mask_x:
                return RepeatersDictionary[mask_x]
        raise KeyError("Tag {0} not found in DICOM dictionary".format(tag))


def dictionary_is_retired(tag):
    """Return True if the dicom retired status
       is 'Retired' for the given tag"""
    if 'retired' in get_entry(tag)[3].lower():
        return True
    return False


def dictionary_VR(tag):
    """Return the dicom value representation
       for the given dicom tag."""
    return get_entry(tag)[0]


def dictionary_VM(tag):
    """Return the dicom value multiplicity
       for the given dicom tag."""
    return get_entry(tag)[1]


def dictionary_description(tag):
    """Return the descriptive text for the given dicom tag."""
    return get_entry(tag)[2]


def dictionary_keyword(tag):
    """Return the official DICOM standard
      (since 2011) keyword for the tag"""
    return get_entry(tag)[4]


def dictionary_has_tag(tag):
    """Return True if the dicom dictionary
       has an entry for the given tag."""
    return (tag in DicomDictionary)


def keyword_for_tag(tag):
    """Return the DICOM keyword for the given tag.

    Will return GroupLength for group length tags,
    and returns empty string ("") if the tag
    doesn't exist in the dictionary.
    """
    try:
        return dictionary_keyword(tag)
    except KeyError:
        return ""


# Provide for the 'reverse' lookup. Given the keyword, what is the tag?
logger.debug("Reversing DICOM dictionary so can look up tag from a keyword...")
keyword_dict = dict([(dictionary_keyword(tag), tag)
                     for tag in DicomDictionary])


def tag_for_keyword(keyword):
    """Return the dicom tag corresponding to keyword,
       or None if none exist."""
    return keyword_dict.get(keyword)


def tag_for_name(name):
    """Deprecated -- use tag_for_keyword"""
    msg = "tag_for_name is deprecated.  Use tag_for_keyword instead"
    warnings.warn(msg, DeprecationWarning)

    return tag_for_keyword(name)


def repeater_has_tag(tag):
    """Return True if the DICOM repeaters dictionary
       has an entry for `tag`."""
    return (mask_match(tag) in RepeatersDictionary)


REPEATER_KEYWORDS = [val[4] for val in RepeatersDictionary.values()]


def repeater_has_keyword(keyword):
    """Return True if the DICOM repeaters element
       exists with `keyword`."""
    return keyword in REPEATER_KEYWORDS


# PRIVATE DICTIONARY handling
# functions in analogy with those of main DICOM dict
def get_private_entry(tag, private_creator):
    """Return the tuple (VR, VM, name, is_retired)
       from a private dictionary"""
    if not isinstance(tag, BaseTag):
        tag = Tag(tag)
    try:
        private_dict = private_dictionaries[private_creator]
    except KeyError:
        msg = "Private creator {0} ".format(private_creator)
        msg += "not in private dictionary"
        raise KeyError(msg)

    # private elements are usually agnostic for
    # "block" (see PS3.5-2008 7.8.1 p44)
    # Some elements in _private_dict are explicit;
    # most have "xx" for high-byte of element
    # Try exact key first, but then try with "xx" in block position
    try:
        dict_entry = private_dict[tag]
    except KeyError:
        #  so here put in the "xx" in the block position for key to look up
        group_str = "%04x" % tag.group
        elem_str = "%04x" % tag.elem
        key = "%sxx%s" % (group_str, elem_str[-2:])
        if key not in private_dict:
            key = "%sxxxx%s" % (group_str[:2], elem_str[-2:])
            if key not in private_dict:
                msg = ("Tag {0} not in private dictionary "
                       "for private creator {1}".format(key, private_creator))
                raise KeyError(msg)
        dict_entry = private_dict[key]
    return dict_entry


def private_dictionary_VR(tag, private_creator):
    """Return the dicom value representation
       for the given dicom tag."""
    return get_private_entry(tag, private_creator)[0]


def private_dictionary_VM(tag, private_creator):
    """Return the dicom value multiplicity
       for the given dicom tag."""
    return get_private_entry(tag, private_creator)[1]


def private_dictionary_description(tag, private_creator):
    """Return the descriptive text
       for the given dicom tag."""
    return get_private_entry(tag, private_creator)[2]
