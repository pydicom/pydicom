.. _api_framereader:

Reading Frames from Pixel Data (:mod:`pydicom.framereader`)
===========================================================

.. currentmodule:: pydicom.framereader

Utilities for reading individual frames from DICOM files and related functions.

.. autosummary::
   :toctree: generated/

   FrameReader
   FrameInfo
   FrameDataset
   BasicOffsetTable
   read_encapsulated_basic_offset_table
   get_encapsulated_basic_offset_table
   build_encapsulated_basic_offset_table
   get_dataset_copy_with_frame_attrs