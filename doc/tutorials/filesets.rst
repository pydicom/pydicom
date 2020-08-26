============================
DICOM File-sets and DICOMDIR
============================

This tutorial is about the DICOM File-set and covers

* An introduction to DICOM File-sets
* Reading and accessing the records in a DICOMDIR file
* Loading a File-set using the FileSet class and accessing it

It's assumed that you're already familiar with the :doc:`dataset basics
<dataset_basics>`.

**Prerequisites**

.. code-block:: bash

    python -m pip install -U pydicom>=2.1

.. code-block:: bash

    conda install pydicom>=2.1

**References**

* :dcm:`Basic Directory IOD<chtml/part03/chapter_F.html>`
* :dcm:`DICOM File Service<part10/chapter_8.html>`

The DICOM File-set
==================

A File-set is a collection of DICOM files (SOP instances written in the
:dcm:`DICOM File Format<part10/chapter_7.html>`) that share a common naming
space within which the File IDs - the filenames - are unique.

The DICOMDIR Dataset
--------------------

Each File-set contains a single file with the filename `DICOMDIR`, which is
a Media Storage Directory Storage instance that contains records listing the
contents of the File-set.


.. code-block:: python

    >>> from pydicom import dcmread
    >>> from pydicom.data import get_testdata_file
    >>> path = get_testdata_file("DICOMDIR")
    >>> ds = dcmread(path)
    >>> ds.file_meta.MediaStorageSOPClassUID.name
    'Media Storage Directory Storage'

The Media Storage Directory SOP Class follows the :dcm:`Basic Directory
IOD<chtml/part03/chapter_F.html>` and contains the File-set's directory
structure in the (0004,1220) *Directory Record Sequence* element. The first
record in the directory is determined through the (0004,1200) *Offset of the
First Directory Record of the Root Directory Entity* element value, which
is the byte offset in the encoded DICOMDIR dataset to the corresponding record.

Each item in the sequence is a directory record of a particular type and
multiple records per managed SOP Instance are used to build up a hierarchy
of the directory structure. The record types and their inter-relationship are
listed in :dcm:`Table F.4-1 in Part 3 of the DICOM Standard
<part03/sect_F.4.html#table_F.4-1>`.

.. code-block:: python

    >>> ds.OffsetOfTheFirstDirectoryRecordOfTheRootDirectoryEntity
    396
    >>> records = ds.DirectoryRecordSequence
    >>> for idx in range(4):
    ...     if idx == 0: print("Offset, Record Type")
    ...     record = records[idx]
    ...     print(f"{record.seq_item_tell}, {record.DirectoryRecordType}")
    ...
    Offset, Record Type
    396, PATIENT
    510, STUDY
    724, SERIES
    856, IMAGE

So the first record for the directory is at offset 396, which is also the
first item in the *Directory Record Sequence* - a PATIENT record. The first
record doesn't necessarily have to be the first item, it can be at any location
within the sequence, nor does it have to be a PATIENT record.

Each record contains two elements that identify it's relationship to other
records:

* (0004,1400) *Offset of the Next Directory Record*
* (0004,1420) *Offset of Referenced Lower-level Directory Record*

These elements contain the byte offsets in the encoded dataset to the
corresponding record as given by the `seq_item_tell` attribute. A value of
``0`` indicates that there's no next or lower record.

.. code-block:: python

    >>> for idx in range(4):
    ...     if idx == 0: print("Next, Child")
    ...     record = records[idx]
    ...     print(f"{record[0x00041400].value}, {record[0x00041420].value}")
    ...
    Next, Child
    3126, 510
    1814, 724
    1090, 856
    0, 0

To summarize the above:

* The PATIENT record has a sibling at offset 3126 and a child at offset 510
  (the STUDY record at index 1)
* The STUDY record has a sibling at offset 1814 and a child at 724
  (the SERIES record at index 2)
* The SERIES record has a sibling at offset 1090 and a child at offset 856
  (the IMAGE record at index 3)
* The IMAGE record has no children (or siblings) and so lies at the bottom of
  this particular branch of the hierarchy

The bottom record usually defines the relative path to the corresponding file:

.. code-block:: python

    >>> record = records[3]
    >>> record.DirectoryRecordType
    'IMAGE'
    >>> record.ReferencedFileID
    ['77654033', 'CR1', '6154']

So, relative to the DICOMDIR file, the referenced file is at
``77654033/CR1/6154`` (i.e. two folders below, with a filename of ``6154``).

FileSet
=======

While you can access everything within a File-set using the DICOMDIR dataset,
a more user-friendly way to interact with it is via the
:class:`~pydicom.dicomdir.FileSet` class.


Loading existing File-sets
--------------------------

When loading a File-set, simply pass the DICOMDIR
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

Rather than representing the File-set as a tree model, the
:class:`~pydicom.dicomdir.FileSet` class treats it as a flat
collection of SOP Instances, abstracting away the need to dig down into the
hierarchy (although that's still possible). For example, iterating over the
:class:`~pydicom.dicomdir.FileSet` yields a
:class:`~pydicom.dicomdir.FileInstance` object for each of the managed SOP
Instances.

.. code-block:: python

    >>> for instance in fs:
    ...     print(instance.PatientName)
    ...     break
    Doe^Archibald

The managed instances in the File-set can be searched and then loaded to return
a :class:`~pydicom.dataset.Dataset`:

.. code-block:: python

    >>> fs.find_values("PatientID")
    ['77654033', '98890234']
    >>> for instance in fs.find(PatientID='77654033'):
    ...     ds = instance.load()
    ...     print(ds.PhotometricInterpretation)
    MONOCHROME1
    MONOCHROME1
    MONOCHROME1
    MONOCHROME2
    MONOCHROME2
    MONOCHROME2
    MONOCHROME2

By default, both :meth:`~pydicom.dicomdir.FileSet.find` and
:meth:`~pydicom.dicomdir.FileSet.find_values` only search the elements within
the directory records of the DICOMDIR file. You can search for any
element within the actual stored instances by using the *load*
keyword parameter:

.. code-block:: python

    >>> fs.find_values("PhotometricInterpretation")
    []
    >>> fs.find_values("PhotometricInterpretation", load=True)
    ['MONOCHROME1', 'MONOCHROME2']
    >>> len(fs.find(PatientID='77654033', PhotometricInterpretation='MONOCHROME1'))
    0
    >>> len(fs.find(PatientID='77654033', PhotometricInterpretation='MONOCHROME1', load=True))
    3

The cost of the *load* parameter is that it's less efficient due to the
overhead of having to read every instance in the File-set.


Recipe: Copy all SOP Instances in a given series
................................................

.. code-block:: python

    from pathlib import Path
    import shutil

    from pydicom import dcmread
    from pydicom.data import get_testdata_file
    from pydicom.dicomdir import FileSet

    path = get_testdata_file("DICOMDIR")
    fs = FileSet(dcmread(path))

    # *load* needed to search 'Series Description'
    results = fs.find(
        PatientID='98890234',
        SeriesDescription='ANGIO Projected from   C',
        load=True
    )

    dst = (Path() / 'temp').resolve()
    for instance in results:
        shutil.copy(instance.path, dst)
