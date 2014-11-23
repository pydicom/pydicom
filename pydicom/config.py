# config.py
"""Pydicom configuration options."""
# Copyright (c) 2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

# doc strings following items are picked up by sphinx for documentation

# Set the type used to hold DS values

use_DS_decimal = False  # default False; was decimal-based in pydicom 0.9.7


def DS_decimal(use_Decimal_boolean=True):
    """Set DS class to be derived from Decimal (True) or from float (False)
    If this function is never called, the default in pydicom >= 0.9.8
    is for DS to be based on float.
    """
    use_DS_decimal = use_Decimal_boolean
    import dicom.valuerep
    if use_DS_decimal:
        dicom.valuerep.DSclass = dicom.valuerep.DSdecimal
    else:
        dicom.valuerep.DSclass = dicom.valuerep.DSfloat


allow_DS_float = False
"""Set allow_float to True to allow DSdecimal instances to be created with floats;
otherwise, they must be explicitly converted to strings, with the user
explicity setting the precision of digits and rounding. Default: False"""

enforce_valid_values = True
"""Raise errors if any value is not allowed by DICOM standard, e.g. DS strings
that are longer than 16 characters; IS strings outside the allowed range.
"""
