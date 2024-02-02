.. _guide_decoder_options:

==========================
Pixel Data Decoder Options
==========================

.. currentmodule:: pydicom.pixels.decoders.base

The following applies to the functions and class methods that use the
:doc:`pixels</reference/pixels>` backend for decoding pixel data. This includes functions
such as :func:`~pydicom.pixels.pixel_array` and :func:`~pydicom.pixels.iter_pixels`
as well as the following methods of :class:`~Decoder` class:

* :meth:`Decoder.as_array`
* :meth:`Decoder.as_buffer`
* :meth:`Decoder.iter_array`
* :meth:`Decoder.iter_buffer`

*Image Pixel* Options
=====================

The following options are required when the decoding source `src` is not a
:class:`~pydicom.dataset.Dataset` and are used to describe the encoded pixel data.
They may be also be used to override the corresponding element values when `src`
is a :class:`~pydicom.dataset.Dataset`:


+------------------------------+------------+-----------+---------------+----------------------------------------------------------+
| Option                       | Type       | Corresponding Element     | Description                                              |
|                              |            +-----------+---------------+                                                          |
|                              |            | Tag       | Name          |                                                          |
+==============================+============+===========+===============+==========================================================+
| `rows`                       |:class:`int`|(0028,0010)| *Rows*        | The number of :ref:`rows<rows>` in `src`                 |
+------------------------------+------------+-----------+---------------+----------------------------------------------------------+
| `columns`                    |:class:`int`|(0028,0011)| *Columns*     | The number of :ref:`columns<columns>` in `src`           |
+------------------------------+------------+-----------+---------------+----------------------------------------------------------+
| `number_of_frames`           |:class:`int`|(0028,0008)| *Number       | The :ref:`number of frames<number_of_frames>` in `src`   |
|                              |            |           | of Frames*    |                                                          |
+------------------------------+------------+-----------+---------------+----------------------------------------------------------+
| `samples_per_pixel`          |:class:`int`|(0028,0002)| *Samples      | The number of :ref:`samples per pixel                    |
|                              |            |           | Per Pixel*    | <samples_per_pixel>`                                     |
+------------------------------+------------+-----------+---------------+----------------------------------------------------------+
| `bits_allocated`             |:class:`int`|(0028,0100)| *Bits         | The number of bits used to :ref:`contain each pixel      |
|                              |            |           | Allocated*    | <bits_allocated>`                                        |
+------------------------------+------------+-----------+---------------+----------------------------------------------------------+
| `bits_stored`                |:class:`int`|(0028,0101)|*Bits Stored*  | The number of bits actually :ref:`used by each pixel     |
|                              |            |           |               | <bits_stored>`                                           |
+------------------------------+------------+-----------+---------------+----------------------------------------------------------+
| `photometric_interpretation` |:class:`str`|(0028,0004)|*Photometric   | The :ref:`color space<photometric_interpretation>`       |
|                              |            |           |Interpretation*| of the encoded pixel data                                |
+------------------------------+------------+-----------+---------------+----------------------------------------------------------+
| `pixel_representation`       |:class:`int`|(0028,0103)|*Pixel         | Required if `pixel_keyword` is ``'PixelData'``, whether  |
|                              |            |           |Representation*| the pixels are :ref:`signed or unsigned                  |
|                              |            |           |               | <pixel_representation>`                                  |
+------------------------------+------------+-----------+---------------+----------------------------------------------------------+
| `planar_configuration`       |:class:`int`|(0028,0006)|*Planar        | Required if `samples_per_pixel` > 1, the :ref:`pixel     |
|                              |            |           |Configuration* | encoding order<planar_configuration>`                    |
+------------------------------+------------+-----------+---------------+----------------------------------------------------------+
| `pixel_keyword`              |:class:`str`|                           | Required if `src` uses a native (uncompressed) transfer  |
|                              |            |                           | syntax, the keyword of the element containing the pixel  |
|                              |            |                           | data. One of ``'PixelData'``, ``'FloatPixelData'``,      |
|                              |            |                           | ``'DoubleFloatPixelData'``                               |
+------------------------------+------------+---------------------------+----------------------------------------------------------+


Image Processing Options
========================

The following options may be used with any transfer syntax for controlling the
processing applied after decoding to a NumPy :class:`~numpy.ndarray` using
:func:`~pydicom.pixels.pixel_array`, :func:`~pydicom.pixels.iter_pixels`,
:meth:`Decoder.as_array` or :meth:`Decoder.iter_array`.

* `as_rgb`: :class:`bool` - if ``True`` (default) then convert pixel data with a
  YCbCr :ref:`photometric interpretation<photometric_interpretation>`
  such as ``"YBR_FULL_422"`` to RGB.
* `force_rgb`: :class:`bool` - if ``True`` then force a YCbCr to RGB color space
  conversion on the array (default ``False``).
* `force_ybr`: :class:`bool` - if ``True`` then force an RGB to YCbCr color space
  conversion on the array (default ``False``).


Miscellaneous Options
=====================

The following options may be used with native (uncompressed) transfer syntaxes
when decoding to a NumPy :class:`~numpy.ndarray` using :func:`~pydicom.pixels.pixel_array`,
:func:`~pydicom.pixels.iter_pixels`, :meth:`Decoder.as_array` or :meth:`Decoder.iter_array`.

* `view_only`: :class:`bool` - if ``True`` and `src` is a
  :class:`~pydicom.dataset.Dataset` or buffer-like then make a best effort
  attempt to return an :class:`~numpy.ndarray` that's a `view
  <https://numpy.org/doc/stable/user/basics.copies.html#view>`_ on the original
  buffer (default ``False``). Note that if the original buffer is immutable then
  the returned :class:`~numpy.ndarray` will be read-only.


.. _guide_decoder_plugin_opts:


Decoding Plugin Options
=======================

The following options are plugin and transfer syntax specific.

*RLE Lossless*
--------------

+---------------+---------------------+----------------------------------------+
| Plugin        | Option              | Description                            |
| name          |                     |                                        |
+===============+=====================+========================================+
| ``pydicom``   |``rle_segment_order``| ``">"`` for big endian segment order   |
+---------------+---------------------+ (default) or ``"<"`` for little endian |
| ``pylibjpeg`` |``byteorder``        | segment order                          |
+---------------+---------------------+----------------------------------------+
