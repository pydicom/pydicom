Handling of compressed image data
---------------------------------

.. currentmodule:: pydicom

.. rubric:: How to get image data from compressed DICOM images

.. |chk|   unicode:: U+02713 .. CHECK MARK

Preconditions
.............
To be able to decompress compressed DICOM image data, you need to have
one or more packages installed that are able to handle this kind of data.
``pydicom`` detects the installed packages and provides image data handlers
that use the available packages.

The following packages can be used with ``pydicom``:

* `GDCM <http://gdcm.sourceforge.net/>`_ - this is the package that supports
  most compressed formats
* `Pillow <http://pillow.readthedocs.io/en/latest/>`_, ideally with
  ``jpeg`` and ``jpeg2000`` plugins
* `jpeg_ls <https://github.com/Who8MyLunch/CharPyLS>`_

Note that you always need the `NumPy <http://numpy.org/>`_ package to be able
to handle image data.

.. caution:: We rely on the image handling capacity of the mentioned
   packages and cannot guarantee the correctness of the generated uncompressed
   images. Be sure to verify the correctness of generated images using other
   means before you use them for medical purposes.

Supported Transfer Syntaxes
...........................
As far as we have been able to verify, the following transfer syntaxes are
handled by the given packages:

+-------------------------------------------------------------+-------+---------+---------+-----------------+
| Transfer Syntax                                             | NumPy | NumPy + | NumPy + | NumPy +         |
+------------------------------------+------------------------+       | JPEG-LS | GDCM    | Pillow          |
| Name                               | UID                    |       |         |         |                 |
+====================================+========================+=======+=========+=========+=================+
| Explicit VR Little Endian          | 1.2.840.10008.1.2.1    | |chk| | |chk|   | |chk|   |     |chk|       |
+------------------------------------+------------------------+-------+---------+---------+-----------------+
| Implicit VR Little Endian          | 1.2.840.10008.1.2      | |chk| | |chk|   | |chk|   |     |chk|       |
+------------------------------------+------------------------+-------+---------+---------+-----------------+
| Explicit VR Big Endian             | 1.2.840.10008.1.2.2    | |chk| | |chk|   | |chk|   |     |chk|       |
+------------------------------------+------------------------+-------+---------+---------+-----------------+
| Deflated Explicit VR Little Endian | 1.2.840.10008.1.2.1.99 | |chk| | |chk|   | |chk|   |     |chk|       |
+------------------------------------+------------------------+-------+---------+---------+-----------------+
| RLE Lossless                       | 1.2.840.10008.1.2.5    | |chk| | |chk|   | |chk|   |     |chk|       |
+------------------------------------+------------------------+-------+---------+---------+-----------------+
| JPEG Baseline (Process 1)          | 1.2.840.10008.1.2.4.50 |       |         | |chk|   | |chk|\ :sup:`1` |
+------------------------------------+------------------------+-------+---------+---------+-----------------+
| JPEG Extended (Process 2 and 4)    | 1.2.840.10008.1.2.4.51 |       |         | |chk|   | |chk|\ :sup:`1` |
+------------------------------------+------------------------+-------+---------+---------+-----------------+
| JPEG Lossless (Process 14)         | 1.2.840.10008.1.2.4.57 |       |         | |chk|   |                 |
+------------------------------------+------------------------+-------+---------+---------+-----------------+
| JPEG Lossless (Process 14, SV1)    | 1.2.840.10008.1.2.4.70 |       |         | |chk|   | |chk|\ :sup:`5` |
+------------------------------------+------------------------+-------+---------+---------+-----------------+
| JPEG LS Lossless                   | 1.2.840.10008.1.2.4.80 |       | |chk|   | |chk|   |                 |
+------------------------------------+------------------------+-------+---------+---------+-----------------+
| JPEG LS Lossy :sup:`3`             | 1.2.840.10008.1.2.4.81 |       | |chk|   | |chk|   |                 |
+------------------------------------+------------------------+-------+---------+---------+-----------------+
| JPEG2000 Lossless                  | 1.2.840.10008.1.2.4.90 |       |         | |chk|   | |chk|\ :sup:`2` |
+------------------------------------+------------------------+-------+---------+---------+-----------------+
| JPEG2000 :sup:`4`                  | 1.2.840.10008.1.2.4.91 |       |         |         | |chk|\ :sup:`5` |
+------------------------------------+------------------------+-------+---------+---------+-----------------+
| JPEG2000 Multi-component Lossless  | 1.2.840.10008.1.2.4.92 |       |         |         |                 |
+------------------------------------+------------------------+-------+---------+---------+-----------------+
| JPEG2000 Multi-component           | 1.2.840.10008.1.2.4.93 |       |         |         |                 |
+------------------------------------+------------------------+-------+---------+---------+-----------------+

| :sup:`1` *only with JpegImagePlugin*
| :sup:`2` *only with Jpeg2KImagePlugin*
| :sup:`3` *handled differently by Pillow and GDCM*
| :sup:`4` *no support for 8 bit Grayscale*
| :sup:`5` *not supported for > 8 bit*

Usage
.....
To use decompressed image data from compressed DICOM images, you have two
options:

* use :meth:`~pydicom.dataset.Dataset.decompress` on the dataset to convert
  it in-place and work with the pixel data as described before
* get an uncompressed copy of the pixel data as a NumPy array using
  :attr:`Dataset.pixel_array<pydicom.dataset.Dataset.pixel_array>` without
  touching the original dataset

.. note:: Using :meth:`~pydicom.dataset.Dataset.decompress` adapts the
   transfer syntax of the data set, but not the *Photometric Interpretation*.
   The *Photometric Interpretation* may not match the pixel data, depending on
   the used decompression handler.

.. _colorspace:

Color space
...........

When using :attr:`Dataset.pixel_array<pydicom.dataset.Dataset.pixel_array>`
with *Pixel Data* that has an (0028,0002) *Samples per Pixel* value
of ``3`` and a (0028,0004) *Photometric Interpretation* which is non-RGB (i.e.
``YBR_FULL``, ``YBR_FULL_422``, etc) then the returned pixel data may be in
a different color space depending on the package used to decompress the data.

* For GDCM, the data will be in the color space listed in *Photometric
  Interpretation*
* For Pillow, YBR data will be converted automatically to RGB

*pydicom* offers a limited ability to convert between 8-bits/channel RGB and
YBR color spaces through the
:func:`~pydicom.pixel_data_handlers.util.convert_color_space`
function. When changing the color space you should also change the value
of *Photometric Interpretation* to match.


.. note:: See the DICOM Standard, Part 3,
   :dcm:`Section C.7.6.3.1<part03/sect_C.7.6.3.html#sect_C.7.6.3.1>` for more
   information about color spaces.
