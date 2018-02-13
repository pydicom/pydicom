Handling of compressed image data
---------------------------------

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

Note that you always need the ``numpy`` package to be able to handle image
data.

.. caution:: We rely on the image handling capacity of the mentioned
   packages and cannot guarantee the correctness of the generated uncompressed
   images. Be sure to verify the correctness of generated images using other
   means before you use them for medical purposes.

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

Decompression of the following tranfer syntaxes may not work or show
derivations from the expected result:

* JPEG 2000 Lossy 8 bit Grayscale
* JPEG 2000 Lossy > 8 bit - not handled by Pillow/OpenJpeg
* JPEG Lossy 8 bit Color - handled differently by Pillow and GDCM
