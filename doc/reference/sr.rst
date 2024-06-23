
Concepts and Context Groups (:mod:`pydicom.sr`)
===============================================

.. module:: pydicom.sr
.. currentmodule:: pydicom.sr

The ``sr`` module contains an interface for DICOM's :dcm:`CIDs<part16/chapter_B.html>`.


.. autosummary::
   :toctree: generated/

   Collection
   Concepts
   Code


Usage
-----

Individual :class:`~pydicom.sr.coding.Code` values can be accessed via either
their scheme (such as SCT) or the DICOM CID::

  >>> from pydicom.sr import codes
  >>> codes.SCT.Transverse
  Code(value='62824007', scheme_designator='SCT', meaning='Transverse', scheme_version=None)
  >>> codes.CID4.Cornea
  Code(value='28726007', scheme_designator='SCT', meaning='Cornea', scheme_version=None)

A list of available attribute keywords for each scheme or CID is available via
:meth:`~pydicom.sr.Collection.dir`::

  >>> dir(codes.CID6)
  ['Coronal', 'FiveChamber', 'FourChamber', ... ]
