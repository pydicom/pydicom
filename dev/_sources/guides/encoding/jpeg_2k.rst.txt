
JPEG 2000 Encoding
==================

The requirements for JPEG 2000 encoding are defined in :dcm:`Section 8.2.4
<part05/sect_8.2.4.html>` and Annex :dcm:`A.4.4<part05/sect_A.4.4.html>` of Part
5 of the DICOM Standard. The JPEG 2000 compression scheme is defined by `ISO/IEC
15444-1 <https://www.iso.org/standard/78321.html>`_/`ITU T.800
<https://www.itu.int/rec/T-REC-T.800-201511-S/en>`_ (the second link has free access).

The following JPEG 2000 encoding parameters are used by `pylibjpeg` plugin:

* For *JPEG 2000 Lossless* the reversible DWT 5-3 wavelet
* For *JPEG 2000* the irreversible DWT 9-7 wavelet
* 6 DWT decomposition levels
* 64 x 64 code block size
* 1 tile
* LRCP progression order
* No sub-sampling
* No JP2 header


Valid Image Pixel Parameters
----------------------------

The table below lists the valid :dcm:`Image Pixel<part03/sect_C.7.6.3.html>`
module parameters for *Pixel Data* encoded using the *JPEG 2000 Lossless* or *JPEG 2000*
transfer syntaxes. For an explanation of each parameter and its relationship
with the *Pixel Data* see the :doc:`glossary of Image Pixel elements<../glossary>`.

+------------+-----------------------+-----------------+----------------+------------+---------+
| *Samples   | *Photometric          | *Pixel          | *Planar        | *Bits      | *Bits   |
| per Pixel* | Interpretation*       | Representation* | Configuration* | Allocated* | Stored* |
+============+=======================+=================+================+============+=========+
| 1          | MONOCHROME1           | 0 or 1          | (absent)       | 8, 16, 24, | 1 to 38 |
|            +-----------------------+                 |                | 32 or 40   |         |
|            | MONOCHROME2           |                 |                |            |         |
|            +-----------------------+-----------------+----------------+------------+---------+
|            | PALETTE COLOR :sup:`1`| 0               | (absent)       | 8 or 16    | 1 to 16 |
+------------+-----------------------+-----------------+----------------+------------+---------+
| 3          | RGB                   | 0               | 0              | 8, 16, 24, | 1 to 38 |
|            +-----------------------+                 |                | 32 or 40   |         |
|            | YBR_RCT               |                 |                |            |         |
|            +-----------------------+                 |                |            |         |
|            | YBR_ICT :sup:`2`      |                 |                |            |         |
|            +-----------------------+                 |                |            |         |
|            | YBR_FULL              |                 |                |            |         |
+------------+-----------------------+-----------------+----------------+------------+---------+

| :sup:`1` *JPEG 2000 Lossless* only
| :sup:`2` *JPEG 2000* only

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

  * For *Photometric Interpretation* ``RGB``, ``YBR_ICT`` or ``YBR_RCT``; nothing
    else is required.
  * For *Photometric Interpretation* ``YBR_FULL`` the pixel data must first be
    converted into RGB color space, however the conversion operation is lossy.

* If your uncompressed pixel data is in `YCbCr
  <https://en.wikipedia.org/wiki/YCbCr>`_ color space:

  * For *Photometric Interpretation* ``RGB``, ``YBR_ICT`` or ``YBR_RCT``; the
    pixel data must first be converted into RGB color space, however the
    conversion operation is lossy.
  * For *Photometric Interpretation* ``YBR_FULL`` nothing else is required.

If your uncompressed pixel data is in RGB color space then setting the
*Photometric Interpretation* to ``YBR_ICT`` or ``YBR_RCT`` will signal the
encoder to apply multiple-component transformation (MCT) to the pixel data
during the encoding process, which should result in a higher compression ratio
for a given image quality. If you don't wish to use MCT then keep the
*Photometric Interpretation* as ``RGB``

Bits Stored
...........
The maximum supported *Bits Stored* value for encoding is ``24``.


Examples
--------

JPEG 2000 Lossless
...................

Losslessly compress unsigned RGB pixel data in-place, without the use of the
multiple-component transformation:

.. code-block:: python

    from pydicom import examples
    from pydicom.uid import JPE2000Lossless

    ds = examples.rgb_color
    assert ds.SamplesPerPixel == 1
    assert ds.PhotometricInterpretation == "RGB"
    assert ds.BitsAllocated == 8
    assert ds.BitsStored == 8
    assert ds.PixelRepresentation == 0
    assert len(ds.PixelData) == 921600

    ds.compress(JPE2000Lossless)

    print(len(ds.PixelData))  # ~334412

Losslessly compress unsigned RGB pixel data in-place with multiple-component
transformation:

.. code-block:: python

    from pydicom import examples
    from pydicom.uid import JPE2000Lossless

    ds = examples.rgb_color
    assert ds.SamplesPerPixel == 1
    assert ds.PhotometricInterpretation == "RGB"
    assert ds.BitsAllocated == 8
    assert ds.BitsStored == 8
    assert ds.PixelRepresentation == 0
    assert len(ds.PixelData) == 921600

    # YBR_ICT is not valid with *JPEG 2000 Lossless*
    ds.PhotometricInterpretation = "YBR_RCT"
    ds.compress(JPE2000Lossless)

    print(len(ds.PixelData))  # ~152342


Losslessly compress signed greyscale pixel data in-place:

.. code-block:: python

    from pydicom import examples
    from pydicom.uid import JPE2000Lossless

    ds = examples.ct
    assert ds.SamplesPerPixel == 1
    assert ds.PhotometricInterpretation == 'MONOCHROME2'
    assert ds.BitsAllocated == 16
    assert ds.BitsStored == 16
    assert ds.PixelRepresentation == 1
    assert len(ds.PixelData) == 32768

    ds.compress(JPE2000Lossless)

    print(len(ds.PixelData))  # ~13656


JPEG 2000
.........

.. warning::

    *pydicom* makes no recommendations for specifying image quality for lossy
    encoding methods. Any examples of lossy encoding are for **illustration
    purposes only**.

When performing lossy encoding one or more quality layers may be used, with each
quality layer allowing the reconstruction of the pixel data at a given resolution.
The image quality of each layer is controlled by passing either the `j2k_cr` or the
`j2k_psnr` parameter to the :meth:`encoding function<pydicom.dataset.Dataset.compress>`
as ``list[float]``, where:

* `j2k_cr`: a list of the compression ratios to use for each quality
  layer. There must be at least one quality layer and the minimum allowable
  compression ratio is ``1``. When using multiple quality layers they should be
  ordered in decreasing value from left to right::

    # 1 quality layer at 1.5:1
    j2k_cr = [1.5]

    # 2 quality layers at 5:1, and 2:1
    j2k_cr = [5, 2]

* `j2k_psnr`: a list of the peak signal-to-noise ratios (in dB) to use
  for each quality layer. There must be at least one quality layer and when
  using multiple quality layers they should be ordered in increasing value from
  left to right::

    # 1 quality layer
    j2k_psnr = [80]

    # 3 quality layers
    j2k_psnr = [80, 100, 200]

Lossy compression of unsigned RGB pixel data without multiple-component transformation:

.. code-block:: python

    from pydicom import examples
    from pydicom.uid import JPEG2000

    ds = examples.rgb_color
    assert ds.SamplesPerPixel == 1
    assert ds.PhotometricInterpretation == 'RGB'
    assert ds.BitsAllocated == 8
    assert ds.BitsStored == 8
    assert ds.PixelRepresentation == 0
    assert len(ds.PixelData) == 921600

    ds.compress(JPEG2000, j2k_cr=[20])

    print(len(ds.PixelData))  # ~46100


Lossy compression of unsigned RGB pixel data with multiple-component transformation:

.. code-block:: python

    from pydicom import examples
    from pydicom.uid import JPEG2000

    ds = examples.rgb_color
    assert ds.SamplesPerPixel == 1
    assert ds.PhotometricInterpretation == 'RGB'
    assert ds.BitsAllocated == 8
    assert ds.BitsStored == 8
    assert ds.PixelRepresentation == 0
    assert len(ds.PixelData) == 921600

    # YBR_RCT is not valid with lossy *JPEG 2000*
    ds.PhotometricInterpretation = "YBR_ICT"

    ds.compress(JPEG2000, j2k_cr=[20])

    print(len(ds.PixelData))  # ~46076


Lossy compression of signed greyscale pixel data:

.. code-block:: python

    from pydicom import examples
    from pydicom.uid import JPEG2000

    ds = examples.ct
    assert ds.SamplesPerPixel == 1
    assert ds.PhotometricInterpretation == 'MONOCHROME2'
    assert ds.BitsAllocated == 16
    assert ds.BitsStored == 16
    assert ds.PixelRepresentation == 1
    assert len(ds.PixelData) == 32768

    ds.compress(JPEG2000, j2k_cr=[20])

    print(ds.PixelData)  # ~1582


Available Plugins
-----------------


pylibjpeg
.........

.. |br| raw:: html

   <br />

.. _np: https://numpy.org/
.. _pylj: https://github.com/pydicom/pylibjpeg
.. _oj: https://github.com/pydicom/pylibjpeg-openjpeg

+----------------------------------------------------------+-----------------------------------------------+
| Encoder                                                  | Plugins                                       |
|                                                          +-----------+-----------------------------+-----+
|                                                          | Name      | Requires                    |Added|
+==========================================================+===========+=============================+=====+
|:attr:`~pydicom.pixels.encoders.JPEG2000LosslessEncoder`  | pylibjpeg | `numpy <np_>`_,             |v3.0 |
+----------------------------------------------------------+           | `pylibjpeg <_pylj>`_,       |     |
|:attr:`~pydicom.pixels.encoders.JPEG2000Encoder`          |           | `pylibjpeg-openjpeg <_oj>`_ |     |
+----------------------------------------------------------+-----------+-----------------------------+-----+
