.. _faq:

==========================
Frequently asked questions
==========================

.. _faq_general:

General
=======

What happened to import dicom?
------------------------------
Starting in version 1.0, *pydicom* changed the library import from
``import dicom`` to ``import pydicom``. If you're used to using the earlier
versions of *pydicom* see the :doc:`transitioning guide
<../old/transition_to_pydicom1>` on how to make the change.

How do I cite pydicom?
----------------------

The easiest method is probably to `find the Zenodo DOI
<https://zenodo.org/search?page=1&size=20&q=conceptrecid:1291985&all_versions&sort=-version>`_
for the version you are using and then entering your required citation style
in the *Cite as* box.

Alternatively, you can use something along the lines of:

.. code-block:: text

  Mason, D. L., et al, pydicom: An open source DICOM library, https://github.com/pydicom/pydicom [Online; accessed YYYY-MM-DD].


.. _faq_install:

Installation
============

What are pydicom's prerequisites?
---------------------------------

Required
~~~~~~~~
*pydicom* requires Python.

Optional
~~~~~~~~
When manipulating *Pixel Data* it's recommended you install
`NumPy <https://numpy.org/>`_. When dealing with JPEG
compressed *Pixel Data* see :ref:`this table<guide_compressed>` for which
libraries are required.

.. _faq_install_version:

What version of Python can I use?
---------------------------------

+-----------------+------------------+---------------------------+
| pydicom version |  Release date    | Python versions           |
+=================+==================+===========================+
| 1.0             | March 2018       | 2.7, 3.4, 3.5, 3.6        |
+-----------------+------------------+---------------------------+
| 1.1             | June 2018        | 2.7, 3.4, 3.5, 3.6        |
+-----------------+------------------+---------------------------+
| 1.2             | October 2018     | 2.7, 3.4, 3.5, 3.6        |
+-----------------+------------------+---------------------------+
| 1.3             | July 2019        | 2.7, 3.4, 3.5, 3.6        |
+-----------------+------------------+---------------------------+
| 1.4             | January 2020     | 2.7, 3.5, 3.6, 3.7, 3.8   |
+-----------------+------------------+---------------------------+
| 2.0             | May 2020         | 3.5, 3.6, 3.7, 3.8        |
+-----------------+------------------+---------------------------+
| 2.1             | November 2020    | 3.6, 3.7, 3.8, 3.9        |
+-----------------+------------------+---------------------------+
| 2.2             | August 2021      | 3.6, 3.7, 3.8, 3.9        |
+-----------------+------------------+---------------------------+
| 2.3             | March 2022       | 3.6, 3.7, 3.8, 3.9, 3.10  |
+-----------------+------------------+---------------------------+
| 2.4             | ~September 2022  | 3.7, 3.8, 3.9, 3.10, 3.11 |
+-----------------+------------------+---------------------------+

What about support for Python 2.7?
----------------------------------

Python 2.7 reached `end of life <https://www.python.org/doc/sunset-python-2/>`_
on 1st January, 2020 and is no longer supported by *pydicom*. More information
is available :doc:`here</old/python2_support>`.
