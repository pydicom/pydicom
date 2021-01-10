.. _working_with_overlay_data:
.. title:: Working with Overlay Data

Working with Overlay Data
=========================

.. currentmodule:: pydicom

.. rubric:: How to work with overlay data in pydicom.

Introduction
------------

:dcm:`Overlays<part03/sect_C.9.2.html>` in DICOM are present in what's called
a :dcm:`Repeating Group<part05/sect_7.6.html>`, where the group number of the
element tags are defined over a range rather than a specific value. For
example, the tag's group number for (60xx,3000) *Overlay Data* may be (in hex)
``6000``, ``6002``, or any even value up to ``601E``. This allows a dataset to
include multiple overlays, where the related elements for each overlay use the
same group number. Because of this, the only way to access a particular
element from an overlay is to use the ``Dataset[group, elem]`` method:

>>> import pydicom
>>> from pydicom.data import get_testdata_files
>>> fpath = get_testdata_files("MR-SIEMENS-DICOM-WithOverlays.dcm")[0]
>>> ds = pydicom.dcmread(fpath)
>>> elem = ds[0x6000, 0x3000]  # returns a DataElement
>>> print(elem)
(6000, 3000) Overlay Data                        OW: Array of 29282 elements


pydicom tends to be "lazy" in interpreting DICOM data. For example, by default
it doesn't do anything with overlay data except read in the raw bytes::

  >>> elem.value # doctest: +ELLIPSIS
  b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00...

``Dataset.overlay_array()``
---------------------------

.. warning::

   :meth:`Dataset.overlay_array()<pydicom.dataset.Dataset.overlay_array>`
   requires `NumPy <http://numpy.org/>`_.

The *Overlay Data* element contains the raw bytes exactly as found in the file
as bit-packed data. To unpack and get an overlay in a more useful form you
can use the :meth:`~pydicom.dataset.Dataset.overlay_array` method to return a
:class:`numpy.ndarray`. To use it you simply pass the group number of the
overlay elements you're interested in::

  >>> arr = ds.overlay_array(0x6000) # doctest: +NORMALIZE_WHITESPACE
  >>> arr
  array([[ 0, 0, 0, ...,  0,  0,  0],
         [ 0, 0, 0, ...,  0,  0,  0],
         [ 0, 0, 0, ...,  0,  0,  0],
         ...,
         [ 0, 0, 0, ...,  0,  0,  0],
         [ 0, 0, 0, ...,  0,  0,  0],
         [ 0, 0, 0, ...,  0,  0,  0],], dtype=uint8)
  >>> arr.shape
  (484, 484)

One thing to remember when dealing with *Overlay Data* is that the top left
of the overlay doesn't necessarily have to line up with the top left of the
related *Pixel Data*. The actual offset between them can be determined from
(60xx,0050) *Overlay Origin*, where a value of ``[1, 1]`` indicates that
the top left pixels are aligned and a value of ``[0, 0]`` indicates that the
overlay pixels start 1 row above and 1 row to the left of the image pixels.

NumPy can be used to modify the pixels, but if the changes are to be saved,
they must be bit-packed (using something like
:func:`~pydicom.pixel_data_handlers.numpy_handler.pack_bits`) and written
back to the correct element:

.. code-block:: python

  # Add a line
  arr[10, :] = 1

  # Pack the data
  from pydicom.pixel_data_handlers.numpy_handler import pack_bits
  packed_bytes = pack_bits(arr)

  # Update the element value
  ds[0x6000, 0x3000].value = packed_bytes
  ds.save_as("temp.dcm")

Some changes may require other DICOM elements to be modified. For example, if
the overlay data is reduced (e.g. a 512x512 image is collapsed
to 256x256) then the corresponding (60xx,0010) *Overlay Rows*
and (60xx,0011) *Overlay Columns* should be set appropriately. You must
explicitly set these yourself; pydicom does not do so automatically.
