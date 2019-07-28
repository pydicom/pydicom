# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Pydicom configuration options."""

# doc strings following items are picked up by sphinx for documentation

import logging

# Set the type used to hold DS values
#    default False; was decimal-based in pydicom 0.9.7
use_DS_decimal = False
"""Set to ``True`` to use ``decimal.Decimals`` to hold DS values.

Default ``False``.
"""

data_element_callback = None
"""Set data_element_callback to a function to be called from ``dcmread()``
every time a ``RawDataElement`` has been returned, before it is added
to the dataset.

Default ``None``.
"""

data_element_callback_kwargs = {}
"""Set this to use as keyword arguments passed to the ``data_element_callback``
function.

Default ``{}``.
"""


def reset_data_element_callback():
    """Reset the data_element_callback function to the default."""
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
"""Set `allow_DS_float` to ``True`` to allow ``DSdecimal`` instances to be
created with floats; otherwise, they must be explicitly converted to strings,
with the user explicity setting the precision of digits and rounding.

Default ``False``.
"""

enforce_valid_values = False
"""Raise exceptions if any value is not allowed by DICOM standard.

e.g. DS strings that are longer than 16 characters; IS strings outside
the allowed range.

Default ``False``.
"""

datetime_conversion = False
"""Set ``datetime_conversion`` to convert DA, DT and TM data elements to
``datetime.date``, ``datetime.datetime`` and ``datetime.time`` respectively.

Default ``False``
"""

# Logging system and debug function to change logging level
logger = logging.getLogger('pydicom')
handler = logging.StreamHandler()
formatter = logging.Formatter("%(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


import pydicom.pixel_data_handlers.numpy_handler as np_handler  # noqa
import pydicom.pixel_data_handlers.rle_handler as rle_handler  # noqa
import pydicom.pixel_data_handlers.pillow_handler as pillow_handler  # noqa
import pydicom.pixel_data_handlers.jpeg_ls_handler as jpegls_handler  # noqa
import pydicom.pixel_data_handlers.gdcm_handler as gdcm_handler  # noqa

pixel_data_handlers = [
    np_handler,
    rle_handler,
    gdcm_handler,
    pillow_handler,
    jpegls_handler,
]
"""Handlers for converting (7fe0,0010) *Pixel Data*.

This is an ordered list of *Pixel Data* handlers that the
``Dataset.convert_pixel_data()`` method will use to try to extract a
correctly sized numpy array from the *Pixel Data* element.

Handlers shall have four methods:

def supports_transfer_syntax(ds)
    Returns ``True`` if the handler might support the transfer syntax
    indicated in the Dataset `ds`.

def is_available():
    Returns ``True`` if the handler's dependencies are installed, ``False``
    otherwise.

def get_pixeldata(ds):
    This shall either throw an exception or return a correctly sized numpy
    1D array derived from the *Pixel Data* in Dataset `ds`. Reshaping the
    1D array to the correct dimensions is handled automatically.

def needs_to_convert_to_RGB(ds):
    Returns ``True`` if the *Pixel Data* in the Dataset `ds` needs to be
    converted to the RGB colourspace, ``False`` otherwise.

The first handler that both announces that it supports the transfer syntax
and does not throw an exception, either in getting the data or when the data
is reshaped to the correct dimensions, is the handler that will provide the
data.

If they all fail, the last one to throw an exception gets to see its
exception thrown up.

If no one throws an exception, but they all refuse to support the transfer
syntax, then this fact is announced in a NotImplementedError exception.
"""


def debug(debug_on=True):
    """Turn debugging of DICOM file reading and writing on or off.
    When debugging is on, file location and details about the
    elements read at that location are logged to the 'pydicom'
    logger using python's logging module.

    Parameters
    ----------
    debug_on : bool, optional
        True (default) to turn on debugging, False to turn off.
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
