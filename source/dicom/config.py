# config.py
"""Pydicom configuration options."""
# Copyright (c) 2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

# doc strings following items are picked up by sphinx for documentation

allow_DS_float = False
"""Set allow_float to True to allow DS instances to be created with floats;
otherwise, they must be explicitly converted to strings, with the user
explicity setting the precision of digits and rounding. Default: False"""

enforce_valid_values = True
"""Raise errors if any value is not allowed by DICOM standard, e.g. DS strings
that are longer than 16 characters; IS strings outside the allowed range.
"""