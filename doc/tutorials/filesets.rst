============================
DICOM File-sets and DICOMDIR
============================

This tutorial is about DICOM File-sets and covers

* An introduction to DICOM File-sets
* Reading and accessing the records in a DICOMDIR file
* Loading a File-set using the :class:`~pydicom.dicomdir.FileSet` class and
  accessing its managed SOP instances

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

The DICOMDIR
------------

.. note::

    Despite its name, a DICOMDIR file is not a file system directory and
    is read using :func:`~pydicom.filereader.dcmread` like any other DICOM
    dataset

Every File-set must contain a single file with the filename ``DICOMDIR``, the
location of which is dependent on the type of media used to store the File-set.
For the most commonly used media (DVD, CD, USB, PC file system, etc), the
DICOMDIR file will be in the root directory of the File-set. For other
media types, :dcm:`Part 12 of the DICOM Standard<part12/ps3.12.html>`
specifies where the DICOMDIR must be located.

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
Record Sequence*. Each item in the sequence is a *directory record*,
and one or more records are used to briefly describe the available SOP
Instances and their location within the File-set's directory structure.

At a minimum, every directory record has a (0004,1430) *Directory Record Type*
and two elements that identify it's relationship to other records; (0004,1400)
*Offset of the Next Directory Record* and (0004,1420) *Offset of Referenced
Lower-level Directory Record*:

.. code-block:: python

    >>> print(ds.DirectoryRecordSequence[0])
    (0004, 1400) Offset of the Next Directory Record UL: 3126
    (0004, 1410) Record In-use Flag                  US: 65535
    (0004, 1420) Offset of Referenced Lower-Level Di UL: 510
    (0004, 1430) Directory Record Type               CS: 'PATIENT'
    (0008, 0005) Specific Character Set              CS: 'ISO_IR 100'
    (0010, 0010) Patient's Name                      PN: 'Doe^Archibald'
    (0010, 0020) Patient ID                          LO: '77654033'

The *Directory Record Type* specifies the *type* of the record, which is
in turn affects what additional elements are available in the record. For a
``'PATIENT'`` directory record we should also expect to see *Patient's Name*
and *Patient ID* elements. The full list of available record types is defined
in :dcm:`Annex F.5 of Part 3 of the DICOM Standard<part03/sect_F.5.html>`.

Different record types are related to each other using the hierarchy given in
:dcm:`Table F.4-1<part03/sect_F.4.html#table_F.4-1>` and the first record
in the directory is determined through the (0004,1200)
*Offset of the First Directory Record of the Root Directory Entity* element.
This is the byte offset in the encoded DICOMDIR dataset to the corresponding
record. The byte offset for each record is given by the sequence item's
`seq_item_tell` attribute:

.. code-block:: python

    >>> ds.OffsetOfTheFirstDirectoryRecordOfTheRootDirectoryEntity
    396
    >>> print(ds.DirectoryRecordSequence[0].seq_item_tell)
    396

So the first record for the directory is at offset 396, which for this dataset
also happens to be the first item in the *Directory Record Sequence*. Having
the first record as the first item isn't necessary; it could be at any location
within the sequence.

Let's take a quick look at how some of our records are related. The first four
items in our *Directory Records Sequence* are:

.. code-block:: python

    >>> records = ds.DirectoryRecordSequence
    >>> for idx in range(4):
    ...     if idx == 0: print("idx: offset, type, next, child")
    ...     record = records[idx]
    ...     print(
    ...         f"  {idx}: {record.seq_item_tell}, {record.DirectoryRecordType}, "
    ...         f"{record.OffsetOfTheNextDirectoryRecord}, "
    ...         f"{record.OffsetOfReferencedLowerLevelDirectoryEntity}"
    ...     )
    ...
    idx: offset, type, next, child
      0: 396, PATIENT, 3126, 510
      1: 510, STUDY, 1814, 724
      2: 724, SERIES, 1090, 856
      3: 856, IMAGE, 0, 0

* The PATIENT record has a sibling at offset 3126 and a child at offset 510
  (the STUDY record at index 1)
* The STUDY record has a sibling at offset 1814 and a child at 724
  (the SERIES record at index 2)
* The SERIES record has a sibling at offset 1090 and a child at offset 856
  (the IMAGE record at index 3)
* The IMAGE record has no children or siblings (as a value of ``0`` indicates
  no next or lower record) and so lies at the end of this particular branch of
  the hierarchy

So our first four records are ordered as:

* 396 PATIENT

  * 510 STUDY

   * 724 SERIES

     * 856 IMAGE

The lowest record usually defines the relative path to the corresponding file
using the (0004,1500) *Referenced File ID*:

.. code-block:: python

    >>> records[3].ReferencedFileID
    ['77654033', 'CR1', '6154']

So, relative to the DICOMDIR file, the referenced file is at
``77654033/CR1/6154``, i.e. two directories below, with a filename of ``6154``.

FileSet
=======

While you can access everything within a File-set using the DICOMDIR dataset,
a more user-friendly way to interact with it is via the
:class:`~pydicom.dicomdir.FileSet` class.


Loading existing File-sets
--------------------------

When loading a File-set, simply pass a DICOMDIR
:class:`~pydicom.dataset.Dataset` to :class:`~pydicom.dicomdir.FileSet`:

.. code-block:: python

    >>> from pydicom.dicomdir import FileSet
    >>> fs = FileSet(ds)

An overview of the File-set's contents is shown when printing:

.. code-block:: python

    >>> print(fs)
    DICOM File-set
    Root directory: /home/user/env/lib/python3.7/site-packages/pydicom/data/test_files/dicomdirtests
    File-set ID: PYDICOM_TEST
    File-set UID: 1.2.276.0.7230010.3.1.4.0.31906.1359940846.78187
    Managed Instances:
      PATIENT: PatientID=77654033, PatientName=Doe^Archibald
        STUDY: StudyDate=20010101, StudyTime=000000, StudyDescription=XR C Spine Comp Min 4 Views
          SERIES: Modality=CR, SeriesNumber=1
            IMAGE: SOPInstanceUID=1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.11
          SERIES: Modality=CR, SeriesNumber=2
            IMAGE: SOPInstanceUID=1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.7
          SERIES: Modality=CR, SeriesNumber=3
            IMAGE: SOPInstanceUID=1.3.6.1.4.1.5962.1.1.0.0.0.1196527414.5534.0.9
        STUDY: StudyDate=19950903, StudyTime=173032, StudyDescription=CT, HEAD/BRAIN WO CONTRAST
          SERIES: Modality=CT, SeriesNumber=2
            IMAGE: SOPInstanceUID=1.3.6.1.4.1.5962.1.1.0.0.0.1196530851.28319.0.93
            IMAGE: SOPInstanceUID=1.3.6.1.4.1.5962.1.1.0.0.0.1196530851.28319.0.94
            IMAGE: SOPInstanceUID=1.3.6.1.4.1.5962.1.1.0.0.0.1196530851.28319.0.95
            IMAGE: SOPInstanceUID=1.3.6.1.4.1.5962.1.1.0.0.0.1196530851.28319.0.96
      PATIENT: PatientID=98890234, PatientName=Doe^Peter
       STUDY: StudyDate=20010101, StudyTime=000000
          SERIES: Modality=CT, SeriesNumber=4
            IMAGE: SOPInstanceUID=1.3.6.1.4.1.5962.1.1.0.0.0.1194734704.16302.0.3
            IMAGE: SOPInstanceUID=1.3.6.1.4.1.5962.1.1.0.0.0.1194734704.16302.0.5
          ...
          SERIES: Modality=MR, SeriesNumber=700
            IMAGE: SOPInstanceUID=1.3.6.1.4.1.5962.1.1.0.0.0.1196533885.18148.0.121
            IMAGE: SOPInstanceUID=1.3.6.1.4.1.5962.1.1.0.0.0.1196533885.18148.0.120
            IMAGE: SOPInstanceUID=1.3.6.1.4.1.5962.1.1.0.0.0.1196533885.18148.0.122
            IMAGE: SOPInstanceUID=1.3.6.1.4.1.5962.1.1.0.0.0.1196533885.18148.0.119
            IMAGE: SOPInstanceUID=1.3.6.1.4.1.5962.1.1.0.0.0.1196533885.18148.0.123
            IMAGE: SOPInstanceUID=1.3.6.1.4.1.5962.1.1.0.0.0.1196533885.18148.0.125
            IMAGE: SOPInstanceUID=1.3.6.1.4.1.5962.1.1.0.0.0.1196533885.18148.0.124

The :class:`~pydicom.dicomdir.FileSet` class treats a File-set as a flat
collection of SOP Instances, abstracting away the need to dig down into the
hierarchy like you would with a DICOMDIR dataset. For example,
iterating over the :class:`~pydicom.dicomdir.FileSet` yields a
:class:`~pydicom.dicomdir.FileInstance` object for each of the managed
instances.

.. code-block:: python

    >>> for instance in fs:
    ...     print(instance.PatientName)
    ...     break
    ...
    Doe^Archibald

A list of unique element values within the File-set can be found using the
:meth:`~pydicom.dicomdir.FileSet.find_values` method, which by default
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
a query using the :func:`~pydicom.dicomdir.FileSet.find` method, which returns
a list of :class:`~pydicom.dicomdir.FileInstance`. The corresponding file
can then be read and decoded using :meth:`FileInstance.load()
<pydicom.dicomdir.FileInstance.load>`, returning it as a
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

:func:`~pydicom.dicomdir.FileSet.find` also supports the use of the `load`
parameter:

.. code-block:: python

    >>> len(fs.find(PatientID='77654033', PhotometricInterpretation='MONOCHROME1'))
    0
    >>> len(fs.find(PatientID='77654033', PhotometricInterpretation='MONOCHROME1', load=True))
    3
