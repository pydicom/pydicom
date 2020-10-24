# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Pydicom configuration options."""

# doc strings following items are picked up by sphinx for documentation

import logging
import os
from typing import Optional

have_numpy = True
try:
    import numpy
except ImportError:
    have_numpy = False


# Set the type used to hold DS values
#    default False; was decimal-based in pydicom 0.9.7
use_DS_decimal = False
"""Set using :func:`~pydicom.config.DS_decimal` to control if elements with a
VR of **DS** are represented as :class:`~decimal.Decimal`.

Default ``False``.
"""

data_element_callback = None
"""Set to a callable function to be called from
:func:`~pydicom.filereader.dcmread` every time a
:class:`~pydicom.dataelem.RawDataElement` has been returned,
before it is added to the :class:`~pydicom.dataset.Dataset`.

Default ``None``.
"""

data_element_callback_kwargs = {}
"""Set the keyword arguments passed to :func:`data_element_callback`.

Default ``{}``.
"""


def reset_data_element_callback():
    """Reset the :func:`data_element_callback` function to the default."""
    global data_element_callback
    global data_element_callback_kwargs
    data_element_callback = None
    data_element_callback_kwargs = {}


def DS_numpy(use_numpy=True):
    """Set whether multi-valued elements with VR of **DS** will be numpy arrays

    .. versionadded:: 2.0

    Parameters
    ----------
    use_numpy : bool, optional
        ``True`` (default) to read multi-value **DS** elements
        as :class:`~numpy.ndarray`, ``False`` to read multi-valued **DS**
        data elements as type :class:`~python.mulitval.MultiValue`

        Note: once a value has been accessed, changing this setting will
        no longer change its type

    Raises
    ------
    ValueError
        If :data:`use_DS_decimal` and `use_numpy` are both True.

    """

    global use_DS_numpy

    if use_DS_decimal and use_numpy:
        raise ValueError(
            "Cannot use numpy arrays to read DS elements"
            "if `use_DS_decimal` is True"
        )
    use_DS_numpy = use_numpy


def DS_decimal(use_Decimal_boolean=True):
    """Set DS class to be derived from :class:`decimal.Decimal` or
    :class:`float`.

    If this function is never called, the default in *pydicom* >= 0.9.8
    is for DS to be based on :class:`float`.

    Parameters
    ----------
    use_Decimal_boolean : bool, optional
        ``True`` (default) to derive :class:`~pydicom.valuerep.DS` from
        :class:`decimal.Decimal`, ``False`` to derive it from :class:`float`.

    Raises
    ------
    ValueError
        If `use_Decimal_boolean` and :data:`use_DS_numpy` are
        both ``True``.
    """
    global use_DS_decimal

    use_DS_decimal = use_Decimal_boolean

    if use_DS_decimal and use_DS_numpy:
        raise ValueError(
            "Cannot set use_DS_decimal True " "if use_DS_numpy is True"
        )

    import pydicom.valuerep

    if use_DS_decimal:
        pydicom.valuerep.DSclass = pydicom.valuerep.DSdecimal
    else:
        pydicom.valuerep.DSclass = pydicom.valuerep.DSfloat


# Configuration flags
use_DS_numpy = False
"""Set using the function :func:`~pydicom.config.DS_numpy` to control
whether arrays of VR **DS** are returned as numpy arrays.
Default: ``False``.

.. versionadded:: 2.0
"""

use_IS_numpy = False
"""Set to False to avoid IS values being returned as numpy ndarray objects.
Default: ``False``.

.. versionadded:: 2.0
"""

allow_DS_float = False
"""Set to ``True`` to allow :class:`~pydicom.valuerep.DSdecimal`
instances to be created using :class:`floats<float>`; otherwise, they must be
explicitly converted to :class:`str`, with the user explicitly setting the
precision of digits and rounding.

Default ``False``.
"""

enforce_valid_values = False
"""Raise exceptions if any value is not allowed by DICOM Standard.

e.g. DS strings that are longer than 16 characters; IS strings outside
the allowed range.

Default ``False``.
"""

datetime_conversion = False
"""Set to ``True`` to convert the value(s) of elements with a VR of DA, DT and
TM to :class:`datetime.date`, :class:`datetime.datetime` and
:class:`datetime.time` respectively.

Default ``False``
"""

use_none_as_empty_text_VR_value = False
""" If ``True``, the value of a decoded empty data element with
a text VR is ``None``, otherwise (the default), it is is an empty string.
For all other VRs the behavior does not change - the value is en empty
list for VR **SQ** and ``None`` for all other VRs.
Note that the default of this value may change to ``True`` in a later version.

.. versionadded:: 1.4
"""

replace_un_with_known_vr = True
""" If ``True``, and the VR of a known data element is encoded as **UN** in
an explicit encoding, the VR is changed to the known value.
Can be set to ``False`` where the content of the tag shown as **UN** is
not DICOM conformant and would lead to a failure if accessing it.

.. versionadded:: 2.0
"""

show_file_meta = True
"""
.. versionadded:: 2.0

If ``True`` (default), the 'str' and 'repr' methods
of :class:`~pydicom.dataset.Dataset` begin with a separate section
displaying the file meta information data elements
"""

# Logging system and debug function to change logging level
logger = logging.getLogger("pydicom")
logger.addHandler(logging.NullHandler())

import pydicom.overlays.numpy_handler as overlay_np  # noqa

overlay_data_handlers = [overlay_np]
"""Handlers for converting (60xx,3000) *Overlay Data*

.. versionadded:: 1.4

.. deprecated:: 2.1

.. currentmodule:: pydicom.dataset

This is an ordered list of *Overlay Data* handlers that the
:meth:`~Dataset.overlay_array` method will use to try to extract a correctly
sized numpy array from an *Overlay Data* element.

Handlers have two required methods:

def is_available():
    Return ``True`` if the handler's dependencies are installed, ``False``
    otherwise.

def get_overlay_array(ds, group):
    Return a correctly shaped :class:`numpy.ndarray` derived from the
    *Overlay Data* with element tag `group`, in :class:`Dataset` `ds` or raise
    an exception.

And two required attributes:

DEPENDENCIES : dict
    A dict containing the dependencies of the handler as
    {'package_import_name': ('http://package.com/url', 'Package Name')}
HANDLER_NAME : str
    The name of the handler, e.g. 'Numpy Overlay'

The first handler that both announces that it supports the transfer syntax
and does not raise an exception is the handler that will provide the
data.

If all handlers fail to convert the data only the last exception is raised.
"""

import pydicom.pixel_data_handlers.numpy_handler as np_handler  # noqa
import pydicom.pixel_data_handlers.rle_handler as rle_handler  # noqa
import pydicom.pixel_data_handlers.pillow_handler as pillow_handler  # noqa
import pydicom.pixel_data_handlers.jpeg_ls_handler as jpegls_handler  # noqa
import pydicom.pixel_data_handlers.gdcm_handler as gdcm_handler  # noqa
import pydicom.pixel_data_handlers.pylibjpeg_handler as pylibjpeg_handler  # noqa

pixel_data_handlers = [
    np_handler,
    rle_handler,
    gdcm_handler,
    pillow_handler,
    jpegls_handler,
    pylibjpeg_handler,
]
"""Handlers for converting (7FE0,0010) *Pixel Data*.

.. versionadded:: 1.2

.. currentmodule:: pydicom.dataset

This is an ordered list of *Pixel Data* handlers that the
:meth:`~Dataset.convert_pixel_data` method will use to try to extract a
correctly sized numpy array from the *Pixel Data* element.

Handlers shall have four methods:

def supports_transfer_syntax(ds)
    Return ``True`` if the handler supports the transfer syntax indicated in
    :class:`Dataset` `ds`, ``False`` otherwise.

def is_available():
    Return ``True`` if the handler's dependencies are installed, ``False``
    otherwise.

def get_pixeldata(ds):
    Return a correctly sized 1D :class:`numpy.ndarray` derived from the
    *Pixel Data* in :class:`Dataset` `ds` or raise an exception. Reshaping the
    returned array to the correct dimensions is handled automatically.

def needs_to_convert_to_RGB(ds):
    Return ``True`` if the *Pixel Data* in the :class:`Dataset` `ds` needs to
    be converted to the RGB colourspace, ``False`` otherwise.

The first handler that both announces that it supports the transfer syntax
and does not raise an exception, either in getting the data or when the data
is reshaped to the correct dimensions, is the handler that will provide the
data.

If they all fail only the last exception is raised.

If none raise an exception, but they all refuse to support the transfer
syntax, then this fact is announced in a :class:`NotImplementedError`
exception.
"""

APPLY_J2K_CORRECTIONS = True
"""Use the information within JPEG 2000 data to correct the returned pixel data

.. versionadded:: 2.1

If ``True`` (default), then for handlers that support JPEG 2000 pixel data,
use the component precision and sign to correct the returned ndarray when
using the pixel data handlers. If ``False`` then only rely on the element
values within the dataset when applying corrections.
"""

INVALID_KEYWORD_BEHAVIOR = "WARN"
"""Control the behavior when setting a :class:`~pydicom.dataset.Dataset`
attribute that's not a known element keyword.

.. versionadded:: 2.1

If ``"WARN"`` (default), then warn when an element value is set using
``Dataset.__setattr__()`` and the keyword is camel case but doesn't match a
known DICOM element keyword. If ``"RAISE"`` then raise a :class:`ValueError`
exception. If ``"IGNORE"`` then neither warn nor raise.

Examples
--------

>>> from pydicom import config
>>> config.INVALID_KEYWORD_BEHAVIOR = "WARN"
>>> ds = Dataset()
>>> ds.PatientName = "Citizen^Jan"  # OK
>>> ds.PatientsName = "Citizen^Jan"
../pydicom/dataset.py:1895: UserWarning: Camel case attribute 'PatientsName'
used which is not in the element keyword data dictionary
"""

INVALID_KEY_BEHAVIOR = "WARN"
"""Control the behavior when invalid keys are used with
:meth:`~pydicom.dataset.Dataset.__contains__` (e.g. ``'invalid' in ds``).

.. versionadded:: 2.1

Invalid keys are objects that cannot be converted to a
:class:`~pydicom.tag.BaseTag`, such as unknown element keywords or invalid
element tags like ``0x100100010``.

If ``"WARN"`` (default), then warn when an invalid key is used, if ``"RAISE"``
then raise a :class:`ValueError` exception. If ``"IGNORE"`` then neither warn
nor raise.

Examples
--------

>>> from pydicom import config
>>> config.INVALID_KEY_BEHAVIOR = "RAISE"
>>> ds = Dataset()
>>> 'PatientName' in ds  # OK
False
>>> 'PatientsName' in ds
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File ".../pydicom/dataset.py", line 494, in __contains__
    raise ValueError(msg) from exc
ValueError: Invalid value used with the 'in' operator: must be an
element tag as a 2-tuple or int, or an element keyword
"""


def debug(debug_on=True, default_handler=True):
    """Turn on/off debugging of DICOM file reading and writing.

    When debugging is on, file location and details about the elements read at
    that location are logged to the 'pydicom' logger using Python's
    :mod:`logging`
    module.

    .. versionchanged:1.4

        Added `default_handler` keyword parameter.

    Parameters
    ----------
    debug_on : bool, optional
        If ``True`` (default) then turn on debugging, ``False`` to turn off.
    default_handler : bool, optional
        If ``True`` (default) then use :class:`logging.StreamHandler` as the
        handler for log messages.
    """
    global logger, debugging

    if default_handler:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    if debug_on:
        logger.setLevel(logging.DEBUG)
        debugging = True
    else:
        logger.setLevel(logging.WARNING)
        debugging = False


# force level=WARNING, in case logging default is set differently (issue 103)
debug(False, False)

_use_future = False
_use_future_env = os.getenv("PYDICOM_FUTURE")

if _use_future_env:
    if _use_future_env.lower() in ["true", "yes", "on", "1"]:
        _use_future = True
    elif _use_future_env.lower() in ["false", "no", "off", "0"]:
        _use_future = False
    else:
        raise ValueError(
            "Unknown setting for environment variable "
            "PYDICOM_FUTURE. Use True or False."
        )


def future_behavior(enable_future: bool = True) -> None:
    """Imitate the behavior for the next major version of *pydicom*.

    .. versionadded:: 2.1

    This can be used to ensure your code is "future-proof" for known
    upcoming changes in the next major version of *pydicom*. Typically,
    deprecations become errors, and default values of config flags may change.

    Parameters
    ----------
    enable_future: bool
        Set ``True`` (default) to emulate future pydicom behavior,
        ``False`` to reset to current pydicom behavior.

    See also
    --------
    :attr:`~pydicom.config.INVALID_KEYWORD_BEHAVIOR`
    :attr:`~pydicom.config.INVALID_KEY_BEHAVIOR`

    """
    global _use_future, INVALID_KEYWORD_BEHAVIOR

    if enable_future:
        _use_future = True
        INVALID_KEYWORD_BEHAVIOR = "RAISE"
    else:
        _use_future = False
        INVALID_KEYWORD_BEHAVIOR = "WARN"


if _use_future:
    future_behavior()
