.. _getting_started:

============================
Getting Started with pydicom
============================

.. rubric:: Brief overview of pydicom and how to install.


Introduction
============

pydicom is a pure python package for working with `DICOM
<http://en.wikipedia.org/wiki/DICOM>`_ files such as medical images, reports,
and radiotherapy objects.

pydicom makes it easy to read these complex files into natural pythonic
structures for easy manipulation. Modified datasets can be written again to
DICOM format files.

Here is a simple example of using pydicom in an interactive session, to read a
radiotherapy plan file, change the patient setup from head-first-supine to
head-first-prone, and save to a new file::

  >>> import os
  >>> import pydicom
  >>> from pydicom.data import get_testdata_files
  >>> filename = get_testdata_files("rtplan.dcm")[0]
  >>> ds = pydicom.dcmread(filename)  # plan dataset
  >>> ds.PatientName
  'Last^First^mid^pre'
  >>> ds.dir("setup")    # get a list of tags with "setup" somewhere in the name
  ['PatientSetupSequence']
  >>> ds.PatientSetupSequence[0]
  (0018, 5100) Patient Position                    CS: 'HFS'
  (300a, 0182) Patient Setup Number                IS: '1'
  (300a, 01b2) Setup Technique Description         ST: ''
  >>> ds.PatientSetupSequence[0].PatientPosition = "HFP"
  >>> ds.save_as("rtplan2.dcm")

..
  >>> os.remove("rtplan2.dcm")

pydicom is not a DICOM server [#]_, and is not primarily about viewing
images. It is designed to let you manipulate data elements in DICOM files with
python code.

pydicom is easy to install and use, and because it is a pure python package, it
should run anywhere python runs.

One limitation of pydicom: compressed pixel data (e.g. JPEG) can only be
altered in an intelligent way if :doc:`decompressing </image_data_handlers>`
them first. Once decompressed, they can be altered and written back to a
DICOM file the same way as initially uncompressed data.

License
=======

pydicom has an MIT-based `license
<https://github.com/pydicom/pydicom/blob/master/LICENSE>`_.

Installing
==========

As a pure python package, pydicom is easy to install and has no requirements
other than python itself (the NumPy library is recommended, but is only
required if manipulating pixel data).

.. note::
   In addition to the instructions below, pydicom can also be installed
   through the `Python(x,y) <https://sourceforge.net/projects/python-xy/>`_
   distribution, which can install python and a number of packages [#]_
   (including pydicom) at once.

Prerequisites
-------------

* Python 2.7, 3.4 or later
* Optional dependencies:
   * numpy
   * pillow
   * gdcm
   * jpeg_ls
   * jpeg2000

We encourage you to use `Miniconda <https://conda.io/miniconda.html>`_ or
`Anaconda <https://docs.continuum.io/anaconda/>`_ which is cross-platforms
compatible.

Installing pydicom
------------------

pydicom is currently available on `PyPi <https://pypi.python.org/pypi/pydicom/>`_
and you can install it using ``pip``::

  pip install -U pydicom

If you prefer, you can clone it and run the ``setup.py`` file. Use the
following commands to get a copy from GitHub and install all dependencies::

  git clone https://github.com/pydicom/pydicom.git
  cd pydicom
  pip install .

Or install using pip and GitHub::

  pip install -U git+https://github.com/pydicom/pydicom.git

Test and coverage
=================

You want to test the installed code::

  make test-code

You wish to test the coverage of your versions::

  make test-coverage

Using pydicom
=============

Once installed, the package can be imported at a python command line or used
in your own python program with ``import pydicom``.
See the `examples directory
<https://github.com/pydicom/pydicom/tree/master/examples>`_
for both kinds of uses. Also see the :doc:`User Guide </pydicom_user_guide>`
for more details of how to use the package.

Support
=======

Please join the `pydicom discussion group
<http://groups.google.com/group/pydicom>`_ to ask questions or give feedback.
Bugs can be submitted through the `issue tracker
<https://github.com/pydicom/pydicom/issues>`_.  Besides the example directory,
cookbook recipes are encouraged to be posted on the `wiki page
<https://github.com/pydicom/pydicom/wiki>`_.

New versions, major bug fixes, etc. will also be announced through the group.

Next Steps
==========

To start learning how to use pydicom, see the :doc:`pydicom_user_guide`.

.. rubric:: Footnotes::

.. [#] For DICOM network capabilities, see the
   `pynetdicom <https://github.com/patmun/pynetdicom>`_ and the newer
   `pynetetdicom3 <https://github.com/pydicom/pynetdicom3>`_ projects.
.. [#] If using python(x,y), other packages you might be interested in include IPython
   (an indispensable interactive shell with auto-completion, history etc),
   Numpy (optionally used by pydicom for pixel data), and ITK/VTK or PIL
   (image processing and visualization).
