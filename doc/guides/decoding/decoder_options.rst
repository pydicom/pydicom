.. _guide_decoder_options:

==========================
Pixel Data Decoder Options
==========================

.. currentmodule:: pydicom.pixels.decoders.base

The following applies to the functions and class methods that use the
:doc:`pixels</reference/pixels>` backend for decoding pixel data.


When decoding to a NumPy :class:`~numpy.ndarray`:

* The :attr:`Dataset.pixel_array<pydicom.dataset.Dataset.pixel_array>` property
  (configurable via :meth:`Dataset.pixel_array_options()<pydicom.dataset.Dataset.pixel_array_options>`)
* :func:`~pydicom.pixels.pixel_array`
* :func:`~pydicom.pixels.iter_pixels`
* :func:`~pydicom.pixels.decompress`
* :meth:`Decoder.as_array()<pydicom.pixels.decoders.base.Decoder.as_array>`
* :meth:`Decoder.iter_array()<pydicom.pixels.decoders.base.Decoder.iter_array>`


When decoding to a buffer (such as :class:`bytes`, :class:`bytearray` or :class:`memoryview`):

* :meth:`Decoder.as_buffer()<pydicom.pixels.decoders.base.Decoder.as_buffer>`
* :meth:`Decoder.iter_buffer()<pydicom.pixels.decoders.base.Decoder.iter_buffer>`

*Image Pixel* Options
=====================

The following options are required when the decoding source `src` is not a
:class:`~pydicom.dataset.Dataset` and are used to describe the encoded pixel data.
They may also be used to override the corresponding element values when `src`
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
| `pixel_keyword`              |:class:`str`|                           | Required if `src` uses a :ref:`native transfer syntax    |
|                              |            |                           | <transfer_syntax>`, the keyword of the element containing|
|                              |            |                           | the pixel data. One of ``'PixelData'``,                  |
|                              |            |                           | ``'FloatPixelData'``, ``'DoubleFloatPixelData'``         |
+------------------------------+------------+---------------------------+----------------------------------------------------------+


Image Processing Options
========================

The following options may be used with any transfer syntax for controlling the
processing applied after decoding to a NumPy :class:`~numpy.ndarray`:

* `as_rgb`: :class:`bool` - if ``True`` (default) then convert pixel data with a
  YCbCr :ref:`photometric interpretation<photometric_interpretation>`
  such as ``"YBR_FULL_422"`` to RGB.
* `force_rgb`: :class:`bool` - if ``True`` then force a YCbCr to RGB color space
  conversion on the array (default ``False``).
* `force_ybr`: :class:`bool` - if ``True`` then force an RGB to YCbCr color space
  conversion on the array (default ``False``).


Miscellaneous Options
=====================

The following options may be used with both native (uncompressed) and encapsulated
(compressed) transfer syntaxes when decoding to a NumPy :class:`~numpy.ndarray`:

* `correct_unused_bits`: :class:`bool` - if ``True`` (default) and *Bits Stored*
  doesn't equal *Bits Allocated* then apply bit-shifting operations to correct
  for any misinterpretation due to the unused bits. For example, if *Bits Stored*
  is 5 and *Bits Allocated* is 8 then the 3 most significant bits are unused.
  A raw value of ``0b00011001`` with a *Pixel Representation* of 1 would therefore
  be interpreted as the value 25 if `correct_unused_bits` is ``False`` instead
  of its correct value of -7. However, in most cases this correction shouldn't
  be necessary as the unused bits are typically filled with values that will
  produce the correct interpretation.

The following options may be used with both native (uncompressed) and encapsulated
(compressed) transfer syntaxes when decoding to a NumPy :class:`~numpy.ndarray` or
buffer-like object:

* `allow_excess_frames`: :class:`bool` - if ``True`` (default) and `src` contains
  more frames of data than given by the value of (0028,0008) *Number of Frames* then
  include those extra frames in the returned data, otherwise return only the number
  of frames given by *Number of Frames*.

The following options may be used with native (uncompressed) transfer syntaxes
when decoding to a NumPy :class:`~numpy.ndarray`:

* `view_only`: :class:`bool` - if ``True`` and `src` is a
  :class:`~pydicom.dataset.Dataset` or buffer-like then make a best effort
  attempt to return an :class:`~numpy.ndarray` that's a `view
  <https://numpy.org/doc/stable/user/basics.copies.html#view>`_ on the original
  buffer (default ``False``). Note that if the original buffer is immutable then
  the returned :class:`~numpy.ndarray` will be read-only.

The following options may be used with encapsulated (compressed) transfer syntaxes
of the corresponding type when decoding to a NumPy :class:`~numpy.ndarray`:

* `apply_jls_sign_correction`: :class:`bool` - if ``True`` (default), `src` contains
  JPEG-LS compressed pixel data and the pixel representation is 1, then convert
  the raw decoded pixel values from unsigned to signed integers.
* `apply_j2k_sign_correction`: :class:`bool` - if ``True`` (default), `src` contains
  JPEG 2000 compressed pixel data and the pixel representation doesn't match the
  signedness given in the JPEG 2000 codestream, then convert the raw decoded
  pixel values to match the pixel representation.


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
