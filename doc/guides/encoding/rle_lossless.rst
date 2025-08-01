
RLE Lossless Encoding
=====================

The requirements for RLE encoding are defined in :dcm:`Section 8.2.2
<part05/sect_8.2.2.html>` and Annexes :dcm:`A.4.2<part05/sect_A.4.2.html>`
and :dcm:`G<part05/chapter_G.html>` of Part 5 of the DICOM Standard. The
underlying algorithm is based on the
`PackBits <https://en.wikipedia.org/wiki/PackBits>`_ compression scheme.

Valid Image Pixel Parameters
----------------------------

The table below lists the valid :dcm:`Image Pixel<part03/sect_C.7.6.3.html>`
module parameters for *Pixel Data* encoded using the *RLE Lossless* transfer
syntax. For an explanation of each parameter and its relationship with the
*Pixel Data* see the :doc:`glossary of Image Pixel elements<../glossary>`.

+------------+-----------------+-----------------+------------+---------+
| *Samples   | *Photometric    | *Pixel          | *Bits      | *Bits   |
| per Pixel* | Interpretation* | Representation* | Allocated* | Stored* |
+============+=================+=================+============+=========+
| 1          | | MONOCHROME1   | 0 or 1          | 8 or 16    | 1 to 16 |
|            | | MONOCHROME2   |                 |            |         |
|            +-----------------+-----------------+------------+---------+
|            | PALETTE COLOR   | 0               | 8 or 16    | 1 to 16 |
+------------+-----------------+-----------------+------------+---------+
| 3          | RGB             | 0               | 8 or 16    | 1 to 16 |
|            +-----------------+-----------------+------------+---------+
|            | YBR_FULL        | 0               | 8          | 1 to 8  |
+------------+-----------------+-----------------+------------+---------+

To ensure you have the correct *Photometric Interpretation* when encoding using
*RLE Lossless*, the uncompressed pixel data should already be in the
corresponding color space:

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
  * For *Photometric Interpretation* ``YBR_FULL`` data must be :func:`converted into
    YCbCr color space <pydicom.pixels.processing.convert_color_space>`, however
    the conversion operation is lossy.

* If your uncompressed pixel data is in `YCbCr
  <https://en.wikipedia.org/wiki/YCbCr>`_ color space:

  * For *Photometric Interpretation* ``RGB`` the pixel data must first be
    :func:`converted into RGB color space
    <pydicom.pixels.processing.convert_color_space>`, however the conversion
    operation is lossy.
  * For *Photometric Interpretation* ``YBR_FULL`` nothing else is required.

If a change is made to existing *Pixel Data*, such as conversion to a different
color space or downsampling to 8-bit then a new *SOP Instance UID* should be
generated.

You might be asking why you would convert uncompressed RGB pixel data to YCbCr
(or vice versa) if the conversion itself is lossy. The answer is that
using YCbCr data should result in a higher compression ratio than
with RGB, while YCbCr data is usually converted back to RGB before viewing.
The decision to change the color space should be made with the intended
usage of your dataset in mind.


Available Plugins
-----------------

.. |br| raw:: html

   <br />

+---------------------------------------------------+-----------------------------------------------------------------------------+
| Encoder                                           | Plugins                                                                     |
|                                                   +---------+--------------------------------------+-----+----------------------+
|                                                   | Name    | Requires                             |Added| Known Limitations    |
+===================================================+=========+======================================+=====+======================+
|:attr:`~pydicom.pixels.encoders.RLELosslessEncoder`| pydicom |                                      |v2.2 | ~20x slower to encode|
|                                                   +---------+--------------------------------------+-----+----------------------+
|                                                   |pylibjpeg|:ref:`NumPy<tut_install_np>`,         |v2.2 |                      |
|                                                   |         |:ref:`pylibjpeg<tut_install_pylj>`,   |     |                      |
|                                                   |         |:ref:`pylibjpeg-rle<tut_install_pylj>`|     |                      |
|                                                   +---------+--------------------------------------+-----+----------------------+
|                                                   | gdcm    |:ref:`GDCM<tut_install_gdcm>`         |v2.2 |                      |
+---------------------------------------------------+---------+--------------------------------------+-----+----------------------+

Examples
--------

Compressing grayscale pixel data in-place:

.. code-block:: python

    >>> from pydicom import examples
    >>> from pydicom.uid import RLELossless
    >>> ds = examples.ct
    >>> ds.SamplesPerPixel
    1
    >>> ds.PhotometricInterpretation
    'MONOCHROME2'
    >>> ds.BitsAllocated
    16
    >>> ds.PixelRepresentation
    1
    >>> ds.compress(RLELossless)
    >>> len(ds.PixelData)
    21020

Compressing RGB pixel data in-place:

.. code-block:: python

    >>> from pydicom import examples
    >>> ds = examples.rgb_color
    >>> ds.SamplesPerPixel
    3
    >>> ds.PhotometricInterpretation
    'RGB'
    >>> ds.BitsAllocated
    8
    >>> ds.PixelRepresentation
    0
    >>> len(ds.PixelData)
    921600
    >>> ds.compress(RLELossless)
    >>> len(ds.PixelData)
    424152


Convert RGB pixel data to YCbCr (requires :ref:`NumPy<tut_install_np>`), then
compress in-place. Because the color space has changed we need to generate a
new *SOP Instance UID*:

.. code-block:: python

    >>> from pydicom import examples
    >>> from pydicom.pixels import convert_color_space
    >>> from pydicom.uid import generate_uid
    >>> ds = examples.rgb_color
    >>> rgb = ds.pixel_array
    >>> ybr = convert_color_space(rgb, 'RGB', 'YBR_FULL')
    >>> ds.PhotometricInterpretation = 'YBR_FULL'
    >>> ds.compress(RLELossless, ybr)
    >>> ds.SOPInstanceUID = generate_uid()
    >>> len(ds.PixelData)
    187460
