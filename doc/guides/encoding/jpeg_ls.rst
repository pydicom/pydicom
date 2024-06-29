
JPEG-LS Encoding
================

The requirements for JPEG-LS encoding are defined in :dcm:`Section 8.2.3
<part05/sect_8.2.3.html>` and Annex :dcm:`A.4.3<part05/sect_A.4.3.html>` of Part
5 of the DICOM Standard. The JPEG-LS compression scheme is defined by `ISO/IEC
14495-1 <https://www.iso.org/standard/22397.html>`_/`ITU T.87
<https://www.itu.int/rec/T-REC-T.87-199806-I>`_ (the second link has free access).

Valid Image Pixel Parameters
----------------------------

The table below lists the valid :dcm:`Image Pixel<part03/sect_C.7.6.3.html>`
module parameters for *Pixel Data* encoded using the *JPEG-LS Lossless* or *JPEG-LS
Near-lossless* transfer syntaxes. For an explanation of each parameter and its relationship
with the *Pixel Data* see the :doc:`glossary of Image Pixel elements<../glossary>`.

+------------+-----------------------+-----------------+----------------+------------+---------+
| *Samples   | *Photometric          | *Pixel          | *Planar        | *Bits      | *Bits   |
| per Pixel* | Interpretation*       | Representation* | Configuration* | Allocated* | Stored* |
+============+=======================+=================+================+============+=========+
| 1          | MONOCHROME1           | 0 or 1          | (absent)       | 8 or 16    | 2 to 16 |
|            +-----------------------+                 |                |            |         |
|            | MONOCHROME2           |                 |                |            |         |
|            +-----------------------+-----------------+                |            |         |
|            | PALETTE COLOR :sup:`1`| 0               |                |            |         |
+------------+-----------------------+-----------------+----------------+------------+---------+
| 3          | RGB                   | 0               | 0              | 8 or 16    | 2 to 16 |
|            +-----------------------+                 |                +------------+---------+
|            | YBR_FULL              |                 |                | 8          | 2 to 8  |
+------------+-----------------------+-----------------+----------------+------------+---------+

| :sup:`1` *JPEG-LS Lossless* only

Pixel Representation
....................

The DICOM Standard allows the use of the *JPEG-LS Near Lossless* transfer
syntax with signed pixel data as long as the *Photometric Interpretation*
is ``MONOCHROME1`` or ``MONOCHROME2``. In practice, however, this is complicated
by the way lossy JPEG-LS encoding works:

* JPEG-LS does not track the signedness of the pixel data, so all data is
  assumed to be unsigned during compression
* JPEG-LS uses the specified absolute pixel value error as the constraint when
  performing lossy encoding (the NEAR parameter - in *pydicom* this is the
  `jls_error` parameter passed to the :meth:`encoding functions
  <pydicom.dataset.Dataset.compress>`)

Because of this, even though a NEAR value of ``1`` should limit the absolute
pixel value error to 1 intensity unit, it's possible to have pixels with an
absolute error up to the sample bit-depth of the data:

.. code-block:: text

    Raw 8-bit value:
        -128: 0b10000000 (as signed integer)
         128: 0b10000000 (as unsigned integer)

    Possible value after lossy encoding with a NEAR value of 1:
         127: 0b01111111 (as signed/unsigned integer)

    Total error as unsigned: 1 - OK
    Total error as signed: 255 - Very much not OK

Signed pixel data values should therefore be limited to the range (MIN + NEAR,
MAX - NEAR), where MIN and MAX are the minimum and maximum values allowed for
the given *Bits Stored* value: ``-2**(Bits Stored - 1)`` and
``2**(Bits Stored - 1) - 1``. For example, when performing lossy encoding of
8-bit signed data and a NEAR value of 3 you should limit the pixel data values
to the range (-128 + 3, 127 - 3).

Lossless JPEG-LS encoding has no such restriction and the full value range for
the given *Bits Stored* can be used with both signed and unsigned pixel data.

Photometric Interpretation
..........................

To ensure you have the correct *Photometric Interpretation* the uncompressed
pixel data should already be in the corresponding color space:

* If your uncompressed pixel data is grayscale (intensity) based:

  * Use ``MONOCHROME1`` if the minimum intensity value should be displayed as
    white.
  * Use ``MONOCHROME2`` if the minimum intensity value should be displayed as
    black.

* If your uncompressed pixel data uses a single sample per pixel and is an index
  to the :dcm:`Red, Green and Blue Palette Color Lookup Tables
  <part03/sect_C.7.6.3.html#sect_C.7.6.3.1.5>`:

  * Use ``PALETTE COLOR``.

* If your uncompressed pixel data is in RGB color space:

  * For *Photometric Interpretation* ``RGB`` nothing else is required.
  * For *Photometric Interpretation* ``YBR_FULL``

    * For *Bits Allocated* and *Bits Stored* less than or equal to 8: pixel
      data must be :func:`converted into YCbCr color space
      <pydicom.pixels.processing.convert_color_space>`. However
      you should keep in mind that the conversion operation is lossy.
    * For *Bits Allocated* and *Bits Stored* between 9 and 16 (inclusive):
      pixel data should be downscaled to 8-bit (with *Bits Stored*, *Bits
      Allocated* and *High Bit* updated accordingly) and converted to `YCbCr
      <https://en.wikipedia.org/wiki/YCbCr>`_ color space. Both of these
      operations are lossy.

* If your uncompressed pixel data is in `YCbCr
  <https://en.wikipedia.org/wiki/YCbCr>`_ color space:

  * For *Photometric Interpretation* ``RGB`` the pixel data must first be
    :func:`converted into RGB color space
    <pydicom.pixels.processing.convert_color_space>`. However the conversion
    operation is lossy.
  * For *Photometric Interpretation* ``YBR_FULL`` nothing else is required.

Planar Configuration
....................

If your uncompressed pixel data is in ``RGB`` or ``YBR_FULL`` color space then
you may use a *Planar Configuration* of either ``0`` or ``1`` as JPEG-LS allows
the use of different interleave modes. While a *Planar Configuration* of
``1`` (interleave mode 0) may result in better compression ratios, its also
more likely to result in downstream issues with decoders that expect the more
common *Planar Configuration* ``0`` (interleave mode 2) pixel ordering.

For either case, if the pixel data being encoded is in an :class:`~numpy.ndarray`
then each frame should be shaped as (rows, columns, samples). If the pixel data
being encoded is :class:`bytes` then with *Planar Configuration* ``0`` the data
is ordered as color-by-pixel::

    # Three 8-bit RGB pixels: (255, 255, 0), (0, 255, 0), (0, 255, 255)
    # Each pixel is encoded separately the concatenated
    #       first pixel | second px | third px  |
    src = b"\xFF\xFF\x00\x00\xFF\x00\x00\xFF\xFF"

With *Planar Configuration* ``1`` the data is ordered as color-by-plane::

    # Three 8-bit RGB pixels: (255, 255, 0), (0, 255, 0), (0, 255, 255)
    # Each color channel is encoded separately then concatenated
    #       red channel | green ch. | blue ch.  |
    src = b"\xFF\x00\x00\xFF\xFF\xFF\x00\x00\xFF"


Examples
--------

JPEG-LS Lossless
................

Losslessly compress unsigned RGB pixel data in-place:

.. code-block:: python

    from pydicom import examples
    from pydicom.uid import JPEGLSLossless

    ds = examples.rgb_color
    assert ds.SamplesPerPixel == 1
    assert ds.PhotometricInterpretation == 'RGB'
    assert ds.BitsAllocated == 8
    assert ds.BitsStored == 8
    assert ds.PixelRepresentation == 0
    assert len(ds.PixelData) == 921600

    ds.compress(JPEGLSLossless)

    print(len(ds.PixelData))  # ~261792


Losslessly compress signed greyscale pixel data in-place:

.. code-block:: python

    from pydicom import examples
    from pydicom.uid import JPEGLSLossless

    ds = examples.ct
    assert ds.SamplesPerPixel == 1
    assert ds.PhotometricInterpretation == 'MONOCHROME2'
    assert ds.BitsAllocated == 16
    assert ds.BitsStored == 16
    assert ds.PixelRepresentation == 1
    assert len(ds.PixelData) == 32768

    ds.compress(JPEGLSLossless)

    print(len(ds.PixelData))  # ~14180


JPEG-LS Near-lossless
.....................

.. warning::

    *pydicom* makes no recommendations for specifying image quality for lossy
    encoding methods. Any examples of lossy encoding are for **illustration
    purposes only**.

When using the *JPEG-LS Near-lossless* transfer syntax, image quality is
controlled by passing the `jls_error` parameter to the :meth:`encoding function
<pydicom.dataset.Dataset.compress>`. `jls_error` is directly related to the JPEG-LS
NEAR parameter, which is the allowed absolute error in pixel intensity units from
the compression process and should be in the range ``(0, 2**BitsStored - 1)``.

Lossy compression of unsigned pixel data with a maximum error of 2 pixel
intensity units:

.. code-block:: python

    from pydicom import examples
    from pydicom.uid import JPEGLSNearLossless

    ds = examples.rgb_color
    assert ds.SamplesPerPixel == 1
    assert ds.PhotometricInterpretation == 'RGB'
    assert ds.BitsAllocated == 8
    assert ds.BitsStored == 8
    assert ds.PixelRepresentation == 0
    assert len(ds.PixelData) == 921600

    ds.compress(JPEGLSNearLossless, jls_error=2)

    print(len(ds.PixelData))  # ~149188


Lossy compression of signed pixel data with a maximum error of 3 pixel
intensity units:

.. code-block:: python

    from pydicom import examples
    from pydicom.uid import JPEGLSNearLossless

    ds = examples.ct
    assert ds.SamplesPerPixel == 1
    assert ds.PhotometricInterpretation == 'MONOCHROME2'
    assert ds.BitsAllocated == 16
    assert ds.BitsStored == 16
    assert ds.PixelRepresentation == 1
    assert len(ds.PixelData) == 32768

    # Our pixel data therefore uses signed 16-bit integers with a single channel
    # We need to make sure the maximum and minimum values are within the allowed
    #   range (see the section on Pixel Representation near the start of this page)
    jls_error = 3

    # The minimum and maximum sample values for the given *Bits Stored*
    minimum = -2**(ds.BitsStored - 1)
    maximum = 2**(ds.BitsStored - 1) - 1

    arr = ds.pixel_array

    # Clip the array so all values are within the limits, you may want to
    # rescale instead of clipping. For this dataset this isn't actually
    # necessary as the pixel data is already within the limits
    arr = np.clip(minimum + jls_error, maximum - jls_error)

    ds.compress(JPEGLSNearLossless, arr, jls_error=jls_error)

    print(ds.PixelData)  # ~8508


Available Plugins
-----------------

.. |br| raw:: html

   <br />

.. _np: https://numpy.org/
.. _jls: https://github.com/pydicom/pyjpegls

+----------------------------------------------------------+------------------------------------+
| Encoder                                                  | Plugins                            |
|                                                          +---------+--------------------+-----+
|                                                          | Name    | Requires           |Added|
+==========================================================+=========+====================+=====+
|:attr:`~pydicom.pixels.encoders.JPEGLSLosslessEncoder`    | pyjpegls| `numpy <np_>`_,    |v3.0 |
+----------------------------------------------------------+         | `pyjpegls <jls_>`_ |     |
|:attr:`~pydicom.pixels.encoders.JPEGLSNearLosslessEncoder`|         |                    |     |
+----------------------------------------------------------+---------+--------------------+-----+
