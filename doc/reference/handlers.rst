.. _api_handlers:

Bulk Data Handlers
==================

Functions for handling bulk data elements such as (7FE0,0010) *Pixel Data*

.. toctree::
   :maxdepth: 1
   :includehidden:

   handlers.pixel_data

Pixel Data Utilities
====================

Functions for manipulating (7FE0,0010) *Pixel Data*.

.. currentmodule:: pydicom.pixel_data_handlers

.. autosummary::
   :toctree: generated/

   apply_color_lut
   apply_modality_lut
   apply_rescale
   apply_windowing
   apply_voi
   apply_voi_lut
   convert_color_space
   util
