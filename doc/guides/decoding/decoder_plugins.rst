.. _guide_decoder_plugins:

==========================
Pixel Data Decoder Plugins
==========================

.. note::

    This guide is intended for advanced users who need support for something
    not provided by the :doc:`existing decoder plugins </reference/pixels.decoders>`.

*Pixel Data* decoding in *pydicom* uses a :class:`~pydicom.pixels.decoders.base.Decoder`
instance to manage plugins that perform the actual decoding work. This guide covers
the requirements for those plugins and how to add them to *pydicom*.

Plugin Requirements
===================

Each available pixel data decoder in *pydicom* corresponds directly to a
single DICOM *Transfer Syntax UID*, and is intended to provide a mechanism for
converting raw encoded source data to unencoded pixel values. In order to do
so, each decoder for compressed transfer syntaxes has at least one decoding
plugin which performs the actual conversion.

A decoding plugin must implement three objects within the same module:

* A function named ``is_available`` with the following signature:

  .. code-block:: python

      def is_available(uid: pydicom.uid.UID) -> bool:

  Where `uid` is the *Transfer Syntax UID* for the corresponding decoder as
  a :class:`~pydicom.uid.UID`. If the plugin supports the `uid` and has
  its dependencies met then it should return ``True``, otherwise it should
  return ``False``.

* A :class:`dict` named ``DECODER_DEPENDENCIES`` with the type
  ``dict[pydicom.uid.UID, tuple[str, ...]``, such as:

  .. code-block:: python

      from pydicom.uid import RLELossless, JPEG2000

      DECODER_DEPENDENCIES = {
          RLELossless: ('numpy', 'pillow', 'imagecodecs'),
          JPEG2000: ('numpy', 'gdcm'),
      }

  This will be used to provide the user with a list of dependencies
  required by the plugin.

* A function that performs the decoding with the following function signature:

  .. code-block:: python

    def decoder(src: bytes, runner: DecodeRunner) -> bytearray | bytes:

  Where

  * `src` is a single frame's worth of raw compressed data to be decoded.
  * `runner` is a :class:`~pydicom.pixels.decoders.base.DecodeRunner` instance
    that manages the decoding process and has access to the decoding options,
    either directly through the class properties or indirectly with the
    :meth:`~pydicom.pixels.decoders.base.DecodeRunner.get_option` method.

  At a minimum the following decoding options should be available:

  * ``transfer_syntax_uid``: :class:`~pydicom.uid.UID` - the *Transfer
    Syntax UID* of the encoded data.
  * ``rows``: :class:`int` - the number of rows of pixels in decoded data.
  * ``columns``: :class:`int` -  the number of columns of pixels in the
    decoded data.
  * ``samples_per_pixel``: :class:`int` - the number of samples used per
    pixel, e.g. 1 for grayscale images or 3 for RGB.
  * ``number_of_frames``: :class:`int` - the number of image frames
    contained in `src`
  * ``bits_allocated``: :class:`int` - the number of bits used to contain
    each pixel in `src`, should be 1 or a multiple of 8.
  * ``photometric_interpretation``: :class:`str` - the color space
    of the encoded data, such as ``'YBR_FULL'``
  * ``pixel_keyword``: :class:`str` - one of ``"PixelData"``, ``"FloatPixelData"``,
    ``"DoubleFloatPixelData"``.
  * ``as_rgb``: :class:`bool` - whether or not YCbCr data should be converted to RGB.

  And conditionally:

  * ``bits_stored``: :class:`int` - required when `pixel_keyword` is ``"PixelData"``,
    the number of bits actually used by each pixel in `src`, e.g. 12-bit pixel data
    (range 0 to 4095) will be contained by 16-bits (range 0 to 65535).
  * ``pixel_representation``: :class:`int` - required when
    `pixel_keyword` is ``"PixelData"``, ``0`` for unsigned integers,
    ``1`` for signed.
  * ``planar_configuration``: :class:`int` - required when ``samples_per_pixel``
    > 1, ``0`` for color-by-pixel, ``1`` for color-by-plane.

  In addition, the following options for individual frames can be set or retrieved
  by the plugin using the :meth:`~pydicom.pixels.decoders.base.DecodeRunner.get_frame_option`
  and :meth:`~pydicom.pixels.decoders.base.DecodeRunner.set_frame_option` methods:

  * ``bits_allocated``: :class:`int` - the number of bits used to contain each pixel
    in the decoded frame, should be 1 (for bit-packed data) or a multiple of 8.
  * ``photometric_interpretation``: :class:`str` - the color space of the decoded
    frame, such as ``'YBR_FULL'``.
  * ``planar_configuration``: :class:`int` - the order of the pixels in the decoded
    frame, available when ``samples_per_pixel`` > 1, ``0`` for color-by-pixel, ``1``
    for color-by-plane.
  * ``jls_precision`` :class:`int` - the precision used in the JPEG-LS codestream for
    the frame being decoded (JPEG-LS transfer syntaxes only).
  * ``j2k_precision``: :class:`int` - the precision used in the JPEG 2000 codestream
    for the frame being decoded (JPEG 2000 transfer syntaxes only).
  * ``j2k_is_signed``: :class:`bool` - whether the JPEG 2000 codestream for the frame
    frame being decoded uses signed integers or not (JPEG 2000 transfer syntaxes only).

  The values for these frame options should be set appropriately to match the decoded
  pixel data returned by the plugin. For example, if a frame's original
  ``photometric_interpretation`` is ``YBR_FULL`` and the plugin converts it to ``RGB``
  then you should use :meth:`~pydicom.pixels.decoders.base.DecodeRunner.set_frame_option`
  to reflect the change in color space.

  When possible it's recommended that the decoding function return the decoded
  pixel data as a :class:`bytearray` to minimize later memory usage.

An example of the requirements of a plugin is available :gh:`here
<pydicom/blob/main/src/pydicom/pixels/decoders/rle.py>`.


Adding Plugins to a Decoder
===========================

Additional plugins can be added to an existing decoder with the
:meth:`~pydicom.pixels.decoders.base.Decoder.add_plugin` method, which takes the
a unique :class:`str` `plugin_label`, and a :class:`tuple` of ``('the import
path to the decoder function's module', 'decoder function name')``. For
example, if you'd import your decoder function `my_decoder_func` with
``from my_package.decoders import my_decoder_func``, then you'd do the
following:

.. code-block:: python

    from pydicom.pixels.decoders import RLELosslessDecoder

    RLELosslessDecoder.add_plugin(
        'my_decoder',  # the plugin's label
        ('my_package.decoders', 'my_decoder_func')  # the import paths
    )

The ``my_package.decoders`` module must contain the encoding function and the
``DECODER_DEPENDENCIES`` and ``is_available`` objects.
