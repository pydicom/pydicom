======================
How to install pydicom
======================

.. note::

   We recommend installing into a
   `virtual environment <https://docs.python.org/3/tutorial/venv.html>`_,
   which is an isolated Python environment that allows you to install
   packages without admin privileges. See the
   :doc:`virtual environments tutorial<virtualenvs>` on how to create and
   manage virtual environments.


.. _tut_install:

Install the official release
============================

*pydicom*, being a Python library, requires `Python
<https://www.python.org/>`_. If you're not sure whether or not your version of
Python is supported, check :ref:`this table<faq_install_version>`.

Install using pip
-----------------

*pydicom* is available on `PyPi <https://pypi.python.org/pypi/pydicom/>`_, the
official third-party Python software repository. The simplest way to install
from PyPi is using `pip <https://pip.pypa.io/>`_ with the command::

  pip install pydicom

You may need to use this instead, depending on your operating system::

  python -m pip install pydicom

You can also perform an offline installation by
`downloading <https://github.com/pydicom/pydicom/releases>`_ and installing
one of the release ``*.whl`` files. For example, with the v2.0 release::

  pip install pydicom-2.0.0-py3-none-any.whl


Install using conda
-------------------

*pydicom* is also available for `conda <https://docs.conda.io/>`_ at
`conda-forge <https://anaconda.org/conda-forge/pydicom>`_::

  conda install -c conda-forge pydicom


Downloading example/test DICOM files
------------------------------------

To keep the package size small, a number of the larger DICOM files are not
distributed with *pydicom* and are instead kept in the
`pydicom-data <https://github.com/pydicom/pydicom-data>`_
repository. To get the complete set of testing and example files you can either
install the *pydicom-data* repository::

  pip install git+https://github.com/pydicom/pydicom-data

Or download the missing files to the local cache (after installing *pydicom*)::

  python -c "import pydicom; pydicom.data.fetch_data_files()"


.. _tut_install_libs:

Install the optional libraries
==============================

If you're going to be manipulating pixel data then
`NumPy <https://numpy.org/>`_ is required.

Using pip::

  pip install numpy

Through conda::

  conda install numpy

To decode JPEG compressed pixel data one or more additional libraries will
need to be installed. See :ref:`this page <guide_compressed>` for a list of
which library is needed to handle a given JPEG format, as specified by
the dataset's (0002,0010) *Transfer Syntax UID* value.


Installing Pillow
-----------------

`Pillow <https://pillow.readthedocs.io/>`_ is a popular Python imaging library
that can handle the decompression of some JPEG and JPEG 2000 images.

Using pip; you may need to make sure that the
`libjpeg <http://libjpeg.sourceforge.net/>`_ (for JPEG) and
`openjpeg <http://www.openjpeg.org/>`_ (for JPEG 2000) libraries are installed
beforehand::

  pip install pillow

Through conda::

  conda install -c conda-forge openjpeg jpeg
  conda install pillow


Installing CharPyLS
-------------------

`CharPyLS <https://github.com/Who8MyLunch/CharPyLS>`_ is a Python interface to
the `CharLS <https://github.com/team-charls/charls>`_ C++ library and can
decompress JPEG-LS images.

Using pip::

  pip install cython
  pip install git+https://github.com/Who8MyLunch/CharPyLS

Through conda::

  conda install cython
  pip install git+https://github.com/Who8MyLunch/CharPyLS


Installing GDCM
---------------

`GDCM <http://gdcm.sourceforge.net/>`_ is a C++ library for working with
DICOM datasets that can decompress JPEG, JPEG-LS and JPEG 2000 images.

Unfortunately there's no easy way to install the Python GDCM bindings
using pip. :gh:`This page
<pydicom/wiki/Installing-the-Python-GDCM-bindings-without-Conda>`
has instructions for installing in a virtual environment in Ubuntu
19.04+ or Debian Buster+ using the ``python3-gdcm`` package.

Through conda::

  conda install gdcm -c conda-forge


Installing pylibjpeg
--------------------

`pylibjpeg <https://github.com/pydicom/pylibjpeg>`_ is a Python framework for
decompressing JPEG, JPEG-LS and JPEG 2000 images provided a suitable plugin
is installed.

Using pip::

  pip install pylibjpeg pylibjpeg-libjpeg pylibjpeg-openjpeg


.. _tut_install_dev:

Install the development version
===============================

To install a snapshot of the latest code (the ``master`` branch) from
`GitHub <https://github.com/pydicom/pydicom>`_::

  pip install git+https://github.com/pydicom/pydicom.git

The ``master`` branch is under active development and while it is usually
stable, it may have undocumented changes or bugs.

If you want to keep up-to-date with the latest code, make sure you have
`Git <https://git-scm.com/>`_ installed and then clone the ``master``
branch (this will create a ``pydicom`` directory in your current directory)::

  git clone --depth=1 https://github.com/pydicom/pydicom.git

Then install using pip in editable (``-e``) mode::

  pip install -e pydicom/

When you want to update your copy of the source code, run ``git pull`` from
within the ``pydicom`` directory and Git will download and apply any changes.
