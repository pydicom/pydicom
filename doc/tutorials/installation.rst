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

*pydicom* is available on `PyPI <https://pypi.python.org/pypi/pydicom/>`_, the
official third-party Python software repository. The simplest way to install
from PyPI is using `pip <https://pip.pypa.io/>`_ with the command::

  pip install pydicom

You may need to use this instead, depending on your operating system::

  python -m pip install pydicom

You can also perform an offline installation by
:gh:`downloading <pydicom/releases>` and installing
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
:gh:`pydicom-data <pydicom-data>` repository. To get the complete set of
testing and example files you can either install the *pydicom-data* repository::

  pip install git+https://github.com/pydicom/pydicom-data

Or download the missing files to the local cache (after installing *pydicom*)::

  python -c "import pydicom; pydicom.data.fetch_data_files()"


.. _tut_install_libs:
.. _tut_install_np:

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


.. _tut_install_pil:

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


Installing pyjpegls
-------------------

`pyjpegls <https://github.com/pydicom/pyjpegls>`_ is a Python interface to
the `CharLS <https://github.com/team-charls/charls>`_ C++ library and can
decompress JPEG-LS images. It is a fork of `CharPyLS <https://github.com/Who8MyLunch/CharPyLS>`_
created to provide compatibility with the latest Python versions.

Using pip::

  pip install pyjpegls

Through conda::

  conda install cython
  pip install git+https://github.com/pydicom/pyjpegls


.. _tut_install_gdcm:

Installing GDCM
---------------

`GDCM <http://gdcm.sourceforge.net/>`_ is a C++ library for working with
DICOM datasets that can decompress JPEG, JPEG-LS and JPEG 2000 images.

The wheels on `PyPI <https://pypi.org/project/python-gdcm/>`_ are built by the
`python-gdcm <https://github.com/tfmoraes/python-gdcm>`_ project for current
versions of Python on Windows, MacOS and Linux, and can be installed using pip::

  pip install python-gdcm

The wheels available through `conda-forge <https://anaconda.org/conda-forge/gdcm>`_
tend to be older versions and not as well supported. They're available on conda using::

  conda install gdcm -c conda-forge


.. _tut_install_pylj:

Installing pylibjpeg
--------------------

:gh:`pylibjpeg <pylibjpeg>` is a Python framework for
decompressing JPEG, JPEG-LS, JPEG 2000 images and compressing or decompressing
RLE images provided a suitable plugin is installed.

Using pip::

  pip install -U pylibjpeg[all]


.. _tut_install_dev:

Install the development version
===============================

To install a snapshot of the latest code (the ``master`` branch) from
:gh:`GitHub <pydicom>`::

  pip install git+https://github.com/pydicom/pydicom

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
