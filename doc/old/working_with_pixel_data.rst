.. _working_with_pixel_data:
.. title:: Working with Pixel Data

Working with Pixel Data
=======================

.. currentmodule:: pydicom

.. rubric:: How to work with pixel data in pydicom.

Introduction
------------

pydicom tends to be "lazy" in interpreting DICOM data. For example, by default
it doesn't do anything with pixel data except read in the raw bytes::

  >>> import pydicom
  >>> from pydicom.data import get_testdata_files
  >>> filename = get_testdata_files("MR_small.dcm")[0]
  >>> ds = pydicom.dcmread(filename)
  >>> ds.PixelData # doctest: +ELLIPSIS
  b'\x89\x03\xfb\x03\xcb\x04\xeb\x04\xf9\x02\x94\x01\x7f...

``PixelData`` contains the raw bytes exactly as found in the file. If the
image is JPEG compressed, these bytes will be the compressed pixel data, not
the expanded, uncompressed image. Whether the image is e.g. 16-bit or 8-bit,
multiple frames or not, ``PixelData`` contains the same raw bytes. But there is
a function that can shape the pixels more sensibly if you need to work with
them ...

``Dataset.pixel_array``
-----------------------

.. warning::

    :attr:`Dataset.pixel_array<pydicom.dataset.Dataset.pixel_array>`
    requires `NumPy <http://numpy.org/>`_.

:attr:`Dataset.pixel_array<pydicom.dataset.Dataset.pixel_array>` returns a
:class:`numpy.ndarray` containing the *Pixel Data*::

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

If the *Pixel Data* is compressed then
:attr:`~pydicom.dataset.Dataset.pixel_array` will return the uncompressed data,
provided the dependencies of the required pixel data handler are available. See
:doc:`handling compressed image data <image_data_handlers>` for more
information.

NumPy can be used to modify the pixel data, but if the changes are to be saved,
they must be written back to the dataset's ``PixelData`` element:

.. code-block:: python

  # example: zero anything < 300
  arr = ds.pixel_array
  arr[arr < 300] = 0
  ds.PixelData = arr.tobytes()
  ds.save_as("temp.dcm")

Some changes may require other DICOM tags to be modified. For example, if the
pixel data is reduced (e.g. a :math:`512 \times 512` image is collapsed to
:math:`256 \times 256`) then ``Rows`` and ``Columns`` should be set
appropriately. You must explicitly set these yourself; pydicom does not do so
automatically.

See :ref:`sphx_glr_auto_examples_image_processing_plot_downsize_image.py` for
an example.

:attr:`~pydicom.dataset.Dataset.pixel_array` can also be used to pass image
data to graphics libraries for viewing. See :doc:`viewing_images` for details.

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

    fname = get_testdata_files("OBXXXX1A.dcm")[0]
    ds = dcmread(fname)
    arr = ds.pixel_array
    rgb = apply_color_lut(arr, ds)


Its also possible to apply one of the DICOM
:dcm:`well-known color palettes<part06/chapter_B.html>` provided the bit-depth
of the pixel data is 8-bit.

.. code-block:: python

    from pydicom.pixel_data_handlers.util import apply_color_lut

    fname = get_testdata_files("OBXXXX1A.dcm")[0]
    ds = dcmread(fname)
    arr = ds.pixel_array
    # You could also use the corresponding well-known SOP Instance UID
    rgb = apply_color_lut(arr, palette='PET')


.. note::

    See the DICOM Standard, Part 3, Annexes
    :dcm:`C.7.6.3<part03/sect_C.7.6.3.html>` and
    :dcm:`C.7.9<part03/sect_C.7.9.html>` for more information.


Modality LUT
------------

The DICOM :dcm:`Modality LUT<part03/sect_C.11.html#sect_C.11.1>` module
converts raw unitless pixel data values to a specific output unit (such as
Hounsfield units for CT). The
:func:`~pydicom.pixel_data_handlers.util.apply_modality_lut` function can be
used with an input array of raw values and a dataset containing a Modality LUT
module to return the defined values.

.. code-block:: python

    from pydicom.pixel_data_handlers.util import apply_modality_lut

    fname = get_testdata_files("CT_small.dcm")[0]
    ds = dcmread(fname)
    arr = ds.pixel_array
    hu = apply_modality_lut(arr, ds)
