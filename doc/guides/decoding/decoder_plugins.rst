.. _guide_decoder_plugins:

==========================
Pixel Data Decoder Plugins
==========================

*Pixel Data* decoding in *pydicom* uses an :class:`~pydicom.pixels.decoders.base.Decoder`
instance for the specific *Transfer Syntax* as a manager for plugins that
perform the decoding work. This guide covers the requirements for those plugins
and how to add them to *pydicom*.

Plugin Requirements
===================

Each available pixel data decoder in *pydicom* corresponds directly to a
single DICOM *Transfer Syntax UID*, and is intended to provide a mechanism for
converting raw encoded source data to unencoded pixel values. In order to do
so, each decoder for compressed transfer syntaxes has at least one decoding
plugin which performs the actual conversion.

An decoding plugin must implement three objects within the same module:

* A function that performs the decoding with the following function signature:

  .. code-block:: python

      def decoder(src: bytes, opts: DecodeOptions) -> bytearray | bytes:

  Where

  * `src` is a single frame's worth of raw compressed data to be decoded as
    :class:`bytes`.
  * `opts` is a :class:`dict` which at a minimum contains the following
    required keys:

    * ``'transfer_syntax_uid'``: :class:`~pydicom.uid.UID` - the *Transfer
      Syntax UID* of the encoded data.
    * ``'rows'``: :class:`int` - the number of rows of pixels in decoded data.
    * ``'columns'``: :class:`int` -  the number of columns of pixels in the
      decoded data.
    * ``'samples_per_pixel'``: :class:`int` - the number of samples used per
      pixel, e.g. 1 for grayscale images or 3 for RGB.
    * ``'number_of_frames'``: :class:`int` - the number of image frames
      contained in `src`
    * ``'bits_allocated'``: :class:`int` - the number of bits used to contain
      each pixel in `src`, should be a multiple of 8.
    * ``'bits_stored'``: :class:`int` - the number of bits actually used by
      each pixel in `src`, e.g. 12-bit pixel data (range 0 to 4095) will be
      contained by 16-bits (range 0 to 65535).
    * ``'photometric_interpretation'``: :class:`str` - the color space
      of the encoded data, such as ``'YBR_FULL'``
    * `pixel_representation`: :class:`int` - required when
      `pixel_keyword` is ``"PixelData"``, ``0`` for unsigned integers,
      ``1`` for signed.

    And conditionally contains the following keys:

    * ``'planar_configuration'``: :class:`int` - present when ``'samples_per_pixel'``
      > 1, ``0`` for color-by-pixel, ``1`` for color-by-plane.

    `opts` may also contain optional parameters intended to be used
    with the decoder function to allow customization of the decoding process
    or to provide additional functionality. Support for these optional
    parameters is not required, however.

    `opts` is a reference to the options dict used by the
    :class:`~pydicom.pixels.base.DecodeRunner` that manages the decoding process,
    so if your decoder needs to signal that one of the option values needs to be
    modified (say for example to flag that the photometric interpretation of the
    decoded frame has already been changed from YBR_FULL to RGB by the plugin),
    then this can be done by modifying the corresponding value in `opts`. Note
    that you should only do this after successfully decoding the frame, as if the
    decoding fails then changing the option value may cause issues with other
    decoding plugins.

  When possible it's recommended that the decoding function return the decoded
  pixel data as a :class:`bytearray` to minimize later memory usage.

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
