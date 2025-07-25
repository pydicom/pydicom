
Reading a dataset
=================

.. note::

    We're going to be using example DICOM datasets that are included with
    *pydicom*, such as :gh:`CT_small.dcm<pydicom/blob/main/src/pydicom/data/test_files/CT_small.dcm>`.
    You can get the local file path to these datasets by using the :func:`~pydicom.examples.get_path`
    function to return the path as a :class:`pathlib.Path` (your path may vary)::

        >>> from pydicom import examples
        >>> path = examples.get_path("ct")
        >>> path
        PosixPath('/path/to/pydicom/data/test_files/CT_small.dcm')

    When using *pydicom* to read your own data, use the path to those files directly
    instead.


To read the DICOM dataset at a given file path (as a :class:`str` or :class:`pathlib.Path`)
we use :func:`~pydicom.filereader.dcmread`, which returns a
:class:`~pydicom.dataset.FileDataset` instance::

    >>> from pydicom import dcmread, examples
    >>> path = get_path("ct")
    >>> ds = dcmread(path)

:func:`~pydicom.filereader.dcmread` can also handle file-likes::

    >>> with open(path, 'rb') as f:
    ...     ds = dcmread(f)

And can be used as a context manager::

    >>> with dcmread(path) as ds:
    ...    type(ds)
    ...
    <class 'pydicom.dataset.FileDataset'>

By default, :func:`~pydicom.filereader.dcmread` will read any DICOM dataset
stored in accordance with the :dcm:`DICOM File Format<part10/chapter_7.html>`.
However, you may occasionally read a file that gives you the following
exception:

.. code-block:: pycon

    >>> no_meta_path = examples.get_path('no_meta')
    >>> ds = dcmread(no_meta_path)
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File ".../pydicom/filereader.py", line 887, in dcmread
        force=force, specific_tags=specific_tags)
      File ".../pydicom/filereader.py", line 678, in read_partial
        preamble = read_preamble(fileobj, force)
      File ".../pydicom/filereader.py", line 631, in read_preamble
        raise InvalidDicomError("File is missing DICOM File Meta Information "
      pydicom.errors.InvalidDicomError: File is missing DICOM File Meta Information
      header or the 'DICM' prefix is missing from the header. Use force=True to
      force reading.

This indicates that either:

* The file isn't a DICOM file, or
* The file contains DICOM data but isn't in the DICOM File Format

If you're sure the file contains DICOM data, you can use the `force`
keyword parameter to force reading::

  >>> ds = dcmread(no_meta_path, force=True)

A note of caution about using ``force=True``; because *pydicom* uses a
deferred-read system, **no exceptions** will be raised at the time of reading,
no matter what the contents of the file are:

.. code-block:: pycon

    >>> with open('not_dicom.txt', 'w') as not_dicom:
    ...    not_dicom.write('This is not a DICOM file!')
    ...
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
      KeyError: "Unknown DICOM tag (6854,7369) can't look up VR"


Viewing and accessing
=====================

The ``CT_small.dcm`` dataset is also included as an example ``FileDataset``:

    >>> from pydicom import examples
    >>> ds = examples.ct
    >>> type(ds)
    <class 'pydicom.dataset.FileDataset'>
    >>> ds.filename
    '/path/to/pydicom/data/test_files/CT_small.dcm'

You can view the contents of the entire dataset by using :func:`print`::

    >>> print(ds)
    Dataset.file_meta -------------------------------
    (0002,0000) File Meta Information Group Length  UL: 192
    (0002,0001) File Meta Information Version       OB: b'\x00\x01'
    (0002,0002) Media Storage SOP Class UID         UI: CT Image Storage
    (0002,0003) Media Storage SOP Instance UID      UI: 1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322
    (0002,0010) Transfer Syntax UID                 UI: Explicit VR Little Endian
    (0002,0012) Implementation Class UID            UI: 1.3.6.1.4.1.5962.2
    (0002,0013) Implementation Version Name         SH: 'DCTOOL100'
    (0002,0016) Source Application Entity Title     AE: 'CLUNIE1'
    -------------------------------------------------
    (0008,0005) Specific Character Set              CS: 'ISO_IR 100'
    (0008,0008) Image Type                          CS: ['ORIGINAL', 'PRIMARY', 'AXIAL']
    (0008,0012) Instance Creation Date              DA: '20040119'
    (0008,0013) Instance Creation Time              TM: '072731'
    (0008,0014) Instance Creator UID                UI: 1.3.6.1.4.1.5962.3
    (0008,0016) SOP Class UID                       UI: CT Image Storage
    ...
    (0010,1002)  Other Patient IDs Sequence   2 item(s) ----
        (0010,0020) Patient ID                          LO: 'ABCD1234'
        (0010,0022) Type of Patient ID                  CS: 'TEXT'
        ---------
        (0010,0020) Patient ID                          LO: '1234ABCD'
        (0010,0022) Type of Patient ID                  CS: 'TEXT'
        ---------
    ...
    (0043,0010) Private Creator                     LO: 'GEMS_PARM_01'
    (0043,1010) [Window value]                      US: 400
    ...
    (7FE0,0010) Pixel Data                          OW: Array of 32768 elements
    (FFFC,FFFC) Data Set Trailing Padding           OB: Array of 126 elements

The print output shows a list of the :dcm:`Data Elements
<part05/chapter_7.html#sect_7.1>` (or *elements* for short) present in the
dataset, one element per line. The format of each line is:

* **(0008,0005)**: The element's :dcm:`tag<part05/chapter_7.html#sect_7.1.1>`,
  as (group number, element number) in hexadecimal
* **Specific Character Set**: the element's name, if known
* **CS**: The element's :dcm:`Value Representation<part05/sect_6.2.html>` (VR),
  if known
* **'ISO_IR_100'**: the element's stored value, or the length of the value if it's too
  long to show concisely

Elements
--------

There are three categories of elements:

* **Standard elements** such as (0008,0016) *SOP Class UID*. These elements
  are registered in :dcm:`Part 6<part06/chapter_6.html>` of the official DICOM Standard,
  have a tag with an even group number and are unique at each level of the dataset.
* **Repeating group elements** such as (60xx,3000) *Overlay Data* (not found
  in this dataset). :dcm:`Repeating group<part05/sect_7.6.html>` elements are
  also registered in the official DICOM Standard, however they have a tag with a group
  number defined over a range rather than a fixed value.
  For example, there may be multiple *Overlay Data* elements at a given level
  of the dataset as long as each has its own unique group number; ``0x6000``,
  ``0x6002``, ``0x6004``, or any even value up to ``0x601E``.
* **Private elements** such as (0043,1010) *[Window value]*.
  :dcm:`Private elements<part05/sect_7.8.html>` have a tag with an odd group number,
  aren't registered in the official DICOM Standard, and are instead created
  privately, as specified by the (gggg,0010-00FF) *Private Creator* element.

  * If the private creator is unknown then the element name will be *Private
    tag data* and the VR **UN**.
  * If the private creator is known then the element name will be surrounded
    by square brackets, e.g. *[Window value]* and the VR will be as
    shown.

For all element categories, we can access a particular element in the dataset
through its tag, which returns a :class:`~pydicom.dataelem.DataElement`
instance::

    >>> elem = ds[0x0008, 0x0016]
    >>> elem
    (0008,0016) SOP Class UID                       UI: CT Image Storage
    >>> elem.tag
    (0008,0016)
    >>> elem.keyword
    'SOPClassUID'
    >>> private_elem = ds[0x0043, 0x1010]
    >>> private_elem
    (0043,1010) [Window value]                      US: 400
    >>> private_elem.keyword
    ''

We can also access standard elements through their *keyword*. The keyword is
usually the same as the element's name without any spaces, but there are
exceptions - such as (0010,0010) *Patient's Name* having a keyword of
*PatientName*. A list of keywords for all standard elements can be found
:dcm:`here<part06/chapter_6.html>`.

::

    >>> elem = ds['SOPClassUID']
    >>> elem
    (0008,0016) SOP Class UID                       UI: CT Image Storage

Because of the lack of a unique keyword, this won't work for private or
repeating group elements. So for those elements stick to the
``Dataset[group number, element number]`` method.

In most cases, the important thing about an element is its value::

    >>> elem.value
    '1.2.840.10008.5.1.4.1.1.2'

For standard elements, you can use the Python dot notation with the keyword to
get the value::

    >>> ds.SOPClassUID
    '1.2.840.10008.5.1.4.1.1.2'

This is the recommended method of accessing the value of standard elements.
It's simpler and more human-friendly then dealing with element tags and later
on you'll see how you can use the keyword to do far more than just accessing the value.

Elements may also be multi-valued - that is, have a :dcm:`Value Multiplicity
<part05/sect_6.4.html>` (VM) > 1::

    >>> ds.ImageType
    ['ORIGINAL', 'PRIMARY', 'AXIAL']
    >>> ds['ImageType'].VM
    3

The items for multi-valued elements can be accessed using the standard Python
:class:`~list` methods::

    >>> ds.ImageType[1]
    'PRIMARY'


Sequences
---------

When viewing a dataset, you may see that some of the elements are indented::

    >>> print(ds)
    ...
    (0010,1002)  Other Patient IDs Sequence   2 item(s) ----
        (0010,0020) Patient ID                          LO: 'ABCD1234'
        (0010,0022) Type of Patient ID                  CS: 'TEXT'
        ---------
        (0010,0020) Patient ID                          LO: '1234ABCD'
        (0010,0022) Type of Patient ID                  CS: 'TEXT'
        ---------
    ...

This indicates that those elements are part of a sequence, in this case
part of the *Other Patient IDs Sequence* element. Sequence elements have a
VR of **SQ** and have a name that ends in the word *Sequence*.
DICOM datasets use the `tree data structure
<https://en.wikipedia.org/wiki/Tree_(data_structure)>`_, with non-sequence
elements acting as leaves and sequence elements acting as the nodes where
branches start.

* The top-level (root) dataset contains 0 or more elements:

  * An element may be non-sequence type; its VR is not **SQ** (leaf), or
  * An element may be a sequence type; its VR is **SQ** and it contains 0 or
    more items (branches):

    * Each item in the sequence is another dataset, containing 0 or more
      elements:

      * An element may be non-sequence type, or
      * An element may be a sequence type, and so on...

Sequence elements can be accessed in the same manner as non-sequence ones::

    >>> elem = ds[0x0010, 0x1002]
    >>> elem = ds['OtherPatientIDsSequence']

The main difference between sequence and non-sequence elements is that their value is
a list-like object containing zero or more :class:`~pydicom.dataset.Dataset` instances,
which can be accessed using the standard Python :class:`list` methods::

    >>> len(ds.OtherPatientIDsSequence)
    2
    >>> type(ds.OtherPatientIDsSequence[0])
    <class 'pydicom.dataset.Dataset'>
    >>> ds.OtherPatientIDsSequence[0]
    (0010,0020) Patient ID                          LO: 'ABCD1234'
    (0010,0022) Type of Patient ID                  CS: 'TEXT'
    >>> ds.OtherPatientIDsSequence[1]
    (0010,0020) Patient ID                          LO: '1234ABCD'
    (0010,0022) Type of Patient ID                  CS: 'TEXT'

Dataset.file_meta
-----------------

Earlier we saw that by default :func:`~pydicom.filereader.dcmread` only reads
files that are in the :dcm:`DICOM File Format<part10/chapter_7.html>`. So what's the
difference between a DICOM dataset written to file and one written in the DICOM File Format?
The answer is a file header containing:

* An 128 byte preamble::

    >>> ds.preamble
    b'II*\x00T\x18\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00...

* Followed by a 4 byte ``DICM`` prefix
* Followed by the required DICOM :dcm:`File Meta Information
  <part10/chapter_7.html#table_7.1-1>` elements, which in *pydicom* are
  stored in a :class:`~pydicom.dataset.FileMetaDataset` instance in the
  :attr:`~pydicom.dataset.FileDataset.file_meta` attribute::

    >>> ds.file_meta
    (0002,0000) File Meta Information Group Length  UL: 192
    (0002,0001) File Meta Information Version       OB: b'\x00\x01'
    (0002,0002) Media Storage SOP Class UID         UI: CT Image Storage
    (0002,0003) Media Storage SOP Instance UID      UI: 1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322
    (0002,0010) Transfer Syntax UID                 UI: Explicit VR Little Endian
    (0002,0012) Implementation Class UID            UI: 1.3.6.1.4.1.5962.2
    (0002,0013) Implementation Version Name         SH: 'DCTOOL100'
    (0002,0016) Source Application Entity Title     AE: 'CLUNIE1'

As you can see, all the elements in the ``file_meta`` have tags with a group number of
``0x0002``. In fact, the DICOM File Format header is the only place you should find group
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
    >>> ds.file_meta.TransferSyntaxUID.keyword
    'ExplicitVRLittleEndian'

Modifying a dataset
===================

Modifying elements
------------------

We can modify the value of any element by retrieving it and setting the value::

    >>> elem = ds[0x0010, 0x0010]
    >>> elem.value
    'CompressedSamples^CT1'
    >>> elem.value = 'Citizen^Jan'
    >>> elem
    (0010,0010) Patient's Name                      PN: 'Citizen^Jan'

Which raises the question; what *kind* of value should be used to set an element's value?
In the above example we used a :class:`str` to set the *Patient's Name*, but what about
for other elements? Should they all be strings too? (Hint: no).

The allowed object type to use for an element's value depends on its :dcm:`Value Representation
<part05/sect_6.2.html>`. We saw that *Patient's Name* has a VR of **PN**. By checking the
:doc:`Element VR and Python types</guides/element_value_types>` guide,
we see that elements with a VR of **PN** can be set using:

* ``None``, :class:`str` or :class:`~pydicom.valuerep.PersonName` if the *Value
  Multiplicity* (VM) is 1, or
* ``list[str]`` or ``list[PersonName]`` for VM > 1.

Each standard element also has restrictions on its allowed VM, given in :dcm:`Part 6
<part06/chapter_6.html>`. For *Patient's Name* the VM must always be 1, so the
allowed types are ``None``, ``str`` or ``PersonName``. If instead we look up
(0018,106C) *Synchronization Channel*, we see the VR is **US** and the allowed VM 2,
so using the *Element VR and Python types* guide, we see the only type that may be
used is ``list[int]``.

For standard elements it's simpler to use the keyword to set the value::

    >>> ds.PatientName = 'Citizen^Snips'
    >>> elem
    (0010,0010) Patient's Name                      PN: 'Citizen^Snips'

Multi-valued elements can be set using a :class:`list` or modified using the
:class:`list` methods::

    >>> ds.ImageType = ['ORIGINAL', 'PRIMARY', 'LOCALIZER']  # VR 'CS'
    >>> ds.ImageType
    ['ORIGINAL', 'PRIMARY', 'LOCALIZER']
    >>> ds.ImageType[1] = 'DERIVED'
    >>> ds.ImageType
    ['ORIGINAL', 'DERIVED', 'LOCALIZER']
    >>> ds.ImageType.insert(1, 'PRIMARY')
    >>> ds.ImageType
    ['ORIGINAL', 'PRIMARY', 'DERIVED', 'LOCALIZER']

Similarly, for sequence elements::

    >>> from pydicom.dataset import Dataset
    >>> ds.OtherPatientIDsSequence = [Dataset(), Dataset()]  # VR 'SQ'
    >>> ds.OtherPatientIDsSequence.append(Dataset())
    >>> len(ds.OtherPatientIDsSequence)
    3

The items in a sequence are always :class:`~pydicom.dataset.Dataset` instances, if you
try to add any other type to a sequence you'll get an exception::

    >>> ds.OtherPatientIDsSequence.append('Hello world?')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File ".../pydicom/multival.py", line 63, in append
        self._list.append(self.type_constructor(val))
      File ".../pydicom/sequence.py", line 15, in validate_dataset
        raise TypeError('Sequence contents must be Dataset instances.')
      TypeError: Sequence contents must be Dataset instances.

You can set any element value as empty by using ``None`` (sequence elements
will automatically be converted to an empty list when you do so)::

    >>> ds.PatientName = None
    >>> elem
    (0010,0010) Patient's Name                      PN: None
    >>> ds.OtherPatientIDsSequence = None
    >>> len(ds.OtherPatientIDsSequence)
    0

Elements with a value of ``None``, ``b''``, ``''`` or ``[]`` will still be
written to file, but will have an empty value and zero length.


Adding elements
---------------

Standard and repeating group elements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
New elements of any category can be added to the dataset with the
:meth:`~pydicom.dataset.Dataset.add_new` method, which takes the tag, VR and
value to use for the new element.

Let's say we wanted to add the (0028,1050) *Window Center* standard element. We
already know the tag is (0028,1050), but how we get the VR and how do we
know the Python :class:`type` to use for the value?

There are two ways to get an element's VR:

* You can use :dcm:`Part 6 of the DICOM Standard<part06/chapter_6.html>`
  and search for the element
* Alternatively, you can use the :func:`~pydicom.datadict.dictionary_VR`
  function to look it up

::

    >>> from pydicom.datadict import dictionary_VR
    >>> dictionary_VR([0x0028, 0x1050])
    'DS'

As we saw earlier, you can use the :doc:`Element VR and Python types
</guides/element_value_types>` guide to find the Python type to use for a given VR.
For **DS** we can use a :class:`str`, :class:`int` or :class:`float`, so to add the new element::

    >>> ds.add_new([0x0028, 0x1050], 'DS', "100.0")
    >>> elem = ds[0x0028, 0x1050]
    >>> elem
    (0028,1050) Window Center                       DS: "100.0"

Some VRs also require the value be formatted correctly. For example, elements with
a VR of **DA** should use the YYYYMMDD format and only allow ASCII characters 0 to 9 (unless
used for query matching). The full list of VRs and their formatting requirements can be found in
:dcm:`Section 6.2 of Part 5 of the DICOM Standard<part05/sect_6.2.html>`.


Alternative for standard elements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Adding elements with :meth:`~pydicom.dataset.Dataset.add_new` is a lot of
work, so for standard elements you can just use the keyword
and *pydicom* will do the lookup for you::

    >>> 'WindowWidth' in ds
    False
    >>> ds.WindowWidth = 500
    >>> ds['WindowWidth']
    (0028,1051) Window Width                        DS: "500.0"

Notice how we can also use the element keyword with the Python
:func:`in<operator.__contains__>` operator to see if a standard element is in
the dataset? This also works with element tags, so private and repeating group
elements are also covered::

    >>> [0x0043, 0x1010] in ds
    True

Sequences
~~~~~~~~~
Because sequence items are also :class:`~pydicom.dataset.Dataset` instances,
you can use the same methods on them as well.

    >>> seq = ds.OtherPatientIDsSequence
    >>> seq += [Dataset(), Dataset(), Dataset()]
    >>> seq[0].PatientID = 'Citizen^Jan'
    >>> seq[0].TypeOfPatientID = 'TEXT'
    >>> seq[1].PatientID = 'CompressedSamples^CT1'
    >>> seq[1].TypeOfPatientID = 'TEXT'
    >>> seq[0]
    (0010,0020) Patient ID                          LO: 'Citizen^Jan'
    (0010,0022) Type of Patient ID                  CS: 'TEXT'
    >>> seq[1]
    (0010,0020) Patient ID                          LO: 'CompressedSamples^CT1'
    (0010,0022) Type of Patient ID                  CS: 'TEXT'

Private elements
~~~~~~~~~~~~~~~~

When adding private elements, the DICOM Standard :dcm:`requires<part05/sect_7.8.html#sect_7.8.1>`
a (gggg,0010-00FF) *Private Creator* element also be added to identify and reserve the
``gggg`` section of private tags. *pydicom* provides the
:meth:`~pydicom.dataset.Dataset.add_new_private` convenience method to help manage this::

    >>> ds.add_new_private("Private Creator Name", 0x000B, 0x01, "my value", "SH")
    >>> ds
    ...
    (000B,0010) Private Creator                     LO: 'Private Creator Name'
    (000B,1001) Private tag data                    SH: 'my value'
    ...


Deleting elements
-----------------

All elements can be deleted with the :func:`del<operator.__delitem__>`
operator in combination with the element tag::

    >>> del ds[0x0043, 0x1010]
    >>> [0x0043, 0x1010] in ds
    False

For standard elements you can use the keyword instead::

    >>> del ds.WindowCenter
    >>> 'WindowCenter' in ds
    False

And you can remove items from sequences and multi-valued elements using your
preferred :class:`list` method::

    >>> del ds.OtherPatientIDsSequence[2]
    >>> len(seq)
    2
    >>> del ds.ImageType[2]
    >>> ds.ImageType
    ['ORIGINAL', 'PRIMARY', 'LOCALIZER']


Writing a dataset
=================

After changing the dataset, the final step is to write the modifications back
to file. This can be done by using :meth:`~pydicom.dataset.Dataset.save_as` to
write the dataset to the supplied path::

    >>> ds.save_as('out.dcm')

You can also write to any Python file-like::

    >>> with open('out.dcm', 'wb') as f:
    ...    ds.save_as(f)
    ...

::

    >>> from io import BytesIO
    >>> out = BytesIO()
    >>> ds.save_as(out)

By default, :meth:`~pydicom.dataset.Dataset.save_as` will write the dataset
as-is. This means that even if your dataset is not conformant to the
:dcm:`DICOM File Format<part10/chapter_7.html>` it will
still be written exactly as given. To be certain you're writing the
dataset in the DICOM File Format you can use the `enforce_file_format` keyword
parameter::

    >>> ds.save_as('out.dcm', enforce_file_format=True)

This will attempt to automatically add in any missing required group
``0x0002`` File Meta Information elements and set a blank 128 byte preamble (if
required). If it's unable to do so then an exception will be raised:

.. code-block:: pycon

    >>> del ds.file_meta
    >>> ds.save_as('out.dcm', enforce_file_format=True)
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File ".../pydicom/dataset.py", line 2452, in save_as
        pydicom.dcmwrite(
      File ".../pydicom/filewriter.py", line 1311, in dcmwrite
        validate_file_meta(file_meta, enforce_standard=True)
      File ".../pydicom/dataset.py", line 3204, in validate_file_meta
        raise AttributeError(
    AttributeError: Required File Meta Information elements are either missing
    or have an empty value: (0002,0010) Transfer Syntax UID

The exception message contains the required element(s) that need to be added,
usually this will only be the *Transfer Syntax UID*. It's an important element,
so get in the habit of making sure it's there and correct.

Because we deleted the :attr:`~pydicom.dataset.FileDataset.file_meta` dataset
we need to add it back::

    >>> from pydicom.dataset import FileMetaDataset
    >>> ds.file_meta = FileMetaDataset()

And now we can add our *Transfer Syntax UID* element and save to file::

    >>> ds.file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.1'
    >>> ds.save_as('out.dcm', enforce_file_format=True)
