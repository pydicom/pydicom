# Copyright 2008-2019 pydicom authors. See LICENSE file for details.
"""Methods for converting Datasets and DataElements to/from json"""

# Order of keys is significant!
from pydicom.compat import int_type

JSON_VALUE_KEYS = ('Value', 'BulkDataURI', 'InlineBinary',)

BINARY_VR_VALUES = ['OW', 'OB', 'OD', 'OF', 'OL', 'UN',
                    'OB or OW', 'US or OW', 'US or SS or OW']
VRs_TO_BE_FLOATS = ['DS', 'FL', 'FD', ]
VRs_TO_BE_INTS = ['IS', 'SL', 'SS', 'UL', 'US', 'US or SS']


def convert_to_python_number(value, vr):
    """Makes sure that values are either ints or floats
    based on their value representation.

    Parameters
    ----------
    value: Union[Union[str, int, float], List[Union[str, int, float]]]
        value of data element
    vr: str
        value representation of data element

    Returns
    -------
    Union[Union[str, int, float], List[Union[str, int, float]]]

    """
    if value is None:
        return None
    number_type = None
    if vr in VRs_TO_BE_INTS:
        number_type = int_type
    if vr in VRs_TO_BE_FLOATS:
        number_type = float
    if number_type is not None:
        if isinstance(value, (list, tuple,)):
            value = [number_type(e) for e in value]
        else:
            value = number_type(value)
    return value
