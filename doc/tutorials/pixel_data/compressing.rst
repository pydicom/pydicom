========================
Compressing *Pixel Data*
========================

.. currentmodule:: pydicom

This tutorial is about compressing a dataset's *Pixel Data* and covers

* An introduction to compressed DICOM datasets
* Using data compressed by third-party packages
* Compressing data using *pydicom*

It's assumed that you're already familiar with the :doc:`dataset basics
<../dataset_basics>`.


Introduction
------------



Compressing using third-party packages
--------------------------------------

Because *pydicom* currently offers limited support for compressing *Pixel Data*
you'll have to rely on third-party packages to perform the actual compression.
*pydicom* can then be used to take that compressed data and add it to the
dataset.

The requirements for compressed *Pixel Data* in the DICOM Standard are:

* Each frame of pixel data must be encoded separately
* All the encoded frames must then be encapsulated, either using :func:`basic
  <pydicom.encaps.encapsulate>` or :func:`extended encapsulation
  <pydicom.encaps.encapsulate_extended>`

See the :dcm:`relevant sections of the DICOM Standard<part05/sect_8.2.html>`
for more information.

.. code-block:: python

    from pydicom import dcmread
    from pydicom.data import get_testdata_file
    from pydicom.encaps import encapsulate, encapsulate_extended
    from pydicom.uid import JPEG2000

    path = get_testdata_file("CT_small.dcm")
    ds = dcmread(path)

    # Use third-party package to compress
    # Let's assume it compresses to JPEG 2000 (lossless)
    frames: List[bytes] = third_party_compression_func(...)

    # Set the *Transfer Syntax UID* appropriately
    ds.file_meta.TransferSyntaxUID = JPEG2000

    # Basic encapsulation
    ds.PixelData = encapsulate(frames)
    ds.save_as("CT_small_compressed_basic.dcm")

    # Extended encapsulation
    result: Tuple(bytes, bytes, bytes) = encapsulate_extended(frames)
    ds.PixelData = result[0]
    ds.ExtendedOffsetTable = result[1]
    ds.ExtendedOffsetTableLength = result[2]
    ds.save_as("CT_small_compressed_ext.dcm")


Compressing using pydicom
-------------------------

*Pixel Data* can be compressed natively using *pydicom* for the following
transfer syntaxes:

.. _np: http://numpy.org/
.. _pylj: https://github.com/pydicom/pylibjpeg
.. _rle: https://github.com/pydicom/pylibjpeg-rle

+------------------------------------+--------------------+-------------------------+
| Transfer Syntax                    | Plugin names       | Dependencies            |
+--------------+---------------------+                    |                         |
| Name         | UID                 |                    |                         |
+==============+=====================+====================+=========================+
| RLE Lossless | 1.2.840.10008.1.2.5 | pydicom            | `numpy <np_>`_          |
+              +                     +--------------------+-------------------------+
|              |                     | pylibjpeg :sup:`1` | `numpy <np_>`_,         |
|              |                     |                    | `pylibjpeg <pylj_>`_,   |
|              |                     |                    | `pylibjpeg-rle <rle_>`_ |
+--------------+---------------------+--------------------+-------------------------+

| :sup:`1` *~25x faster than the pydicom plugin*

Usage
.....

Use :func:`Dataset.compress()<pydicom.dataset.Dataset.compress>` to compress
an uncompressed dataset in-place:

.. code-block:: python

    from pydicom.data import get_testdata_file
    from pydicom.uid import RLELossless

    ds = get_testdata_file("CT_small.dcm", read=True)
    ds.compress(RLELossless)
    ds.save_as("CT_small_rle.dcm")

A specific encoding plugin can be used by passing the plugin name via the
`encoding_plugin` argument:

.. code-block:: python

    ds.compress(RLELossless, encoding_plugin='pylibjpeg')
    ds.save_as("CT_small_rle.dcm")


Change the compression on an already compressed dataset. Because this requires
that the *Pixel Data* be uncompressed, a matching
:doc:`image data handler</old/image_data_handlers>` for the initial compression
method is required.

.. code-block:: python

    # Requires a JPEG 2000 compatible image data handler
    ds = get_testdata_file("US1_J2KR.dcm", read=True)
    ds.compress(RLELossless)
    ds.save_as("US1_RLE.dcm")


Compressing
===========

.. code-block:: python

    >>> from pydicom import dcmread
    >>> from pydicom.data import get_testdata_file
    >>> path = get_testdata_file("CT_small.dcm")
    >>> ds = dcmread(path)
    >>> ds.file_meta.TransferSyntaxUID.name
    'Explicit VR Little Endian'
    >>> len(ds.PixelData)
    32768
    >>> 'PlanarConfiguration' in ds
    False


.. code-block:: python

    >>> from pydicom.uid import RLELossless
    >>> ds.compress(RLELossless)
    >>> ds.file_meta.TransferSyntaxUID.name
    "RLE Lossless"
    >>> len(ds.PixelData)
    ...
    >>> ds.PlanarConfiguration
    1
