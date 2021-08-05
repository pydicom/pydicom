========================
Compressing *Pixel Data*
========================

.. currentmodule:: pydicom

This tutorial is about compressing a dataset's *Pixel Data* and covers

* An introduction to compression
* Using data compressed by third-party packages
* Compressing data using *pydicom*

It's assumed that you're already familiar with the :doc:`dataset basics
<../dataset_basics>`.


**Prerequisites**

This tutorial uses packages in addition to *pydicom* that are not installed
by default, but are required for *RLE Lossless* compression of *Pixel Data*.
For more information on what packages are available to compress a given
transfer syntax see the :ref:`image compression guide
<guide_compression_supported>`.

Installing using pip:

.. code-block:: bash

    python -m pip install -U pydicom>=2.2 numpy pylibjpeg

Installing on conda:

.. code-block:: bash

    conda install numpy
    conda install -c conda-forge pydicom>=2.2
    pip install pylibjpeg


Introduction
------------

DICOM conformant applications are usually required to support the
*Little Endian Implicit VR* transfer syntax, which is an uncompressed (native)
transfer syntax. This means that datasets using *Little Endian Implicit VR* have
no compression of their *Pixel Data*. So if applications are required to
support it, why do we need *Pixel Data* compression?

The answer, of course, is file size. A *CT Image* instance
typically consists of 1024 x 1024 16-bit pixels, and a CT scan may have
hundreds of instances, giving a total series size of hundreds of megabytes.
When you factor in other SOP Classes such as *Whole Slide Microscopy* which
uses even larger full color images, the size of the uncompressed *Pixel Data*
may get into the gigabyte territory. Being able to compress these images can
result in significantly reduced file sizes.

However, with the exception of *RLE Lossless*, *pydicom* doesn't currently
offer any native support for compression of *Pixel Data*. This means that it's
entirely up to you to compress the *Pixel Data* in a manner conformant to
the :dcm:`requirements of the DICOM Standard<part05/sect_8.2.html>`.

.. note::

    We recommend that you use `GDCM
    <http://gdcm.sourceforge.net/wiki/index.php/Main_Page>`_ for *Pixel Data*
    compression as it provides support for all the most commonly used
    *Transfer Syntaxes* and being another DICOM library, should do so in
    a conformant manner.

The general requirements for compressed *Pixel Data* in the DICOM Standard are:

* Each frame of pixel data must be encoded separately
* All the encoded frames must then be :dcm:`encapsulated
  <part05/sect_A.4.html>`.
* When the amount of encoded frame data is very large
  then it's recommended (but not required) that an :dcm:`extended offset table
  <part03/sect_C.7.6.3.html>` also be included with the dataset

Each *Transfer Syntax* has it's own specific requirements, found
in :dcm:`Part 5 of the DICOM Standard<part05/PS3.5.html>`.


Encapsulating data compressed by third-party packages
-----------------------------------------------------

Once you've used a third-party package to compress the *Pixel Data*,
*pydicom* can be used to encapsulate and add it to the
dataset, with either the :func:`~pydicom.encaps.encapsulate` or
:func:`~pydicom.encaps.encapsulate_extended` functions:

.. code-block:: python

    from typing import List, Tuple

    from pydicom import dcmread
    from pydicom.data import get_testdata_file
    from pydicom.encaps import encapsulate, encapsulate_extended
    from pydicom.uid import JPEG2000Lossless

    path = get_testdata_file("CT_small.dcm")
    ds = dcmread(path)

    # Use third-party package to compress
    # Let's assume it compresses to JPEG 2000 (lossless)
    frames: List[bytes] = third_party_compression_func(...)

    # Set the *Transfer Syntax UID* appropriately
    ds.file_meta.TransferSyntaxUID = JPEG2000Lossless
    # For *Samples per Pixel* 1 the *Photometric Interpretation* is unchanged

    # Basic encapsulation
    ds.PixelData = encapsulate(frames)
    ds.save_as("CT_small_compressed_basic.dcm")

    # Extended encapsulation
    result: Tuple[bytes, bytes, bytes] = encapsulate_extended(frames)
    ds.PixelData = result[0]
    ds.ExtendedOffsetTable = result[1]
    ds.ExtendedOffsetTableLength = result[2]
    ds.save_as("CT_small_compressed_ext.dcm")


Compressing using pydicom
-------------------------

Currently, only the *RLE Lossless* transfer syntax is supported for
compressing *Pixel Data* natively using *pydicom*. The easiest method is to
pass the UID for *RLE Lossless* to :func:`Dataset.compress()
<pydicom.dataset.Dataset.compress>`:

.. code-block:: python

    >>> from pydicom import dcmread
    >>> from pydicom.data import get_testdata_file
    >>> from pydicom.uid import RLELossless
    >>> path = get_testdata_file("CT_small.dcm")
    >>> ds = dcmread(path)
    >>> ds.compress(RLELossless)
    >>> ds.save_as("CT_small_rle.dcm")

This will compress the existing *Pixel Data* and update the *Transfer Syntax
UID* before saving the dataset to file as  ``CT_small_rle.dcm``.

If you're creating a dataset from scratch you can instead pass a
:class:`~numpy.ndarray` to be compressed and used as the *Pixel Data*:

.. code-block:: python

    >>> import numpy as np
    >>> arr = np.zeros((ds.Rows, ds.Columns), dtype='<i2')
    >>> ds.compress(RLELossless, arr)

Note that the :attr:`~numpy.ndarray.shape`, :class:`~numpy.dtype` and contents
of `arr` must match the corresponding elements in the dataset, such as *Rows*,
*Columns*, *Samples per Pixel*, etc. If they don't match you'll get an
exception:

.. code-block:: python

    >>> arr = np.zeros((ds.Rows, ds.Columns + 1), dtype='<i2')
    >>> ds.compress(RLELossless, arr)
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File ".../pydicom/dataset.py", line 1697, in compress
        encoded = [f for f in frame_iterator]
      File ".../pydicom/dataset.py", line 1697, in <listcomp>
        encoded = [f for f in frame_iterator]
      File ".../pydicom/encoders/base.py", line 382, in iter_encode
        yield self._encode_array(src, idx, encoding_plugin, **kwargs)
      File ".../pydicom/encoders/base.py", line 209, in _encode_array
        src = self._preprocess(arr, **kwargs)
      File ".../pydicom/encoders/base.py", line 533, in _preprocess
        raise ValueError(
    ValueError: Unable to encode as the shape of the ndarray (128, 129) doesn't match the values for the rows, columns and samples per pixel

A specific encoding plugin can be used by passing the plugin name via the
`encoding_plugin` argument:

.. code-block:: python

    >>> ds.compress(RLELossless, encoding_plugin='pylibjpeg')

The plugins available for each encoder are listed in the
:mod:`API reference<pydicom.encoders>` for the encoder type.

Implicitly changing the compression on an already compressed dataset is not
currently supported, however it can still be done explicitly by decompressing
prior to calling :meth:`~pydicom.dataset.Dataset.compress`. In the example
below, a matching :doc:`image data handler</old/image_data_handlers>` for the
original transfer syntax - *JPEG 2000 Lossless* - is required.

.. code-block:: python

    >>> ds = get_testdata_file("US1_J2KR.dcm", read=True)
    >>> ds.SamplesPerPixel
    3
    >>> ds.PhotometricInterpretation
    'YBR_RCT'
    >>> ds.PhotometricInterpretation = "RGB"
    >>> ds.compress(RLELossless)

Note that in this case we also needed to change the *Photometric
Interpretation*, from the original value of ``'YBR_RCT'`` when the dataset
was using *JPEG 2000 Lossless* compression to ``'RGB'``, which for this dataset
will be the correct value after recompressing using *RLE Lossless*.
