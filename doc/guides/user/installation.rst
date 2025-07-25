============
Installation
============

.. note::

   We recommend installing into a
   `virtual environment <https://docs.python.org/3/tutorial/venv.html>`_,
   which is an isolated Python environment that allows you to install
   packages without admin privileges.


.. _tut_install:

Install the official release
============================

*pydicom*, being a Python library, requires `Python
<https://www.python.org/>`_. If you're not sure whether or not your version of
Python is supported, you can check :ref:`this table<faq_install_version>`.

.. tab-set::
    :sync-group: install
    :class: sd-width-content-min

    .. tab-item:: pip
        :sync: pip

        .. code-block:: bash

            pip install -U pydicom

    .. tab-item:: conda
        :sync: conda

        .. code-block:: bash

            conda install -c conda-forge pydicom

You can also perform an offline installation by
`downloading <https://pypi.org/project/pydicom/#files>`_ and installing
one of the release ``*.whl`` files. For example, with the `file for the v3.0
release <https://pypi.org/project/pydicom/3.0.1/#files>`_::

  pip install pydicom-3.0.1-py3-none-any.whl


Additional type hints
---------------------

*pydicom's* default type hinting doesn't cover standard elements accessed via their
keyword through :class:`~pydicom.dataset.Dataset`::

    # foo.py
    from pydicom import Dataset

    ds = Dataset()
    ds.PatientName = 1234

.. code-block:: shell

    $ mypy foo.py
    Success: no issues found in 1 source file

To add type hints for these attributes you can install the `types-pydicom <https://github.com/pydicom/types-pydicom>`_ package::

    pip install -U types-pydicom

.. code-block:: shell

    $ mypy foo.py
    foo.py:5: error: Incompatible types in assignment (expression has type "int", variable has type "str | PersonName | None")  [assignment]
    Found 1 error in 1 file (checked 1 source file)


.. _tut_install_libs:
.. _tut_install_np:

Install the optional libraries
==============================

If you're going to be manipulating pixel data as anything other than raw :class:`bytes`
then `NumPy <https://numpy.org/>`_ is required.


.. tab-set::
    :sync-group: install
    :class: sd-width-content-min

    .. tab-item:: pip
        :sync: pip

        .. code-block:: bash

            pip install -U numpy

    .. tab-item:: conda
        :sync: conda

        .. code-block:: bash

            conda install numpy


To decode JPEG compressed pixel data one or more additional libraries will
need to be installed. See :doc:`this page </guides/plugin_table>` for details of
which library is needed to compress or decompress using a given compression
method, as specified by the dataset's (0002,0010) *Transfer Syntax UID* value.


.. _tut_install_pil:

Installing Pillow
-----------------

`Pillow <https://pillow.readthedocs.io/>`_ is a popular Python imaging library
that can handle the decompression of some JPEG and JPEG 2000 images. It includes
JPEG support by default, however JPEG 2000 requires the
`openjpeg <https://www.openjpeg.org/>`_  library be installed.

.. tab-set::
    :sync-group: install
    :class: sd-width-content-min

    .. tab-item:: pip
        :sync: pip

        .. code-block:: bash

            pip install -U pillow

    .. tab-item:: conda
        :sync: conda

        .. code-block:: bash

            conda install -c conda-forge openjpeg jpeg
            conda install pillow


.. _tut_install_pylj:

Installing pylibjpeg
--------------------

:gh:`pylibjpeg <pylibjpeg>` is a Python framework for
decompressing JPEG, JPEG-LS images and compressing or decompressing JPEG 2000 and
RLE images, provided a suitable plugin is installed.

.. tab-set::
    :sync-group: install
    :class: sd-width-content-min

    .. tab-item:: pip
        :sync: pip

        .. code-block:: bash

            pip install -U pylibjpeg[all]

    .. tab-item:: conda
        :sync: conda

        .. code-block:: bash

            conda install -c conda-forge pylibjpeg[all]


Installing pyjpegls
-------------------

`pyjpegls <https://github.com/pydicom/pyjpegls>`_ is a Python interface to
the `CharLS <https://github.com/team-charls/charls>`_ C++ library and can
compress and decompress JPEG-LS images. It's a fork of `CharPyLS
<https://github.com/Who8MyLunch/CharPyLS>`_ created to provide compatibility with the
latest Python versions.

.. tab-set::
    :sync-group: install
    :class: sd-width-content-min

    .. tab-item:: pip
        :sync: pip

        .. code-block:: bash

            pip install -U pyjpegls

    .. tab-item:: conda
        :sync: conda

        .. code-block:: bash

            conda install -c conda-forge pyjpegls



.. _tut_install_gdcm:

Installing GDCM
---------------

`GDCM <https://sourceforge.net/projects/gdcm/>`_ is a C++ library for working
with DICOM datasets that can decompress JPEG, JPEG-LS and JPEG 2000 images.

The wheels on `PyPI <https://pypi.org/project/python-gdcm/>`__ are built by the
`python-gdcm <https://github.com/tfmoraes/python-gdcm>`_ project for current
versions of Python on Windows, MacOS and Linux, and can be installed using pip.

The wheels available through `conda-forge <https://anaconda.org/conda-forge/gdcm>`__
tend to be older versions and may not be as well supported.

.. tab-set::
    :sync-group: install
    :class: sd-width-content-min

    .. tab-item:: pip
        :sync: pip

        .. code-block:: bash

            pip install -U python-gdcm

    .. tab-item:: conda
        :sync: conda

        .. code-block:: bash

            conda install -c conda-forge gdcm


.. _tut_install_dev:

Install the development version
===============================

To install a snapshot of the latest code (the ``main`` branch) from
:gh:`GitHub <pydicom>`::

  pip install git+https://github.com/pydicom/pydicom

The ``main`` branch is under active development and while it's usually
stable, it may have undocumented changes or bugs.

If you want to keep up-to-date with the latest code, make sure you have
`Git <https://git-scm.com/>`_ installed and then clone the ``main``
branch (this will create a ``pydicom`` directory in your current directory)::

  git clone --depth=1 https://github.com/pydicom/pydicom.git

Then install using pip in editable (``-e``) mode::

  pip install -e pydicom/

When you want to update your copy of the source code, run ``git pull`` from
within the ``pydicom`` directory and Git will download and apply any changes.
