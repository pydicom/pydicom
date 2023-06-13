.. _guide_compressed:

Handling of compressed pixel data
---------------------------------

.. currentmodule:: pydicom

.. rubric:: How to get compressed pixel data

.. |chk|   unicode:: U+02713 .. CHECK MARK


Preconditions
.............
To be able to decompress compressed DICOM pixel data, you need to install
one or more packages that are able to handle the format the data
is encoded in.

The following packages can be used with *pydicom*:

* `GDCM <http://gdcm.sourceforge.net/>`_ - this is the package that supports
  most compressed formats
* `Pillow <http://pillow.readthedocs.io/en/latest/>`_, ideally with
  ``jpeg`` and ``jpeg2000`` plugins
* `jpeg_ls <https://github.com/pydicom/pyjpegls>`_
* :gh:`pylibjpeg <pylibjpeg>`, with the ``-libjpeg``, ``-openjpeg`` and
  ``-rle`` plugins

Note that you always need the `NumPy <http://numpy.org/>`_ package to be able
to handle pixel data.

.. caution:: We rely on the data handling capacity of the mentioned
   packages and cannot guarantee the correctness of the generated uncompressed
   pixel data. Be sure to verify the correctness of the output using other
   means before you use them for medical purposes.

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

+-------------------------------------------------------------+-------+-------------+----------+-----------------+-----------------+
| Transfer Syntax                                             | NumPy | | NumPy +   | | NumPy +| | NumPy +       | | NumPy +       |
+------------------------------------+------------------------+       | | JPEG-LS   | | GDCM   | | Pillow        | | pylibjpeg     |
| Name                               | UID                    |       |             |          |                 |                 |
+====================================+========================+=======+=============+==========+=================+=================+
| Explicit VR Little Endian          | 1.2.840.10008.1.2.1    | |chk| | |chk|       | |chk|    |     |chk|       | |chk|           |
+------------------------------------+------------------------+-------+-------------+----------+-----------------+-----------------+
| Implicit VR Little Endian          | 1.2.840.10008.1.2      | |chk| | |chk|       | |chk|    |     |chk|       | |chk|           |
+------------------------------------+------------------------+-------+-------------+----------+-----------------+-----------------+
| Explicit VR Big Endian             | 1.2.840.10008.1.2.2    | |chk| | |chk|       | |chk|    |     |chk|       | |chk|           |
+------------------------------------+------------------------+-------+-------------+----------+-----------------+-----------------+
| Deflated Explicit VR Little Endian | 1.2.840.10008.1.2.1.99 | |chk| | |chk|       | |chk|    |     |chk|       | |chk|           |
+------------------------------------+------------------------+-------+-------------+----------+-----------------+-----------------+
| RLE Lossless                       | 1.2.840.10008.1.2.5    | |chk| | |chk|       | |chk|    |     |chk|       | |chk|\ :sup:`4` |
+------------------------------------+------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG Baseline (Process 1)          | 1.2.840.10008.1.2.4.50 |       |             | |chk|    | |chk|\ :sup:`1` | |chk|\ :sup:`5` |
+------------------------------------+------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG Extended (Process 2 and 4)    | 1.2.840.10008.1.2.4.51 |       |             | |chk|    | |chk|\          | |chk|\ :sup:`5` |
|                                    |                        |       |             |          | :sup:`1,3`      |                 |
+------------------------------------+------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG Lossless (Process 14)         | 1.2.840.10008.1.2.4.57 |       |             | |chk|    |                 | |chk|\ :sup:`5` |
+------------------------------------+------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG Lossless (Process 14, SV1)    | 1.2.840.10008.1.2.4.70 |       |             | |chk|    |                 | |chk|\ :sup:`5` |
+------------------------------------+------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG LS Lossless                   | 1.2.840.10008.1.2.4.80 |       | |chk|       | |chk|    |                 | |chk|\ :sup:`5` |
+------------------------------------+------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG LS Lossy                      | 1.2.840.10008.1.2.4.81 |       | |chk|       | |chk|    |                 | |chk|\ :sup:`5` |
+------------------------------------+------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG2000 Lossless                  | 1.2.840.10008.1.2.4.90 |       |             | |chk|    | |chk|\ :sup:`2` | |chk|\ :sup:`6` |
+------------------------------------+------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG2000                           | 1.2.840.10008.1.2.4.91 |       |             | |chk|    | |chk|\ :sup:`2` | |chk|\ :sup:`6` |
+------------------------------------+------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG2000 Multi-component Lossless  | 1.2.840.10008.1.2.4.92 |       |             |          |                 |                 |
+------------------------------------+------------------------+-------+-------------+----------+-----------------+-----------------+
| JPEG2000 Multi-component           | 1.2.840.10008.1.2.4.93 |       |             |          |                 |                 |
+------------------------------------+------------------------+-------+-------------+----------+-----------------+-----------------+

| :sup:`1` *only with JpegImagePlugin*
| :sup:`2` *only with Jpeg2KImagePlugin*
| :sup:`3` *only if (0028,0100) Bits Allocated = 8*
| :sup:`4` *with the pylibjpeg-rle plugin and using the* :meth:`~pydicom.dataset.Dataset.decompress` *method, 4-5x faster than default*
| :sup:`5` *with the pylibjpeg-libjpeg plugin*
| :sup:`6` *with the pylibjpeg-openjpeg plugin*

Usage
.....
To get uncompressed pixel data you have two options:

* use :meth:`~pydicom.dataset.Dataset.decompress` on the dataset to convert
  it in-place and work with the pixel data as described before
* get an uncompressed copy of the pixel data as a NumPy ``ndarray`` using
  :attr:`Dataset.pixel_array<pydicom.dataset.Dataset.pixel_array>` without
  changing the original dataset

.. note:: Using :meth:`~pydicom.dataset.Dataset.decompress` adapts the
   transfer syntax of the data set, but not the *Photometric Interpretation*.
   The *Photometric Interpretation* may not match the pixel data, depending on
   the used decompression handler.
