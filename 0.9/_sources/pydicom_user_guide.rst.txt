.. _pydicom_user_guide:

==================
Pydicom User Guide
==================

.. rubric:: pydicom object model, description of classes, examples

Dataset
=======

Dataset is the base object in pydicom's object model.
The relationship between Dataset and other objects is:

Dataset (derived from python's `dict`)
   ---> contains DataElement instances
      --> the value of the data element can be one of:
           * a regular value like a number, string, etc.
           * a list of regular values (e.g. a 3-D coordinate)
           * a Sequence instance
              --> a Sequence is a list of Datasets (and so we come full circle)

Dataset is the main object you will work with directly. Dataset is derived 
from python's ``dict``, so it inherits (and overrides some of) the methods 
of ``dict``. In other words it is a collection of key:value pairs, where 
the key value is the DICOM (group,element) tag (as a Tag object, 
described below), and the value is a DataElement instance 
(also described below).

A dataset could be created directly, but you will usually get one by reading 
an existing DICOM file::

    >>> import dicom
    >>> ds = dicom.read_file("rtplan.dcm") # (rtplan.dcm is in the testfiles directory)


You can display the entire dataset by simply printing its string 
(str or repr) value::

    >>> ds
    (0008, 0012) Instance Creation Date              DA: '20030903'
    (0008, 0013) Instance Creation Time              TM: '150031'
    (0008, 0016) SOP Class UID                       UI: RT Plan Storage
    (0008, 0018) SOP Instance UID                    UI: 1.2.777.777.77.7.7777.7777.20030903150023
    (0008, 0020) Study Date                          DA: '20030716'
    (0008, 0030) Study Time                          TM: '153557'
    (0008, 0050) Accession Number                    SH: ''
    (0008, 0060) Modality                            CS: 'RTPLAN'

Note: you can also view DICOM files in a collapsible tree using 
the example program `dicomtree.py 
<http://code.google.com/p/pydicom/source/browse/source/dicom/examples/dicomtree.py>`_.

You can access specific data elements by name or by DICOM tag number::

    >>> ds.PatientsName
    'Last^First^mid^pre'
    >>> ds[0x10,0x10].value
    'Last^First^mid^pre'

In the latter case (using the tag number directly) a DataElement instance 
is returned, so the ``.value`` must be used to get the value.

You can also set values by name or tag number::

    >>> ds.PatientID = "12345"
    >>> ds.SeriesNumber = 5
    >>> ds[0x10,0x10].value = 'Test'

The use of names is possible because pydicom intercepts requests for 
member variables, and checks if they are in the DICOM dictionary. 
It translates the name to a (group,element) number and returns 
the corresponding value for that key if it exists. The names are the 
descriptive text from the dictionary with spaces and apostrophes, 
etc. removed. 

DICOM Sequences are turned into python ``list`` s. For these, the name is 
from the dictionary name with "sequence" removed, and the normal English 
plural added. So "Beam Sequence" becomes "Beams", 
"Referenced Film Box Sequence" becomes "ReferencedFilmBoxes". 
Items in the sequence are referenced by number, beginning at index 0 as per 
python convention.
::

    >>> ds.Beams[0].BeamName
    'Field 1'
    >>> # Same thing with tag numbers:
    >>> ds[0x300a,0xb0][0][0x300a,0xc2].value
    'Field 1'
    >>> # yet another way, using another variable
    >>> beam1=ds[0x300a,0xb0][0]
    >>> beam1.BeamName, beam1[0x300a,0xc2].value
    ('Field 1', 'Field 1')


Since you may not always remember the exact name, Dataset provides 
a handy `dir()` method, useful during interactive sessions 
at the python prompt::

    >>> ds.dir("pat")
    ['PatientSetups', 'PatientsBirthDate', 'PatientsID', 'PatientsName', 'PatientsSex']

``dir`` will return any DICOM tag names in the dataset that have 
the specified string anywhere in the name (case insensitive). 
Calling `dir` with no string will list all tag names available in the dataset. 
You can also see all the names that pydicom knows about by viewing the 
`_dicom_dict.py` file. You could modify that file to add tags 
that pydicom doesn't already know about.

Under the hood, Dataset stores a DataElement object for each item, 
but when accessed by name (e.g. ``ds.PatientsName``) only the `value` 
of that DataElement is returned. If you need the whole DataElement 
(see the DataElement class discussion), you can use Dataset's data_element() 
method or access the item using the tag number::

    >>> data_element = ds.data_element("PatientsName")  # or data_element = ds[0x10,0x10]
    >>> data_element.VR, data_element.value
    ('PN', 'Last^First^mid^pre')

To check for the existence of a particular tag before using it, 
use the `in` keyword::

    >>> "PatientsName" in ds
    True

To remove a data element from the dataset,  use ``del``::

    >>> del ds[0x10,0x1000]
    >>> # OR
    >>> tag = ds.data_element("OtherPatientIDs").tag
    >>> del ds[tag]

To work with pixel data, the raw bytes are available through the usual tag::

    >>> pixel_bytes = ds.PixelData

but to work with them in a more intelligent way, use ``pixel_array`` 
(requires the `NumPy library <http://numpy.org>`_)::

    >>> pix = ds.pixel_array

For more details, see :doc:`working_with_pixel_data`.


DataElement
===========

The DataElement class is not usually used directly in user code, 
but is used extensively by Dataset. 
DataElement is a simple object which stores the following things:

  * tag -- a DICOM tag (as a Tag object)
  * VR -- DICOM value representation -- various number and string formats, etc
  * VM -- value multiplicity. This is 1 for most DICOM tags, but 
    can be multiple, e.g. for coordinates. You do not have to specify this, 
    the DataElement class keeps track of it based on value.
  * value -- the actual value. A regular value like a number or string 
    (or list of them), or a Sequence.
 
Tag
===

The Tag class is derived from python's ``long``, so in effect, it is just 
a number with some extra behaviour:

  * Tag enforces that the DICOM tag fits in the expected 4-byte (group,element)
  * a Tag instance can be created from a long or from a tuple containing 
    the (group,element) separately::

        >>> from dicom.tag import Tag
        >>> t1=Tag(0x00100010) # all of these are equivalent
        >>> t2=Tag(0x10,0x10)
        >>> t3=Tag((0x10, 0x10))
        >>> t1
        (0010, 0010)
        >>> t1==t2, t1==t3
        (True, True)

  * Tag has properties group and element (or elem) to return the group and element portions
  * the ``is_private`` property checks whether the tag represents 
    a private tag (i.e. if group number is odd).
  
Sequence
========
  
Sequence is derived from python's ``list``. The only added functionality is 
to make string representations prettier. Otherwise all the usual methods of 
``list`` like item selection, append, etc. are available.