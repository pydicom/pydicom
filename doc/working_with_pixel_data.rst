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

``pixel_array``
---------------

.. warning::

    To work with the pixel_array property `NumPy <http://numpy.org/>`_ must be
    installed on your system.

A property of :class:`dataset.Dataset` called ``pixel_array`` provides more
useful pixel data for uncompressed and compressed images
(:doc:`decompressing compressed images if supported </image_data_handlers>`).
The ``pixel_array`` property returns a NumPy array::

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

NumPy can be used to modify the pixels, but if the changes are to be saved,
they must be written back to the ``PixelData`` attribute:

.. code-block:: python

  for n,val in enumerate(ds.pixel_array.flat): # example: zero anything < 300
      if val < 300:
          ds.pixel_array.flat[n]=0
  ds.PixelData = ds.pixel_array.tobytes()
  ds.save_as("newfilename.dcm")

  import os
  os.remove("newfilename.dcm")

Some changes may require other DICOM tags to be modified. For example, if the
pixel data is reduced (e.g. a :math:`512 \times 512` image is collapsed to
:math:`256 \times 256`) then ``ds.Rows`` and ``ds.Columns`` should be set
appropriately. You must explicitly set these yourself; pydicom does not do so
automatically.

See :ref:`sphx_glr_auto_examples_image_processing_plot_downsize_image.py` for
an example.

``pixel_array`` can also be used to pass image data to graphics libraries
for viewing. See :doc:`viewing_images` for details.
