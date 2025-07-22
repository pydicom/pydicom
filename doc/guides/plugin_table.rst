
====================================================
Plugins for Pixel Data compression and decompression
====================================================

The default installation of *pydicom* doesn't support decompression or compression of
*Pixel Data*, except for *RLE Lossless* and *Deflated Image Frame Compression*.
Support for other compressed transfer syntaxes is added through plugins, each of which
requires installing `NumPy <https://numpy.org/>`_ and one or more third-party packages.

To determine that transfer syntax used by a dataset you can use the following snippet::

    from pydicom import dcmread

    ds = dcmread("path/to/dataset")
    print(ds.file_meta.TransferSyntaxUID.name)


.. _guide_decoding_plugins:

Plugins for decompression
=========================

The table below lists the plugins available for decompressing pixel data that's been
compressed using the method corresponding to the *Transfer Syntax UID*. No plugins are
required for uncompressed pixel data, as *pydicom* can handle these natively as long as
`NumPy <https://numpy.org/>`_ is installed.

If your dataset uses a compressed transfer syntax that isn't listed below then
you'll have to rely on third-party methods for decoding, :ref:`as described here
<tut_pixel_data_decode_third_party>`.

Supported Transfer Syntaxes
---------------------------

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
| *Deflated Image Frame   | 1.2.840.10008.1.2.8.1   |                 |          |                 |              | |chk|       |
| Compression*            |                         |                 |          |                 |              |             |
+-------------------------+-------------------------+-----------------+----------+-----------------+--------------+-------------+

| :sup:`1` with ``pylibjpeg-libjpeg``
| :sup:`2` with ``pylibjpeg-openjpeg``
| :sup:`3` with ``pylibjpeg-rle``
| :sup:`4` with Pillow's *Jpeg2KImagePlugin*


Plugin requirements and limitations
-----------------------------------

.. _pylj: https://github.com/pydicom/pylibjpeg
.. _pylj-lj: https://github.com/pydicom/pylibjpeg-libjpeg
.. _pylj-oj: https://github.com/pydicom/pylibjpeg-openjpeg
.. _pylj-rle: https://github.com/pydicom/pylibjpeg-rle
.. _py-gdcm: https://github.com/tfmoraes/python-gdcm
.. _pil: https://pillow.readthedocs.io/en/stable/
.. _pil_j2k: https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#jpeg-2000
.. _pyjls: https://github.com/pydicom/pyjpegls
.. _pyd: https://github.com/pydicom/pydicom


+---------------+-------------------------------------------+---------------------------------------------------------------------+
| Plugin        | Requires                                  | Known limitations                                                   |
+===============+===========================================+===============================+=====================================+
| ``pylibjpeg`` | `pylibjpeg <pylj_>`_ and at least one of  | * Maximum supported *Bits Stored* for JPEG 2000 and HTJ2K is 24     |
|               | `pylibjpeg-libjpeg <pylj-lj_>`_,          |                                                                     |
|               | `pylibjpeg-openjpeg <pylj-oj_>`_ and      |                                                                     |
|               | `pylibjpeg-rle <pylj-rle_>`_              |                                                                     |
+---------------+-------------------------------------------+---------------------------------------------------------------------+
| ``gdcm``      | `python-gdcm <py-gdcm_>`_                 | * *JPEG Extended 12-bit* is only available if *Bits Allocated* is 8 |
|               |                                           | * *JPEG-LS Near Lossless* only if *Bits Stored* is at least 8       |
|               |                                           |   for a *Pixel Representation* of 1                                 |
|               |                                           | * *JPEG-LS Lossless* and *JPEG-LS Near Lossless* only if            |
|               |                                           |   *Bits Stored* is not 6 or 7                                       |
|               |                                           | * Maximum supported *Bits Stored* is 16                             |
+---------------+-------------------------------------------+---------------------------------------------------------------------+
| ``pillow``    | `Pillow <pil_>`_, with support for JPEG   | * *JPEG Extended 12-bit* is only available if *Bits Allocated* is 8 |
|               | 2000 via Pillow's `Jpeg2KImagePlugin      | * *JPEG 2000 Lossless* and *JPEG 2000* are only available           |
|               | <pil_j2k_>`_                              |   for a *Samples per Pixel* of 3 when *Bits Stored* is <= 8         |
|               |                                           | * Maximum supported *Bits Stored* is 16                             |
+---------------+-------------------------------------------+---------------------------------------------------------------------+
| ``pyjpegls``  | `pyjpegls <pyjls_>`_                      |                                                                     |
+---------------+-------------------------------------------+---------------------------------------------------------------------+
| ``pydicom``   | `pydicom <pyd_>`_                         | * *RLE Lossless*: Slower than the other plugins by 3-4x             |
+---------------+-------------------------------------------+---------------------------------------------------------------------+


.. _guide_encoding_plugins:

Plugins for compression
=======================

.. currentmodule:: pydicom.pixels.encoders

The table below lists the plugins available for compressing pixel data using the method
corresponding to the *Transfer Syntax UID*. If you wish to use a compression method that
isn't listed below then you'll have to rely on third-party methods for encoding,
:ref:`as described here <tut_pixel_data_encode_third_party>`.

Supported Transfer Syntaxes
---------------------------

+------------------------------------------------------+-----------------+--------------------------------------------+
| Transfer Syntax                                      | Plugins         | Encoding guide                             |
+---------------------------+--------------------------+                 |                                            |
| Name                      | UID                      |                 |                                            |
+===========================+==========================+=================+============================================+
| | *JPEG-LS Lossless*      | | 1.2.840.10008.1.2.4.80 | ``pyjpegls``    | :doc:`JPEG-LS</guides/encoding/jpeg_ls>`   |
| | *JPEG-LS Near Lossless* | | 1.2.840.10008.1.2.4.81 |                 |                                            |
+---------------------------+--------------------------+-----------------+--------------------------------------------+
| | *JPEG 2000 Lossless*    | | 1.2.840.10008.1.2.4.90 | ``pylibjpeg``   | :doc:`JPEG 2000</guides/encoding/jpeg_2k>` |
| | *JPEG 2000*             | | 1.2.840.10008.1.2.4.91 |                 |                                            |
+---------------------------+--------------------------+-----------------+--------------------------------------------+
| *RLE Lossless*            | 1.2.840.10008.1.2.5      | | ``pylibjpeg`` | :doc:`RLE</guides/encoding/rle_lossless>`  |
|                           |                          | | ``pydicom``   |                                            |
|                           |                          | | ``gdcm``      |                                            |
+---------------------------+--------------------------+-----------------+--------------------------------------------+
| *Deflated Image Frame     | 1.2.840.10008.1.2.8.1    | ``pydicom``     | :doc:`Deflated Image                       |
| Compression*              |                          |                 | </guides/encoding/defl_image>`             |
+---------------------------+--------------------------+-----------------+--------------------------------------------+


Plugin requirements and limitations
-----------------------------------

+---------------+-------------------------------------------+---------------------------------------------------------------------+
| Plugin        | Requires                                  | Known limitations                                                   |
+===============+===========================================+===============================+=====================================+
| ``pyjpegls``  | `pyjpegls <pyjls_>`_                      |                                                                     |
+---------------+-------------------------------------------+---------------------------------------------------------------------+
| ``pylibjpeg`` | `pylibjpeg <pylj_>`_ and                  | * Maximum supported *Bits Stored* for JPEG 2000 is 24, however the  |
|               | `pylibjpeg-openjpeg <pylj-oj_>`_ and/or   |   results for 20-24 are quite poor when using lossy compression     |
|               | `pylibjpeg-rle <pylj-rle_>`_              |                                                                     |
+---------------+-------------------------------------------+---------------------------------------------------------------------+
| ``pydicom``   | `pydicom <pyd_>`_                         | * *RLE Lossless*: Much slower than the other plugins                |
+---------------+-------------------------------------------+---------------------------------------------------------------------+
| ``gdcm``      | `python-gdcm <py-gdcm_>`_                 |                                                                     |
+---------------+-------------------------------------------+---------------------------------------------------------------------+
