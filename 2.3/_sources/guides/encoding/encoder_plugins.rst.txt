.. _guide_encoder_plugins:

==========================
Pixel Data Encoder Plugins
==========================

*Pixel Data* encoding in *pydicom* uses an :class:`~pydicom.encoders.base.Encoder`
instance for the specific *Transfer Syntax* as a manager for plugins that
perform the encoding work. This guide covers the requirements for those plugins
and how to add them to *pydicom*. For a more general introduction to compression
in *pydicom* see the :doc:`tutorial</tutorials/pixel_data/compressing>` instead.

Plugin Requirements
===================

Each available pixel data encoder in *pydicom* corresponds directly to a
single DICOM *Transfer Syntax UID*, and is intended to provide a mechanism for
converting raw unencoded source data to meet the requirements of that transfer
syntax. In order to do so, each encoder has at least one encoding plugin which
performs the actual conversion.

An encoding plugin must implement three objects within the same module:

* A function that performs the encoding with the following function signature:

  .. code-block:: python

      def foo(src: bytes, **kwargs: Any) -> bytes:

  Where

  * `src` is the raw uncompressed data to be encoded as :class:`bytes`. When
    the data in `src` represents multi-byte values
    (such as 16-bit pixels), then `src` will use little-endian byte
    ordering by default. Support for big-endian byte ordering by the encoding
    function is completely optional.
  * `kwargs` is a :class:`dict` which at a minimum contains the following
    required keys:

    * ``'transfer_syntax_uid'``: :class:`~pydicom.uid.UID` - the intended
      *Transfer Syntax UID* of the encoded data.
    * ``'byteorder'``: :class:`str` - the byte ordering used by `src`, ``'<'``
      for little-endian (the default), ``'>'`` for big-endian.
    * ``'rows'``: :class:`int` - the number of rows of pixels in the `src`.
    * ``'columns'``: :class:`int` -  the number of columns of pixels in the
      `src`.
    * ``'samples_per_pixel'``: :class:`int` - the number of samples used per
      pixel, e.g. 1 for grayscale images or 3 for RGB.
    * ``'number_of_frames'``: :class:`int` - the number of image frames
      contained in `src`
    * ``'bits_allocated'``: :class:`int` - the number of bits used to contain
      each pixel in `src`, should be a multiple of 8.
    * ``'bits_stored'``: :class:`int` - the number of bits actually used by
      each pixel in `src`, e.g. 12-bit pixel data (range 0 to 4095) will be
      contained by 16-bits (range 0 to 65535).
    * ``'pixel_representation'``: :class:`int` - the type of data in `src`,
      ``0`` for unsigned integers, ``1`` for 2's complement (signed)
      integers.
    * ``'photometric_interpretation'``: :class:`str` - the intended color space
      of the encoded data, such as ``'YBR_FULL'``

    `kwargs` may also contain optional parameters intended to be used
    with the encoder function to allow customization of the encoding process
    or to provide additional functionality. Support for these optional
    parameters is not required, however.

  At a minimum the encoding function must support the encoding of
  little-endian byte ordered data and should return the encoded
  data in a format meeting the requirements of the corresponding *Transfer
  Syntax UID* as :class:`bytes`.

* A function named ``is_available`` with the following signature:

  .. code-block:: python

      def is_available(uid: pydicom.uid.UID) -> bool:

  Where `uid` is the *Transfer Syntax UID* for the corresponding encoder as
  a :class:`~pydicom.uid.UID`. If the plugin supports the `uid` and has
  its dependencies met then it should return ``True``, otherwise it should
  return ``False``.

* A :class:`dict` named ``ENCODER_DEPENDENCIES`` with the type
  ``Dict[pydicom.uid.UID, Tuple[str, ...]``, such as:

  .. code-block:: python

      from pydicom.uid import RLELossless, JPEG2000

      ENCODER_DEPENDENCIES = {
          RLELossless: ('numpy', 'pillow', 'imagecodecs'),
          JPEG2000: ('numpy', 'gdcm'),
      }

  This will be used to provide the user with a list of missing dependencies
  required by the plugin.

An example of the requirements of a plugin is available :gh:`here
<pydicom/tree/master/pydicom/encoders/pylibjpeg.py>`.

Adding Plugins to an Encoder
============================

Additional plugins can be added to an existing encoder with the
:meth:`~pydicom.encoders.base.Encoder.add_plugin` method, which takes the
a unique :class:`str` `plugin_label`, and a :class:`tuple` of ``('the import
path to the encoder function's module', 'encoder function name')``. For
example, if you'd import your encoder function `my_encoder_func` with
``from my_package.encoders import my_encoder_func``, then you'd do the
following:

.. code-block:: python

    from pydicom.encoders import RLELosslessEncoder

    RLELosslessEncoder.add_plugin(
        'my_encoder',  # the plugin's label
        ('my_package.encoders', 'my_encoder_func')  # the import paths
    )

The ``my_package.encoders`` module must contain the encoding function and the
``ENCODER_DEPENDENCIES`` and ``is_available`` objects.
