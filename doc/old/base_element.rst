Core elements in pydicom
========================

.. rubric:: pydicom object model, description of classes, examples

Dataset
-------

.. currentmodule:: pydicom

:class:`dataset.Dataset` is the main object you will work with directly.
Dataset wraps a dictionary, where the key is the DICOM (group,element)
tag (as a Tag object, described below), and the value is a DataElement instance
(also described below). It implements most of the methods of ``dict``, so
that it mostly behaves like the wrapped ``dict``. This allows direct access
to the data elements via the the tags, as shown below.

.. note::

  The iterator of a ``DataSet`` yields ``DataElement`` values, e.g. the
  values of the dictionary, as opposed to the keys yielded by a ``dict``
  iterator.

A dataset could be created directly, but you will usually get one by reading
an existing DICOM file::

  >>> import pydicom
  >>> from pydicom.data import get_testdata_files
  >>> # get some test data
  >>> filename = get_testdata_files("rtplan.dcm")[0]
  >>> ds = pydicom.dcmread(filename)

You can display the entire dataset by simply printing its string
(str or repr) value::

  >>> ds # doctest: +ELLIPSIS
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
    the example program `dcm_qt_tree.py
    <https://github.com/pydicom/contrib-pydicom/blob/master/plotting-visualization/dcm_qt_tree.py>`_.

You can access specific data elements by name (DICOM 'keyword') or by DICOM tag
number::

  >>> ds.PatientName
  'Last^First^mid^pre'
  >>> ds[0x10,0x10].value
  'Last^First^mid^pre'

In the latter case (using the tag number directly) a DataElement instance is
returned, so the ``.value`` must be used to get the value.

.. note::

    In pydicom, private data elements are displayed with square brackets
    around the name (if the name is known to pydicom).  These are shown for convenience only;
    the descriptive name in brackets cannot be used to retrieve data elements.
    See details in :doc:`private_data_elements`.

You can also set values by name (DICOM keyword) or tag number::

  >>> ds.PatientID = "12345"
  >>> ds.SeriesNumber = 5
  >>> ds[0x10,0x10].value = 'Test'

The use of names is possible because pydicom intercepts requests for member
variables, and checks if they are in the DICOM dictionary. It translates the
keyword to a (group,element) number and returns the corresponding value for
that key if it exists.

See :ref:`sphx_glr_auto_examples_metadata_processing_plot_anonymize.py` for a
usage example of data elements removal and assignation.

.. note::

   To understand using :class:`sequence.Sequences` in pydicom, please refer to
   this object model:
   :class:`dataset.Dataset` (wraps a Python ``dict``)

    * ---> contains DataElement instances

      * --> the value of the data element can be one of:

          * a regular value like a number, string, etc.
          * a list of regular values (e.g. a 3-D coordinate)
          * a Sequence instance

          * --> a Sequence is a list of :class:`dataset.Dataset` (and so we come full circle)

DICOM :class:`sequence.Sequences` are turned into Python ``list`` s. Items in
the sequence are referenced by number, beginning at index 0 as per Python
convention::

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

If you don't remember or know the exact tag name (aka DICOM keyword), :class:`dataset.Dataset`
provides a handy :func:`dataset.Dataset.dir` method, useful during interactive
sessions at the Python prompt::

  >>> ds.dir("pat")
  ['PatientBirthDate', 'PatientID', 'PatientName', 'PatientSetupSequence', 'PatientSex']

:func:`dataset.Dataset.dir` will return any DICOM tag names in the dataset that
have the specified string anywhere in the name (case insensitive).

.. note::

   Calling :func:`dataset.Dataset.dir` with no string will list all tag names
   available in the dataset.

You can also see all the names that pydicom knows about by viewing the
``_dicom_dict.py`` file. It should not normally be necessary, but you can add
your own entries to the DICOM dictionary at run time using :func:`datadict.add_dict_entries`
or :func:`datadict.add_dict_entry`.  Similarly, you can add private data elements
to the private dictionary using :func:`datadict.add_private_dict_entries` or
:func:`datadict.add_private_dict_entries`.

Under the hood, :class:`dataset.Dataset` stores a DataElement object for each
item, but when accessed by name (e.g. ``ds.PatientName``) only the ``value`` of
that :class:`dataelem.DataElement` is returned. If you need the whole
:mod:`dataelem` (see the :class:`dataelem.DataElement` discussion), you can
use the :func:`dataset.Dataset.data_element` method or access the item using
the tag number::

  >>> # reload the data
  >>> ds = pydicom.dcmread(filename)
  >>> data_element = ds.data_element("PatientName")
  >>> data_element.VR, data_element.value
  ('PN', 'Last^First^mid^pre')
  >>> # an alternative is to use:
  >>> data_element = ds[0x10,0x10]
  >>> data_element.VR, data_element.value
  ('PN', 'Last^First^mid^pre')

To check for the existence of a particular tag before using it,
use the `in` keyword::

  >>> "PatientName" in ds
  True

To remove a data element from the dataset,  use python's `del` statement::

  >>> del ds.SoftwareVersions   # or del ds[0x0018, 0x1020]

To work with pixel data, the raw bytes are available through the usual tag::

  >>> # read data with actual pixel data
  >>> filename = get_testdata_files("CT_small.dcm")[0]
  >>> ds = pydicom.dcmread(filename)
  >>> pixel_bytes = ds.PixelData

but to work with them in a more intelligent way, use :func:`Dataset.pixel_array`
(requires the `NumPy library <http://numpy.org>`_)::

  >>> pix = ds.pixel_array
  >>> pix # doctest: +NORMALIZE_WHITESPACE
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

The :class:`dataelem.DataElement` class is not usually used directly in user
code, but is used extensively by
:class:`dataset.Dataset`. :class:`dataelem.DataElement` is a simple object
which stores the following things:

  * tag -- a DICOM tag (as a Tag object)
  * VR -- DICOM value representation -- various number and string formats, etc
  * VM -- value multiplicity. This is 1 for most DICOM tags, but
    can be multiple, e.g. for coordinates. You do not have to specify this,
    the DataElement class keeps track of it based on value.
  * value -- the actual value. A regular value like a number or string
    (or list of them), or a Sequence.

Tag
---

Tag is not generally used directly in user code, as Tags are automatically created
when you assign or read data elements using the DICOM keywords as illustrated in
sections above.

The Tag class is derived from Python's ``int``, so in effect, it is just
a number with some extra behaviour:

  * Tag enforces that the DICOM tag fits in the expected 4-byte (group,element)
  * A Tag instance can be created from an int or a tuple containing
    the (group,element), or from the DICOM keyword::

      >>> from pydicom.tag import Tag
      >>> t1 = Tag(0x00100010) # all of these are equivalent
      >>> t2 = Tag(0x10,0x10)
      >>> t3 = Tag((0x10, 0x10))
      >>> t4 = Tag("PatientName")
      >>> t1
      (0010, 0010)
      >>> t1==t2, t1==t3, t1==t4
      (True, True, True)

  * Tag has properties group and element (or elem) to return the group and
    element portions
  * The ``is_private`` property checks whether the tag represents
    a private tag (i.e. if group number is odd).

Sequence
--------

Sequence is derived from Python's ``list``. The only added functionality is
to make string representations prettier. Otherwise all the usual methods of
``list`` like item selection, append, etc. are available.

For examples of accessing data nested in sequences, see
:ref:`sphx_glr_auto_examples_metadata_processing_plot_sequences.py`.
