============================
DICOM File-sets and DICOMDIR
============================

This tutorial is about DICOM File-sets and covers

* An introduction to DICOM File-sets and the DICOMDIR file
* Loading a File-set using the :class:`~pydicom.fileset.FileSet` class and
  accessing its managed SOP instances
* Modifying an existing File-set
* Creating a new File-set

It's assumed that you're already familiar with the :doc:`dataset basics
<dataset_basics>`.

**References**

* :dcm:`Basic Directory IOD<chtml/part03/chapter_F.html>`
* :dcm:`DICOM File Service<part10/chapter_8.html>`
* :dcm:`Media Formats and Physical Media for Media Interchange
  <part12/ps3.12.html>`

The DICOM File-set
==================

A File-set is a collection of DICOM files that share a common naming
space. They're frequently seen on the DVDs containing DICOM data that
are given to a patient after a medical procedure (such as an MR or
ultrasound), but are also used elsewhere. The specification for File-sets is
given in :dcm:`Part 10 of the DICOM Standard<part10/chapter_8.html>`.

The DICOMDIR file
-----------------

.. note::

    Despite its name, a DICOMDIR file is not a file system directory and
    can be read using :func:`~pydicom.filereader.dcmread` like any other DICOM
    dataset

Every File-set must contain a single file with the filename ``DICOMDIR``, the
location of which is dependent on the type of media used to store the File-set.
For the most commonly used media (DVD, CD, USB, PC file system, etc), the
DICOMDIR file will be in the root directory of the File-set. For other
media types, :dcm:`Part 12 of the DICOM Standard<part12/ps3.12.html>`
specifies where the DICOMDIR must be located.

.. warning::

    It's **strongly recommended** that you avoid making changes to a DICOMDIR
    dataset directly unless you know what you're doing. Even minor changes may
    require recalculating the offsets for each directory record. Use the
    :class:`~pydicom.fileset.FileSet` methods (see below) instead.

The DICOMDIR file is used to summarize the contents of the File-set, and is a
*Media Storage Directory* instance that follows the
:dcm:`Basic Directory IOD<chtml/part03/chapter_F.html>`.

.. code-block:: python

    >>> from pydicom import dcmread
    >>> from pydicom.data import get_testdata_file
    >>> path = get_testdata_file("DICOMDIR")
    >>> ds = dcmread(path)
    >>> ds.file_meta.MediaStorageSOPClassUID.name
    'Media Storage Directory Storage'

The most important element in a DICOMDIR is the (0004,1220) *Directory
Record Sequence*; each item in the sequence is a *directory record*,
and one or more records are used to briefly describe the available SOP
Instances and their location within the File-set's directory structure. Each
record has a *record type* given by the (0004,1430) *Directory Record Type*
element, and different records are related to each other using the hierarchy
given in :dcm:`Table F.4-1<part03/sect_F.4.html#table_F.4-1>`.

.. code-block:: python

    >>> print(ds.DirectoryRecordSequence[0])
    (0004, 1400) Offset of the Next Directory Record UL: 3126
    (0004, 1410) Record In-use Flag                  US: 65535
    (0004, 1420) Offset of Referenced Lower-Level Di UL: 510
    (0004, 1430) Directory Record Type               CS: 'PATIENT'
    (0008, 0005) Specific Character Set              CS: 'ISO_IR 100'
    (0010, 0010) Patient's Name                      PN: 'Doe^Archibald'
    (0010, 0020) Patient ID                          LO: '77654033'

Here we see a ``'PATIENT'`` record, which from :dcm:`Table F.5-1
<part03/sect_F.5.html#table_F.5-1>` we see must also contain *Patient's Name*
and *Patient ID* elements. The full list of available record types and their
requirements is in :dcm:`Annex F.5 of Part 3 of the DICOM Standard
<part03/sect_F.5.html>`.

FileSet
=======

While it's possible to access everything within a File-set using the DICOMDIR
dataset, making changes to an existing File-set becomes complicated very
quickly. A more user-friendly way to interact with one is via the
:class:`~pydicom.fileset.FileSet` class.


Loading existing File-sets
--------------------------

To loading a existing File-set simply pass a DICOMDIR
:class:`~pydicom.dataset.Dataset`, or the path to the DICOMDIR file to
:class:`~pydicom.fileset.FileSet`:

.. code-block:: python

    >>> from pydicom.fileset import FileSet
    >>> path = get_testdata_file("DICOMDIR")
    >>> ds = dcmread(path)
    >>> fs = FileSet(ds)  # or FileSet(path)

An overview of the File-set's contents is shown when printing:

.. code-block:: python

    >>> print(fs)
    DICOM File-set
      Root directory: /home/user/env/lib/python3.7/site-packages/pydicom/data/test_files/dicomdirtests
      File-set ID: PYDICOM_TEST
      File-set UID: 1.2.276.0.7230010.3.1.4.0.31906.1359940846.78187
      Descriptor file ID: (no value available)
      Descriptor file character set: (no value available)
      Changes staged for write(): DICOMDIR update, directory structure update

      Managed instances:
        PATIENT: PatientID='77654033', PatientName='Doe^Archibald'
          STUDY: StudyDate=20010101, StudyTime=000000, StudyDescription='XR C Spine Comp Min 4 Views'
            SERIES: Modality=CR, SeriesNumber=1
              IMAGE: 1 SOP Instance
            SERIES: Modality=CR, SeriesNumber=2
              IMAGE: 1 SOP Instance
            SERIES: Modality=CR, SeriesNumber=3
              IMAGE: 1 SOP Instance
          STUDY: StudyDate=19950903, StudyTime=173032, StudyDescription='CT, HEAD/BRAIN WO CONTRAST'
            SERIES: Modality=CT, SeriesNumber=2
              IMAGE: 4 SOP Instances
        PATIENT: PatientID='98890234', PatientName='Doe^Peter'
          STUDY: StudyDate=20010101, StudyTime=000000
            SERIES: Modality=CT, SeriesNumber=4
              IMAGE: 2 SOP Instances
            SERIES: Modality=CT, SeriesNumber=5
              IMAGE: 5 SOP Instances
          STUDY: StudyDate=20030505, StudyTime=050743, StudyDescription='Carotids'
            SERIES: Modality=MR, SeriesNumber=1
              IMAGE: 1 SOP Instance
            SERIES: Modality=MR, SeriesNumber=2
              IMAGE: 1 SOP Instance
          STUDY: StudyDate=20030505, StudyTime=025109, StudyDescription='Brain'
            SERIES: Modality=MR, SeriesNumber=1
              IMAGE: 1 SOP Instance
            SERIES: Modality=MR, SeriesNumber=2
              IMAGE: 3 SOP Instances
          STUDY: StudyDate=20030505, StudyTime=045357, StudyDescription='Brain-MRA'
            SERIES: Modality=MR, SeriesNumber=1
              IMAGE: 1 SOP Instance
            SERIES: Modality=MR, SeriesNumber=2
              IMAGE: 3 SOP Instances
            SERIES: Modality=MR, SeriesNumber=700
              IMAGE: 7 SOP Instances


The :class:`~pydicom.fileset.FileSet` class treats a File-set as a flat
collection of SOP Instances, abstracting away the need to dig down into the
hierarchy like you would with a DICOMDIR dataset. For example,
iterating over the :class:`~pydicom.fileset.FileSet` yields a
:class:`~pydicom.fileset.FileInstance` object for each of the managed
instances.

.. code-block:: python

    >>> for instance in fs:
    ...     print(instance.PatientName)
    ...     break
    ...
    Doe^Archibald

A list of unique element values within the File-set can be found using the
:meth:`~pydicom.fileset.FileSet.find_values` method, which by default
searches the corresponding DICOMDIR records:

.. code-block:: python

    >>> fs.find_values("PatientID")
    ['77654033', '98890234']

The search can be expanded to the File-set's managed instances by supplying
the `load` parameter, at the cost of a longer search time due to having
to read and decode the corresponding files:

.. code-block:: python

    >>> fs.find_values("PhotometricInterpretation")
    []
    >>> fs.find_values("PhotometricInterpretation", load=True)
    ['MONOCHROME1', 'MONOCHROME2']

More importantly, the File-set can be searched to find instances matching
a query using the :func:`~pydicom.fileset.FileSet.find` method, which returns
a list of :class:`~pydicom.fileset.FileInstance`. The corresponding file
can then be read and decoded using :meth:`FileInstance.load()
<pydicom.fileset.FileInstance.load>`, returning it as a
:class:`~pydicom.dataset.FileDataset`:

.. code-block:: python

    >>> for instance in fs.find(PatientID='77654033'):
    ...     ds = instance.load()
    ...     print(ds.PhotometricInterpretation)
    ...
    MONOCHROME1
    MONOCHROME1
    MONOCHROME1
    MONOCHROME2
    MONOCHROME2
    MONOCHROME2
    MONOCHROME2

:func:`~pydicom.fileset.FileSet.find` also supports the use of the `load`
parameter:

.. code-block:: python

    >>> len(fs.find(PatientID='77654033', PhotometricInterpretation='MONOCHROME1'))
    0
    >>> len(fs.find(PatientID='77654033', PhotometricInterpretation='MONOCHROME1', load=True))
    3


:class:`~pydicom.fileset.FileSet` and staging
---------------------------------------------

Before we go any further we need to discuss how the
:class:`~pydicom.fileset.FileSet` class manages changes to the File-set.
Modifications to the File-set are first *staged*, which means that although
the :class:`~pydicom.fileset.FileSet` instance behaves as though you've applied
them, nothing will actually change on the file system itself until
you explicitly call :meth:`FileSet.write()<pydicom.fileset.FileSet.write>`.
This includes changes such as:

* Adding SOP instances using the :meth:`FileSet.add()
  <pydicom.fileset.FileSet.add>` or :meth:`FileSet.add_custom()
  <pydicom.fileset.FileSet.add_custom>` methods
* Removing SOP instances with :meth:`FileSet.remove()
  <pydicom.fileset.FileSet.remove>`
* Changing one of the following properties:
  :attr:`~pydicom.fileset.FileSet.ID`, :attr:`~pydicom.fileset.FileSet.UID`,
  :attr:`~pydicom.fileset.FileSet.descriptor_file_id` and
  :attr:`~pydicom.fileset.FileSet.descriptor_character_set`.
* Moving instances from the current directory structure to the one used by
  *pydicom*.

You can tell if changes are staged with the
:attr:`~pydicom.fileset.FileSet.is_staged` property:

.. code-block:: python

    >>> fs.is_staged
    True

You may also have noticed this line in the ``print(fs)`` output shown above:

.. code-block:: text

  Changes staged for write(): DICOMDIR update, directory structure update

This appears when the :class:`~pydicom.fileset.FileSet` is staged and will
contain at least one of the following:

* ``DICOMDIR update`` or ``DICOMDIR creation``: the DICOMDIR file will be
  updated or created
* ``directory structure update``: one or more of the instances in the
  existing File-set will be moved over to use the *pydicom* File-set
  directory structure
* ``N additions``: *N* instances will be added to the File-set
* ``M removals``:  *M* instances will be removed from the File-set


Modifying an existing File-set
------------------------------

Adding instances
................
Adding instances is done through either the
:meth:`~pydicom.fileset.FileSet.add` or
:meth:`~pydicom.fileset.FileSet.add_custom` methods.

:meth:`~pydicom.fileset.FileSet.add` is for normal DICOM SOP Instances and
takes either the instances as a :class:`~pydicom.dataset.Dataset` or the
path to an instance, and returns the instance as a
:class:`~pydicom.fileset.FileInstance`.

.. code-block:: python

    >>> instance = fs.add(get_testdata_file("CT_small.dcm"))
    >>> instance.path
    '/tmp/tmp0aalrzir/1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322'
    >>> instance.is_staged
    True
    >>> instance.for_addition
    True

When instances are staged for addition they're stored in a temporary directory.

When adding instances to a File-set
:meth:`~pydicom.fileset.FileSet.add_custom` let's you add privately defined
instances to the File-set or to customize the instance's directory records in
the DICOMDIR file.

Removing instances
..................


Applying the changes
....................


.. code-block:: python

    >>> fs.write()


Creating a new File-set
-----------------------

You can create a new File-set and add and remove instances in the same manner
as existing File-sets:

.. code-block:: python

    >>> fs = FileSet())
    >>> fs.add(get_testdata_file("CT_small.dcm"))

The File-set UID will be generated automatically:

When it comes time to write() you must supply the `path` parameter, which is
the path where the File-set will be written:

.. code-block:: python

    >>> from tempfile import TemporaryDirectory
    >>> t = TemporaryDirectory()
    >>> fs.write(t.name)
