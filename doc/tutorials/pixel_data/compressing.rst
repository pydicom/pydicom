========================
Compressing *Pixel Data*
========================

This tutorial is about compressing a dataset's *Pixel Data*

* Compressing

It's assumed that you're already familiar with the :doc:`dataset basics
<dataset_basics>`.

.. note::

    *pydicom* currently only supports compression using *RLE Lossless*.


Compressing
===========

.. codeblock:: python

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


.. codeblock:: python

    >>> from pydicom.uid import RLELossless
    >>> ds.compress(RLELossless)
    >>> ds.file_meta.TransferSyntaxUID.name
    "RLE Lossless"
    >>> len(ds.PixelData)
    ...
    >>> ds.PlanarConfiguration
    1
