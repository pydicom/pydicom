.. _api_filereader:

=============================
Pydicom API's Reference Guide
=============================

.. rubric:: Common pydicom functions called by user code

File Reading/Parsing
====================

The main function to read and parse DICOM files using pydicom is
``read_file``. It is coded in the module :mod:`pydicom.dicomio`, but is also
imported when the pydicom package is imported::

   >>> import pydicom
   >>> dataset = pydicom.read_file(...)

If you need fine control over the reading, you can either call ``read_partial``
or use ``open_dicom``.  All are documented below:

.. autofunction:: pydicom.dicomio.read_file

.. autofunction:: pydicom.dicomio.read_partial


File Writing
============

DICOM files can also be written using pydicom. There are two ways to do this.
The first is to use ``write_file`` with a prexisting FileDataset (derived from
Dataset) instance.  The second is to use the ``save_as`` method on an Dataset
instance.

.. autofunction:: pydicom.dicomio.write_file

.. automethod:: pydicom.dataset.Dataset.save_as

Dataset
=======

.. autoclass:: pydicom.dataset.Dataset
