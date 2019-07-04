.. _api_filereader:

===============================
Reading and writing DICOM files
===============================

.. rubric:: Common pydicom functions called by user code

File Reading/Parsing
====================

The main function to read and parse DICOM files using pydicom is ``dcmread``. It is coded in the module
dicom.filereader, but is also imported when the pydicom package is imported::

   >>> import pydicom
   >>> dataset = pydicom.dcmread(...)

If you need fine control over the reading, you can either call ``read_partial`` or use ``open_dicom``.
All are documented below:

.. autofunction:: pydicom.filereader.dcmread

.. autofunction:: pydicom.filereader.read_partial


File Writing
============

DICOM files can also be written using pydicom. There are two ways to do this.
The first is to use ``dcmwrite`` with a prexisting FileDataset (derived from Dataset) instance.
The second is to use the ``save_as`` method on an Dataset instance.

.. autofunction:: pydicom.filewriter.dcmwrite

.. automethod:: pydicom.dataset.Dataset.save_as

You can find the complete API documentation for ``Dataset`` and other
classes in the following section.