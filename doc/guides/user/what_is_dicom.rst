What is DICOM?
==============

`DICOM <https://www.dicomstandard.org/>`_ (Digital Imaging and Communications in Medicine) is a
wide-ranging `collection of standards <https://www.dicomstandard.org/current>`_
relating to the storage, presentation and communication of medical images and information.

A fundamental part of the DICOM Standard is the :dcm:`Data Set<part05/chapter_7.html>`,
which is used as a container for medical and other information. DICOM has standardized
definitions for many different types of Data Set; a Data Set may contain anything from images
acquired during an ultrasound, to a request sent to a DICOM application for transfer of those
images, to the radiologist's report describing them. Despite their differences, because each
type of Data Set is made from the same standard building blocks, all conformant Data Sets can
be easily shared and understood.


How does this relate to *pydicom*?
----------------------------------
*pydicom* can be used to create, read, modify and write DICOM Data Sets and File-sets (collections
of stored Data Sets). It can also be used to convert the imaging and other bulk data commonly
found in Data Sets to a `NumPy <https://numpy.org/>`_ ``ndarray``, making it a very useful part
of an image processing pipeline for medical data.

*pydicom* implements the following parts of the DICOM Standard:

* :dcm:`Part 5: Data Structures and Encoding<part05/ps3.5.html>`, which covers the encoding of
  Data Sets and Data Elements.
* :dcm:`Part 6: Data Dictionary<part06/ps3.6.html>`, which lists the standard Data Elements and UIDs.
* :dcm:`Part 10: Media Storage and File Format for Media Exchange<part10/ps3.10.html>`, which
  defines the DICOM File Format and File-set.
* :dcm:`Part 16: Content Mapping Resource<part16/ps3.16.html>`, which contains the concept
  definitions used by code groups and structured reports.

Furthermore, when used with `pynetdicom <https://pydicom.github.io/pynetdicom/stable/>`_, the
following parts are also implemented, allowing you to easily create code to transfer Data Sets
between DICOM applications:

* :dcm:`Part 4: Service Class Specifications<part04/ps3.4.html>`, which defines the services
  DICOM applications may implement.
* :dcm:`Part 7: Message Exchange<part07/ps3.7.html>`, which defines DIMSE messaging.
* :dcm:`Part 8: Network Communication Support for Message Exchange<part08/ps3.8.html>`, which
  defines how two DICOM applications can communicate by exchanging DIMSE messages.
