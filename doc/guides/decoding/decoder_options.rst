.. _guide_decoder_options:

==========================
Pixel Data Decoder Options
==========================

.. currentmodule:: pydicom.pixels.decoders.base

*Image Pixel* Options
=====================

The following are required when the decoding source `src` is not a
:class:`~pydicom.dataset.Dataset`, or may be used to override the corresponding
element values when `src` is a :class:`~pydicom.dataset.Dataset`:

* `rows`: :class:`int` - the number of :ref:`rows<glossary_rows>` of pixels in
  `src`, maximum 65535.
* `columns`: :class:`int` - the number of :ref:`columns<glossary_columns>` of
  pixels in `src`, maximum 65535.
* `number_of_frames`: :class:`int` - the :ref:`number of frames
  <glossary_number_of_frames>` in `src`, minimum 1.
* `samples_per_pixel`: :class:`int` - the number of :ref:`samples per pixel
  <glossary_samples_per_pixel>` in `src`, should be 1 or 3.
* `bits_allocated`: :class:`int` - the number of :ref:`bits used to contain
  <glossary_bits_allocated>` each pixel, should be 1 or a multiple of 8.
* `bits_stored`: :class:`int` - the number of :ref:`bits actually used
  <glossary_bits_stored>` per pixel. For example, `src` might have 16-bits
  allocated (range 0 to 65535) but only contain 12-bit pixel values (range 0 to
  4095).
* `photometric_interpretation`: :class:`str` - the :ref:`color space
  <glossary_photometric_interpretation>` of the *encoded* pixel data, such as
  ``"YBR_FULL"``.

In addition, the following are conditionally required for native (uncompressed)
transfer syntaxes:

* `pixel_keyword`: :class:`str` - one of ``"PixelData"``, ``"FloatPixelData"``,
  ``"DoubleFloatPixelData"``.
* `pixel_representation`: :class:`int` - required when `pixel_keyword` is
  ``"PixelData"``, this is the :ref:`type of pixel values<glossary_pixel_representation>`,
  ``0`` for unsigned integers, ``1`` for signed.
* `planar_configuration`: :class:`int` - required when `samples_per_pixel` > 1,
  this is whether the pixel data is :ref:`color-by-plane or color-by-pixel
  <glossary_planar_configuration>`. ``0`` for color-by-pixel, ``1`` for color-by-plane.


Image Processing Options
========================

The following options may be used with any transfer syntax for controlling the
processing applied after decoding to a NumPy :class:`~numpy.ndarray` using
:meth:`~Decoder.as_array` or :meth:`~Decoder.iter_array`:

* `as_rgb`: :class:`bool` - if ``True`` (default) then convert pixel data with a
  YCbCr :ref:`photometric interpretation<glossary_photometric_interpretation>`
  such as ``"YBR_FULL_422"`` to RGB.
* `force_rgb`: :class:`bool` - if ``True`` then force a YCbCr to RGB color space
  conversion on the array (default ``False``).
* `force_ybr`: :class:`bool` - if ``True`` then force an RGB to YCbCr color space
  conversion on the array (default ``False``).


Miscellaneous Options
=====================

The following options may be used with native (uncompressed) transfer syntaxes
when decoding to a NumPy :class:`~numpy.ndarray` using :meth:`~Decoder.as_array`
or :meth:`~Decoder.iter_array`:

* `view_only`: :class:`bool` - if ``True`` and `src` is a
  :class:`~pydicom.dataset.Dataset` or buffer-like then make a best effort
  attempt to return an :class:`~numpy.ndarray` that's a `view
  <https://numpy.org/doc/stable/user/basics.copies.html#view>`_ on the original
  buffer (default ``False``).


.. _guide_decoder_plugin_opts:


Decoding Plugin Options
=======================

*RLE Lossless*
--------------

+---------------+--------------------------------------------------------------+
| Plugin        | Options                                                      |
+               +---------------------+----------------------------------------+
|               | Key                 | Value                                  |
+===============+=====================+========================================+
| ``pydicom``   |``rle_segment_order``| ``">"`` for big endian segment order   |
+---------------+---------------------+ (default) or ``"<"`` for little endian |
| ``pylibjpeg`` |``byteorder``        | segment order                          |
+---------------+---------------------+----------------------------------------+
