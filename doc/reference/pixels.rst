.. _api_pixels:

Pixel Data (:mod:`pydicom.pixels`)
==================================

.. currentmodule:: pydicom.pixels


Pixel Data Utilities
====================

Functions for manipulating (7FE0,0010) *Pixel Data*.

.. currentmodule:: pydicom.pixels

.. autosummary::
  :toctree: generated/

  apply_color_lut
  apply_modality_lut
  apply_rescale
  apply_windowing
  apply_voi
  apply_voi_lut
  convert_color_space
  pack_bits
  unpack_bits


Pixel Data Encoding
===================

:class:`~pydicom.pixels.encoders.base.Encoder` class instances for compressing
(7FE0,0010) *Pixel Data*.

.. currentmodule:: pydicom.pixels

.. autosummary::
   :toctree: generated/

   RLELosslessEncoder


Encoding utilities

.. autosummary::
   :toctree: generated/

   get_encoder


Encoding factory class.

.. currentmodule:: pydicom.pixels.encoders.base

.. autosummary::
   :toctree: generated/

   Encoder
