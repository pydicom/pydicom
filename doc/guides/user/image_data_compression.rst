.. _guide_compression:

Compressing *Pixel Data*
========================

.. currentmodule:: pydicom

.. rubric:: How to compress Pixel Data

Compressing using pydicom
-------------------------

.. _guide_compression_supported:

Supported Transfer Syntaxes
...........................

*Pixel Data* can be compressed natively using *pydicom* for the following
transfer syntaxes:

.. _np: https://numpy.org/
.. _pylj: https://github.com/pydicom/pylibjpeg
.. _rle: https://github.com/pydicom/pylibjpeg-rle
.. _oj: https://github.com/pydicom/pylibjpeg-openjpeg
.. _gdcm: https://sourceforge.net/projects/gdcm/
.. _jls: https://github.com/pydicom/pyjpegls

+------------------------------------------------+------------------+-----------------------------+
| Transfer Syntax                                | Plugin names     | Dependencies                |
+-----------------------+------------------------+                  |                             |
| Name                  | UID                    |                  |                             |
+=======================+========================+==================+=============================+
| JPEG-LS Lossless      | 1.2.840.10008.1.2.4.80 | pyjpegls         | `numpy <np_>`_,             |
+-----------------------+------------------------+                  | `pyjpegls <jls_>`_          |
| JPEG-LS Near Lossless | 1.2.840.10008.1.2.4.81 |                  |                             |
+-----------------------+------------------------+------------------+-----------------------------+
| JPEG 2000 Lossless    | 1.2.840.10008.1.2.4.90 | pylibjpeg        | `numpy <np_>`_,             |
+-----------------------+------------------------+                  | `pylibjpeg <pylj_>`_,       |
| JPEG 2000             | 1.2.840.10008.1.2.4.91 |                  | `pylibjpeg-openjpeg <oj_>`_ |
+-----------------------+------------------------+------------------+-----------------------------+
| RLE Lossless          | 1.2.840.10008.1.2.5    | pydicom :sup:`1` |                             |
|                       |                        +------------------+-----------------------------+
|                       |                        | pylibjpeg        | `numpy <np_>`_,             |
|                       |                        |                  | `pylibjpeg <pylj_>`_,       |
|                       |                        |                  | `pylibjpeg-rle <rle_>`_     |
|                       |                        +------------------+-----------------------------+
|                       |                        | gdcm             | `gdcm <gdcm_>`_             |
+-----------------------+------------------------+------------------+-----------------------------+

| :sup:`1` *~20x slower than the other plugins*

Each of the supported transfer syntaxes has a corresponding encoding guide to help
you with the specific requirements of the encoding method.

+-------------------------+-----------------------------------------------------+
| Transfer Syntax         | Encoding guide                                      |
+=========================+=====================================================+
| JPEG-LS Lossless        | :doc:`JPEG-LS Encoding</guides/encoding/jpeg_ls>`   |
+-------------------------+                                                     |
| JPEG-LS Near Lossless   |                                                     |
+-------------------------+-----------------------------------------------------+
| JPEG 2000 Lossless      | :doc:`JPEG 2000 Encoding</guides/encoding/jpeg_2k>` |
+-------------------------+                                                     |
| JPEG 2000               |                                                     |
+-------------------------+-----------------------------------------------------+
| RLE Lossless            | :doc:`RLE Encoding</guides/encoding/rle_lossless>`  |
+-------------------------+-----------------------------------------------------+


Compressing with ``Dataset.compress()``
.......................................

The :meth:`Dataset.compress()<pydicom.dataset.Dataset.compress>` method or
:func:`~pydicom.pixels.compress` function can be used to compress an uncompressed
dataset in-place:

.. code-block:: python

    from pydicom import examples
    from pydicom.uid import RLELossless

    ds = examples.ct
    ds.compress(RLELossless)
    ds.save_as("ct_rle_lossless.dcm")

A specific encoding plugin can be used by passing the plugin name via the
`encoding_plugin` argument:

.. code-block:: python

    # Will set `ds.is_little_endian` and `ds.is_implicit_VR` automatically
    ds.compress(RLELossless, encoding_plugin='pylibjpeg')
    ds.save_as("ct_rle_lossless.dcm")


Implicitly changing the compression on an already compressed dataset is not
currently supported, however it can still be done by decompressing
prior to calling :meth:`~pydicom.dataset.Dataset.compress`. In the example
below, a matching :doc:`image data handler<image_data_handlers>` for the
original transfer syntax - *JPEG 2000 Lossless* - is required.

.. code-block:: python

    # Requires a JPEG 2000 compatible image data handler
    ds = examples.jpeg2k
    ds.decompress()
    ds.compress(RLELossless)
    ds.save_as("US1_RLE.dcm")


Compressing using third-party packages
--------------------------------------

If you need to perform pixel data compression using an encoding method not
supported by *pydicom* - such as :dcm:`ISO/IEC 10918-1 JPEG
<part05/sect_8.2.html#sect_8.2.1>` - then you'll need to find a third-party
package or application to do so. Once you've done that you have to follow the
requirements for compressed *Pixel Data* in the DICOM Standard:

* Each frame of pixel data must be encoded separately
* All the encoded frames must then be :func:`encapsulated
  <pydicom.encaps.encapsulate>` using a basic offset table. When the amount
  of encoded data is too large for the basic offset table then the use of
  the :func:`extended offset table <pydicom.encaps.encapsulate_extended>` is
  recommended.
* A dataset with encapsulated pixel data must use explicit VR little endian
  encoding

See the :dcm:`relevant sections of the DICOM Standard<part05/sect_8.2.html>`
for more information.

.. code-block:: python

    from typing import List, Tuple

    from pydicom import examples
    from pydicom.encaps import encapsulate, encapsulate_extended
    from pydicom.uid import JPEGBaseline8Bit

    # Fetch an example dataset
    ds = examples.ct

    # Use third-party package to compress
    # Let's assume it compresses to JPEG Baseline (lossy)
    frames: List[bytes] = third_party_compression_func(...)

    # Set the *Transfer Syntax UID* appropriately
    ds.file_meta.TransferSyntaxUID = JPEGBaseline8Bit

    # Basic encapsulation
    ds.PixelData = encapsulate(frames)

    # Set the element's VR and use an undefined length
    ds["PixelData"].is_undefined_length = True
    ds["PixelData"].VR = "OB" if ds.BitsAllocated <= 8 else "OW"

    # Save!
    ds.save_as("ct_compressed_basic.dcm")

    # Extended encapsulation
    result: Tuple[bytes, bytes, bytes] = encapsulate_extended(frames)
    ds.PixelData = result[0]
    ds.ExtendedOffsetTable = result[1]
    ds.ExtendedOffsetTableLength = result[2]
    ds.save_as("ct_compressed_ext.dcm")
