==========================
Pixel Data Encoder Plugins
==========================

Plugin Requirements
===================

Each available pixel data encoder in *pydicom* corresponds directly to a
single DICOM *Transfer Syntax UID*, and is intended to provide a mechanism for
converting raw unencoded source data to meet the requirements of that transfer
syntax. In order to do so, each encoder has at least one encoding plugin which
performs the actual conversion.

An encoding plugin must implement three objects within the same module:

* An encoding function with the following function signature:

  .. codeblock:: python

      def foo(src: bytes, **kwargs: Dict[str, Any]) -> bytes:

  Where

  * `src` is a :class:`bytes` instance containing the raw uncompressed
    data to be encoded. When the data contains multi-byte values (i.e. such
    as 16-bit pixels), then by default the data will use little-endian byte
    ordering. Support for big-endian byte ordering by the encoding function
    is completely optional.
  * `kwargs` is a :class:`dict` which at a minimum contains the following
    required keys:

    * :class:`~pydicom.uid.UID` ``'transfer_syntax_uid'``: the intended
      *Transfer Syntax UID* of the encoded data.
    * :class:`str` ``'byteorder'``: the byte ordering used by `src`, ``'<'''
      for little-endian (the default), ``'>'`` for big-endian.
    * :class:`int` ``'rows'``: the number of rows of pixels in the `src`.
    * :class:`int` ``'columns'``: the number of columns of pixels in the
      `src`.
    * :class:`int` ``'samples_per_pixel'``: the number of samples used per
      pixel, e.g. 1 for greyscale images or 3 for RGB.
    * :class:`int` ``'number_of_frames'``: the number of image frames
      contained in `src`
    * :class:`int` ``'bits_allocated'``: the number of bits used to contain
      each pixel in `src`, should be 8, 16, 32 or 64.
    * :class:`int` ``'bits_stored'``: the number of bits actually used by
      each pixel in `src`, e.g. 12-bit pixel data (range 0 to 4095) will be
      contained by 16-bits (range 0 to 65535).
    * :class:`int` ``'pixel_representation'``: the type of data in `src`,
      ``0`` for unsigned integers, ``1`` for 2's complement (signed)
      integers.
    * :class:`str` ``'photometric_interpretation'``: the intended colorspace
      of the encoded data, such as ``'YBR'``

    `kwargs` may also contain optional parameters intended to be used
    with the encoder function to allow customization of the encoding process
    or to provide additional functionality. Support for these optional
    parameters is not required, however.

  At a minimum the encoding function must support the encoding of
  little-endian byte ordered data and should return the encoded
  data in a format meeting the requirements of the corresponding *Transfer
  syntax UID* as :class:`bytes`.

* A function named `is_available` with the following signature:

  .. codeblock:: python

      def is_available(uid: pydicom.uid.UID) -> bool:

  Where `uid` is the *Transfer Syntax UID* for the corresponding encoder as
  a :class:`~pydicom.uid.UID`. If the plugin supports the `uid` and has
  its dependencies met then it should return ``True``, otherwise it should
  return ``False``.

* A dict named ``ENCODER_DEPENDENCIES`` with the type
  ``Dict[pydicom.uid.UID, Tuple[str, ...]``, such as:

  .. codeblock:: python

      from pydicom.uid import RLELossless, JPEG20000

      ENCODER_DEPENDENCIES = {
          RLELossless: ('numpy', 'pillow', 'imagecodecs'),
          JPEG2000: ('numpy', 'gdcm'),
      }

  This will be used to provide the user will a list of missing dependencies
  required by the plugin.

An example of the requirements of a plugin is available `here
<https://github.com/pydicom/pydicom/tree/master/pydicom/encoders/pylibjpeg.py>`_.

Adding Plugins to an Encoder
============================

Additional plugins can be added to an existing encoder with the
:meth:`~pydicom.encoders.base.Encoder.add_plugin` method, which takes the
a unique :class:`str` `plugin_label`, and a :class:`tuple` of ``('the import
path to the encoder function's module', 'encoder function name')``. For
example, if you'd import your encoder function `my_encoder_func` with
``from my_package.encoders import my_func``, then you'd do the following:

.. codeblock:: python

    from pydicom.encoders import RLELosslessEncoder

    RLELosslessEncoder.add_plugin(
        'my_encoder',
        ('my_package.encoders', 'my_encoder_func')
    )

The ``my_package.encoders`` module must contain the encoding function and the
``ENCODER_DEPENDENCIES`` and ``is_available`` objects.
