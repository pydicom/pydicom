
========
Glossary
========

.. _glossary_image_pixel:

:dcm:`Image Pixel Module<part03/sect_C.7.6.3.html>`
===================================================

**(0028,0002) Samples per Pixel**
    The number of samples per pixel, otherwise known as the number of image
    channels, components or planes. An RGB image has 3 samples per pixel (red,
    green and blue), a grayscale image has 1 sample per pixel (intensity).
    The *Samples per Pixel* for all DICOM *Pixel Data* is either 1 or 3,
    however 4 was previously allowed.

    Allowed values: ``1`` or ``3``, but may be constrained by the :dcm:`IOD
    <part03/ps3.3.html>`.

**(0028,0004) Photometric Interpretation**
    The intended interpretation of the *Pixel Data* in its *current form* in
    the dataset. For example:

    * If you have a dataset with RGB *Pixel Data* then the  *Photometric
      Interpretation* should be ``'RGB'``.
    * If you take your RGB data and convert it to `YCbCr
      <https://en.wikipedia.org/wiki/YCbCr>`_ then the *Photometric
      Interpretation* should be ``'YBR_FULL'`` (or a related interpretation
      depending on the conversion method).
    * If you then compress that data using *RLE Lossless* encoding then the
      *Photometric Interpretation* remains ``'YBR_FULL'``.
    * On the other hand, if you take your original RGB data and apply *JPEG
      2000 Lossless* encoding then the *Photometric Interpretation* will either
      be ``'RGB'`` or ``'YBR_RCT'`` depending on whether or not the encoder
      performs multiple component transformation.

    When compressing pixel data using one of the JPEG encodings it's important
    to know if the encoder is performing any color space transformation prior
    to compression, as this needs to be taken into account when setting
    the *Photometric Interpretation*. This is important when an encoder
    performs a transformation and the decoder doesn't, since having a correct
    *Photometric Interpretation* makes it possible to determine which inverse
    transformation to use to return the pixel data to its original color space.

    For more detailed information on each of the defined photometric
    interpretations refer to :dcm:`Annex C.7.6.3.1
    <part03/sect_C.7.6.3.html#sect_C.7.6.3.1.2>` of Part 3 of the DICOM
    Standard.

    Allowed values: ``'MONOCHROME1'``, ``'MONOCHROME2'``, ``'PALETTE COLOR'``,
    ``'RGB'``, ``'YBR_FULL'``, ``'YBR_FULL_422'``, ``'YBR_PARTIAL_420'``,
    ``'YBR_ICT'``, ``'YBR_RCT'``, however restrictions apply based on
    the *Transfer Syntax UID*, and further constraints may be required by the
    :dcm:`IOD<part03/ps3.3.html>`.


**(0028,0006) Planar Configuration**
    Required when *Samples per Pixel* is greater than one, this indicates the
    order of the samples used by the pixel data, as either:

    * ``0``, where sample values for the first pixel is followed by the sample
      value for the second pixel: R1, G1, B1, R2, G2, B2, ..., Rn, Gn, Bn.
    * ``1``, where sample values for each color plane are contiguous: R1, R2,
      ..., Rn, G1, G2, ..., Gn, B1, B2, ..., Bn.

    Allowed values: ``0`` or ``1``


**(0028,0100) Bits Allocated**
    The number of bits used to actually *contain* each sample of each pixel.
    All DICOM *Pixel Data* is either 1 (for bit-packed *Pixel Data*) or more
    typically a multiple of 8 such as 8, 16 or 32, with 64 currently being the
    maximum used. Using the example of a *Bits Stored* of 12, this means that
    the actual number of bits used to contain the values must be at least 16.

    For more detailed information refer to :dcm:`Chapter 8
    <part05/chapter_8.html#sect_8.1.1>` and :dcm:`Annex D
    <part05/chapter_D.html>` in Part 5 of the DICOM Standard.

    Allowed values: ``1`` or a multiple of 8, however many :dcm:`IODs
    <part03/ps3.3.html>` place further restrictions on what the value may be.


**(0028,0101) Bits Stored**
    The number of bits actually *used* by each sample of each
    pixel. For example, with a *Bits Stored* value of ``12``, an unsigned
    grayscale image will have pixel values in the range 0 to 4095 and an
    unsigned RGB image will have values in the range (R: 0 to 4095, G: 0 to
    4095, B: 0 to 4095). Must be equal to or less than *Bits Allocated*.

    For more detailed information refer to :dcm:`Chapter 8
    <part05/chapter_8.html#sect_8.1.1>` and :dcm:`Annex D
    <part05/chapter_D.html>` in Part 5 of the DICOM Standard.

    Allowed values: ``1`` to *Bits Allocated* (inclusive)


**(0028,0102) High Bit**
    The `most significant bit
    <https://en.wikipedia.org/wiki/Bit_numbering#Most_significant_bit>`_ of the
    pixel sample data and is equal to *Bits Stored* - 1, however other values
    have been allowed in past versions of the DICOM Standard.

    Allowed values: *Bits Stored* - 1


**(0028,0103) Pixel Representation**
    Describes the type of pixel values, either signed (using
    `2's complement <https://en.wikipedia.org/wiki/Two%27s_complement>`_)
    or unsigned integers. A value of ``0`` indicates the *Pixel Data* contains
    unsigned integers while a value of ``1`` indicates it contains signed
    integers.

    Allowed values: ``0`` or ``1``, but may be constrained by the :dcm:`IOD
    <part03/ps3.3.html>`.
