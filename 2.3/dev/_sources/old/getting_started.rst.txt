.. _getting_started:

=======================
Introduction to pydicom
=======================

.. rubric:: Brief overview of pydicom.


Introduction
============

*pydicom* is a pure Python package for working with `DICOM
<http://en.wikipedia.org/wiki/DICOM>`_ files such as medical images, reports,
and radiotherapy objects.

*pydicom* makes it easy to read these complex files into natural pythonic
structures for easy manipulation. Modified datasets can be written again to
DICOM format files.

Here is a simple example of using *pydicom* in an interactive session, to read a
radiotherapy plan file, change the patient setup from head-first-supine to
head-first-prone, and save to a new file::

  >>> import pydicom
  >>> from pydicom.data import get_testdata_file
  >>> filename = get_testdata_file("rtplan.dcm")
  >>> ds = pydicom.dcmread(filename)  # plan dataset
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

*pydicom* has an MIT-based :gh:`license <pydicom/blob/master/LICENSE>`.

Installing
==========

See the :doc:`installation guide<../tutorials/installation>`.

Using pydicom
=============

Once installed, the package can be imported at a Python command line or used
in your own Python program with ``import pydicom``.
See the :gh:`examples directory <pydicom/tree/master/examples>`
for both kinds of uses. Also see the :doc:`User Guide <pydicom_user_guide>`
for more details of how to use the package.

Support
=======

Please join the `pydicom discussion group
<http://groups.google.com/group/pydicom>`_ to ask questions or give feedback.
Bugs can be submitted through the :gh:`issue tracker <pydicom/issues>`.

New versions, major bug fixes, etc. will also be announced through the group.

Next Steps
==========

To start learning how to use *pydicom*, see the :doc:`pydicom_user_guide`.
