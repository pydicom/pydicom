Handling of compressed image data
---------------------------------

.. currentmodule:: pydicom

.. rubric:: How to get image data from compressed DICOM images

Preconditions
............
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

Note that you always need the `NumPy <http://numpy.org/>`_ package to be able to handle image
data.

.. caution:: We rely on the image handling capacity of the mentioned
   packages and cannot guarantee the correctness of the generated uncompressed
   images. Be sure to verify the correctness of generated images using other
   means before you use them for medical purposes.

Supported Transfer Syntaxes
...........................
As far as we have been able to verify, the following transfer syntaxes are
handled by the given packages:

+------------------------------------+------------------------+-------+---------+--------+------------+
|       Transfer Syntax Name         |  Transfer Syntax UID   | NumPy | JPEG-LS |  GDCM  |   Pillow   |
+====================================+========================+=======+=========+========+============+
| Explicit VR Little Endian          | 1.2.840.10008.1.2.1    |  *+*  |  *+*    |  *+*   |    *+*     |
+------------------------------------+------------------------+-------+---------+--------+------------+
| Implicit VR Little Endian          | 1.2.840.10008.1.2      |  *+*  |  *+*    |  *+*   |    *+*     |
+------------------------------------+------------------------+-------+---------+--------+------------+
| Explicit VR Big Endian             | 1.2.840.10008.1.2.2    |  *+*  |  *+*    |  *+*   |    *+*     |
+------------------------------------+------------------------+-------+---------+--------+------------+
| Deflated Explicit VR Little Endian | 1.2.840.10008.1.2.1.99 |  *+*  |  *+*    |  *+*   |    *+*     |
+------------------------------------+------------------------+-------+---------+--------+------------+
| RLE Lossless                       | 1.2.840.10008.1.2.5    |  *+*  |  *+*    |  *+*   |    *+*     |
+------------------------------------+------------------------+-------+---------+--------+------------+
| JPEG BaseLine Lossy 8bit           | 1.2.840.10008.1.2.4.50 |  *-*  |  *-*    |  *+*   | +\ :sup:`1`|
+------------------------------------+------------------------+-------+---------+--------+------------+
| JPEG BaseLine Lossy 12bit          | 1.2.840.10008.1.2.4.51 |  *-*  |  *-*    |  *+*   | +\ :sup:`1`|
+------------------------------------+------------------------+-------+---------+--------+------------+
| JPEG Lossless                      | 1.2.840.10008.1.2.4.70 |  *-*  |  *-*    |  *+*   |    *+*     |
+------------------------------------+------------------------+-------+---------+--------+------------+
| JPEG LS Lossless                   | 1.2.840.10008.1.2.4.80 |  *-*  |  *+*    |  *+*   |    *-*     |
+------------------------------------+------------------------+-------+---------+--------+------------+
| JPEG LS Lossy :sup:`3`             | 1.2.840.10008.1.2.4.81 |  *-*  |  *+*    |  *+*   |    *-*     |
+------------------------------------+------------------------+-------+---------+--------+------------+
| JPEG2000 Lossless                  | 1.2.840.10008.1.2.4.90 |  *-*  |  *-*    |  *+*   | +\ :sup:`2`|
+------------------------------------+------------------------+-------+---------+--------+------------+
| JPEG2000 Lossy :sup:`4`            | 1.2.840.10008.1.2.4.91 |  *-*  |  *-*    |  *-*   | +\ :sup:`5`|
+------------------------------------+------------------------+-------+---------+--------+------------+

| (1) only with JpegImagePlugin
| (2) only with Jpeg2KImagePlugin
| (3) handled differently by Pillow and GDCM
| (4) no support for 8 bit Grayscale
| (5) not supported for > 8 bit

Usage
.....
To use decompressed image data from compressed DICOM images, you have two options:

* use ``decompress()`` on the dataset to convert it in-place and work with the pixel data as described before
* get an uncompressed copy of the pixel data as a NumPy array using ``Dataset.pixel_array`` without touching the original dataset

.. note:: Using ``decompress()`` adapts the transfer syntax of the data set, but not the Photometric Interpretation.
   The Photometric Interpretation may not match the pixel data, depending on the used decompression handler.
