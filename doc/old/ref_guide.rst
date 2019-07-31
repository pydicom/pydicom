.. _api_filereader:

===============================
Reading and writing DICOM files
===============================

.. rubric:: Common pydicom functions called by user code

File Reading/Parsing
====================

The main function to read and parse DICOM files using *pydicom* is
:meth:`dcmread() <pydicom.filereader.dcmread>`.
It is coded in the module ``pydicom.filereader``, but is also imported when
the ``pydicom`` package is imported

  ::

    >>> import pydicom
    >>> dataset = pydicom.dcmread('path/to/file')

If you need fine control over the reading, you can either call
:meth:`read_partial() <pydicom.filereader.read_partial>` or use
:meth:`dcmread() <pydicom.filereader.dcmread>`.


File Writing
============

DICOM files can also be written using *pydicom*. There are two ways to do this.

* The first is to use
  :meth:`dcmwrite() <pydicom.filewriter.dcmwrite>`
  with a prexisting
  :class:`FileDataset <pydicom.dataset.FileDataset>` (derived from
  :class:`Dataset <pydicom.dataset.Dataset>`) instance.
* The second is to use the
  :meth:`Dataset.save_as() <pydicom.dataset.Dataset.save_as>`
  method on a ``FileDataset`` or ``Dataset`` instance.


You can find the complete API documentation for ``Dataset`` and other
classes :ref:`here <api_reference>`
