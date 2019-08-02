# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Code to fix non-standard dicom issues in files
"""

from pydicom import config
from pydicom import datadict
from pydicom import values


def fix_separator_callback(raw_elem, **kwargs):
    """Used by fix_separator as the callback function from read_dataset
    """
    return_val = raw_elem
    try_replace = False

    # If elements are implicit VR, attempt to determine the VR
    if raw_elem.VR is None:
        try:
            VR = datadict.dictionary_VR(raw_elem.tag)
        # Not in the dictionary, process if flag says to do so
        except KeyError:
            try_replace = kwargs['process_unkown_VR']
        else:
            try_replace = VR in kwargs['for_VRs']
    else:
        try_replace = raw_elem.VR in kwargs['for_VRs']

    if try_replace:
        # Note value has not been decoded yet when this function called,
        #    so need to replace backslash as bytes
        new_value = raw_elem.value.replace(kwargs['invalid_separator'], b"\\")
        return_val = raw_elem._replace(value=new_value)

    return return_val


def fix_separator(invalid_separator,
                  for_VRs=["DS", "IS"],
                  process_unknown_VRs=True):
    """A callback function to fix RawDataElement values using
    some other separator than the dicom standard backslash character

    Parameters
    ----------
    invalid_separator : bytes
        A single byte to replace with dicom backslash, in raw data element
        values before they have been decoded or processed by pydicom
    for_VRs : list, optional
        A list of VRs for which the replacement will be done.
        If the VR is unknown (for example, if a private element),
        then process_unknown_VR is used to determine whether to replace or not.
    process_unknown_VRs: bool, optional
        If True (default) then attempt the fix even if the VR is not known.

    Returns
    -------
    No return value.  However, the callback function will return either
    the original RawDataElement instance, or a fixed one.
    """
    config.data_element_callback = fix_separator_callback
    config.data_element_callback_kwargs = {
        'invalid_separator': invalid_separator,
        'for_VRs': for_VRs
    }


def fix_mismatch_callback(raw_elem, **kwargs):
    try:
        values.convert_value(raw_elem.VR, raw_elem)
    except ValueError:
        for vr in kwargs['with_VRs']:
            try:
                values.convert_value(vr, raw_elem)
            except ValueError:
                pass
            else:
                raw_elem = raw_elem._replace(VR=vr)
    return raw_elem


def fix_mismatch(with_VRs=['PN', 'DS', 'IS']):
    """A callback function to check that RawDataElements are translatable
    with their provided VRs.  If not, re-attempt translation using
    some other translators.

    Parameters
    ----------
    with_VRs : list, [['PN', 'DS', 'IS']]
        A list of VR strings to attempt if the raw data element value cannot
        be translated with the raw data element's VR.

    Returns
    -------
    No return value.  The callback function will return either
    the original RawDataElement instance, or one with a fixed VR.
    """
    config.data_element_callback = fix_mismatch_callback
    config.data_element_callback_kwargs = {
        'with_VRs': with_VRs,
    }
