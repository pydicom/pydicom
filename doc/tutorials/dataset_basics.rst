=======================================
The basics: read, access, modify, write
=======================================

In this tutorial we're going to cover the basics of using pydicom:

* Reading a DICOM dataset from file using pydicom
* Viewing and accessing the contents of the dataset
* Modifying the dataset by adding, changing and deleting elements
* Writing our modifications back to file

If you haven't installed pydicom yet, follow the instructions in our
:doc:`installation guide</tutorials/installation>`.


Getting our example dataset
===========================

In the tutorial we're going to be using a DICOM dataset included with pydicom:
:gh:`CT_small.dcm<pydicom/blob/master/pydicom/data/test_files/CT_small.dcm>`.
Starting with pydicom v1.4 you can get the path to the file
by using the :func:`~pydicom.data.get_testdata_file` function to return the
path as a :class:`str` (your path may vary)::

    >>> from pydicom.data import get_testdata_file
    >>> fpath = get_testdata_file("CT_small.dcm")
    >>> fpath
    /home/user/env/pyd/lib/python3.7/site-packages/pydicom/data/test_files/CT_small.dcm

If you're using an earlier version then you'll have to use
:func:`~pydicom.data.get_testdata_files` instead, which returns a list
containing matching paths::

    >>> from pydicom.data import get_testdata_files
    >>> fpath = get_testdata_files("CT_small.dcm")[0]
    >>> fpath
    /home/user/env/pyd/lib/python3.7/site-packages/pydicom/data/test_files/CT_small.dcm

To get the version of pydicom you're using you can do the following::

    >>> import pydicom
    >>> pydicom.__version__
    '1.3.0'


Reading
=======

To read the DICOM dataset at a given file path we use
:func:`~pydicom.filereader.dcmread`, which returns a
:class:`~pydicom.dataset.FileDataset` instance::

    >>> from pydicom import dcmread
    >>> from pydicom.data import get_testdata_file
    >>> fpath = get_testdata_file("CT_small.dcm")
    >>> ds = dcmread(fpath)
    >>> type(ds)
    <class 'pydicom.dataset.FileDataset'>

:func:`~pydicom.filereader.dcmread` can also handle file-likes::

    >>> with open(fpath, 'rb') as infile:
    ...     ds = dcmread(infile)

And can even be used as a context manager::

    >>> with dcmread(fpath) as ds:
    ...    type(ds)
    <class 'pydicom.dataset.FileDataset'>

By default, :func:`~pydicom.filereader.dcmread` will read any DICOM dataset
stored in accordance with the :dcm:`DICOM File Format<part10/chapter_7.html>`.
However, occasionally you may try to read a file that gives you the following
exception:

.. code-block:: pycon

    >>> no_meta = get_testdata_file('no_meta.dcm')
    >>> ds = dcmread(no_meta)
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File ".../pydicom/filereader.py", line 887, in dcmread
        force=force, specific_tags=specific_tags)
      File ".../pydicom/filereader.py", line 678, in read_partial
        preamble = read_preamble(fileobj, force)
      File ".../pydicom/filereader.py", line 631, in read_preamble
        raise InvalidDicomError("File is missing DICOM File Meta Information "
      pydicom.errors.InvalidDicomError: File is missing DICOM File Meta Information header or the 'DICM' prefix is missing from the header. Use force=True to force reading.

This indicates that either:

* The file isn't a DICOM file, or
* The file isn't in the DICOM File Format

If you're sure that the file is DICOM then you can use the ``force`` keyword
parameter to force reading::

  >>> ds = dcmread(no_meta, force=True)

A note of caution about using ``force``; because pydicom uses a deferred-read
system, **any file** read with ``force=True`` will ***not*** produce an
exception at the time of reading:

.. code-block:: pycon

    >>> with open('not_dicom.txt', 'w') as not_dicom:
    ...    not_dicom.write('This is not a DICOM file!')
    >>> ds = dcmread('not_dicom.txt', force=True)

You'll only run into problems when trying to use the dataset::

    >>> print(ds)
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "../pydicom/dataset.py", line 1703, in __str__
          return self._pretty_str()
      File "../pydicom/dataset.py", line 1436, in _pretty_str
          for data_element in self:
      File "../pydicom/dataset.py", line 1079, in __iter__
          yield self[tag]
      File "../pydicom/dataset.py", line 833, in __getitem__
          self[tag] = DataElement_from_raw(data_elem, character_set)
      File "../pydicom/dataelem.py", line 581, in DataElement_from_raw
          raise KeyError(msg)
      KeyError: "Unknown DICOM tag (6854, 7369) can't look up VR"

Before we go on to the next section, let's go back to our ``CT_small.dcm``
dataset::

    >>> fpath = get_testdata_file("CT_small.dcm")
    >>> ds = dcmread(fpath)


Viewing and accessing
=====================

You can view the contents of the entire dataset by using :func:`print`::

    >>> print(ds)
    (0008, 0005) Specific Character Set              CS: 'ISO_IR 100'
    (0008, 0008) Image Type                          CS: ['ORIGINAL', 'PRIMARY', 'AXIAL']
    (0008, 0012) Instance Creation Date              DA: '20040119'
    (0008, 0013) Instance Creation Time              TM: '072731'
    (0008, 0014) Instance Creator UID                UI: 1.3.6.1.4.1.5962.3
    (0008, 0016) SOP Class UID                       UI: CT Image Storage
    ...
    (0010, 1002)  Other Patient IDs Sequence   2 item(s) ----
        (0010, 0020) Patient ID                          LO: 'ABCD1234'
        ---------
        (0010, 0020) Patient ID                          LO: '1234ABCD'
        ---------
    ...
    (0043, 104e) [Duration of X-ray on]              FL: 10.60060977935791
    (7fe0, 0010) Pixel Data                          OW: Array of 32768 elements
    (fffc, fffc) Data Set Trailing Padding           OB: Array of 126 elements

The print output shows a list of the :dcm:`data elements
<part05/chapter_7.html#sect_7.1>` present in the dataset, one element per
line. The format of each line is:

* **(0008, 0005)**: The element's :dcm:`tag<part05/chapter_7.html#sect_7.1.1>`,
  as (group number, element number) in hexadecimal
* **Specific Character Set**: the element's name, if known
* **CS**: The element's :dcm:`Value Representation<part05/sect_6.2.html>` (VR),
  if known
* **'ISO_IR_100'**: the element's stored value

Elements
--------

There are three categories of elements:

* Regular elements such as (0008,0016) *SOP Class UID*. These
  elements have an even group number and are unique at each level of the
  dataset.
* :dcm:`Repeating group<part05/sect_7.6.html>` elements such as (60xx,3000)
  *Overlay Data* (not found in this dataset). Repeating group elements have the
  group or element number
  defined over a range rather than a fixed value. For example, there may be
  multiple *Overlay Data* elements as long as each has its own group number
  ``0x6000``, ``0x6002``, ``0x6004``, or any even value up to ``0x601E``.
  Repeating group elements may not be unique at each level of the dataset.
* :dcm:`Private elements<part05/sect_7.8.html>` such as (0043,104E) *[Duration
  of X-ray on]*. Private elements have an odd group number, aren't registered
  in the official DICOM Standard, and are instead created
  privately, usually by a manufacturer. In general, unless the manufacturer
  publishes the details of their private elements, the element name and VR
  aren't known. However, in this case the details have been made public and
  we know the element name is *Duration of X-ray on* with a VR of **FL**.

For all element categories we can access a particular element in the dataset
through it's tag, which returns a :class:`~pydicom.dataelem.DataElement`
instance::

    >>> elem = ds[0x0008, 0x0016]
    >>> elem
    (0008, 0016) SOP Class UID                       UI: CT Image Storage
    >>> elem.keyword
    'SOPClassUID'
    >>> private_elem = ds[0x0043, 0x104E]
    >>> private_elem
    (0043, 104e) [Duration of X-ray on]              FL: 10.60060977935791
    >>> private_elem.keyword
    ''

We can also access regular elements through their *keyword*::

    >>> elem = ds['SOPClassUID']
    >>> elem
    (0008, 0016) SOP Class UID                       UI: CT Image Storage

This won't work for private elements - they have no keyword - nor
for repeating group elements; because there may be multiple elements with the
same keyword at a given dataset level. So for those elements stick to the
``Dataset[group, element]`` method.

In most cases, the most important thing about an element is it's value::

    >>> elem.value
    '1.2.840.10008.5.1.4.1.1.2'

So for regular elements, pydicom provides a quick way of getting the value by
using the Python dot notation with the keyword::

    >>> ds.SOPClassUID
    '1.2.840.10008.5.1.4.1.1.2'

When you're dealing with regular elements this is the recommended method
for accessing element values, as it's simpler and more human-friendly then
dealing with element tags.

Sequences
---------

When you view some datasets (such as this one), you may see that some of the
elements are indented::

    >>> print(ds)
    ...
    (0010, 1002)  Other Patient IDs Sequence   2 item(s) ----
        (0010, 0020) Patient ID                          LO: 'ABCD1234'
        ---------
        (0010, 0020) Patient ID                          LO: '1234ABCD'
        ---------
    ...

This indicates that those elements are part of a sequence (in this
case part of the (0010,1002) *Other Patient IDs Sequence* element). The
structure of a DICOM dataset can be thought of as similar to XML or other
tree-like formats.

* The top-level dataset contains 0 or more elements:

  * An element may be non-sequence type (VR is not **SQ**), or
  * An element may be a sequence type (VR of **SQ**), contains 0 or
    more items:

    * Each item in the sequence is another dataset, containing 0 or more
      elements:

      * An element may be non-sequence type, or
      * An element may be a sequence type, and so on...

Sequence elements can be accessed in the same manner as non-sequence ones::

    >>> seq = ds['0x0010, 0x1002']
    >>> seq = ds['OtherPatientIDsSequence']

The main difference with sequence elements is their values are a list of zero
or more  :class:`~pydicom.dataset.Dataset` objects and can be accessed using
Python list indexing::

    >>> len(ds.OtherPatientIDsSequence)
    2
    >>> type(ds.OtherPatientIDsSequence[0])
    <class 'pydicom.dataset.Dataset'>
    >>> ds.OtherPatientIDsSequence[0]
    (0010, 0020) Patient ID                          LO: 'ABCD1234'
    (0010, 0022) Type of Patient ID                  CS: 'TEXT'
    >>> ds.OtherPatientIDsSequence[1]
    (0010, 0020) Patient ID                          LO: '1234ABCD'
    (0010, 0022) Type of Patient ID                  CS: 'TEXT'

file_meta
---------

Earlier we saw that by default :func:`~pydicom.filereader.dcmread` only reads
files that are in the DICOM File Format. So what is it that makes a file in
the DICOM File Format? The answer is a file header containing:

* An 128 byte preamble::

    >>> ds.preamble
    b'II*\x00T\x18\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00...

* Followed by a 4 byte ``DICM`` prefix
* Followed by the required DICOM :dcm:`File Meta Information
  <part10/chapter_7.html#table_7.1-1>` elements, which in pydicom are
  stored in a :class:`~pydicom.dataset.Dataset` instance in the
  :attr:`~pydicom.dataset.FileDataset.file_meta` attribute::

    >>> ds.file_meta
    (0002, 0000) File Meta Information Group Length  UL: 192
    (0002, 0001) File Meta Information Version       OB: b'\x00\x01'
    (0002, 0002) Media Storage SOP Class UID         UI: CT Image Storage
    (0002, 0003) Media Storage SOP Instance UID      UI: 1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322
    (0002, 0010) Transfer Syntax UID                 UI: Explicit VR Little Endian
    (0002, 0012) Implementation Class UID            UI: 1.3.6.1.4.1.5962.2
    (0002, 0013) Implementation Version Name         SH: 'DCTOOL100'
    (0002, 0016) Source Application Entity Title     AE: 'CLUNIE1'

As you can see, all the elements in the ``file_meta`` are group ``0x0002``. In
fact, the DICOM File Format header is the only place you should find group
``0x0002`` elements as their presence anywhere else is non-conformant.

Out of all of the elements in the ``file_meta``, the most important is
(0002,0010) *Transfer Syntax UID*, as the :dcm:`transfer syntax
<part05/chapter_10.html>` defines the way the
entire dataset (including the pixel data) has been encoded. Chances are
that at some point you'll need to know it::

    >>> ds.file_meta.TransferSyntaxUID
    '1.2.840.10008.1.2.1'
    >>> ds.file_meta.TransferSyntaxUID.name
    'Explicit VR Little Endian'


Modifying
=========

* modifying datasets
* modifying elements
* adding elements
* deleting elements
* deleting sequence items


Writing
=======

* writing a dataset to file (not in file format)
* writing a dataset to file (in file format)
