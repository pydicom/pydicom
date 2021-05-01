.. _guide_compression:

Compression of *Pixel Data*
===========================

.. currentmodule:: pydicom

.. rubric:: How to compress Pixel Data


Supported Transfer Syntaxes
---------------------------

.. _np: http://numpy.org/
.. _pylj: https://github.com/pydicom/pylibjpeg
.. _rle: https://github.com/pydicom/pylibjpeg-rle

+------------------------------------+--------------------+------------------------------------------------------------+
| Transfer Syntax                    | Plugins            | Dependencies                                               |
+--------------+---------------------+                    |                                                            |
| Name         | UID                 |                    |                                                            |
+==============+=====================+====================+============================================================+
| RLE Lossless | 1.2.840.10008.1.2.5 | pydicom            | `numpy<np_>`_                                              |
|              |                     | pylibjpeg :sup:`1` | `numpy<np_>`_, `pylibjpeg<pylj_>`_, `pylibjpeg-rle<rle_>`_ |
+--------------+---------------------+--------------------+------------------------------------------------------------+

| :sup:`1` *~25x faster than the pydicom plugin*

Usage
-----

Compress an uncompressed dataset in-place:

.. codeblock::python

    from pydicom.data import get_testdata_file
    from pydicom.uid import RLELossless

    ds = get_testdata_file("CT_small.dcm", read=True)
    ds.compress(RLELossless)
    ds.save_as("CT_small_rle.dcm")


Compress a compressed dataset in-place. Because this requires the *Pixel Data*
be uncompressed, a matching :doc:`image data handler<image_data_handlers>` is
required.

.. codeblock::python

    # Requires a JPEG 2000 compatible image data handler
    ds = get_testdata_file("US1_J2KR.dcm", read=True)
    ds.compress(RLELossless)
    ds.save_as("US1_RLE.dcm")
