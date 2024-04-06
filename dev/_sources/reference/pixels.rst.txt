.. _api_pixels:

Pixel Data (:mod:`pydicom.pixels`)
==================================

.. module:: pydicom.pixels
.. currentmodule:: pydicom.pixels


Image processing functions

.. autosummary::
  :toctree: generated/

   apply_color_lut
   apply_modality_lut
   apply_voi_lut
   apply_voi
   apply_windowing
   convert_color_space


Utility functions

.. autosummary::
   :toctree: generated/

   as_pixel_options
   get_decoder
   get_encoder
   iter_pixels
   pack_bits
   pixel_array
   unpack_bits


Sub-modules
-----------

.. toctree::
   :maxdepth: 1
   :includehidden:

   pixels.decoders
   pixels.encoders
   pixels.processing
   pixels.utils
