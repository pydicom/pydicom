# Copyright 2008-2021 pydicom authors. See LICENSE file for details.
"""Define the DataElement class.

A DataElement has a tag,
              a value representation (VR),
              a value multiplicity (VM)
              and a value.
"""

import base64
import json
from typing import Any, TYPE_CHECKING, NamedTuple, cast
from collections.abc import Callable, MutableSequence

from pydicom import config  # don't import datetime_conversion directly
from pydicom.config import logger
from pydicom.datadict import (
    dictionary_has_tag,
    dictionary_description,
    dictionary_keyword,
    dictionary_is_retired,
    private_dictionary_description,
    dictionary_VR,
    repeater_has_tag,
    private_dictionary_VR,
)
from pydicom.errors import BytesLengthException
from pydicom.jsonrep import JsonDataElementConverter, BulkDataType
from pydicom.misc import warn_and_log
from pydicom.multival import MultiValue
from pydicom.tag import Tag, BaseTag
from pydicom.uid import UID
from pydicom import jsonrep
import pydicom.valuerep  # don't import DS directly as can be changed by config
from pydicom.valuerep import (
    PersonName,
    BYTES_VR,
    AMBIGUOUS_VR,
    STR_VR,
    ALLOW_BACKSLASH,
    DEFAULT_CHARSET_VR,
    LONG_VALUE_VR,
    VR as VR_,
    validate_value,
)

if config.have_numpy:
    import numpy

if TYPE_CHECKING:  # pragma: no cover
    from pydicom.dataset import Dataset


def empty_value_for_VR(
    VR: str | None, raw: bool = False
) -> bytes | list[str] | str | None | PersonName:
    """Return the value for an empty element for `VR`.

    The behavior of this property depends on the setting of
    :attr:`config.use_none_as_empty_value`. If that is set to ``True``,
    an empty value is represented by ``None`` (except for VR 'SQ'), otherwise
    it depends on `VR`. For text VRs (this includes 'AE', 'AS', 'CS', 'DA',
    'DT', 'LO', 'LT', 'PN', 'SH', 'ST', 'TM', 'UC', 'UI', 'UR' and 'UT') an
    empty string is used as empty value representation, for all other VRs
    except 'SQ', ``None``. For empty sequence values (VR 'SQ') an empty list
    is used in all cases.
    Note that this is used only if decoding the element - it is always
    possible to set the value to another empty value representation,
    which will be preserved during the element object lifetime.

    Parameters
    ----------
    VR : str or None
        The VR of the corresponding element.
    raw : bool, optional
        If ``True``, returns the value for a :class:`RawDataElement`,
        otherwise for a :class:`DataElement`

    Returns
    -------
    str or bytes or None or list
        The value a data element with `VR` is assigned on decoding
        if it is empty.
    """
    if VR == VR_.SQ:
        return b"" if raw else []

    if config.use_none_as_empty_text_VR_value:
        return None

    if VR == VR_.PN:
        return b"" if raw else PersonName("")

    # DS and IS are treated more like int/float than str
    if VR in STR_VR - {VR_.DS, VR_.IS}:
        return b"" if raw else ""

    return None


class DataElement:
    """Contain and manipulate a DICOM Element.

    Examples
    --------

    While its possible to create a new :class:`DataElement` directly and add
    it to a :class:`~pydicom.dataset.Dataset`:

    >>> from pydicom import Dataset
    >>> elem = DataElement(0x00100010, 'PN', 'CITIZEN^Joan')
    >>> ds = Dataset()
    >>> ds.add(elem)

    Its far more convenient to use a :class:`~pydicom.dataset.Dataset`
    to add a new :class:`DataElement`, as the VR and tag are determined
    automatically from the DICOM dictionary:

    >>> ds = Dataset()
    >>> ds.PatientName = 'CITIZEN^Joan'

    Empty DataElement objects (e.g. with VM = 0) show an empty string as
    value for text VRs and `None` for non-text (binary) VRs:

    >>> ds = Dataset()
    >>> ds.PatientName = None
    >>> ds.PatientName
    ''

    >>> ds.BitsAllocated = None
    >>> ds.BitsAllocated

    >>> str(ds.BitsAllocated)
    'None'

    Attributes
    ----------
    descripWidth : int
        For string display, this is the maximum width of the description
        field (default ``35``).
    is_undefined_length : bool
        Indicates whether the length field for the element was ``0xFFFFFFFFL``
        (ie undefined).
    maxBytesToDisplay : int
        For string display, elements with values containing data which is
        longer than this value will display ``"array of # bytes"``
        (default ``16``).
    showVR : bool
        For string display, include the element's VR just before it's value
        (default ``True``).
    tag : pydicom.tag.BaseTag
        The element's tag.
    VR : str
        The element's Value Representation.
    """

    descripWidth = 35
    maxBytesToDisplay = 16
    showVR = True
    is_raw = False

    def __init__(
        self,
        tag: int | str | tuple[int, int],
        VR: str,
        value: Any,
        file_value_tell: int | None = None,
        is_undefined_length: bool = False,
        already_converted: bool = False,
        validation_mode: int | None = None,
    ) -> None:
        """Create a new :class:`DataElement`.

        Parameters
        ----------
        tag : int or str or 2-tuple of int
            The DICOM (group, element) tag in any form accepted by
            :func:`~pydicom.tag.Tag` such as ``'PatientName'``,
            ``(0x10, 0x10)``, ``0x00100010``, etc.
        VR : str
            The 2 character DICOM value representation (see DICOM Standard,
            Part 5, :dcm:`Section 6.2<part05/sect_6.2.html>`).
        value
            The value of the data element. One of the following:

            * a single string value
            * a number
            * a :class:`list` or :class:`tuple` with all strings or all numbers
            * a multi-value string with backslash separator
        file_value_tell : int, optional
            The byte offset to the start of the encoded element value.
        is_undefined_length : bool
            Used internally to store whether the length field for this element
            was ``0xFFFFFFFF``, i.e. 'undefined length'. Default is ``False``.
        already_converted : bool
            Used to determine whether or not the element's value requires
            conversion to a value with VM > 1. Default is ``False``.
        validation_mode : int
            Defines if values are validated and how validation errors are
            handled.
        """
        if validation_mode is None:
            validation_mode = config.settings.reading_validation_mode

        if not isinstance(tag, BaseTag):
            tag = Tag(tag)
        self.tag = tag

        # a known tag shall only have the VR 'UN' if it has a length that
        # exceeds the size that can be encoded in 16 bit - all other cases
        # can be seen as an encoding error and can be corrected
        if (
            VR == VR_.UN
            and not tag.is_private
            and config.replace_un_with_known_vr
            and (is_undefined_length or value is None or len(value) < 0xFFFF)
        ):
            try:
                VR = dictionary_VR(tag)
            except KeyError:
                pass

        self.VR = VR  # Note: you must set VR before setting value
        self.validation_mode = validation_mode
        if already_converted:
            self._value = value
        else:
            self.value = value  # calls property setter which will convert
        self.file_tell = file_value_tell
        self.is_undefined_length: bool = is_undefined_length
        self.private_creator: str | None = None

    def validate(self, value: Any) -> None:
        """Validate the current value against the DICOM standard.
        See :func:`~pydicom.valuerep.validate_value` for details.
        """
        validate_value(self.VR, value, self.validation_mode)

    @classmethod
    def from_json(
        cls: type["DataElement"],
        dataset_class: type["Dataset"],
        tag: str,
        vr: str,
        value: Any,
        value_key: str | None,
        bulk_data_uri_handler: (
            Callable[[str, str, str], BulkDataType]
            | Callable[[str], BulkDataType]
            | None
        ) = None,
    ) -> "DataElement":
        """Return a :class:`DataElement` from a DICOM JSON Model attribute
        object.

        Parameters
        ----------
        dataset_class : dataset.Dataset derived class
            The class object to use for **SQ** element items.
        tag : str
            The data element's tag as uppercase hex.
        vr : str
            The data element's value representation (VR).
        value : str or list[None | str | int | float | bytes | dict]
            The data element's value(s).
        value_key : str or None
            The attribute name for `value`, should be one of:
            ``{"Value", "InlineBinary", "BulkDataURI"}``. If the element's VM
            is ``0`` and none of the keys are used then will be ``None``.
        bulk_data_uri_handler: callable or None
            Callable function that accepts either the `tag`, `vr` and
            "BulkDataURI" `value` or just the "BulkDataURI" `value` of the JSON
            representation of a data element and returns the actual value of
            that data element (retrieved via DICOMweb WADO-RS). If no
            `bulk_data_uri_handler` is specified (default) then the
            corresponding element will have an "empty" value such as
            ``""``, ``b""`` or ``None`` depending on the `vr` (i.e. the
            Value Multiplicity will be 0).

        Returns
        -------
        DataElement
        """
        # TODO: test wado-rs retrieve wrapper
        converter = JsonDataElementConverter(
            dataset_class, tag, vr, value, value_key, bulk_data_uri_handler
        )
        elem_value = converter.get_element_values()

        if (
            vr == VR_.UN
            and config.replace_un_with_known_vr
            and isinstance(elem_value, bytes)
        ):
            raw = RawDataElement(
                Tag(tag), vr, len(elem_value), elem_value, 0, True, True
            )
            elem_value = convert_raw_data_element(raw).value

        try:
            return cls(tag=tag, value=elem_value, VR=vr)
        except Exception as exc:
            raise ValueError(
                f"Data element '{tag}' could not be loaded from JSON: {elem_value}"
            ) from exc

    def to_json_dict(
        self,
        bulk_data_element_handler: Callable[["DataElement"], str] | None,
        bulk_data_threshold: int,
    ) -> dict[str, Any]:
        """Return a dictionary representation of the :class:`DataElement`
        conforming to the DICOM JSON Model as described in the DICOM
        Standard, Part 18, :dcm:`Annex F<part18/chaptr_F.html>`.

        Parameters
        ----------
        bulk_data_element_handler : callable or None
            Callable that accepts a bulk :class`data element
            <pydicom.dataelem.DataElement>` and returns the
            "BulkDataURI" as a :class:`str` for retrieving the value of the
            data element via DICOMweb WADO-RS.
        bulk_data_threshold : int
            Size of base64 encoded data element above which a value will be
            provided in form of a "BulkDataURI" rather than "InlineBinary".
            Ignored if no `bulk_data_element_handler` is given.

        Returns
        -------
        dict
            Mapping representing a JSON encoded data element as ``{str: Any}``.
        """
        json_element: dict[str, Any] = {"vr": self.VR}
        if self.VR in (BYTES_VR | AMBIGUOUS_VR) - {VR_.US_SS}:
            if not self.is_empty:
                binary_value = self.value
                # Base64 makes the encoded value 1/3 longer.
                if bulk_data_element_handler is not None and len(binary_value) > (
                    (bulk_data_threshold // 4) * 3
                ):
                    json_element["BulkDataURI"] = bulk_data_element_handler(self)
                else:
                    # Json is exempt from padding to even length, see DICOM-CP1920
                    encoded_value = base64.b64encode(binary_value).decode("utf-8")
                    logger.info(f"encode bulk data element '{self.name}' inline")
                    json_element["InlineBinary"] = encoded_value
        elif self.VR == VR_.SQ:
            # recursive call to get sequence item JSON dicts
            value = [
                ds.to_json(
                    bulk_data_element_handler=bulk_data_element_handler,
                    bulk_data_threshold=bulk_data_threshold,
                    dump_handler=lambda d: d,
                )
                for ds in self.value
            ]
            json_element["Value"] = value
        elif self.VR == VR_.PN:
            if not self.is_empty:
                elem_value = []
                if self.VM > 1:
                    value = self.value
                else:
                    value = [self.value]
                for v in value:
                    comps = {"Alphabetic": v.components[0]}
                    if len(v.components) > 1:
                        comps["Ideographic"] = v.components[1]
                    if len(v.components) > 2:
                        comps["Phonetic"] = v.components[2]
                    elem_value.append(comps)
                json_element["Value"] = elem_value
        elif self.VR == VR_.AT:
            if not self.is_empty:
                value = self.value
                if self.VM == 1:
                    value = [value]
                json_element["Value"] = [format(v, "08X") for v in value]
        else:
            if not self.is_empty:
                if self.VM > 1:
                    value = self.value
                else:
                    value = [self.value]
                json_element["Value"] = [v for v in value]
        if "Value" in json_element:
            json_element["Value"] = jsonrep.convert_to_python_number(
                json_element["Value"], self.VR
            )
        return json_element

    def to_json(
        self,
        bulk_data_threshold: int = 1024,
        bulk_data_element_handler: Callable[["DataElement"], str] | None = None,
        dump_handler: Callable[[dict[str, Any]], str] | None = None,
    ) -> str:
        """Return a JSON representation of the :class:`DataElement`.

        Parameters
        ----------
        bulk_data_threshold : int, optional
            Size of base64 encoded data element above which a value will be
            provided in form of a "BulkDataURI" rather than "InlineBinary".
            Ignored if no `bulk_data_element_handler` is given.
        bulk_data_element_handler : callable, optional
            Callable that accepts a bulk :class`data element
            <pydicom.dataelem.DataElement>` and returns the
            "BulkDataURI" as a :class:`str` for retrieving the value of the
            data element via DICOMweb WADO-RS.
        dump_handler : callable, optional
            Callable function that accepts a :class:`dict` of ``{str: Any}``
            and returns the serialized (dumped) JSON :class:`str` (by default
            uses :func:`json.dumps`).

        Returns
        -------
        str
            Mapping representing a JSON encoded data element

        See also
        --------
        Dataset.to_json
        """

        def json_dump(d: dict[str, Any]) -> str:
            return json.dumps(d, sort_keys=True)

        dump_handler = json_dump if dump_handler is None else dump_handler

        return dump_handler(
            self.to_json_dict(bulk_data_element_handler, bulk_data_threshold)
        )

    @property
    def value(self) -> Any:
        """Return the element's value."""
        return self._value

    @value.setter
    def value(self, val: Any) -> None:
        """Convert (if necessary) and set the value of the element."""
        # Check if is multiple values separated by backslash
        #   If so, turn them into a list of separate values
        # Exclude splitting values with backslash characters based on:
        # * Which str-like VRs can have backslashes in Part 5, Section 6.2
        # * All byte-like VRs
        # * Ambiguous VRs that may be byte-like
        if self.VR not in ALLOW_BACKSLASH:
            if isinstance(val, str):
                val = val.split("\\") if "\\" in val else val
            elif isinstance(val, bytes):
                val = val.split(b"\\") if b"\\" in val else val

        self._value = self._convert_value(val)

    @property
    def VM(self) -> int:
        """Return the value multiplicity of the element as :class:`int`.

        .. versionchanged:: 3.0

            **SQ** elements now always return a VM of ``1``.
        """
        if self.VR == VR_.SQ:
            return 1

        if self.value is None:
            return 0

        if isinstance(self.value, str | bytes | PersonName):
            return 1 if self.value else 0

        try:
            iter(self.value)
        except TypeError:
            return 1

        return len(self.value)

    @property
    def is_empty(self) -> bool:
        """Return ``True`` if the element has no value."""
        if self.VR == VR_.SQ:
            return not bool(self.value)

        return self.VM == 0

    @property
    def empty_value(self) -> bytes | list[str] | None | str | PersonName:
        """Return the value for an empty element.

        See :func:`empty_value_for_VR` for more information.

        Returns
        -------
        str or None
            The value this data element is assigned on decoding if it is empty.
        """
        return empty_value_for_VR(self.VR)

    def clear(self) -> None:
        """Clears the value, e.g. sets it to the configured empty value.

        See :func:`empty_value_for_VR`.
        """
        self._value = self.empty_value

    def _convert_value(self, val: Any) -> Any:
        """Convert `val` to an appropriate type and return the result.

        Uses the element's VR in order to determine the conversion method and
        resulting type.
        """
        if (
            self.tag == 0x7FE00010
            and config.have_numpy
            and isinstance(val, numpy.ndarray)
        ):
            raise TypeError(
                "The value for (7FE0,0010) 'Pixel Data' should be set using 'bytes' "
                "not 'numpy.ndarray'. See the Dataset.set_pixel_data() method for "
                "an alternative that supports ndarrays."
            )

        if self.VR == VR_.SQ:  # a sequence - leave it alone
            from pydicom.sequence import Sequence

            if isinstance(val, Sequence):
                return val

            return Sequence(val)

        # if the value is a list, convert each element
        if not hasattr(val, "append"):
            return self._convert(val)

        if len(val) == 1:
            return self._convert(val[0])

        # Some ambiguous VR elements ignore the VR for part of the value
        # e.g. LUT Descriptor is 'US or SS' and VM 3, but the first and
        #   third values are always US (the third should be <= 16, so SS is OK)
        if self.tag in _LUT_DESCRIPTOR_TAGS and val:

            def _skip_conversion(val: Any) -> Any:
                return val

            validate_value(VR_.US, val[0], self.validation_mode)
            for value in val[1:]:
                validate_value(self.VR, value, self.validation_mode)

            return MultiValue(_skip_conversion, val)

        return MultiValue(self._convert, val)

    def _convert(self, val: Any) -> Any:
        """Convert `val` to an appropriate type for the element's VR."""
        # If the value is bytes and has a VR that can only be encoded
        # using the default character repertoire, convert it to a string
        if self.VR in DEFAULT_CHARSET_VR and isinstance(val, bytes):
            val = val.decode()

        if self.VR == VR_.IS:
            return pydicom.valuerep.IS(val, self.validation_mode)

        if self.VR == VR_.DA and config.datetime_conversion:
            return pydicom.valuerep.DA(val, validation_mode=self.validation_mode)

        if self.VR == VR_.DS:
            return pydicom.valuerep.DS(val, False, self.validation_mode)

        if self.VR == VR_.DT and config.datetime_conversion:
            return pydicom.valuerep.DT(val, validation_mode=self.validation_mode)

        if self.VR == VR_.TM and config.datetime_conversion:
            return pydicom.valuerep.TM(val, validation_mode=self.validation_mode)

        if self.VR == VR_.UI:
            return UID(val, self.validation_mode) if val is not None else None

        if self.VR == VR_.PN:
            return PersonName(val, validation_mode=self.validation_mode)

        if self.VR == VR_.AT and (val == 0 or val):
            return val if isinstance(val, BaseTag) else Tag(val)

        self.validate(val)
        return val

    def __eq__(self, other: Any) -> Any:
        """Compare `self` and `other` for equality.

        Returns
        -------
        bool
            The result if `self` and `other` are the same class
        NotImplemented
            If `other` is not the same class as `self` then returning
            :class:`NotImplemented` delegates the result to
            ``superclass.__eq__(subclass)``.
        """
        # Faster result if same object
        if other is self:
            return True

        if isinstance(other, self.__class__):
            if self.tag != other.tag or self.VR != other.VR:
                return False

            # tag and VR match, now check the value
            if config.have_numpy and isinstance(self.value, numpy.ndarray):
                return len(self.value) == len(other.value) and numpy.allclose(
                    self.value, other.value
                )

            return self.value == other.value

        return NotImplemented

    def __ne__(self, other: Any) -> Any:
        """Compare `self` and `other` for inequality."""
        return not (self == other)

    def __str__(self) -> str:
        """Return :class:`str` representation of the element."""
        value = self.repval or ""
        name = f"{self.name[:self.descripWidth]:<{self.descripWidth}}"

        if self.showVR:
            return f"{self.tag} {name} {self.VR}: {value}"

        return f"{self.tag} {name} {value}"

    @property
    def repval(self) -> str:
        """Return a :class:`str` representation of the element's value."""
        # If the VR is byte-like or long text (1024+), show a summary instead
        if self.VR in LONG_VALUE_VR:
            try:
                length = len(self.value)
            except TypeError:
                pass
            else:
                if length > self.maxBytesToDisplay:
                    return f"Array of {length} elements"

        if self.VM > self.maxBytesToDisplay:
            return f"Array of {self.VM} elements"

        if isinstance(self.value, UID):
            return self.value.name

        return repr(self.value)

    def __getitem__(self, key: int) -> Any:
        """Return the item at `key` if the element's value is indexable."""
        try:
            return self.value[key]
        except TypeError:
            raise TypeError("DataElement value is unscriptable (not a Sequence)")

    @property
    def name(self) -> str:
        """Return the DICOM dictionary name for the element as :class:`str`.

        Returns
        -------
        str
            * For officially registered DICOM Data Elements this will be the
              *Name* as given in
              :dcm:`Table 6-1<part06/chapter_6.html#table_6-1>`.
            * For private elements known to *pydicom* this will be the *Name*
              in the format ``'[name]'``.
            * For unknown private elements this will be ``'Private tag data'``.
            * Otherwise returns an empty string ``''``.
        """
        if self.tag.is_private:
            if self.private_creator:
                try:
                    # If we have the name from the private dictionary, use it,
                    # but put it in square brackets to make clear
                    # that the tag cannot be accessed by that name
                    name = private_dictionary_description(
                        self.tag, self.private_creator
                    )
                    return f"[{name}]"
                except KeyError:
                    pass
            elif self.tag.element >> 8 == 0:
                return "Private Creator"

            return "Private tag data"  # default

        if dictionary_has_tag(self.tag) or repeater_has_tag(self.tag):
            return dictionary_description(self.tag)

        # implied Group Length dicom versions < 3
        if self.tag.element == 0:
            return "Group Length"

        return ""

    @property
    def is_private(self) -> bool:
        """Return ``True`` if the element's tag is private.

        .. versionadded:: 2.1
        """
        return self.tag.is_private

    @property
    def is_retired(self) -> bool:
        """Return the element's retired status as :class:`bool`.

        For officially registered DICOM Data Elements this will be ``True`` if
        the retired status as given in the DICOM Standard, Part 6,
        :dcm:`Table 6-1<part06/chapter_6.html#table_6-1>` is 'RET'. For private
        or unknown elements this will always be ``False``.
        """
        if dictionary_has_tag(self.tag):
            return dictionary_is_retired(self.tag)

        return False

    @property
    def keyword(self) -> str:
        """Return the element's keyword (if known) as :class:`str`.

        For officially registered DICOM Data Elements this will be the
        *Keyword* as given in
        :dcm:`Table 6-1<part06/chapter_6.html#table_6-1>`. For private or
        unknown elements this will return an empty string ``''``.
        """
        if dictionary_has_tag(self.tag):
            return dictionary_keyword(self.tag)

        return ""

    def __repr__(self) -> str:
        """Return the representation of the element."""
        return str(self)


class RawDataElement(NamedTuple):
    """Container for the data from a raw (mostly) undecoded element."""

    tag: BaseTag
    VR: str | None
    length: int
    value: bytes | None
    value_tell: int
    is_implicit_VR: bool
    is_little_endian: bool
    is_raw: bool = True


def _private_vr_for_tag(ds: "Dataset | None", tag: BaseTag) -> str:
    """Return the VR for a known private tag, otherwise "UN".

    Parameters
    ----------
    ds : Dataset, optional
        The dataset needed for the private creator lookup.
        If not given, "UN" is returned.
    tag : BaseTag
        The private tag to lookup. The caller has to ensure that the
        tag is private.

    Returns
    -------
    str
        "LO" if the tag is a private creator, the VR of the private tag if
        found in the private dictionary, or "UN".
    """
    if tag.is_private_creator:
        return VR_.LO

    # invalid private tags are handled as UN
    if ds is not None and (tag.element & 0xFF00):
        private_creator_tag = tag.group << 16 | (tag.element >> 8)
        private_creator = ds.get(private_creator_tag, "")
        if private_creator:
            try:
                return private_dictionary_VR(tag, private_creator.value)
            except KeyError:
                pass

    return VR_.UN


# The first and third values of the following elements are always US
#   even if the VR is SS (PS3.3 C.7.6.3.1.5, C.11.1, C.11.2).
# (0028,1101-1103) RGB Palette Color LUT Descriptor
# (0028,3002) LUT Descriptor
_LUT_DESCRIPTOR_TAGS = (0x00281101, 0x00281102, 0x00281103, 0x00283002)


def convert_raw_data_element(
    raw: RawDataElement,
    *,
    encoding: str | MutableSequence[str] | None = None,
    ds: "Dataset | None" = None,
) -> DataElement:
    """Return a :class:`DataElement` created from `raw`.

    .. versionadded:: 3.0

    `raw` may be modified prior to conversion by setting the
    :attr:`~pydicom.config.Settings.raw_data_element_modifiers` attribute to
    a list of modification functions.

    Parameters
    ----------
    raw : pydicom.dataelem.RawDataElement
        The raw data to convert to a :class:`DataElement`.
    encoding : str | list[str], optional
        The character encoding of the raw data.
    ds : pydicom.dataset.Dataset, optional
        If given, used to resolve the VR for known private tags.

    Returns
    -------
    pydicom.dataelem.DataElement
        A :class:`~pydicom.dataelem.DataElement` instance created from `raw`.
    """
    from pydicom.values import convert_value

    if not config.settings.raw_data_element_modifiers:
        if config.data_element_callback:
            raw = config.data_element_callback(
                raw,
                encoding=encoding,
                **config.data_element_callback_kwargs,
            )

        vr = raw.VR
        if vr is None:  # Can be if was implicit VR
            try:
                vr = dictionary_VR(raw.tag)
            except KeyError:
                # just read the bytes, no way to know what they mean
                if raw.tag.is_private:
                    # for VR for private tags see PS3.5, 6.2.2
                    vr = _private_vr_for_tag(ds, raw.tag)

                # group length tag implied in versions < 3.0
                elif raw.tag.element == 0:
                    vr = VR_.UL
                else:
                    msg = f"VR lookup failed for the raw element with tag {raw.tag}"
                    if config.settings.reading_validation_mode == config.RAISE:
                        raise KeyError(msg)

                    vr = VR_.UN
                    warn_and_log(f"{msg} - setting VR to 'UN'")

        elif vr == VR_.UN and config.replace_un_with_known_vr:
            # handle rare case of incorrectly set 'UN' in explicit encoding
            # see also DataElement.__init__()
            if raw.tag.is_private:
                vr = _private_vr_for_tag(ds, raw.tag)
            elif raw.value is None or len(raw.value) < 0xFFFF:
                try:
                    vr = dictionary_VR(raw.tag)
                except KeyError:
                    pass

        vr = cast(str, vr)
        try:
            value = convert_value(vr, raw, encoding)
        except NotImplementedError as exc:
            raise NotImplementedError(f"{exc} in tag {raw.tag}")
        except BytesLengthException as exc:
            # Failed conversion, either raise or convert to a UN VR
            msg = (
                f"{exc} This occurred while trying to parse {raw.tag} according "
                f"to VR '{raw.VR}'."
            )
            if not config.convert_wrong_length_to_UN:
                raise BytesLengthException(
                    f"{msg} To replace this error with a warning set "
                    "pydicom.config.convert_wrong_length_to_UN = True."
                )

            warn_and_log(f"{msg} Setting VR to 'UN'.")
            vr = VR_.UN
            value = raw.value

        if raw.tag in _LUT_DESCRIPTOR_TAGS:
            # We only fix the first value as the third value is 8 or 16
            if value and isinstance(value, list):
                try:
                    if value[0] < 0:
                        value[0] += 65536
                except Exception:
                    pass

        return DataElement(
            raw.tag,
            vr,
            value,
            raw.value_tell,
            raw.length == 0xFFFFFFFF,
            already_converted=True,
        )

    # Custom conversion to DataElement
    modifiers = config.settings.raw_data_element_modifiers
    kwargs = config.settings.raw_data_element_kwargs
    kwargs.update({"encoding": encoding, "ds": ds})

    d: dict[str, Any] = {}
    for func in modifiers:
        d = func(raw, **kwargs)
        kwargs.update(d)

    return DataElement(
        d.get("tag", raw.tag),
        d.get("VR", raw.VR),
        d.get("value", raw.value),
        d.get("value_tell", raw.value_tell),
        d.get("length", raw.length) == 0xFFFFFFFF,
        already_converted=True,
    )


def _DataElement_from_raw(
    raw_data_element: RawDataElement,
    encoding: str | MutableSequence[str] | None = None,
    dataset: "Dataset | None" = None,
) -> DataElement:
    """Return a :class:`DataElement` created from `raw_data_element`.

    .. deprecated:: 3.0

        ``DataElement_from_raw`` will be removed in v4.0, use
        :func:`~pydicom.dataelem.convert_raw_data_element` instead.

    Call the configured data_element_callbacks to do relevant
    pre/post-processing and convert values from raw to native types

    Parameters
    ----------
    raw : pydicom.dataelem.RawDataElement
        The raw data to convert to a :class:`DataElement`.
    encoding : str | list[str], optional
        The character encoding of the raw data.
    dataset : pydicom.dataset.Dataset, optional
        If given, used to resolve the VR for known private tags.

    Returns
    -------
    pydicom.dataelem.DataElement
        A :class:`~pydicom.dataelem.DataElement` instance created from `raw`.
    """
    msg = (
        "'pydicom.dataelem.DataElement_from_raw' is deprecated and will be removed "
        "in v4.0, please use 'pydicom.dataelem.convert_raw_data_element' instead"
    )
    warn_and_log(msg, DeprecationWarning)

    return convert_raw_data_element(
        raw=raw_data_element,
        encoding=encoding,
        ds=dataset,
    )


_DEPRECATED = {
    "DataElement_from_raw": _DataElement_from_raw,
}


def __getattr__(name: str) -> Any:
    if name in _DEPRECATED and not config._use_future:
        return _DEPRECATED[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
