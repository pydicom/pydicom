# config.py
"""Pydicom configuration options."""
# Copyright (c) 2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

# doc strings following items are picked up by sphinx for documentation


import logging

# Set the type used to hold DS values
#    default False; was decimal-based in pydicom 0.9.7
use_DS_decimal = False

data_element_callback = None
"""Set data_element_callback to a function to be called from read_dataset
every time a RawDataElement has been returned, before it is added
to the dataset.
"""

data_element_callback_kwargs = {}
"""Set this to use as keyword arguments passed to the data_element_callback
function"""


def reset_data_element_callback():
    global data_element_callback
    global data_element_callback_kwargs
    data_element_callback = None
    data_element_callback_kwargs = {}


def DS_decimal(use_Decimal_boolean=True):
    """Set DS class to be derived from Decimal (True) or from float (False)
    If this function is never called, the default in pydicom >= 0.9.8
    is for DS to be based on float.
    """
    use_DS_decimal = use_Decimal_boolean
    import pydicom.valuerep
    if use_DS_decimal:
        pydicom.valuerep.DSclass = pydicom.valuerep.DSdecimal
    else:
        pydicom.valuerep.DSclass = pydicom.valuerep.DSfloat

# Configuration flags
allow_DS_float = False
"""Set allow_float to True to allow DSdecimal instances to be created with floats;
otherwise, they must be explicitly converted to strings, with the user
explicity setting the precision of digits and rounding. Default: False"""

enforce_valid_values = False
"""Raise errors if any value is not allowed by DICOM standard, e.g. DS strings
that are longer than 16 characters; IS strings outside the allowed range.
"""

datetime_conversion = False
"""Set datetime_conversion to convert DA, DT and TM data elements to
datetime.date, datetime.datetime and datetime.time respectively. Default: False
"""


# Logging system and debug function to change logging level
logger = logging.getLogger('pydicom')
handler = logging.StreamHandler()
formatter = logging.Formatter("%(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


def debug(debug_on=True):
    """Turn debugging of DICOM file reading and writing on or off.
    When debugging is on, file location and details about the elements read at
    that location are logged to the 'pydicom' logger using python's logging module.

    :param debug_on: True (default) to turn on debugging, False to turn off.
    """
    global logger, debugging
    if debug_on:
        logger.setLevel(logging.DEBUG)
        debugging = True
    else:
        logger.setLevel(logging.WARNING)
        debugging = False

# force level=WARNING, in case logging default is set differently (issue 103)
debug(False)
