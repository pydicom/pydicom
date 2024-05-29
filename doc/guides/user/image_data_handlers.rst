.. _guide_compressed:

Handling of compressed pixel data
---------------------------------

.. currentmodule:: pydicom

.. rubric:: How to get compressed pixel data

.. |chk|   unicode:: U+02713 .. CHECK MARK


Prerequisites
.............
To be able to decompress compressed DICOM pixel data, you need to install
one or more packages that are able to handle the format the data
is encoded in.

The following packages can be used with *pydicom* and `NumPy <https://numpy.org/>`_ to
decompress compressed *Pixel Data*:

* :gh:`pylibjpeg <pylibjpeg>` with the ``pylibjpeg-libjpeg``, ``pylibjpeg-openjpeg``
  and ``pylibjpeg-rle`` plugins. Supports the most commonly used transfer syntaxes.
* `jpeg_ls <https://github.com/pydicom/pyjpegls>`_ supports JPEG-LS transfer syntaxes.
* `GDCM <https://sourceforge.net/projects/gdcm/>`_ supports the most commonly
  used transfer syntaxes.
* `Pillow <https://python-pillow.org/>`_, ideally with the ``jpeg`` and ``jpeg2000``
  plugins. However we don't recommend using Pillow as it performs a number of
  undesirable operations on the decoded images which are not always reversible.

.. caution::

    We rely on the data handling capacity of the mentioned
    packages and cannot guarantee the correctness of the generated uncompressed
    pixel data. Be sure to verify the correctness of the output using other
    means before you use them.

Supported Transfer Syntaxes
...........................

To get the transfer syntax of a dataset you can do::

  >>> from pydicom import dcmread
  >>> ds = dcmread('path/to/dicom/file')
  >>> ds.file_meta.TransferSyntaxUID
  '1.2.840.10008.1.2.1'
  >>> ds.BitsAllocated
  16

As far as we have been able to verify, the following transfer syntaxes are
handled by the given packages:

+---------------------------------------------------------------------+-------+-------------+----------+-----------------+-----------------+
| Transfer Syntax                                                     | NumPy | NumPy +     | NumPy +  | NumPy +         | NumPy +         |
+-------------------------------------------+-------------------------+       | JPEG-LS     | GDCM     | Pillow          | pylibjpeg       |
| Name                                      | UID                     |       |             |          |                 |                 |
+===========================================+=========================+=======+=============+==========+=================+=================+
| Explicit VR Little Endian                 | 1.2.840.10008.1.2.1     | |chk| | |chk|       | |chk|    |     |chk|       | |chk|           |
+-------------------------------------------+-------------------------+-------+-------------+----------+-----------------+-----------------+
| Implicit VR Little Endian                 | 1.2.840.10008.1.2       | |chk| | |chk|       | |chk|    |     |chk|       | |chk|           |
+-------------------------------------------+-------------------------+-------+-------------+----------+-----------------+-----------------+
| Explicit VR Big Endian                    | 1.2.840.10008.1.2.2     | |chk| | |chk|       | |chk|    |     |chk|       | |chk|           |
+-------------------------------------------+-------------------------+-------+-------------+----------+-----------------+-----------------+
| Deflated Explicit VR Little Endian        | 1.2.840.10008.1.2.1.99  | |chk| | |chk|       | |chk|    |     |chk|       | |chk|           |
+-------------------------------------------+-------------------------+-------+-------------+----------+-----------------+-----------------+
| RLE Lossless                              | 1.2.840.10008.1.2.5     | |chk| | |chk|       | |chk|    |     |chk|       | |chk|\ :sup:`4` |
+-------------------------------------------+-------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG Baseline (Process 1)                 | 1.2.840.10008.1.2.4.50  |       |             | |chk|    | |chk|\ :sup:`1` | |chk|\ :sup:`5` |
+-------------------------------------------+-------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG Extended (Process 2 and 4)           | 1.2.840.10008.1.2.4.51  |       |             | |chk|    | |chk|\          | |chk|\ :sup:`5` |
|                                           |                         |       |             |          | :sup:`1,3`      |                 |
+-------------------------------------------+-------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG Lossless (Process 14)                | 1.2.840.10008.1.2.4.57  |       |             | |chk|    |                 | |chk|\ :sup:`5` |
+-------------------------------------------+-------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG Lossless (Process 14, SV1)           | 1.2.840.10008.1.2.4.70  |       |             | |chk|    |                 | |chk|\ :sup:`5` |
+-------------------------------------------+-------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG LS Lossless                          | 1.2.840.10008.1.2.4.80  |       | |chk|       | |chk|    |                 | |chk|\ :sup:`5` |
+-------------------------------------------+-------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG LS Lossy                             | 1.2.840.10008.1.2.4.81  |       | |chk|       | |chk|    |                 | |chk|\ :sup:`5` |
+-------------------------------------------+-------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG 2000 Lossless                        | 1.2.840.10008.1.2.4.90  |       |             | |chk|    | |chk|\ :sup:`2` | |chk|\ :sup:`6` |
+-------------------------------------------+-------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG 2000                                 | 1.2.840.10008.1.2.4.91  |       |             | |chk|    | |chk|\ :sup:`2` | |chk|\ :sup:`6` |
+-------------------------------------------+-------------------------+-------+-------------+----------+-----------------+-----------------+
| High-Throughput JPEG 2000 Lossless        | 1.2.840.10008.1.2.4.201 |       |             |          |                 | |chk|\ :sup:`6` |
+-------------------------------------------+-------------------------+-------+-------------+----------+-----------------+-----------------+
| High-Throughput JPEG 2000 (RPCL) Lossless | 1.2.840.10008.1.2.4.202 |       |             |          |                 | |chk|\ :sup:`6` |
+-------------------------------------------+-------------------------+-------+-------------+----------+-----------------+-----------------+
| High-Throughput JPEG 2000                 | 1.2.840.10008.1.2.4.203 |       |             |          |                 | |chk|\ :sup:`6` |
+-------------------------------------------+-------------------------+-------+-------------+----------+-----------------+-----------------+

| :sup:`1` *only with JpegImagePlugin*
| :sup:`2` *only with Jpeg2KImagePlugin*
| :sup:`3` *only if (0028,0100) Bits Allocated = 8*
| :sup:`4` *with the pylibjpeg-rle plugin, 4-5x faster than default*
| :sup:`5` *with the pylibjpeg-libjpeg plugin*
| :sup:`6` *with the pylibjpeg-openjpeg plugin*

Usage
.....
To get uncompressed pixel data as a NumPy :class:`~numpy.ndarray` you have a number of options, depending on your requirements:

* To access the pixel data without modifying the dataset you can use
  the :attr:`Dataset.pixel_array<pydicom.dataset.Dataset.pixel_array>` property, or the
  :func:`~pydicom.pixels.pixel_array` and :func:`~pydicom.pixels.iter_pixels` functions with a
  :class:`~pydicom.dataset.Dataset` instance.
* To access the pixel data while minimizing memory usage you can use the :func:`~pydicom.pixels.pixel_array` or
  :func:`~pydicom.pixels.iter_pixels` functions with the path to the dataset.
* To decompress a dataset in-place you can use :meth:`Dataset.decompress()<pydicom.dataset.Dataset.decompress>` or
  the :func:`~pydicom.pixels.decompress` function.
