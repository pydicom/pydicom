.. _api_filereader:

=======================
Pydicom Reference Guide
=======================

.. rubric:: Common pydicom functions called by user code

File Reading/Parsing
====================

The main function to read and parse DICOM files using pydicom is ``read_file``. It is coded in the module
dicom.filereader, but is also imported when the dicom package is imported::

   >>> import dicom
   >>> dataset = dicom.read_file(...)

If you need fine control over the reading, you can either call ``read_partial`` or use ``open_dicom``.
All are documented below:

.. autofunction:: dicom.filereader.read_file

.. autofunction:: dicom.filereader.read_partial

.. autofunction:: dicom.filereader.open_dicom

Dataset
=======

.. autoclass:: dicom.dataset.Dataset