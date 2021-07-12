# Copyright 2008-2019 pydicom authors. See LICENSE file for details.
"""Methods for converting Datasets and DataElements to/from json"""

import base64
from inspect import signature
import inspect
from typing import (
    Callable, Optional, Union, Any, cast, Type, TypeVar, Dict, TYPE_CHECKING
)
import warnings

from pydicom.tag import BaseTag, TagType

if TYPE_CHECKING:  # pragma: no cover
    from pydicom.dataset import Dataset

# Order of keys is significant!
JSON_VALUE_KEYS = ('Value', 'BulkDataURI', 'InlineBinary',)

BINARY_VR_VALUES = [
    'OB', 'OD', 'OF', 'OL', 'OV', 'OW', 'UN',
    'OB or OW', 'US or OW', 'US or SS or OW'
]
VRs_TO_BE_FLOATS = ['DS', 'FD', 'FL']
VRs_TO_BE_INTS = ['IS', 'SL', 'SS', 'SV', 'UL', 'US', 'UV', 'US or SS']


def convert_to_python_number(value: Any, vr: str) -> Any:
    """When possible convert numeric-like values to either ints or floats
    based on their value representation.

    .. versionadded:: 1.4

    Parameters
    ----------
    value : Any
        Value of the data element.
    vr : str
        Value representation of the data element.

    Returns
    -------
    Any

        * If `value` is ``None`` then returns ``None``
        * If `vr` is a integer-like VR type then returns ``int``, ``List[int]``
          or ``""`` if empty
        * If `vr` is a float-like VR type then returns ``float``,
          ``List[float]`` or ``""`` if empty
        * Otherwise returns `value` unchanged

    """
    if value is None or "":
        return value

    number_type: Optional[Union[Type[int], Type[float]]] = None
    if vr in VRs_TO_BE_INTS:
        number_type = int
    if vr in VRs_TO_BE_FLOATS:
        number_type = float

    if number_type is None:
        return value

    if isinstance(value, (list, tuple,)):
        return [number_type(e) for e in value]

    return number_type(value)


class JsonDataElementConverter:
    """Handles conversion between JSON struct and :class:`DataElement`.

    .. versionadded:: 1.4
    """

    def __init__(
        self,
        dataset_class: Type["Dataset"],
        tag: TagType,
        vr: str,
        value: Any,
        value_key: Optional[str],
        bulk_data_uri_handler: Optional[
            Union[
                Callable[[TagType, str, str], Any],
                Callable[[str], Any]
            ]
        ] = None
    ) -> None:
        """Create a new converter instance.

        Parameters
        ----------
        dataset_class : dataset.Dataset derived class
            Class used to create sequence items.
        tag : BaseTag
            The data element tag or int.
        vr : str
            The data element value representation.
        value : Any
            The data element's value(s).
        value_key : str or None
            Key of the data element that contains the value
            (options: ``{"Value", "InlineBinary", "BulkDataURI"}``)
        bulk_data_uri_handler: callable or None
            Callable function that accepts either the tag, vr and "BulkDataURI"
            or just the "BulkDataURI" of the JSON
            representation of a data element and returns the actual value of
            that data element (retrieved via DICOMweb WADO-RS)
        """
        self.dataset_class = dataset_class
        self.tag = tag
        self.vr = vr
        self.value = value
        self.value_key = value_key

        HandlerType = Optional[Callable[[TagType, str, str], Any]]
        self.bulk_data_element_handler: HandlerType

        handler = bulk_data_uri_handler

        def wrapper(tag: TagType, vr: str, value: str) -> Any:
            x = cast(Callable[[str], Any], handler)
            return x(value)

        if handler and len(signature(handler).parameters) == 1:
            # handler is Callable[[str], Any]
            self.bulk_data_element_handler = wrapper
        else:
            self.bulk_data_element_handler = cast(HandlerType, handler)

    def get_element_values(self) -> Any:
        """Return a the data element value or list of values.

        Returns
        -------
        Any
            The value or value list of the newly created data element.
        """
        from pydicom.dataelem import empty_value_for_VR

        if self.value_key == 'Value':
            if not isinstance(self.value, list):
                raise TypeError(
                    f"'{self.value_key}' of data element '{self.tag}' must "
                    "be a list"
                )

            if not self.value:
                # None, "", b"", [], PersonName("")
                return empty_value_for_VR(self.vr)

            element_value = [
                self.get_regular_element_value(v) for v in self.value
            ]

            if len(element_value) == 1 and self.vr != 'SQ':
                element_value = element_value[0]

            # Any
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
                raise TypeError(
                    f"'{self.value_key}' of data element '{self.tag}' must "
                    "be a bytes-like object"
                )

            # bytes
            return base64.b64decode(value)

        if self.value_key == 'BulkDataURI':
            if not isinstance(value, str):
                raise TypeError(
                    f"'{self.value_key}' of data element '{self.tag}' must "
                    "be a string"
                )

            if self.bulk_data_element_handler is None:
                warnings.warn(
                    'No bulk data URI handler provided for retrieval '
                    f'of value of data element "{self.tag}"'
                )
                return empty_value_for_VR(self.vr, raw=True)

            # Any
            return self.bulk_data_element_handler(self.tag, self.vr, value)

        return empty_value_for_VR(self.vr)

    def get_regular_element_value(self, value: Any) -> Any:
        """Return a the data element value created from a json "Value" entry.

        Parameters
        ----------
        value : Any
            The data element's value from the json entry.

        Returns
        -------
        Any
            A single value of the corresponding :class:`DataElement`.
        """
        if self.vr == 'SQ':
            # Dataset
            return self.get_sequence_item(value)

        if self.vr == 'PN':

            return self.get_pn_element_value(value)

        if self.vr == 'AT':
            # Optional[int]
            try:
                return int(value, 16)
            except ValueError:
                warnings.warn(
                    f"Invalid value '{value}' for AT element - ignoring it"
                )

            return None

        return value

    def get_sequence_item(self, value: Optional[Dict[str, Any]]) -> "Dataset":
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
        from pydicom import DataElement
        from pydicom.dataelem import empty_value_for_VR

        ds = self.dataset_class()

        value = {} if value is None else value
        for key, val in value.items():
            if 'vr' not in val:
                raise KeyError(
                    f"Data element '{self.tag}' must have key 'vr'"
                )

            vr = val['vr']
            unique_value_keys = tuple(
                set(val.keys()) & set(JSON_VALUE_KEYS)
            )

            if not unique_value_keys:
                # data element with no value
                elem = DataElement(
                    tag=int(key, 16),
                    value=empty_value_for_VR(vr),
                    VR=vr
                )
            else:
                value_key = unique_value_keys[0]
                elem = DataElement.from_json(
                    self.dataset_class,
                    key,
                    vr,
                    val[value_key],
                    value_key,
                    self.bulk_data_element_handler
                )
            ds.add(elem)

        return ds

    def get_pn_element_value(self, value: Any) -> Any:
        """Return PersonName value from JSON value.

        Values with VR PN have a special JSON encoding, see the DICOM Standard,
        Part 18, :dcm:`Annex F.2.2<part18/sect_F.2.2.html>`.

        Parameters
        ----------
        value : dict[str, str]
            The person name components in the JSON entry.

        Returns
        -------
        str
            The decoded PersonName object or an empty string.
        """
        if not isinstance(value, dict):
            # Some DICOMweb services get this wrong, so we
            # workaround the issue and warn the user
            # rather than raising an error.
            warnings.warn(
                f"Value of data element '{self.tag}' with VR Person Name (PN) "
                "is not formatted correctly"
            )
            return value

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

        return '='.join(comps)
