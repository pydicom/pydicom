.. _getting_started:

============================
Getting Started with pydicom
============================

.. rubric:: Brief overview of pydicom and how to install.


Introduction
==============

pydicom is a pure python package for working with 
`DICOM <http://en.wikipedia.org/wiki/DICOM>`_
files such as medical images, reports, and radiotherapy objects.

pydicom makes it easy to read these complex files into natural pythonic 
structures for easy manipulation. Modified datasets can be written again to 
DICOM format files.

Here is a simple example of using pydicom in an interactive session, to read
a radiotherapy plan file, change the patient setup from head-first-supine to 
head-first-prone, and save to a new file:

>>> from pydicom import dicomio
>>> ds = dicomio.read_file("rtplan.dcm")  # plan dataset
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


pydicom is not a DICOM server [#]_, and is not primarily about viewing images. It is designed to let you manipulate data elements in DICOM files with python code.

pydicom is easy to install and use, and because it is a pure 
python package, it should run anywhere python runs. 

One limitation of pydicom: compressed pixel data (e.g. JPEG) 
cannot be altered in an intelligent way as it can be for uncompressed pixels. 
Files can always be read and saved, but compressed pixel data cannot 
easily be modified.


License
=======

pydicom has an MIT-based `license
<https://github.com/darcymason/pydicom/blob/master/source/dicom/license.txt>`_.


Installing
==========

As a pure python package, pydicom is easy to install and has no
requirements other than python itself (the NumPy library is recommended, 
but is only required if manipulating pixel data).

.. note::
    In addition to the instructions below, pydicom can also be installed
    through the `Python(x,y) <http://www.pythonxy.com/>`_ distribution, which can
    install python and a number of packages [#]_ (including pydicom) at once.


Prerequisites
-------------

  * python 2.6, 2.7, 3.3 or later
  * `NumPy <http://numpy.scipy.org/>`_ -- optional, only needed
    if manipulating pixel data

.. note::
    To run unit tests when using python 2.6, `Unittest2 <https://pypi.python.org/pypi/unittest2>`_
    is required.

Python installers can be found at the python web site 
(http://python.org/download/). On Windows, the `Activepython 
<http://activestate.com/activepython>`_ distributions are also quite good.

Installing using pip (all platforms)
----------------------------------------------------
The easiest way to install pydicom is using `pip <https://pypi.python.org/pypi/pip>`_::

    pip pydicom

Depending on your python version, there may be some warning messages, 
but the install should still be ok.

.. note::
    Pip comes pre-installed with Python 3.x.


Installing from source (all platforms)
--------------------------------------
  * `Download <https://github.com/darcymason/pydicom/archive/master.zip>`_ the source code directly, or
    `clone <github-windows://openRepo/https://github.com/darcymason/pydicom>`_ the repo with
    Github's desktop application.
  * In a command terminal, move to the directory with the setup.py file
  * With admin privileges, run ``python setup.py install``

    * With some linux variants, for example, use ``sudo python setup.py install``
    * With other linux variants you may have to ``su`` before running the command.


Installing on Mac
-----------------

Using pip as described above is recommended.  However, there was previously a 
`MacPorts portfile <https://www.macports.org/ports.php?by=library&substr=py27-pydicom>`_. 
This is maintained by other users and may not immediately be up to 
the latest release.


Using pydicom
=============

Once installed, the package can be imported at a python command line or used 
in your own python program with ``import pydicom``.
See the `examples directory 
<https://github.com/darcymason/pydicom/tree/dev/pydicom/examples>`_
for both kinds of uses. Also see the :doc:`User Guide </pydicom_user_guide>` 
for more details of how to use the package.


Support
=======

Please join the `pydicom discussion group <http://groups.google.com/group/pydicom>`_ 
to ask questions or give feedback.
Bugs can be submitted through the `issue tracker <https://github.com/darcymason/pydicom/issues>`_.
Besides the example directory, cookbook recipes are encouraged to be posted on the
`wiki page <https://github.com/darcymason/pydicom/wiki>`_

New versions, major bug fixes, etc. will also be announced through the group.


Next Steps
==========

To start learning how to use pydicom, see the :doc:`pydicom_user_guide`.

.. rubric:: Footnotes::

.. [#] For DICOM network capabilities, see the `pynetdicom <http://pynetdicom.googlecode.com>`_ project.
.. [#] If using python(x,y), other packages you might be interested in include IPython 
   (an indispensable interactive shell with auto-completion, history etc), 
   Numpy (optionally used by pydicom for pixel data), and ITK/VTK or PIL (image processing and visualization).
