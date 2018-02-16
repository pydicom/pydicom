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

* `gdcm <http://gdcm.sourceforge.net/>`_ - this is the package that supports
  most compressed formats
* `pillow <http://pillow.readthedocs.io/en/latest/>`_, ideally with
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
handled correctly:

* Explicit and Implicit VR Little Endian (uncompressed)
* Explicit VR Big Endian (uncompressed)
* Deflated Explicit VR Little Endian
* RLE Lossless
* JPEG Lossless
* JPEG-LS Lossless
* JPEG 2000 Lossless
* JPEG Lossy 8 Bit Grayscale
* JPEG-LS Lossy (probably)

Decompression of the following transfer syntaxes may not work or show
deviations from the expected result:

* JPEG 2000 Lossy 8 bit Grayscale
* JPEG 2000 Lossy > 8 bit - not handled by Pillow/OpenJpeg
* JPEG Lossy 8 bit Color - handled differently by Pillow and GDCM

Usage
.....
To use decompressed image data from compressed DICOM images, you have two options:

* use ``decompress()`` on the dataset to convert it in-place and work with the pixel data as described before
* get an uncompressed copy of the pixel data as a NumPy array using ``Dataset.pixel_array`` without touching the original dataset

.. note:: Using ``decompress()`` adapts the transfer syntax of the data set, but not the Photometric Interpretation.
   The Photometric Interpretation may not match the pixel data, depending on the used decompression handler.
