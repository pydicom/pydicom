
====================================================
Plugins for Pixel Data Compression and Decompression
====================================================


.. _guide_decoding_plugins:

Plugins for Decompression
=========================

The table below lists the plugins available for decompressing pixel data that's been compressed using the corresponding
*Transfer Syntax UID*. No plugins are used for uncompressed pixel data.

.. |chk|   unicode:: U+02713 .. CHECK MARK

+---------------------------------------------------+---------------------------------------------------------------------------+
| Transfer Syntax                                   | Plugins                                                                   |
+-------------------------+-------------------------+-----------------+----------+-----------------+--------------+-------------+
| Name                    | UID                     | ``pylibjpeg``   | ``gdcm`` | ``pillow``      | ``pyjpegls`` | ``pydicom`` |
+=========================+=========================+=================+==========+=================+==============+=============+
| *JPEG Baseline 8-bit*   | 1.2.840.10008.1.2.4.50  | |chk|\ :sup:`1` | |chk|    | |chk|           |              |             |
+-------------------------+-------------------------+-----------------+----------+-----------------+--------------+-------------+
| *JPEG Extended 12-bit*  | 1.2.840.10008.1.2.4.51  | |chk|\ :sup:`1` | |chk|    | |chk|           |              |             |
+-------------------------+-------------------------+-----------------+----------+-----------------+--------------+-------------+
| *JPEG Lossless P14*     | 1.2.840.10008.1.2.4.57  | |chk|\ :sup:`1` | |chk|    |                 |              |             |
+-------------------------+-------------------------+-----------------+----------+-----------------+--------------+-------------+
| *JPEG Lossless SV1*     | 1.2.840.10008.1.2.4.70  | |chk|\ :sup:`1` | |chk|    |                 |              |             |
+-------------------------+-------------------------+-----------------+----------+-----------------+--------------+-------------+
| *JPEG-LS Lossless*      | 1.2.840.10008.1.2.4.80  | |chk|\ :sup:`1` | |chk|    |                 | |chk|        |             |
+-------------------------+-------------------------+-----------------+----------+-----------------+--------------+-------------+
| *JPEG-LS Near Lossless* | 1.2.840.10008.1.2.4.81  | |chk|\ :sup:`1` | |chk|    |                 | |chk|        |             |
+-------------------------+-------------------------+-----------------+----------+-----------------+--------------+-------------+
| *JPEG 2000 Lossless*    | 1.2.840.10008.1.2.4.90  | |chk|\ :sup:`2` | |chk|    | |chk|\ :sup:`4` |              |             |
+-------------------------+-------------------------+-----------------+----------+-----------------+--------------+-------------+
| *JPEG 2000*             | 1.2.840.10008.1.2.4.91  | |chk|\ :sup:`2` | |chk|    | |chk|\ :sup:`4` |              |             |
+-------------------------+-------------------------+-----------------+----------+-----------------+--------------+-------------+
| *HTJ2K Lossless*        | 1.2.840.10008.1.2.4.201 | |chk|\ :sup:`2` |          |                 |              |             |
+-------------------------+-------------------------+-----------------+----------+-----------------+--------------+-------------+
| *HTJ2K Lossless RPCL*   | 1.2.840.10008.1.2.4.202 | |chk|\ :sup:`2` |          |                 |              |             |
+-------------------------+-------------------------+-----------------+----------+-----------------+--------------+-------------+
| *HTJ2K*                 | 1.2.840.10008.1.2.4.203 | |chk|\ :sup:`2` |          |                 |              |             |
+-------------------------+-------------------------+-----------------+----------+-----------------+--------------+-------------+
| *RLE Lossless*          | 1.2.840.10008.1.2.5     | |chk|\ :sup:`3` | |chk|    |                 |              | |chk|       |
+-------------------------+-------------------------+-----------------+----------+-----------------+--------------+-------------+

| :sup:`1` with ``pylibjpeg-libjpeg``
| :sup:`2` with ``pylibjpeg-openjpeg``
| :sup:`3` with ``pylibjpeg-rle``
| :sup:`4` with Pillow's *Jpeg2KImagePlugin*


Plugins
-------

``pylibjpeg``
.............

Requires `pylibjpeg <https://github.com/pydicom/pylibjpeg>`_ and at least one of:

* `pylibjpeg-libjpeg <https://github.com/pydicom/pylibjpeg-libjpeg>`_
* `pylibjpeg-openjpeg <https://github.com/pydicom/pylibjpeg-openjpeg>`_
* `pylibjpeg-rle <https://github.com/pydicom/pylibjpeg-rle>`_

**Known limitations**

* Maximum supported *Bits Stored* for JPEG 2000 and HTJ2K is 24

``gdcm``
........

Requires `python-gdcm <https://github.com/tfmoraes/python-gdcm>`_.

**Known limitations**

* *JPEG Extended 12-bit* is only available if *Bits Allocated* is 8
* *JPEG-LS Near Lossless* only if *Bits Stored* is at least 8 for a *Pixel Representation* of 1
* *JPEG-LS Lossless* and *JPEG-LS Near Lossless* only if *Bits Stored* is not 6 or 7
* Maximum supported *Bits Stored* is 16

``pillow``
..........

Requires `Pillow <https://pillow.readthedocs.io/en/stable/>`_, with support for
JPEG 2000 via Pillow's `Jpeg2KImagePlugin
<https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#jpeg-2000>`_
requiring `OpenJPEG <https://www.openjpeg.org/>`_.

**Known limitations**

* *JPEG Extended 12-bit* is only available if *Bits Allocated* is 8
* *JPEG 2000 Lossless* and *JPEG 2000* are only available for a *Samples per Pixel* of
  3 when *Bits Stored* is <= 8
* Maximum supported *Bits Stored* is 16

``pyjpegls``
............

Requires `pyjpegls <https://github.com/pydicom/pyjpegls>`_.

``pydicom``
...........

Requires `pydicom <https://github.com/pydicom/pydicom>`_.

**Known limitations**

* Slower than the other plugins by 3-4x



.. _guide_encoding_plugins:

Plugins for Compression
=======================

.. currentmodule:: pydicom.pixels.encoders

+---------------------------------------------------+---------------+--------------------------------------------+
| Transfer Syntax                                   | Plugins       | Encoding guide                             |
+-------------------------+-------------------------+               |                                            |
| Name                    | UID                     |               |                                            |
+=========================+=========================+===============+============================================+
| *JPEG-LS Lossless*      | 1.2.840.10008.1.2.4.80  | ``pyjpegls``  | :doc:`JPEG-LS</guides/encoding/jpeg_ls>`   |
+-------------------------+-------------------------+               |                                            |
| *JPEG-LS Near Lossless* | 1.2.840.10008.1.2.4.81  |               |                                            |
+-------------------------+-------------------------+---------------+--------------------------------------------+
| *JPEG 2000 Lossless*    | 1.2.840.10008.1.2.4.90  | ``pylibjpeg`` | :doc:`JPEG 2000</guides/encoding/jpeg_2k>` |
+-------------------------+-------------------------+               |                                            |
| *JPEG 2000*             | 1.2.840.10008.1.2.4.91  |               |                                            |
+-------------------------+-------------------------+---------------+--------------------------------------------+
| *RLE Lossless*          | 1.2.840.10008.1.2.5     | ``pylibjpeg`` | :doc:`RLE</guides/encoding/rle_lossless>`  |
|                         |                         +---------------+                                            |
|                         |                         | ``pydicom``   |                                            |
+-------------------------+-------------------------+---------------+--------------------------------------------+


Plugins
-------

``pyjpegls``
............

Requires `pyjpegls <https://github.com/pydicom/pyjpegls>`_.


``pylibjpeg``
.............

Requires `pylibjpeg <https://github.com/pydicom/pylibjpeg>`_ as well as
`pylibjpeg-openjpeg <https://github.com/pydicom/pylibjpeg-openjpeg>`_ for JPEG 2000
compression and `pylibjpeg-rle <https://github.com/pydicom/pylibjpeg-rle>`_ for
*RLE Lossless*.

**Known limitations**

* The maximum supported *Bits Stored* for JPEG 2000 is 24, however the results
  for 20-24 are very poor when using lossy compression.

``pydicom``
...........

Requires `pydicom <https://github.com/pydicom/pydicom>`_.

**Known limitations**

* Much slower than the other plugins
