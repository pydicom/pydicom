.. _api_filereader:

===============================
Reading and writing DICOM files
===============================

.. rubric:: Common pydicom functions called by user code

.. currentmodule:: pydicom

File Reading/Parsing
====================

The main function to read and parse DICOM files using *pydicom* is
:func:`~filereader.dcmread`. It's part of the
:ref:`pydicom.filereader<api_fileio_filereader>`
module, but is also imported when the ``pydicom`` package is
imported

  ::

    >>> import pydicom
    >>> dataset = pydicom.dcmread('path/to/file')

If you need fine control over the reading, you can either call
:func:`~filereader.read_partial` or use :func:`~filereader.dcmread`.


File Writing
============

DICOM files can also be written using *pydicom*. There are two ways to do this.

* The first is to use
  :func:`~filewriter.dcmwrite` with a preexisting :class:`~dataset.FileDataset`
  (derived from :class:`~dataset.Dataset`) instance.
* The second is to use the :meth:`Dataset.save_as()<dataset.Dataset.save_as>`
  method on a ``FileDataset`` or ``Dataset`` instance.
