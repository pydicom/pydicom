.. _api_encaps:

Bulk Data Encapsulation Utilities (:mod:`pydicom.encaps`)
=========================================================

.. currentmodule:: pydicom.encaps

Functions for parsing and applying encapsulation to bulk data elements such
as (7FE0,0010) *Pixel Data*.

Parsing Encapsulated Data
-------------------------

.. autosummary::
   :toctree: generated/

   decode_data_sequence
   defragment_data
   generate_pixel_data
   generate_pixel_data_fragment
   generate_pixel_data_frame
   get_frame_offsets
   read_item

Creating Encapsulated Data
--------------------------

.. autosummary::
   :toctree: generated/

   encapsulate
   encapsulate_extended
   fragment_frame
   itemize_fragment
   itemize_frame
