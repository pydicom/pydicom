.. _getting_started:

=======================
Introduction to pydicom
=======================

.. rubric:: Brief overview of pydicom.


Introduction
============

*pydicom* is a pure Python package for working with `DICOM
<https://en.wikipedia.org/wiki/DICOM>`_ files such as medical images, reports,
and radiotherapy objects.

*pydicom* makes it easy to read these complex files into natural pythonic
structures for easy manipulation. Modified datasets can be written again to
DICOM format files.

Below is a simple example of using *pydicom* in an interactive session. In it we
use the :func:`~pydicom.data.get_testdata_file` helper function to get the
path to one of the pydicom test datasets, which in this case is a radiotherapy
plan file. We then read the dataset from the path using :func:`~pydicom.filereader.dcmread`,
which returns a :class:`~pydicom.dataset.FileDataset` instance `ds`. This is then
used to print the *Patient Name* and change the *Patient Position* from
head-first-supine (HFS) to head-first-prone (HFP). The changes are then saved to a
new file `rtplan2.dcm`::

  >>> import pydicom
  >>> from pydicom.data import get_testdata_file
  >>> # Fetch the path to the example dataset
  >>> path = get_testdata_file("rtplan.dcm")
  >>> path
  '/path/to/pydicom/data/test_files/rtplan.dcm'
  >>> ds = pydicom.dcmread(path)
  >>> ds.PatientName
  'Last^First^mid^pre'
  >>> ds.dir("setup")  # get a list of tags with "setup" somewhere in the name
  ['PatientSetupSequence']
  >>> ds.PatientSetupSequence[0]
  (0018, 5100) Patient Position                    CS: 'HFS'
  (300a, 0182) Patient Setup Number                IS: '1'
  (300a, 01b2) Setup Technique Description         ST: ''
  >>> ds.PatientSetupSequence[0].PatientPosition = "HFP"
  >>> ds.save_as("rtplan2.dcm")

..
  >>> os.remove("rtplan2.dcm")

A more thorough introduction to pydicom can be found in the :doc:`dataset basics
tutorial</tutorials/dataset_basics>`.

*pydicom* is not a DICOM server (see :gh:`pynetdicom <pynetdicom>` instead),
and is not primarily about viewing images. It is designed to let you manipulate
data elements in DICOM files with Python code.

*pydicom* is easy to install and use, and because it is a pure Python package,
it should run wherever Python runs.

One limitation is that compressed pixel data (e.g. JPEG) can only be
altered in an intelligent way if :doc:`decompressing <image_data_handlers>`
it first. Once decompressed, it can be altered and written back to a
DICOM file the same way as initially uncompressed data.


License
=======

*pydicom* has an MIT-based :gh:`license <pydicom/blob/main/LICENSE>`.

Installing
==========

See the :doc:`installation guide<../tutorials/installation>`.

Using pydicom
=============

Once installed, the package can be imported at a Python command line or used
in your own Python program with ``import pydicom``.
See the :gh:`examples directory <pydicom/tree/main/examples>`
for both kinds of uses. Also see the :doc:`User Guide <pydicom_user_guide>`
for more details of how to use the package.

Support
=======

Please join the `pydicom discussion group
<https://groups.google.com/group/pydicom>`_ to ask questions or give feedback.
Bugs can be submitted through the :gh:`issue tracker <pydicom/issues>`.

New versions, major bug fixes, etc. will also be announced through the group.

Next Steps
==========

To start learning how to use *pydicom*, see the :doc:`pydicom_user_guide`.
