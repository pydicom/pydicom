============================
DICOM File-sets and DICOMDIR
============================

This tutorial is about DICOM File-sets and covers:

* An introduction to DICOM File-sets and the DICOMDIR file
* Loading a File-set using the :class:`~pydicom.fileset.FileSet` class and
  accessing its managed SOP instances
* Creating a new File-set and modifying existing ones

It's assumed that you're already familiar with the :doc:`dataset basics
<dataset_basics>`.

**References**

* :dcm:`Basic Directory IOD<part03/chapter_F.html>`
* :dcm:`DICOM File Service<part10/chapter_8.html>`
* :dcm:`Media Formats and Physical Media for Media Interchange
  <part12/ps3.12.html>`

The DICOM File-set
==================

A File-set is a collection of DICOM files that share a common naming
space. Most people have probably interacted with a File-set without being aware
of it; one place they're frequently used is on the CDs/DVDs containing DICOM
data that are given to a patient after a medical procedure (such as an MR or
ultrasound).

The specification for File-sets is given in :dcm:`Part 10 of the DICOM
Standard<part10/chapter_8.html>`.

The DICOMDIR file
-----------------

.. note::

    Despite its name, a DICOMDIR file is not a file system directory and
    can be read using :func:`~pydicom.filereader.dcmread` like any other DICOM
    dataset.

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

The DICOMDIR file is used to summarize the contents of the File-set and is a
*Media Storage Directory* instance that follows the
:dcm:`Basic Directory IOD<part03/chapter_F.html>`.

.. code-block:: python

    >>> from pydicom import dcmread
    >>> from pydicom.data import get_testdata_file
    >>> path = get_testdata_file("DICOMDIR")
    >>> ds = dcmread(path)
    >>> ds.file_meta.MediaStorageSOPClassUID.name
    'Media Storage Directory Storage'

The most important element in a DICOMDIR is the (0004,1220) *Directory
Record Sequence*; each item in the sequence is a *directory record*,
and one or more records are used to briefly describe an available SOP
Instance and its location within the File-set's directory structure. Each
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

Here we have a ``'PATIENT'`` record, which from :dcm:`Table F.5-1
<part03/sect_F.5.html#table_F.5-1>` we see must also contain *Patient's Name*
and *Patient ID* elements. The full list of available record types and their
requirements is in :dcm:`Annex F.5 of Part 3 of the DICOM Standard
<part03/sect_F.5.html>`.

FileSet
=======

While it's possible to access everything within a File-set using the DICOMDIR
dataset, making changes to an existing File-set quickly becomes complicated
due to the need to add and remove directory records, recalculate the
byte offsets for existing records and manage the corresponding file
system changes. A more user-friendly way to interact with one is via the
:class:`~pydicom.fileset.FileSet` class.


Loading existing File-sets
--------------------------

To load an existing File-set just pass a DICOMDIR
:class:`~pydicom.dataset.Dataset` or the path to the DICOMDIR file to
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

Creating a new File-set
-----------------------

You can create a new File-set by creating a new
:class:`~pydicom.fileset.FileSet` instance:

.. code-block:: python

    >>> fs = FileSet()

This will create a completely conformant File-set, however it won't contain
any SOP instances. Since empty File-sets aren't very useful, our next step
will be to add some.

Modifying a File-set
--------------------
:class:`~pydicom.fileset.FileSet` and staging
.............................................

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
  :attr:`~pydicom.fileset.FileSet.descriptor_character_set`
* When the :class:`~pydicom.fileset.FileSet` class determines it needs to move
  SOP instances from an existing File-set's directory structure to the
  structure used by *pydicom*

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
* ``directory structure update``: one or more of the SOP instances in the
  existing File-set will be moved over to use the *pydicom* File-set
  directory structure
* ``N additions``: *N* SOP instances will be added to the File-set
* ``M removals``:  *M* SOP instances will be removed from the File-set


Adding SOP instances
....................

The simplest way to add new SOP instances to the File-set is with the
:meth:`~pydicom.fileset.FileSet.add` method, which takes the path to the
instance or the instance itself as a :class:`~pydicom.dataset.Dataset` and
returns the addition as a :class:`~pydicom.fileset.FileInstance`.

To reduce memory usage, instances staged for addition are written to a
temporary directory and only copied to the File-set itself when
:meth:`~pydicom.fileset.FileSet.write` is called. However, they can still be
accessed and loaded:

.. code-block:: python

    >>> path = get_testdata_file("CT_small.dcm")
    >>> instance = fs.add(path)
    >>> instance.is_staged
    True
    >>> instance.for_addition
    True
    >>> instance.path
    '/tmp/tmp0aalrzir/1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322'
    >>> type(instance.load())
    <class 'pydicom.dataset.FileDataset'>

Alternatively, if you want more control over the directory records that will
be added to the DICOMDIR file, or if you need to use PRIVATE records, you can
use the :meth:`~pydicom.fileset.FileSet.add_custom` method.

The :meth:`~pydicom.fileset.FileSet.add` method uses *pydicom's* default
directory record creation functions to create the necessary records based on
the SOP instance's attributes, such as *SOP Class UID* and *Modality*.
Occasionally, they may fail when an element required by these functions
is empty or missing:

.. code-block:: python

    >>> path = get_testdata_file("rtdose.dcm")
    >>> fs.add(path)
    Traceback (most recent call last):
      File ".../pydicom/fileset.py", line 1858, in _recordify
        record = DIRECTORY_RECORDERS[record_type](ds)
      File ".../pydicom/fileset.py", line 2338, in _define_rt_dose
        _check_dataset(ds, ["InstanceNumber", "DoseSummationType"])
      File ".../pydicom/fileset.py", line 2281, in _check_dataset
        raise ValueError(
    ValueError: The instance's (0020, 0013) 'Instance Number' element cannot be empty

    The above exception was the direct cause of the following exception:

    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File ".../pydicom/fileset.py", line 1039, in add
        record = next(record_gen)
      File ".../pydicom/fileset.py", line 1860, in _recordify
        raise ValueError(
    ValueError: Unable to use the default 'RT DOSE' record creator as the instance is missing a required element or value. Either update the instance, define your own record creation function or use 'FileSet.add_custom()' instead

When this occurs, there are three options:

* Update the instance to include the required element and/or value
* Override the default record creation functions with your own by modifying
  :attr:`~pydicom.fileset.DIRECTORY_RECORDERS`
* Use the :meth:`~pydicom.fileset.FileSet.add_custom` method

According to the exception message above, the *Instance Number* element is empty.
Let's update the instance and try adding it again:

.. code-block:: python

    >>> ds = dcmread(path)
    >>> ds.InstanceNumber = "1"
    >>> fs.add(ds)


Removing instances
..................

SOP instances can be removed from the File-set with the
:meth:`~pydicom.fileset.FileSet.remove` method, which takes the
:class:`~pydicom.fileset.FileInstance` or :class:`list` of
:class:`~pydicom.fileset.FileInstance` to be removed:

.. code-block:: python

    >>> len(fs)
    2
    >>> instances = fs.find(PatientID="1CT1")
    >>> len(instances)
    1
    >>> fs.remove(instances)
    >>> len(fs)
    1

Applying the changes
--------------------

Let's add a couple of SOP instances back to the File-set:

.. code-block:: python

    >>> fs.add(get_testdata_file("CT_small.dcm"))
    >>> fs.add(get_testdata_file("MR_small.dcm"))

To apply the changes we've made to the File-set we use
:meth:`~pydicom.fileset.FileSet.write`. For new File-sets, we have to supply the
path where the File-set root directory will be located:

.. code-block:: python

    >>> from pathlib import Path
    >>> from tempfile import TemporaryDirectory
    >>> t = TemporaryDirectory()
    >>> t.name
    '/tmp/tmpsqz8rhgb'
    >>> fs.write(t.name)
    >>> fs.is_staged
    False
    >>> root = Path(t.name)
    >>> for path in sorted([p for p in root.glob('**/*') if p.is_file()]):
    ...     print(path)
    ...
    /tmp/tmpsqz8rhgb/DICOMDIR
    /tmp/tmpsqz8rhgb/PT000000/ST000000/SE000000/RD000000
    /tmp/tmpsqz8rhgb/PT000001/ST000000/SE000000/IM000000
    /tmp/tmpsqz8rhgb/PT000002/ST000000/SE000000/IM000000

The root directory for existing File-sets cannot be changed, so for those
you only need to call :meth:`~pydicom.fileset.FileSet.write` without any
arguments:

.. code-block:: python

    >>> instances = fs.find(PatientID="1CT1")
    >>> fs.remove(instances)
    >>> fs.write()
    >>> for path in sorted([p for p in root.glob('**/*') if p.is_file()]):
    ...     print(path)
    ...
    /tmp/tmpsqz8rhgb/DICOMDIR
    /tmp/tmpsqz8rhgb/PT000000/ST000000/SE000000/RD000000
    /tmp/tmpsqz8rhgb/PT000001/ST000000/SE000000/IM000000


For existing File-sets that don't use the same directory structure semantics
as :class:`~pydicom.fileset.FileSet`, calling
:meth:`~pydicom.fileset.FileSet.write` will move SOP instances over to the
new structure. However, if the only modification you've made is to remove SOP
instances or change :attr:`~pydicom.fileset.FileSet.ID`,
:attr:`~pydicom.fileset.FileSet.UID`,
:attr:`~pydicom.fileset.FileSet.descriptor_file_id`, or
:attr:`~pydicom.fileset.FileSet.descriptor_character_set`, then you can pass
the *use_existing* keyword parameter to keep the existing directory structure
and update the DICOMDIR file.

First, we need to copy the existing example File-set to a temporary directory
so we don't accidentally modify it:

.. code-block:: python

    >>> from shutil import copytree, copyfile
    >>> t = TemporaryDirectory()
    >>> dst = Path(t.name)
    >>> src = Path(get_testdata_file("DICOMDIR")).parent
    >>> copyfile(src / "DICOMDIR", dst / "DICOMDIR")
    >>> copytree(src / "77654033", dst / "77654033")
    >>> copytree(src / "98892001", dst / "98892001")
    >>> copytree(src / "98892003", dst / "98892003")

Now we load the File-set from the temporary directory, remove instances and
write out the changes with *use_existing* to keep the current directory
structure:

.. code-block:: python

    >>> fs = FileSet(dst / "DICOMDIR")
    >>> instances = fs.find(PatientID="98890234")
    >>> fs.remove(instances)
    >>> fs.write(use_existing=True)  # Keep the current directory structure
    >>> for path in sorted([p for p in dst.glob('**/*') if p.is_file()]):
    ...     print(path)
    ...
    /tmp/tmpu068kdwp/DICOMDIR
    /tmp/tmpu068kdwp/77654033/CR1/6154
    /tmp/tmpu068kdwp/77654033/CR2/6247
    /tmp/tmpu068kdwp/77654033/CR3/6278
    /tmp/tmpu068kdwp/77654033/CT2/17106
    /tmp/tmpu068kdwp/77654033/CT2/17136
    /tmp/tmpu068kdwp/77654033/CT2/17166
    /tmp/tmpu068kdwp/77654033/CT2/17196

If you'd just called :meth:`~pydicom.fileset.FileSet.write` without
*use_existing*, then it would've moved the SOP instances to the new
directory structure:

.. code-block:: python

    >>> fs.write()
    >>> for path in sorted([p for p in dst.glob('**/*') if p.is_file()]):
    ...     print(path)
    ...
    /tmp/tmpu068kdwp/DICOMDIR
    /tmp/tmpu068kdwp/PT000000/ST000000/SE000000/IM000000
    /tmp/tmpu068kdwp/PT000000/ST000000/SE000001/IM000000
    /tmp/tmpu068kdwp/PT000000/ST000000/SE000002/IM000000
    /tmp/tmpu068kdwp/PT000000/ST000001/SE000000/IM000000
    /tmp/tmpu068kdwp/PT000000/ST000001/SE000000/IM000001
    /tmp/tmpu068kdwp/PT000000/ST000001/SE000000/IM000002
    /tmp/tmpu068kdwp/PT000000/ST000001/SE000000/IM000003


Conclusion
==========

In this tutorial you've learned about DICOM File-sets and the DICOMDIR file.
You should now be able to use the :class:`~pydicom.fileset.FileSet` class
to create new File-sets, and to load, search and modify existing ones.
