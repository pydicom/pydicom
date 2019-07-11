.. _getting_started:

============================
Getting Started with pydicom
============================

.. rubric:: Brief overview of pydicom and how to install.


Introduction
============

Pydicom is a pure Python package for working with `DICOM
<http://en.wikipedia.org/wiki/DICOM>`_ files such as medical images, reports,
and radiotherapy objects.

Pydicom makes it easy to read these complex files into natural pythonic
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

Pydicom is not a DICOM server [#]_, and is not primarily about viewing
images. It is designed to let you manipulate data elements in DICOM files with
Python code.

Pydicom is easy to install and use, and because it is a pure Python package, it
should run wherever Python runs.

One limitation of pydicom: compressed pixel data (e.g. JPEG) can only be
altered in an intelligent way if :doc:`decompressing </image_data_handlers>`
them first. Once decompressed, they can be altered and written back to a
DICOM file the same way as initially uncompressed data.

License
=======

Pydicom has an MIT-based `license
<https://github.com/pydicom/pydicom/blob/master/LICENSE>`_.

Installing
==========

As a pure Python package, pydicom is easy to install and has no requirements
other than Python itself (the NumPy library is recommended, but is only
required if manipulating pixel data).


Prerequisites
-------------

* Python 2.7, 3.4 or later
* Optional dependencies:
   * numpy
   * pillow
   * gdcm
   * jpeg_ls
   * jpeg2000
   * pytest (if running pydicom's test suite). pytest<5 if in Python 2.


Installing pydicom
------------------

Pydicom is currently available on `PyPi <https://pypi.python.org/pypi/pydicom/>`_
. The simplest way to install pydicom alone is using ``pip`` at a command line::

  pip install -U pydicom

which installs the latest release.  To install the latest code from the repository
(usually stable, but may have undocumented changes or bugs)::

  pip install -U git+https://github.com/pydicom/pydicom.git


Pydicom is also available on conda-forge::

  conda install pydicom --channel conda-forge

To install pydicom along with image handlers for compressed pixel data, 
we encourage you to use `Miniconda <https://conda.io/miniconda.html>`_ or
`Anaconda <https://docs.continuum.io/anaconda/>`_.  For example::

  conda create --name pydicomenv python=3.6 pip numpy
  conda install pydicom --channel conda-forge

will install pip, pydicom, and numpy in an environment called pydicomenv.  
To add gdcm after activating the environment::

  conda install -c conda-forge gdcm

The environment is optional; see the conda software for details of its setup 
and use of environments.

For developers, you can clone the pydicom repository and run 
the ``setup.py`` file. Use the following commands to get a copy 
from GitHub and install all dependencies::

  git clone https://github.com/pydicom/pydicom.git
  cd pydicom
  pip install .

or, for the last line, instead use::

  pip install -e .

to install in 'develop' or 'editable' mode, where changes can be made to the
local working code and Python will use the updated pydicom code.


Test and coverage
=================

To test the installed code on any platform, change to the directory of 
pydicom's setup.py file and::

  python setup.py test

This will install `pytest <https://pytest.org>`_ if it is not 
already installed.

In v1.3 run under Python 2, if pytest is not found, please `python2 -m pip install "pytest<5"`
  
Or, in linux you can also use::

  make test-code

To test the coverage of your versions in linux::

  make test-coverage


Using pydicom
=============

Once installed, the package can be imported at a Python command line or used
in your own Python program with ``import pydicom``.
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
   `pynetdicom3 <https://github.com/pydicom/pynetdicom3>`_ projects.
.. [#] If using python(x,y), other packages you might be interested in include IPython
   (an indispensable interactive shell with auto-completion, history etc),
   NumPy (optionally used by pydicom for pixel data), and ITK/VTK or PIL
   (image processing and visualization).
