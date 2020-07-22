# Copyright 2008-2019 pydicom authors. See LICENSE file for details.
"""Methods for converting Datasets and DataElements to/from json"""

import base64
import warnings

from pydicom.valuerep import PersonName

# Order of keys is significant!
JSON_VALUE_KEYS = ('Value', 'BulkDataURI', 'InlineBinary',)

BINARY_VR_VALUES = ['OW', 'OB', 'OD', 'OF', 'OL', 'UN',
                    'OB or OW', 'US or OW', 'US or SS or OW']
VRs_TO_BE_FLOATS = ['DS', 'FL', 'FD', ]
VRs_TO_BE_INTS = ['IS', 'SL', 'SS', 'UL', 'US', 'US or SS']


def convert_to_python_number(value, vr):
    """Makes sure that values are either ints or floats
    based on their value representation.

    .. versionadded:: 1.4

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
        number_type = int
    if vr in VRs_TO_BE_FLOATS:
        number_type = float
    if number_type is not None:
        if isinstance(value, (list, tuple,)):
            value = [number_type(e) for e in value]
        else:
            value = number_type(value)
    return value


class JsonDataElementConverter:
    """Handles conversion between JSON struct and :class:`DataElement`.

    .. versionadded:: 1.4
    """

    def __init__(self, dataset_class, tag, vr, value, value_key,
                 bulk_data_uri_handler):
        """Create a new converter instance.

        Parameters
        ----------
        dataset_class : dataset.Dataset derived class
            Class used to create sequence items.
        tag : BaseTag
            The data element tag.
        vr : str
            The data element value representation.
        value : list
            The data element's value(s).
        value_key : str or None
            Key of the data element that contains the value
            (options: ``{"Value", "InlineBinary", "BulkDataURI"}``)
        bulk_data_uri_handler: callable or None
            Callable function that accepts the "BulkDataURI" of the JSON
            representation of a data element and returns the actual value of
            that data element (retrieved via DICOMweb WADO-RS)
        """
        self.dataset_class = dataset_class
        self.tag = tag
        self.vr = vr
        self.value = value
        self.value_key = value_key
        self.bulk_data_uri_handler = bulk_data_uri_handler

    def get_element_values(self):
        """Return a the data element value or list of values.

        Returns
        -------
        str or bytes or int or float or dataset_class
        or PersonName or list of any of these types
            The value or value list of the newly created data element.
        """
        from pydicom.dataelem import empty_value_for_VR
        if self.value_key == 'Value':
            if not isinstance(self.value, list):
                fmt = '"{}" of data element "{}" must be a list.'
                raise TypeError(fmt.format(self.value_key, self.tag))
            if not self.value:
                return empty_value_for_VR(self.vr)
            element_value = [self.get_regular_element_value(v)
                             for v in self.value]
            if len(element_value) == 1 and self.vr != 'SQ':
                element_value = element_value[0]
            return convert_to_python_number(element_value, self.vr)

        # The value for "InlineBinary" shall be encoded as a base64 encoded
        # string, as shown in PS3.18, Table F.3.1-1, but the example in
        # PS3.18, Annex F.4 shows the string enclosed in a list.
        # We support both variants, as the standard is ambiguous here,
        # and do the same for "BulkDataURI".
        value = self.value
        if isinstance(value, list):
            value = value[0]

        if self.value_key == 'InlineBinary':
            if not isinstance(value, (str, bytes)):
                fmt = '"{}" of data element "{}" must be a bytes-like object.'
                raise TypeError(fmt.format(self.value_key, self.tag))
            return base64.b64decode(value)

        if self.value_key == 'BulkDataURI':
            if not isinstance(value, str):
                fmt = '"{}" of data element "{}" must be a string.'
                raise TypeError(fmt.format(self.value_key, self.tag))
            if self.bulk_data_uri_handler is None:
                warnings.warn(
                    'no bulk data URI handler provided for retrieval '
                    'of value of data element "{}"'.format(self.tag)
                )
                return empty_value_for_VR(self.vr, raw=True)
            return self.bulk_data_uri_handler(value)
        return empty_value_for_VR(self.vr)

    def get_regular_element_value(self, value):
        """Return a the data element value created from a json "Value" entry.

        Parameters
        ----------
        value : str or int or float or dict
            The data element's value from the json entry.

        Returns
        -------
        dataset_class or PersonName
        or str or int or float
            A single value of the corresponding :class:`DataElement`.
        """
        if self.vr == 'SQ':
            return self.get_sequence_item(value)

        if self.vr == 'PN':
            return self.get_pn_element_value(value)

        if self.vr == 'AT':
            try:
                return int(value, 16)
            except ValueError:
                warnings.warn('Invalid value "{}" for AT element - '
                              'ignoring it'.format(value))
            return
        return value

    def get_sequence_item(self, value):
        """Return a sequence item for the JSON dict `value`.

        Parameters
        ----------
        value : dict or None
            The sequence item from the JSON entry.

        Returns
        -------
        dataset_class
            The decoded dataset item.

        Raises
        ------
        KeyError
            If the "vr" key is missing for a contained element
        """
        ds = self.dataset_class()
        if value:
            for key, val in value.items():
                if 'vr' not in val:
                    fmt = 'Data element "{}" must have key "vr".'
                    raise KeyError(fmt.format(self.tag))
                vr = val['vr']
                unique_value_keys = tuple(
                    set(val.keys()) & set(JSON_VALUE_KEYS)
                )
                from pydicom import DataElement
                from pydicom.dataelem import empty_value_for_VR
                if not unique_value_keys:
                    # data element with no value
                    elem = DataElement(
                        tag=int(key, 16),
                        value=empty_value_for_VR(vr),
                        VR=vr)
                else:
                    value_key = unique_value_keys[0]
                    elem = DataElement.from_json(
                        self.dataset_class, key, vr,
                        val[value_key], value_key
                    )
                ds.add(elem)
        return ds

    def get_pn_element_value(self, value):
        """Return PersonName value from JSON value.

        Values with VR PN have a special JSON encoding, see the DICOM Standard,
        Part 18, :dcm:`Annex F.2.2<part18/sect_F.2.2.html>`.

        Parameters
        ----------
        value : dict
            The person name components in the JSON entry.

        Returns
        -------
        PersonName or str
            The decoded PersonName object or an empty string.
        """
        if not isinstance(value, dict):
            # Some DICOMweb services get this wrong, so we
            # workaround the issue and warn the user
            # rather than raising an error.
            warnings.warn(
                'value of data element "{}" with VR Person Name (PN) '
                'is not formatted correctly'.format(self.tag)
            )
            return value
        else:
            if 'Phonetic' in value:
                comps = ['', '', '']
            elif 'Ideographic' in value:
                comps = ['', '']
            else:
                comps = ['']
            if 'Alphabetic' in value:
                comps[0] = value['Alphabetic']
            if 'Ideographic' in value:
                comps[1] = value['Ideographic']
            if 'Phonetic' in value:
                comps[2] = value['Phonetic']
            elem_value = '='.join(comps)
            return elem_value
