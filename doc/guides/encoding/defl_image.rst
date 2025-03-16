
Deflated Image Frame Compression
================================

The requirements for *Deflated Image Frame Compression* encoding are defined in
:dcm:`Section 8.2.16<part05/sect_8.2.16.html>` and Annex :dcm:`A.4.13
<part05/sect_A.4.13.html>` in Part 5 of the DICOM Standard. The underlying algorithm
is the `Deflate <https://en.wikipedia.org/wiki/Deflate>`_ compression method.

*Deflated Image Frame Compression* is primary intended for single-bit segmentation
encoding, however there are no restrictions on using it with other types of pixel data.

Valid Image Pixel Parameters
----------------------------

To ensure you have the correct *Photometric Interpretation* when encoding using
*Deflated Image Frame Compression*, the uncompressed pixel data should already be in the
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


Available Plugins
-----------------

.. |br| raw:: html

   <br />

+---------------------------------------------------------------------+-----------------+
| Encoder                                                             | Plugins         |
|                                                                     +---------+-------+
|                                                                     | Name    | Added |
+=====================================================================+=========+=======+
|:attr:`~pydicom.pixels.encoders.DeflatedImageFrameCompressionEncoder`| pydicom | v3.1  |
+---------------------------------------------------------------------+---------+-------+

Examples
--------

Compressing grayscale pixel data in-place:

.. code-block:: python

    >>> from pydicom import examples
    >>> from pydicom.uid import DeflatedImageFrameCompression
    >>> ds = examples.ct
    >>> ds.SamplesPerPixel
    1
    >>> ds.PhotometricInterpretation
    'MONOCHROME2'
    >>> ds.BitsAllocated
    16
    >>> ds.PixelRepresentation
    1
    >>> ds.compress(DeflatedImageFrameCompression)
    >>> len(ds.PixelData)
    22288
