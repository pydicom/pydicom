Core elements in pydicom
========================

.. rubric:: pydicom object model, description of classes, examples

Dataset
-------

.. currentmodule:: pydicom

:class:`~dataset.Dataset` is the main object you will work with
directly. :class:`~dataset.Dataset` wraps a dictionary, where the key
is the DICOM tag (as a :class:`~pydicom.tag.BaseTag` object,
described below), and the value is the corresponding
:class:`~dataelem.DataElement` instance (also described below).
It implements most of the methods of :class:`dict`, so that it mostly behaves
like a wrapped :class:`dict`. This allows direct access to the data elements
via their tags, as shown below.

.. warning::

  The iterator of a :class:`~dataset.Dataset` yields
  :class:`~dataelem.DataElement` instances, e.g. the values of the
  dictionary instead of the keys normally yielded by iterating a :class:`dict`.

A :class:`~dataset.Dataset` could be created directly, but you will
usually get one by reading an existing DICOM file::

  >>> import pydicom
  >>> from pydicom.data import get_testdata_file
  >>> # get some test data
  >>> filename = get_testdata_file("rtplan.dcm")
  >>> ds = pydicom.dcmread(filename)

You can display the entire dataset by simply printing its string
(:class:`str()<str>` or :func:`repr`) value::

  >>> ds # doctest: +ELLIPSIS
  Dataset.file_meta -------------------------------
  (0002, 0000) File Meta Information Group Length  UL: 156
  (0002, 0001) File Meta Information Version       OB: b'\x00\x01'
  (0002, 0002) Media Storage SOP Class UID         UI: RT Plan Storage
  (0002, 0003) Media Storage SOP Instance UID      UI: 1.2.999.999.99.9.9999.9999.20030903150023
  (0002, 0010) Transfer Syntax UID                 UI: Implicit VR Little Endian
  (0002, 0012) Implementation Class UID            UI: 1.2.888.888.88.8.8.8
  -------------------------------------------------
  (0008, 0012) Instance Creation Date              DA: '20030903'
  (0008, 0013) Instance Creation Time              TM: '150031'
  (0008, 0016) SOP Class UID                       UI: RT Plan Storage
  (0008, 0018) SOP Instance UID                    UI: 1.2.777.777.77.7.7777.7777.20030903150023
  (0008, 0020) Study Date                          DA: '20030716'
  (0008, 0030) Study Time                          TM: '153557'
  (0008, 0050) Accession Number                    SH: ''
  (0008, 0060) Modality                            CS: 'RTPLAN'
  ...

.. note::

    You can also view DICOM files in a collapsible tree using
    the example program :gh:`dcm_qt_tree.py
    <contrib-pydicom/blob/master/plotting-visualization/dcm_qt_tree.py>`.

You can access specific elements by their DICOM keyword or tag number::

  >>> ds.PatientName
  'Last^First^mid^pre'
  >>> ds[0x10,0x10].value
  'Last^First^mid^pre'

When using the tag number directly a :class:`~dataelem.DataElement`
instance is returned, so :attr:`DataElement.value<dataelem.DataElement.value>`
must be used to get the value.

.. warning::

    In *pydicom*, private data elements are displayed with square brackets
    around the name (if the name is known to *pydicom*).  These are shown for
    convenience only; the descriptive name in brackets cannot be used to
    retrieve data elements. See details in :doc:`private_data_elements`.

You can also set an element's value by using the element's keyword or tag
number::

  >>> ds.PatientID = "12345"
  >>> ds.SeriesNumber = 5
  >>> ds[0x10,0x10].value = 'Test'

The use of names is possible because *pydicom* intercepts requests for member
variables, and checks if they are in the DICOM dictionary. It translates the
keyword to a (group,element) tag and returns the corresponding value for
that tag if it exists in the dataset.

See :ref:`sphx_glr_auto_examples_metadata_processing_plot_anonymize.py` for a
usage example of data elements removal and assignation.

.. note::

   To understand using :class:`~sequence.Sequence` in *pydicom*, please refer
   to this object model:

   * :class:`~dataset.Dataset` (wraps a Python :class:`dict`)

     * Contains :class:`~dataelem.DataElement` instances, the value of each
       element can be one of:

       * a regular numeric, string or text value as an :class:`int`,
         :class:`float`, :class:`str`, :class:`bytes`, etc
       * a :class:`list` of regular values (e.g. a 3-D coordinate)
       * a :class:`~sequence.Sequence` instance, where
         :class:`~sequence.Sequence` is a :class:`list` of
         :class:`~dataset.Dataset` instances

         * Where each :class:`~dataset.Dataset` contains
           :class:`~dataelem.DataElement` instances, and so on...

The value of sequence elements is a :class:`~sequence.Sequence`
instance, which wraps a Python :class:`list<list>`. Items in the sequence are
referenced by number, beginning at index ``0`` as per Python convention::

  >>> ds.BeamSequence[0].BeamName
  'Field 1'
  >>> # Or, set an intermediate variable to a dataset in the list
  >>> beam1 = ds.BeamSequence[0]  # First dataset in the sequence
  >>> beam1.BeamName
  'Field 1'

See :ref:`sphx_glr_auto_examples_metadata_processing_plot_sequences.py`.

Using DICOM keywords is the recommended way to access data elements, but you
can also use the tag numbers directly, such as::

  >>> # Same thing with tag numbers - much harder to read:
  >>> # Really should only be used if DICOM keyword not in pydicom dictionary
  >>> ds[0x300a,0xb0][0][0x300a,0xc2].value
  'Field 1'

If you don't remember or know the exact element tag or keyword,
:class:`~dataset.Dataset` provides a handy
:func:`Dataset.dir()<dataset.Dataset.dir>` method, useful during interactive
sessions at the Python prompt::

  >>> ds.dir("pat")
  ['PatientBirthDate', 'PatientID', 'PatientName', 'PatientSetupSequence', 'PatientSex']

:func:`Dataset.dir()<dataset.Dataset.dir>` will return any non-private element
keywords in the dataset that have the specified string anywhere in the
keyword (case insensitive).

.. note::

   Calling :func:`Dataset.dir()<dataset.Dataset.dir>` without passing it an
   argument will return a :class:`list` of all non-private element keywords in
   the dataset.

You can also see all the names that *pydicom* knows about by viewing the
:gh:`_dicom_dict.py<pydicom/blob/master/pydicom/_dicom_dict.py>` file. It
should not normally be necessary, but you can add your own entries to the
DICOM dictionary at run time using :func:`~datadict.add_dict_entry` or
:func:`~datadict.add_dict_entries`. Similarly, you can add private data
elements to the private dictionary using
:func:`~datadict.add_private_dict_entry` or
:func:`~datadict.add_private_dict_entries`.

Under the hood, :class:`~dataset.Dataset` stores a
:class:`~dataelem.DataElement` object for each item, but when
accessed by keyword (e.g. ``ds.PatientName``) only the value of that
:class:`~dataelem.DataElement` is returned. If you need the object itself,
you can use the access the item using either the keyword (for official DICOM
elements) or tag number::

  >>> # reload the data
  >>> ds = pydicom.dcmread(filename)
  >>> elem = ds['PatientName']
  >>> elem.VR, elem.value
  ('PN', 'Last^First^mid^pre')
  >>> # an alternative is to use:
  >>> elem = ds[0x0010,0x0010]
  >>> elem.VR, elem.value
  ('PN', 'Last^First^mid^pre')

To see whether the :class:`~dataset.Dataset` contains a particular element, use
the ``in`` operator with the element's keyword or tag::

  >>> "PatientName" in ds  # or (0x0010,0x0010) in ds
  True

To remove an element from the :class:`~dataset.Dataset`, use the ``del``
operator::

  >>> del ds.SoftwareVersions  # or del ds[0x0018, 0x1020]

To work with (7FE0,0010) *Pixel Data*, the raw :class:`bytes` are available
through the `PixelData` keyword::

  >>> # read data with actual pixel data
  >>> filename = get_testdata_file("CT_small.dcm")
  >>> ds = pydicom.dcmread(filename)
  >>> pixel_bytes = ds.PixelData

However its much more convenient to use
:func:`Dataset.pixel_array<dataset.Dataset.pixel_array>` to return a
:class:`numpy.ndarray` (requires the `NumPy library <http://numpy.org>`_)::

  >>> arr = ds.pixel_array
  >>> arr # doctest: +NORMALIZE_WHITESPACE
  array([[175, 180, 166, ..., 203, 207, 216],
         [186, 183, 157, ..., 181, 190, 239],
         [184, 180, 171, ..., 152, 164, 235],
         ...,
         [906, 910, 923, ..., 922, 929, 927],
         [914, 954, 938, ..., 942, 925, 905],
         [959, 955, 916, ..., 911, 904, 909]], dtype=int16)

For more details, see :doc:`working_with_pixel_data`.

DataElement
-----------

The :class:`~dataelem.DataElement` class is not usually used directly in user
code, but is used extensively by :class:`~dataset.Dataset`.
:class:`~dataelem.DataElement` is a simple object which stores the following
things:

  * :attr:`~dataelem.DataElement.tag` -- the element's tag (as a
    :class:`~pydicom.tag.BaseTag` object).
  * :attr:`~dataelem.DataElement.VR` -- the element's Value Representation
    -- a two letter :class:`str` that describes to the format of the stored
    value.
  * :attr:`~dataelem.DataElement.VM` -- the element's Value Multiplicity as
    an :class:`int`. This is automatically determined from the contents of
    the :attr:`~dataelem.DataElement.value`.
  * :attr:`~dataelem.DataElement.value` -- the element's actual value.
    A regular value like a number or string (or :class:`list` of them if the
    VM > 1), or a :class:`~sequence.Sequence`.

Tag
---

:func:`~tag.Tag` is not generally used directly in user code, as
:func:`BaseTags<tag.BaseTag>` are automatically created when you assign or read
elements using their keywords as illustrated in sections above.

The :class:`~tag.BaseTag` class is derived from :class:`int`,
so in effect, it is just a number with some extra behavior:

  * :func:`~tag.Tag` is used to create instances of :class:`~tag.BaseTag` and
    enforces the expected 4-byte (group,element) structure.
  * A :class:`~tag.BaseTag` instance can be created from an :class:`int` or a
    :class:`tuple` containing the (group,element), or from the DICOM keyword::

      >>> from pydicom.tag import Tag
      >>> t1 = Tag(0x00100010) # all of these are equivalent
      >>> t2 = Tag(0x10,0x10)
      >>> t3 = Tag((0x10, 0x10))
      >>> t4 = Tag("PatientName")
      >>> t1
      (0010, 0010)
      >>> type(t1)
      <class `pydicom.tag.BaseTag`>
      >>> t1==t2, t1==t3, t1==t4
      (True, True, True)

  * :attr:`BaseTag.group<tag.BaseTag.group>` and
    :attr:`BaseTag.elem<tag.BaseTag.elem>` to return the group and element
    portions of the tag.
  * The :attr:`BaseTag.is_private<tag.BaseTag.is_private>` property checks
    whether the tag represents a private tag (i.e. if group number is odd).

Sequence
--------

:class:`~sequence.Sequence` is derived from Python's :class:`list`.
The only added functionality is to make string representations prettier.
Otherwise all the usual methods of :class:`list` like item selection, append,
etc. are available.

For examples of accessing data nested in sequences, see
:ref:`sphx_glr_auto_examples_metadata_processing_plot_sequences.py`.
