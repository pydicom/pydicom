============================
Introduction to JSON support
============================

.. versionadded:: 1.3

Starting in *pydicom* version 1.3, some support for converting DICOM data to
and from JSON format has been added. This support is considered to be in
beta state, and the API is still subject to change.

Support for the JSON format has been added to the DICOM Standard in
Part 18 as the :dcm:`DICOM JSON Model<part18/chapter_F.html>`. The standard
describes how different DICOM value representations can be encoded in JSON.

Converting a dataset into JSON format
=====================================

*pydicom* supports the conversion of a DICOM dataset both into a JSON string
and into a deserialized JSON dictionary:

  >>> import pydicom
  >>> from pydicom.data import get_testdata_file
  >>> filename = get_testdata_file("CT_small.dcm")
  >>> ds = pydicom.dcmread(filename)
  >>> ds.to_json()
  '{"00080005": {"Value": ["ISO_IR 100"], "vr": "CS"}, "00080008": {"Value":...
  >>> ds.to_json_dict()
  {"00080005": {"Value": ["ISO_IR 100"], "vr": "CS"}, "00080008": {"Value":...

Which of these methods you need depends on your use case. The JSON string
format created by :func:`~pydicom.dataset.Dataset.to_json` can be used in
low-level APIs to serialize the dataset.
Higher-level Python APIs (like Django) often work directly with Python
dictionaries deserialized from a JSON string instead, so
:func:`~pydicom.dataset.Dataset.to_json_dict` can be more convenient here.

Creating a dataset from JSON
============================

Similar, a dataset can be created both from a JSON string and from a JSON
dictionary. There is only a single function to handle both cases:

  >>> from pydicom.dataset import Dataset
  >>> Dataset.from_json('{"00080005": {"Value": ["ISO_IR 100"], "vr": "CS"}}')
  (0008, 0005) Specific Character Set              CS: u'ISO_IR 100'
  >>> Dataset.from_json({"00080005": {"Value": ["ISO_IR 100"], "vr": "CS"}})
  (0008, 0005) Specific Character Set              CS: u'ISO_IR 100'

The conversion in both directions is symmetric:

  >>> import pydicom
  >>> filename = pydicom.data.get_testdata_file("CT_small.dcm")
  >>> ds = pydicom.dcmread(filename)
  >>> ds_json = ds.to_json()
  >>> ds1 = pydicom.dataset.Dataset.from_json(ds_json)
  >>> assert ds == ds1


Working with large binary data
==============================

Large binary data can be handled in two ways. It can be encoded
:dcm:`inline<part18/sect_F.2.7.html>` as a base64-encoded string, or it can
be accessed via a :dcm:`BulkDataURI<part18/sect_F.2.6.html>` provided in the
JSON data, that provides the possibility to retrieve the data using the
`DICOMweb WADO-RS <https://www.dicomstandard.org/dicomweb/retrieve-wado-rs-and-wado-uri/>`_
standard.

If you don't provide additional arguments to the encoding functions, the
data is encoded inline. If you want to save or retrieve data using DICOMweb
WADO-RS, you have to provide a bulk data handler.

On writing JSON data, the bulk data handler is responsible to store the data
so it can be retrieved via the ``BulkDataURI`` saved in the JSON dataset.
Note that only data greater than ``bulk_data_threshold`` (by default set to
1024) is handled by the bulk data handler - smaller data is encoded inline.

  >>> import pydicom
  >>> def bulk_data_handler(data_element):
  >>>     uri = store_data_and_return_uri(data_element)
  >>>     return uri
  >>>
  >>> filename = pydicom.data.get_testdata_file("CT_small.dcm")
  >>> ds = pydicom.dcmread(filename)
  >>> ds_json = ds.to_json(bulk_data_element_handler=bulk_data_handler)

On reading JSON data, the handler must be able to retrieve the data using
the stored ``BulkDataURI``:

  >>> def bulk_data_reader(bulk_data_uri):
  >>>     return data_retrieved_via_uri(bulk_data_uri)
  >>>
  >>> json_data = {
  >>>     "00091002": {"vr": "OB", "BulkDataURI": "https://my.wado.org/123"}
  >>> }
  >>> ds = Dataset.from_json(json_data, bulk_data_uri_handler=bulk_data_reader)

or, if you need to also know the tag and the vr, in addition to the stored
``BulkDataURI``:

  >>> def bulk_data_reader(tag, vr, bulk_data_uri):
  >>>     return data_retrieved_for_tag_and_vr_via_uri(tag, vr, bulk_data_uri)
  >>>
  >>> json_data = {
  >>>     "00091002": {"vr": "OB", "BulkDataURI": "https://my.wado.org/123"}
  >>> }
  >>> ds = Dataset.from_json(json_data, bulk_data_uri_handler=bulk_data_reader)
