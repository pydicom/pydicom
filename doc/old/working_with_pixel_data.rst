.. _working_with_pixel_data:
.. title:: Working with Pixel Data

Working with Pixel Data
=======================

.. currentmodule:: pydicom

.. rubric:: How to work with pixel data in pydicom.

Introduction
------------

Many DICOM SOP classes contain bulk pixel data, which is usually used to
represent one or more image frames (although :dcm:`other types of data
<part03/sect_A.18.3.html>` are possible). In these SOP classes the pixel
data is (almost) always contained in the (7FE0,0010) *Pixel Data* element.
The only exception to this is :dcm:`Parametric Map Storage
<part03/sect_A.75.3.html>` which may instead contain data in the (7FE0,0008)
*Float Pixel Data* or (7FE0,0009) *Double Float Pixel Data* elements.

.. note::

    In the following the term *pixel data* will be used to refer to
    the bulk data from *Pixel Data*, *Float Pixel Data* and *Double Float
    Pixel Data* elements. While the examples use ``PixelData``,
    ``FloatPixelData`` or ``DoubleFloatPixelData`` could also be used
    interchangeably provided the dataset contains the corresponding element.

By default *pydicom* reads in pixel data as the raw bytes found in the file::

  >>> from pydicom import dcmread
  >>> from pydicom.data import get_testdata_file
  >>> filename = get_testdata_file("MR_small.dcm")
  >>> ds = dcmread(filename)
  >>> ds.PixelData # doctest: +ELLIPSIS
  b'\x89\x03\xfb\x03\xcb\x04\xeb\x04\xf9\x02\x94\x01\x7f...

``PixelData`` is often not immediately useful as data may be
stored in a variety of different ways:

 - The pixel values may be signed or unsigned integers, or floats
 - There may be multiple image frames
 - There may be :dcm:`multiple planes per frame
   <part03/sect_C.7.6.3.html#sect_C.7.6.3.1.1>` (i.e. RGB) and the :dcm:`order
   of the pixels<part03/sect_C.7.6.3.html#sect_C.7.6.3.1.3>` may be different
 - The image data may be encoded using one of the available compression
   standards (``1.2.840.10008.1.2.4.50`` *JPEG Baseline*,
   ``1.2.840.10008.1.2.5`` *RLE Lossless*, etc). Encoded image data will also
   be :dcm:`encapsulated<part05/sect_A.4.html>` and each encapsulated image
   frame may be broken up into one or more fragments.

Because of the complexity in interpreting the pixel data, *pydicom* provides
an easy way to get it in a convenient form:
:attr:`Dataset.pixel_array<pydicom.dataset.Dataset.pixel_array>`.

If memory efficiency is a priority, refer to
:ref:`Reading Pixel Data with framereader<_working_with_framereader>`

``Dataset.pixel_array``
-----------------------

.. warning::

    :attr:`Dataset.pixel_array<pydicom.dataset.Dataset.pixel_array>`
    requires `NumPy <http://numpy.org/>`_.

:attr:`Dataset.pixel_array<pydicom.dataset.Dataset.pixel_array>` returns a
:class:`numpy.ndarray` containing the pixel data::

  >>> ds.pixel_array # doctest: +NORMALIZE_WHITESPACE
  array([[ 905, 1019, 1227, ...,  302,  304,  328],
         [ 628,  770,  907, ...,  298,  331,  355],
         [ 498,  566,  706, ...,  280,  285,  320],
         ...,
         [ 334,  400,  431, ..., 1094, 1068, 1083],
         [ 339,  377,  413, ..., 1318, 1346, 1336],
         [ 378,  374,  422, ..., 1369, 1129,  862]], dtype=int16)
  >>> ds.pixel_array.shape
  (64, 64)

If the pixel data is compressed then
:attr:`~pydicom.dataset.Dataset.pixel_array` will return the uncompressed data,
provided the dependencies of the required :ref:`pixel data handler
<api_handlers_pixeldata>` are available. See
:doc:`handling compressed image data <image_data_handlers>` for more
information.

NumPy can be used to modify the data, but if the changes are to be saved,
they must be written back to the dataset's ``PixelData`` element.

.. warning::

    Converting data from an ``ndarray`` back to ``bytes`` may not be
    as straightforward as in the following example, particularly for
    multi-planar images or where compression is required.

.. code-block:: python

  # example: zero anything < 300
  arr = ds.pixel_array
  arr[arr < 300] = 0
  ds.PixelData = arr.tobytes()
  ds.save_as("temp.dcm")

Some changes may require other DICOM tags to be modified. For example, if the
image size is reduced (e.g. a 512x512 image is shrunk to 256x256) then
``Rows`` and ``Columns`` should be set
appropriately. You must explicitly set these yourself; *pydicom* does not do so
automatically.

See :ref:`sphx_glr_auto_examples_image_processing_plot_downsize_image.py` for
an example.

:attr:`~pydicom.dataset.Dataset.pixel_array` can also be used to pass image
data to graphics libraries for viewing. See :doc:`viewing_images` for details.


.. _colorspace:

Color space
-----------

When using :attr:`~pydicom.dataset.Dataset.pixel_array`
with *Pixel Data* that has an (0028,0002) *Samples per Pixel* value
of ``3`` then the returned pixel data will be in the color space as given by
(0028,0004) *Photometric Interpretation* (e.g. ``RGB``, ``YBR_FULL``,
``YBR_FULL_422``, etc).

*pydicom* offers a limited ability to convert between 8-bits/channel YBR and
RGB color spaces through the
:func:`~pydicom.pixel_data_handlers.util.convert_color_space`
function. When changing the color space you should also change the value
of *Photometric Interpretation* to match.


.. note:: See the DICOM Standard, Part 3,
   :dcm:`Section C.7.6.3.1<part03/sect_C.7.6.3.html#sect_C.7.6.3.1>` for more
   information about color spaces.


Palette Color
-------------

Some DICOM datasets store their output image pixel values in a lookup table
(LUT), where the values in *Pixel Data* are the index to a corresponding
LUT entry. When a dataset's (0028,0004) *Photometric Interpretation* value is
``PALETTE COLOR`` then the
:func:`~pydicom.pixel_data_handlers.util.apply_color_lut` function can be used
to apply a palette color LUT to the pixel data to produce an RGB image.

.. code-block:: python

    from pydicom.pixel_data_handlers.util import apply_color_lut

    fname = get_testdata_file("OBXXXX1A.dcm")
    ds = dcmread(fname)
    arr = ds.pixel_array
    rgb = apply_color_lut(arr, ds)


It's also possible to apply one of the DICOM
:dcm:`well-known color palettes<part06/chapter_B.html>` provided the bit-depth
of the pixel data is 8-bit.

.. code-block:: python

    from pydicom.pixel_data_handlers.util import apply_color_lut

    fname = get_testdata_file("OBXXXX1A.dcm")
    ds = dcmread(fname)
    arr = ds.pixel_array
    # You could also use the corresponding well-known SOP Instance UID
    rgb = apply_color_lut(arr, palette='PET')


.. note::

    See the DICOM Standard, Part 3, Annexes
    :dcm:`C.7.6.3<part03/sect_C.7.6.3.html>` and
    :dcm:`C.7.9<part03/sect_C.7.9.html>` for more information.


Modality LUT or Rescale Operation
---------------------------------

The DICOM :dcm:`Modality LUT<part03/sect_C.11.html#sect_C.11.1>` module
converts raw pixel data values to a specific (possibly unitless) physical
quantity, such as Hounsfield units for CT. The
:func:`~pydicom.pixel_data_handlers.util.apply_modality_lut` function can be
used with an input array of raw values and a dataset containing a Modality LUT
module to return the converted values. When a dataset requires multiple
grayscale transformations, the Modality LUT transformation is always applied
first.

.. code-block:: python

    from pydicom.pixel_data_handlers.util import apply_modality_lut

    fname = get_testdata_file("CT_small.dcm")
    ds = dcmread(fname)
    arr = ds.pixel_array
    hu = apply_modality_lut(arr, ds)


VOI LUT or Windowing Operation
------------------------------

The DICOM :dcm:`VOI LUT<part03/sect_C.11.2.html>` module applies a
VOI or windowing operation to input values. The
:func:`~pydicom.pixel_data_handlers.util.apply_voi_lut` function
can be used with an input array and a dataset containing a VOI LUT module to
return values with applied VOI LUT or windowing. When a dataset contains
multiple VOI or windowing views then a particular view can be returned by
using the `index` keyword parameter.

When a dataset requires multiple grayscale transformations, then it's assumed
that the modality LUT or rescale operation has already been applied.

.. code-block:: python

    from pydicom.pixel_data_handlers.util import apply_voi_lut

    fname = get_testdata_file("MR-SIEMENS-DICOM-WithOverlays.dcm")
    ds = dcmread(fname)
    arr = ds.pixel_array
    out = apply_voi_lut(arr, ds, index=0)


.. _working_with_framereader:
Reading Pixel Data with ``framereader``
---------------------------------------

The :mod:`~pydicom.framereader` module provides several classes and functions
for working with pixel data when it is not feasible to read the entire Pixel
Data element into memory. This is especially the case for multi-frame DICOMs,
which may have pixel data that is several GigaBytes in size.

The :class:`~pydicom.framereader.FrameReader` class can be used to read and
decode individual frames. The
:meth:`~pydicom.framereader.FrameReader.read_frame_raw` method can be used to
retrieve frame bytes and :meth:`~pydicom.framereader.FrameReader.read_frame`
can be used to retrieve the frame's pixel array if numpy is installed.

.. warning::

    :meth:`~pydicom.framereader.FrameReader.read_frame`
    requires `NumPy <http://numpy.org/>`_.

.. code-block:: python

    from pydicom import framereader

    test_path = get_testdata_file("emri_small.dcm")

    # Basic usage with path
    with framereader.FrameReader(test_path) as frame_reader:
        # index starts at 0, so 0 for the first frame
        index = 0
        # read_frame_raw for retrieving frame bytes
        frame_bytes = frame_reader.read_frame_raw(index)
        # read_frame for the pixel array (requires numpy)
        frame_array = frame_reader.read_frame(index)


:class:`~pydicom.framereader.FrameReader` can take either a path as above or a
file-like object (has `read`, `tell`, `seek` methods) as below

.. code-block:: python

    # Basic usage with file-like object
    with open(test_path, "rb") as file_like:
        with framereader.FrameReader(file_like) as frame_reader:
            # iterate over all frames
            n_frames = frame_reader.number_of_frames
            frame_bytes_list = [
                frame_reader.read_frame_raw(i) for i in range(n_frames)
            ]


In cases the frames may be read several times for a given file, the
:attr:`~pydicom.framereader.FrameReader.frame_info` can be stored as a
dictionary (which could be saved as a json file or to a database) to improve
performance of subsequent reads.



  >>> with framereader.FrameReader(test_path) as frame_reader:
  ...     # seek to pixel data
  ...     frame_reader.fp.seek(frame_reader.pixel_data_location)
  ...     # get the frame_info dictionary
  ...     frame_info_dict = frame_reader.frame_info.to_dict()
  >>> frame_info_dict
  {'basic_offset_table': {'basic_offset_table': [0,
                                                 8192,
                                                 16384,
                                                 24576,
                                                 32768,
                                                 40960,
                                                 49152,
                                                 57344,
                                                 65536,
                                                 73728],
                          'first_frame_location': 2336,
                          'pixel_data_location': 2324},
   'dataset': {'TransferSyntaxUID': '1.2.840.10008.1.2.1',
               'dicom_json': {'00280002': {'Value': [1], 'vr': 'US'},
                              '00280004': {'Value': ['MONOCHROME2'], 'vr': 'CS'},
                              '00280006': {'vr': 'US'},
                              '00280010': {'Value': [64], 'vr': 'US'},
                              '00280011': {'Value': [64], 'vr': 'US'},
                              '00280100': {'Value': [16], 'vr': 'US'},
                              '00280101': {'Value': [12], 'vr': 'US'},
                              '00280102': {'Value': [11], 'vr': 'US'},
                              '00280103': {'Value': [0], 'vr': 'US'}},
               'is_implicit_VR': None,
               'is_little_endian': None},
   'transfer_syntax_uid': '1.2.840.10008.1.2.1'}

To illustrate the benefit of storing frame info to a dictionary, suppose that
it's necessary to store pixel data in separate files and do read frames from
these separate files. One could do the following:

.. code-block:: python

    from io import BytesIO

    # BytesIO for storing Pixel Data
    with BytesIO() as bytes_io_file_like:
        with framereader.FrameReader(test_path) as frame_reader:
            # write pixel data to bytes_io_file_like
            # get length of pixel data
            frame_reader.dicom_file_like.seek(frame_reader.pixel_data_location)
            frame_reader.dicom_file_like.read_tag()
            pixel_data_length = frame_reader.dicom_file_like.read_UL()
            # seek to pixel data
            frame_reader.fp.seek(frame_reader.pixel_data_location)
            # write pixel data to bytes_io_file_like
            bytes_io_file_like.write(frame_reader.fp.read())


            # get the frame_info dictionary
            frame_info_dict = frame_reader.frame_info.to_dict()
            # correct the pixel_data_location to match bytes_io_file_like
            frame_info_dict["basic_offset_table"]["pixel_data_location"] = 0
            # correct the first_frame_location to match bytes_io_file_like
            ff = frame_reader.first_frame_location - frame_reader.pixel_data_location
            frame_info_dict["basic_offset_table"]["first_frame_location"] = ff

            # save frame bytes for comparison
            n_frames = frame_reader.number_of_frames
            original_frame_bytes = [
                frame_reader.read_frame_raw(i) for i in range(n_frames)
            ]
        del frame_reader
        # create FrameInfo object to provide as frame_info kwarg
        frame_info = framereader.FrameInfo.from_dict(frame_info_dict)
        with framereader.FrameReader(
            bytes_io_file_like, frame_info=frame_info
        ) as frame_reader:
            new_frame_bytes = [
                frame_reader.read_frame_raw(i) for i in range(n_frames)
            ]
            # compare to illustrate
            assert new_frame_bytes == original_frame_bytes