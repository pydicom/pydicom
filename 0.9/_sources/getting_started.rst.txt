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

>>> import dicom
>>> plan = dicom.read_file("rtplan.dcm")
>>> plan.PatientName
'Last^First^mid^pre'
>>> plan.dir("setup")    # get a list of tags with "setup" somewhere in the name
['PatientSetupSequence']
>>> plan.PatientSetupSequence[0]
(0018, 5100) Patient Position                    CS: 'HFS'
(300a, 0182) Patient Setup Number                IS: '1'
(300a, 01b2) Setup Technique Description         ST: ''
>>> plan.PatientSetupSequence[0].PatientPosition = "HFP"
>>> plan.save_as("rtplan2.dcm")


pydicom is not a DICOM server [#]_, and is not primarily about viewing images. It is designed to let you manipulate data elements in DICOM files with python code.

pydicom is easy to install and use, and because it is a pure 
python package, it should run anywhere python runs. 

One limitation of pydicom: compressed pixel data (e.g. JPEG) 
cannot be altered in an intelligent way as it can be for uncompressed pixels. 
Files can always be read and saved, but compressed pixel data cannot 
easily be modified.


License
=======
pydicom has a `license 
<http://code.google.com/p/pydicom/source/browse/source/dicom/license.txt>`_ 
based on the MIT license.


Installing
==========

As a pure python package, pydicom is easy to install and has no
requirements other than python itself (the NumPy library is recommended, 
but is only required if manipulating pixel data).

Note: in addition to the instructions below, pydicom can also be installed 
through the `Python(x,y) <http://www.pythonxy.com/>`_ distribution, which can 
install python and a number of packages [#]_ (including pydicom) at once.

Prerequisites
-------------
  * python 2.4 through 2.6 (or python 2.3 can be used for pydicom < 0.9.4)
  * [ NumPy (http://numpy.scipy.org/) ] -- optional, only needed 
    if manipulating pixel data

Python installers can be found at the python web site 
(http://python.org/download/). On Windows, the `Activepython 
<http://activestate.com/activepython>`_ distributions are also quite good.


Installing on Windows
---------------------

On Windows, pydicom can be installed using the executable installer from the 
`Downloads <http://code.google.com/p/pydicom/downloads/list>`_ tab.

Alternatively, pydicom can be installed with easy_install, pip, or 
from source, as described in the sections below.


Installing using easy_install or pip (all platforms)
----------------------------------------------------

if you have `setuptools <http://pypi.python.org/pypi/setuptools>`_ installed, 
just use easy_install at the command line (you may need ``sudo`` on linux)::
    
   easy_install pydicom

Depending on your python version, there may be some warning messages, 
but the install should still be ok.

`pip <http://http://pip.openplans.org/>`_ is a newer install tool that works
quite similarly to easy_install and can also be used.


Installing from source (all platforms)
--------------------------------------
  * download the source code from the 
    `Downloads tab <http://code.google.com/p/pydicom/downloads/list>`_ or 
    `checkout the mercurial repository source 
    <http://code.google.com/p/pydicom/source/checkout>`_
  * at a command line, change to the directory with the setup.py file
  * with admin privileges, run ``python setup.py install``

    * with some linux variants, for example, use ``sudo python setup.py install``
    * with other linux variants you may have to ``su`` before running the command.

  * for python < 2.6, you may get a syntax error message when the python files 
    are "built" -- this is due to some python 2.6 specific code in one unit 
    test file. The installation seems to still be ok.

Installing on Mac
-----------------

The instructions above for easy_install or installing from source 
will work on Mac OS. There is also a MacPorts portfile (py25-pydicom) 
available at 
http://trac.macports.org/browser/trunk/dports/python/py25-pydicom. 
This is maintained by other users and may not immediately be up to 
the latest release.


Using pydicom
=============

Once installed, the package can be imported at a python command line or used 
in your own python program with ``import dicom`` (note the package name is 
``dicom``, not ``pydicom`` when used in code. 
See the `examples directory 
<http://code.google.com/p/pydicom/source/browse/#hg/source/dicom/examples>`_ 
for both kinds of uses. Also see the :doc:`User Guide </pydicom_user_guide>` 
for more details of how to use the package.


Support
=======

Please join the `pydicom discussion group <http://groups.google.com/group/pydicom>`_ 
to ask questions, give feedback, post example code for others -- in other words 
for any discussion about the pydicom code. New versions, major bug fixes, etc. 
will also be announced through the group.


Next Steps
==========

To start learning how to use pydicom, see the :doc:`pydicom_user_guide`.

.. rubric: Footnotes::

.. [#] For DICOM network capabilities, see the `pynetdicom <http://pynetdicom.googlecode.com>`_ project.
.. [#] If using python(x,y), other packages you might be interested in include IPython 
   (an indispensable interactive shell with auto-completion, history etc), 
   Numpy (optionally used by pydicom for pixel data), and ITK/VTK or PIL (image processing and visualization).