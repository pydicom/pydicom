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
