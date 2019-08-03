# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Define the DataElement class.

A DataElement has a tag,
              a value representation (VR),
              a value multiplicity (VM)
              and a value.
"""

from __future__ import absolute_import

import base64
import json
import warnings
from collections import namedtuple

from pydicom import config  # don't import datetime_conversion directly
from pydicom import compat
from pydicom.charset import default_encoding
from pydicom.compat import in_py2
from pydicom.config import logger
from pydicom.datadict import (dictionary_has_tag, dictionary_description,
                              dictionary_keyword, dictionary_is_retired,
                              private_dictionary_description, dictionary_VR,
                              dictionary_VM, repeater_has_tag)
from pydicom.multival import MultiValue
from pydicom.tag import Tag, BaseTag
from pydicom.uid import UID
from pydicom import jsonrep
import pydicom.valuerep  # don't import DS directly as can be changed by config

from pydicom.valuerep import PersonNameUnicode
if not in_py2:
    from pydicom.valuerep import PersonName3 as PersonNameUnicode
    PersonName = PersonNameUnicode


def isMultiValue(value):
    """Return ``True`` if `value` is list-like (iterable).

    .. deprecation:: 1.3
       This function is deprecated, use :attr:`DataElement.VM` instead.

    """
    msg = 'isMultiValue is deprecated, use DataElement.VM instead'
    warnings.warn(msg, DeprecationWarning)
    if isinstance(value, compat.char_types):
        return False
    try:
        iter(value)
    except TypeError:
        return False
    return True


def _is_bytes(val):
    """Return True only in Python 3 if `val` is of type `bytes`."""
    return False if in_py2 else isinstance(val, bytes)


# double '\' because it is used as escape chr in Python
_backslash_str = "\\"
_backslash_byte = b"\\"


class DataElement(object):
    """Contain and manipulate a DICOM Element.

    Examples
    --------

    While its possible to create a new :class:`DataElement` directly and add
    it to a :class:`~pydicom.dataset.Dataset`:

    >>> elem = DataElement(0x00100010, 'PN', 'CITIZEN^Joan')
    >>> ds = Dataset()
    >>> ds.add(elem)

    Its far more convenient to use a :class:`~pydicom.dataset.Dataset`
    to add a new :class:`DataElement`, as the VR and tag are determined
    automatically from the DICOM dictionary:

    >>> ds = Dataset()
    >>> ds.PatientName = 'CITIZEN^Joan'

    Attributes
    ----------
    descripWidth : int
        For string display, this is the maximum width of the description
        field (default ``35``).
    is_retired : bool
        For officially registered DICOM Data Elements this will be ``True`` if
        the retired status as given in the DICOM Standard, Part 6,
        :dcm:`Table 6-1<part06/chapter_6.html#table_6-1>` is 'RET'. For private
        or unknown elements this will always be ``False``.
    is_undefined_length : bool
        Indicates whether the length field for the element was ``0xFFFFFFFFL``
        (ie undefined).
    keyword : str
        For officially registered DICOM Data Elements this will be the
        *Keyword* as given in
        :dcm:`Table 6-1<part06/chapter_6.html#table_6-1>`. For private or
        unknown elements this will return an empty string ``''``.
    maxBytesToDisplay : int
        For string display, elements with values containing data which is
        longer than this value will display ``"array of # bytes"``
        (default ``16``).
    name : str
        For officially registered DICOM Data Elements this will be the *Name*
        as given in :dcm:`Table 6-1<part06/chapter_6.html#table_6-1>`.
        For private elements known to *pydicom*
        this will be the *Name* in the format ``'[name]'``. For unknown
        private elements this will be ``'Private Creator'``. For unknown
        elements this will return an empty string ``''``.
    showVR : bool
        For string display, include the element's VR just before it's value
        (default ``True``).
    tag : BaseTag
        The element's tag.
    value
        The element's stored value(s).
    VM : int
        The Value Multiplicity of the element's stored value(s).
    VR : str
        The element's Value Representation.
    """

    descripWidth = 35
    maxBytesToDisplay = 16
    showVR = True
    is_raw = False

    # Python 2: Classes which define __eq__
    # should flag themselves as unhashable
    __hash__ = None

    def __init__(self,
                 tag,
                 VR,
                 value,
                 file_value_tell=None,
                 is_undefined_length=False,
                 already_converted=False):
        """Create a new :class:`DataElement`.

        Parameters
        ----------
        tag : int or or str or list or tuple
            The DICOM (group, element) tag in any form accepted by
            :func:`~pydicom.tag.Tag` such as ``[0x0010, 0x0010]``,
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

        file_value_tell : int or None
            Used internally by :class:`~pydicom.dataset.Dataset` to
            store the write position for the ``ReplaceDataElementValue()``
            method. Default is ``None``.
        is_undefined_length : bool
            Used internally to store whether the length field for this element
            was ``0xFFFFFFFFL``, i.e. 'undefined length'. Default is ``False``.
        already_converted : bool
            Used to determine whether or not the element's value requires
            conversion to a value with VM > 1. Default is ``False``.
        """
        if not isinstance(tag, BaseTag):
            tag = Tag(tag)
        self.tag = tag

        # a known tag shall only have the VR 'UN' if it has a length that
        # exceeds the size that can be encoded in 16 bit - all other cases
        # can be seen as an encoding error and can be corrected
        if VR == 'UN' and (is_undefined_length or value is None or
                           len(value) < 0xffff):
            try:
                VR = dictionary_VR(tag)
            except KeyError:
                pass

        self.VR = VR  # Note!: you must set VR before setting value
        if already_converted:
            self._value = value
        else:
            self.value = value  # calls property setter which will convert
        self.file_tell = file_value_tell
        self.is_undefined_length = is_undefined_length

    @classmethod
    def from_json(cls, dataset_class, tag, vr, value, value_key,
                  bulk_data_uri_handler=None, encodings=None):
        """Return a :class:`DataElement` from JSON.

        Parameters
        ----------
        dataset_class : Dataset derived class
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

        Returns
        -------
        DataElement
        """
        # TODO: test wado-rs retrieve wrapper
        try:
            vm = dictionary_VM(tag)
        except KeyError:
            # Private tag
            vm = str(len(value))
        if value_key == 'Value':
            if not(isinstance(value, list)):
                fmt = '"{}" of data element "{}" must be a list.'
                raise TypeError(fmt.format(value_key, tag))
        elif value_key in {'InlineBinary', 'BulkDataURI'}:
            if isinstance(value, list):
                fmt = '"{}" of data element "{}" must be a {}.'
                expected_type = ('string' if value_key == 'BulkDataURI'
                                 else 'bytes-like object')
                raise TypeError(fmt.format(value_key, tag, expected_type))
        if vr == 'SQ':
            elem_value = []
            for value_item in value:
                ds = dataset_class()
                if value_item:
                    for key, val in value_item.items():
                        if 'vr' not in val:
                            fmt = 'Data element "{}" must have key "vr".'
                            raise KeyError(fmt.format(tag))
                        unique_value_keys = tuple(
                            set(val.keys()) & set(jsonrep.JSON_VALUE_KEYS)
                        )
                        if len(unique_value_keys) == 0:
                            logger.debug(
                                'data element has neither key "{}".'.format(
                                    '" nor "'.join(jsonrep.JSON_VALUE_KEYS)
                                )
                            )
                            elem = DataElement(tag=tag, value='', VR=vr)
                        else:
                            value_key = unique_value_keys[0]
                            elem = cls.from_json(
                                dataset_class, key, val['vr'],
                                val[value_key], value_key
                            )
                        ds.add(elem)
                elem_value.append(ds)
        elif vr == 'PN':
            # Special case, see DICOM Part 18 Annex F2.2
            elem_value = []
            for v in value:
                if not isinstance(v, dict):
                    # Some DICOMweb services get this wrong, so we
                    # workaround the issue and warn the user
                    # rather than raising an error.
                    logger.error(
                        'value of data element "{}" with VR Person Name (PN) '
                        'is not formatted correctly'.format(tag)
                    )
                    elem_value.append(v)
                else:
                    elem_value.extend(list(v.values()))
            if vm == '1':
                try:
                    elem_value = elem_value[0]
                except IndexError:
                    elem_value = ''
        else:
            if vm == '1':
                if value_key == 'InlineBinary':
                    elem_value = base64.b64decode(value)
                elif value_key == 'BulkDataURI':
                    if bulk_data_uri_handler is None:
                        logger.warning(
                            'no bulk data URI handler provided for retrieval '
                            'of value of data element "{}"'.format(tag)
                        )
                        elem_value = b''
                    else:
                        elem_value = bulk_data_uri_handler(value)
                else:
                    if value:
                        elem_value = value[0]
                    else:
                        elem_value = value
            else:
                elem_value = value
        if elem_value is None:
            logger.warning('missing value for data element "{}"'.format(tag))
            elem_value = ''

        elem_value = jsonrep.convert_to_python_number(elem_value, vr)

        try:
            if compat.in_py2 and vr == "PN":
                elem_value = PersonNameUnicode(elem_value, 'UTF8')
            return DataElement(tag=tag, value=elem_value, VR=vr)
        except Exception:
            raise ValueError(
                'Data element "{}" could not be loaded from JSON: {}'.format(
                    tag, elem_value
                    )
            )

    def to_json(self, bulk_data_element_handler,
                bulk_data_threshold, dump_handler):
        """Converts a :class:`DataElement` to JSON representation.

        Parameters
        ----------
        bulk_data_element_handler: callable or None
            Callable that accepts a bulk data element and returns the
            "BulkDataURI" for retrieving the value of the data element
            via DICOMweb WADO-RS
        bulk_data_threshold: int
            Size of base64 encoded data element above which a value will be
            provided in form of a "BulkDataURI" rather than "InlineBinary"

        Returns
        -------
        dict
            Mapping representing a JSON encoded data element

        Raises
        ------
        TypeError
            When size of encoded data element exceeds `bulk_data_threshold`
            but `bulk_data_element_handler` is ``None`` and hence not callable

        """
        # TODO: Determine whether more VRs need to be converted to strings
        _VRs_TO_QUOTE = ['AT', ]
        json_element = {'vr': self.VR, }
        if self.VR in jsonrep.BINARY_VR_VALUES:
            if self.value is not None:
                binary_value = self.value
                encoded_value = base64.b64encode(binary_value).decode('utf-8')
                if len(encoded_value) > bulk_data_threshold:
                    if bulk_data_element_handler is None:
                        raise TypeError(
                            'No bulk data element handler provided to '
                            'generate URL for value of data element "{}".'
                            .format(self.name)
                        )
                    json_element['BulkDataURI'] = bulk_data_element_handler(
                        self
                    )
                else:
                    logger.info(
                        'encode bulk data element "{}" inline'.format(
                            self.name
                        )
                    )
                    json_element['InlineBinary'] = encoded_value
        elif self.VR == 'SQ':
            # recursive call to co-routine to format sequence contents
            value = [
                json.loads(e.to_json(
                    bulk_data_element_handler=bulk_data_element_handler,
                    bulk_data_threshold=bulk_data_threshold,
                    dump_handler=dump_handler
                ))
                for e in self
            ]
            json_element['Value'] = value
        elif self.VR == 'PN':
            elem_value = self.value
            if elem_value is not None:
                if compat.in_py2:
                    elem_value = PersonNameUnicode(elem_value, 'UTF8')
                if len(elem_value.components) > 2:
                    json_element['Value'] = [
                        {'Phonetic': elem_value.components[2], },
                    ]
                elif len(elem_value.components) > 1:
                    json_element['Value'] = [
                        {'Ideographic': elem_value.components[1], },
                    ]
                else:
                    json_element['Value'] = [
                        {'Alphabetic': elem_value.components[0], },
                    ]
        else:
            if self.value is not None:
                is_multivalue = isinstance(self.value, MultiValue)
                if self.VM > 1 or is_multivalue:
                    value = self.value
                else:
                    value = [self.value]
                # ensure it's a list and not another iterable
                # (e.g. tuple), which would not be JSON serializable
                if self.VR in _VRs_TO_QUOTE:
                    json_element['Value'] = [str(v) for v in value]
                else:
                    json_element['Value'] = [v for v in value]
        if hasattr(json_element, 'Value'):
            json_element['Value'] = jsonrep.convert_to_python_number(
                json_element['Value'], self.VR
            )
        return json_element

    @property
    def value(self):
        """Return the element's value."""
        return self._value

    @value.setter
    def value(self, val):
        """Convert (if necessary) and set the value of the element."""
        # Check if is a string with multiple values separated by '\'
        # If so, turn them into a list of separate strings
        #  Last condition covers 'US or SS' etc
        if isinstance(val, compat.char_types) and self.VR not in \
                ['UT', 'ST', 'LT', 'FL', 'FD', 'AT', 'OB', 'OW', 'OF', 'SL',
                 'SQ', 'SS', 'UL', 'OB/OW', 'OW/OB', 'OB or OW',
                 'OW or OB', 'UN'] and 'US' not in self.VR:
            try:
                if _backslash_str in val:
                    val = val.split(_backslash_str)
            except TypeError:
                if _backslash_byte in val:
                    val = val.split(_backslash_byte)
        self._value = self._convert_value(val)

    @property
    def VM(self):
        """Return the value multiplicity of the element as :class:`int`."""
        if isinstance(self.value, compat.char_types):
            return 1
        try:
            iter(self.value)
        except TypeError:
            return 1
        return len(self.value)

    def _convert_value(self, val):
        """Convert `val` to an appropriate type and return the result.

        Uses the element's VR in order to determine the conversion method and
        resulting type.
        """
        if self.VR == 'SQ':  # a sequence - leave it alone
            from pydicom.sequence import Sequence
            if isinstance(val, Sequence):
                return val
            else:
                return Sequence(val)

        # if the value is a list, convert each element
        try:
            val.append
        except AttributeError:  # not a list
            return self._convert(val)
        else:
            return MultiValue(lambda x: self._convert(x), val)

    def _convert(self, val):
        """Convert `val` to an appropriate type for the element's VR."""

        # If the value is a byte string and has a VR that can only be encoded
        # using the default character repertoire, we convert it to a string
        # here to allow for byte string input in these cases
        if _is_bytes(val) and self.VR in (
                'AE', 'AS', 'CS', 'DA', 'DS', 'DT', 'IS', 'TM', 'UI', 'UR'):
            val = val.decode()

        if self.VR == 'IS':
            return pydicom.valuerep.IS(val)
        elif self.VR == 'DA' and config.datetime_conversion:
            return pydicom.valuerep.DA(val)
        elif self.VR == 'DS':
            return pydicom.valuerep.DS(val)
        elif self.VR == 'DT' and config.datetime_conversion:
            return pydicom.valuerep.DT(val)
        elif self.VR == 'TM' and config.datetime_conversion:
            return pydicom.valuerep.TM(val)
        elif self.VR == "UI":
            return UID(val if val else '')
        elif not in_py2 and self.VR == "PN":
            return PersonName(val)
        # Later may need this for PersonName as for UI,
        #    but needs more thought
        # elif self.VR == "PN":
        #    return PersonName(val)
        else:  # is either a string or a type 2 optionally blank string
            return val  # this means a "numeric" value could be empty string ""
        # except TypeError:
            # print "Could not convert value '%s' to VR '%s' in tag %s" \
            # % (repr(val), self.VR, self.tag)
        # except ValueError:
            # print "Could not convert value '%s' to VR '%s' in tag %s" \
            # % (repr(val), self.VR, self.tag)

    def __eq__(self, other):
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
            if self.tag == other.tag and self.VR == other.VR \
                    and self.value == other.value:
                return True

        return NotImplemented

    def __ne__(self, other):
        """Compare `self` and `other` for inequality."""
        return not (self == other)

    def __str__(self):
        """Return :class:`str` representation of the element."""
        repVal = self.repval
        if self.showVR:
            s = "%s %-*s %s: %s" % (str(self.tag), self.descripWidth,
                                    self.description()[:self.descripWidth],
                                    self.VR, repVal)
        else:
            s = "%s %-*s %s" % (str(self.tag), self.descripWidth,
                                self.description()[:self.descripWidth], repVal)
        return s

    @property
    def repval(self):
        """Return a :class:`str` representation of the element's value."""
        long_VRs = {"OB", "OD", "OF", "OW", "UN", "UT"}
        if set(self.VR.split(" or ")) & long_VRs:
            try:
                length = len(self.value)
            except TypeError:
                pass
            else:
                if length > self.maxBytesToDisplay:
                    return "Array of %d elements" % length
        if self.VM > self.maxBytesToDisplay:
            repVal = "Array of %d elements" % self.VM
        elif isinstance(self.value, UID):
            repVal = self.value.name
        else:
            repVal = repr(self.value)  # will tolerate unicode too
        return repVal

    def __unicode__(self):
        """Return unicode representation of the element."""
        if isinstance(self.value, compat.text_type):
            # start with the string rep then replace the value part
            #   with the unicode
            strVal = str(self)
            strVal = strVal.replace(self.repval, "")
            uniVal = compat.text_type(strVal) + self.value
            return uniVal
        else:
            return compat.text_type(str(self))

    def __getitem__(self, key):
        """Return the item at `key` if the element's value is indexable."""
        try:
            return self.value[key]
        except TypeError:
            raise TypeError("DataElement value is unscriptable "
                            "(not a Sequence)")

    @property
    def name(self):
        """Return the DICOM dictionary name for the element as :class:`str`."""
        return self.description()

    def description(self):
        """Return the DICOM dictionary name for the element as :class:`str`."""
        if self.tag.is_private:
            name = "Private tag data"  # default
            if hasattr(self, 'private_creator'):
                try:
                    # If have name from private dictionary, use it, but
                    #   but put in square brackets so is differentiated,
                    #   and clear that cannot access it by name
                    name = private_dictionary_description(
                        self.tag, self.private_creator)
                    name = "[%s]" % (name)
                except KeyError:
                    pass
            elif self.tag.elem >> 8 == 0:
                name = "Private Creator"
        elif dictionary_has_tag(self.tag) or repeater_has_tag(self.tag):
            name = dictionary_description(self.tag)

        # implied Group Length dicom versions < 3
        elif self.tag.element == 0:
            name = "Group Length"
        else:
            name = ""
        return name

    @property
    def is_retired(self):
        """Return the element's retired status as :class:`bool`."""
        if dictionary_has_tag(self.tag):
            return dictionary_is_retired(self.tag)
        else:
            return False

    @property
    def keyword(self):
        """Return the element's keyword (if known) as :class:`str`."""
        if dictionary_has_tag(self.tag):
            return dictionary_keyword(self.tag)
        else:
            return ''

    def __repr__(self):
        """Return the representation of the element."""
        if self.VR == "SQ":
            return repr(self.value)
        else:
            return str(self)


msg = 'tag VR length value value_tell is_implicit_VR is_little_endian'
RawDataElement = namedtuple('RawDataElement', msg)
RawDataElement.is_raw = True


def DataElement_from_raw(raw_data_element, encoding=None):
    """Return a :class:`DataElement` created from `raw_data_element`.

    Parameters
    ----------
    raw_data_element : RawDataElement namedtuple
        The raw data to convert to a :class:`DataElement`.
    encoding : str, optional
        The character encoding of the raw data.

    Returns
    -------
    DataElement
    """
    # XXX buried here to avoid circular import
    # filereader->Dataset->convert_value->filereader
    # (for SQ parsing)

    if in_py2:
        encoding = encoding or default_encoding
    from pydicom.values import convert_value
    raw = raw_data_element

    # If user has hooked into conversion of raw values, call his/her routine
    if config.data_element_callback:
        data_elem = config.data_element_callback
        raw = data_elem(raw_data_element,
                        **config.data_element_callback_kwargs)
    VR = raw.VR
    if VR is None:  # Can be if was implicit VR
        try:
            VR = dictionary_VR(raw.tag)
        except KeyError:
            # just read the bytes, no way to know what they mean
            if raw.tag.is_private:
                # for VR for private tags see PS3.5, 6.2.2
                if raw.tag.is_private_creator:
                    VR = 'LO'
                else:
                    VR = 'UN'

            # group length tag implied in versions < 3.0
            elif raw.tag.element == 0:
                VR = 'UL'
            else:
                msg = "Unknown DICOM tag {0:s}".format(str(raw.tag))
                msg += " can't look up VR"
                raise KeyError(msg)
    try:
        value = convert_value(VR, raw, encoding)
    except NotImplementedError as e:
        raise NotImplementedError("{0:s} in tag {1!r}".format(str(e), raw.tag))
    return DataElement(raw.tag, VR, value, raw.value_tell,
                       raw.length == 0xFFFFFFFF, already_converted=True)
