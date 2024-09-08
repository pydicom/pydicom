.. _api_encaps:

Bulk Data Encapsulation Utilities (:mod:`pydicom.encaps`)
=========================================================

.. module:: pydicom.encaps
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
   parse_basic_offsets
   parse_fragments
   generate_fragments
   generate_fragmented_frames
   generate_frames
   get_frame

Creating Encapsulated Data
--------------------------

.. autosummary::
   :toctree: generated/

   encapsulate
   encapsulate_buffer
   encapsulate_extended
   encapsulate_extended_buffer
   fragment_frame
   itemize_fragment
   itemize_frame


Management class for encapsulating buffers:

.. autoclass:: EncapsulatedBuffer
    :exclude-members: close, detach, fileno, flush, isatty, read1, readinto, readint1, readline, readlines, truncate, writable, write, writelines
