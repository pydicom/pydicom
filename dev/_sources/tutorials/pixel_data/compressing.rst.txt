====================================================
*Pixel Data* - Part 3: Compression and decompression
====================================================

.. currentmodule:: pydicom


In part 1 of this tutorial you learned how to :doc:`access the pixel data
</tutorials/pixel_data/introduction>` as either the raw :class:`bytes` or a NumPy
:class:`~numpy.ndarray` and in part 2 you learned how to :doc:`create new pixel data
</tutorials/pixel_data/creation>` and add it to a :class:`~pydicom.dataset.Dataset`.
In this final part you'll learn how to compress and decompress datasets containing
*Pixel Data*.

**Prerequisites**

Installing using pip:

.. code-block:: bash

    python -m pip install -U pydicom numpy pylibjpeg[all] pyjpegls

Installing on conda:

.. code-block:: bash

    conda install numpy
    conda install -c conda-forge pydicom
    pip install pylibjpeg[all] pyjpegls


Compression of *Pixel Data*
===========================

*pydicom* can perform dataset compression for the the following transfer syntaxes:

* *JPEG-LS Lossless* and *JPEG-LS Near-lossless* compression with `pyjpegls
  <https://github.com/pydicom/pyjpegls>`_.
* *JPEG 2000 Lossless* and *JPEG 2000* compression with `pylibjpeg
  <https://github.com/pydicom/pylibjpeg>`_ and `pylibjpeg-openjpeg
  <https://github.com/pydicom/pylibjpeg-openjpeg>`_.
* *RLE Lossless*, which doesn't need any additional packages but can be sped up
  if `pylibjpeg <https://github.com/pydicom/pylibjpeg>`_ and `pylibjpeg-rle
  <https://github.com/pydicom/pylibjpeg-rle>`_ are available.

For all other transfer syntaxes it's entirely up to you to compress the *Pixel
Data* in a manner conformant to the :dcm:`requirements of the DICOM Standard
<part05/sect_8.2.html>`:

* Each frame of pixel data must be compressed separately
* All compressed frames must then be :dcm:`encapsulated<part05/sect_A.4.html>`.
* The encapsulated byte stream is used to set the *Pixel Data* value
* When the amount of compressed frame data is very large then it's recommended (but
  not required) that an :dcm:`extended offset table<part03/sect_C.7.6.3.html>`
  also be included in the dataset
* The VR for compressed *Pixel Data* is always **OB**


Compressing a dataset (with *RLE Lossless*)
-------------------------------------------

Compression of an existing uncompressed dataset can be performed by passing the *Transfer
Syntax UID* of the compression method you'd like to use to :meth:`Dataset.compress()
<pydicom.dataset.Dataset.compress>`, or by using the :func:`~pydicom.pixels.compress`
function. We'll be using *RLE Lossless* to start with, which is based on the
`PackBits <https://en.wikipedia.org/wiki/PackBits>`_ compression scheme:

.. code-block:: python

    >>> from pydicom import examples
    >>> from pydicom.uid import RLELossless
    >>> ds = examples.ct
    >>> ds.file_meta.TransferSyntaxUID.is_compressed
    False
    >>> ds.compress(RLELossless)

If you're creating a new dataset, or if you want to update the *Pixel Data* for an
existing dataset, you can pass an :class:`~numpy.ndarray` along with the *Transfer
Syntax UID*::

    import numpy as np
    from pydicom import Dataset
    from pydicom.uid import RLELossless

    ds = Dataset()
    ds.Rows = 320
    ds.Columns = 480
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = ds.BitsStored - 1
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"

    arr = np.ones((ds.Rows, ds.Columns), dtype="uint8")
    ds.compress(RLELossless, arr)

    assert ds.file_meta.TransferSyntaxUID == RLELossless
    assert isinstance(ds.PixelData, bytes)

In both cases this will compress the :class:`~pydicom.dataset.Dataset` in-place:

* The *Pixel Data* will be set with the encapsulated RLE codestream
* The *Transfer Syntax UID* will be set to *RLE Lossless*
* A new *SOP Instance UID* value will be also be generated, but this can
  be disabled by passing ``generate_instance_uid=False``.

When using an :class:`~numpy.ndarray` the :attr:`~numpy.ndarray.shape`,
:class:`~numpy.dtype` and contents of `arr` must match the corresponding
:dcm:`Image Pixel<part03/sect_C.7.6.3.html>` module elements in the dataset,
such as *Rows*, *Columns*, *Samples per Pixel*, etc. If they don't match you'll get an exception:

.. code-block:: python

    >>> from pydicom import examples
    >>> from pydicom.uid import RLELossless
    >>> ds = examples.ct
    >>> arr = np.zeros((ds.Rows, ds.Columns + 1), dtype='<i2')
    >>> ds.compress(RLELossless, arr)
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File ".../pydicom/src/pydicom/dataset.py", line 1957, in compress
        encoded = [f for f in frame_iterator]
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File ".../pydicom/pixels/encoders/base.py", line 678, in iter_encode
        runner.validate()
      File ".../pydicom/pixels/encoders/base.py", line 304, in validate
        self._validate_array()
      File ".../pydicom/pixels/encoders/base.py", line 333, in _validate_array
        raise ValueError(
      ValueError: Mismatch between the expected ndarray shape (128, 128) and the actual shape (128, 129)

When there are multiple plugins available for compressing the given transfer syntax
a :ref:`specific encoding plugin<guide_encoding_plugins>` can be used by passing
the plugin name via the `encoding_plugin` argument:

.. code-block:: python

    >>> ds.compress(RLELossless, encoding_plugin='pylibjpeg')

The RLE compression method is well supported by DICOM applications and can
compress a wide range of images, however it's usually less efficient than the JPEG
family of compression schemes. More information on performing compression with
*RLE Lossless* can be found in the :doc:`RLE encoding guide</guides/encoding/rle_lossless>`.


Compressing with JPEG-LS
------------------------

The JPEG-LS compression scheme is based on `ISO/IEC
14495-1 <https://www.iso.org/standard/22397.html>`_/`ITU T.87
<https://www.itu.int/rec/T-REC-T.87-199806-I>`_. While it can compress 2- to 16-bit
images and uses a lossy quality specification mechanism that's easy to understand,
it's not well suited for lossy compression of signed integers and is generally not
well supported by third-party applications, so keep that in mind if you decide to use it.

**Lossless compression**

Performing lossless compression is straightforward::

    >>> from pydicom import examples
    >>> from pydicom.uid import JPEGLSLossless
    >>> ds = examples.ct
    >>> ds.compress(JPEGLSLossless)

**Lossy compression**

Lossy compression is a bit more complicated, especially when the pixel data
uses signed integers. First up though, we'll use an example with unsigned pixel data.

.. warning::

    *pydicom* makes no recommendations for specifying the image quality for
    lossy encoding methods. Any examples of lossy encoding are for
    **illustration purposes only**.

.. code-block:: python

    >>> from pydicom import examples
    >>> from pydicom.uid import JPEGLSNearLossless
    >>> ds = examples.rgb_color
    >>> ds.PixelRepresentation
    0
    >>> ds.compress(JPEGLSNearLossless, jls_error=3)

The `jls_error` parameter is used to control the loss in image quality, and is
directly related to the JPEG-LS NEAR parameter, which is the absolute allowed error
in (unsigned) pixel data values. A `jls_error` of ``3`` therefore means that all
pixels will be within 3 intensity units of the original.

In our second lossy JPEG-LS example we'll use a dataset with 16-bit signed integers,
which is where the complication starts. The NEAR parameter is defined in terms of
unsigned integers, so when used with signed values there can potentially be
compression errors of up to the maximum bit-depth of the pixel data. To avoid this,
the range of pixel values must be in the `closed interval
<https://en.wikipedia.org/wiki/Interval_(mathematics)>`_::

    [-2**(ds.BitsStored - 1) + jls_error, 2**(ds.BitsStored - 1) - 1 - jls_error]

For example, with a *Bits Stored* of ``8`` and ``jls_error=3`` the pixels must be in the
range [-125, 124].

.. code-block:: python

    >>> from pydicom import examples
    >>> from pydicom.uid import JPEGLSNearLossless
    >>> ds = examples.ct
    >>> ds.PixelRepresentation
    1
    >>> ds.BitsStored
    16
    >>> arr = ds.pixel_array
    >>> arr.min(), arr.max()
    (128, 2191)
    >>> ds.compress(JPEGLSNearLossless, jls_error=3)

In this example the pixel values are within the allowed range so we don't
need to do anything further. If that weren't the case you'd have to rescale
the values or use a different compression method such as JPEG 2000 (recommended).

More information on performing compression with JPEG-LS can be found in
the :doc:`JPEG-LS encoding guide</guides/encoding/jpeg_ls>`.


Compressing with JPEG 2000
--------------------------

The JPEG 2000 compression scheme is based on `ISO/IEC 15444-1
<https://www.iso.org/standard/78321.html>`_/`ITU T.800
<https://www.itu.int/rec/T-REC-T.800-201511-S/en>`_. The format is fairly well supported
by third-party applications and it can compress images with a wide variety of
properties, making it a good choice for compressing datasets.

Two transfer syntaxes are available that use JPEG 2000 compression; *JPEG 2000 Lossless*
and *JPEG 2000*. While the DICOM Standard allows *JPEG 2000* to be either lossy or
lossless, when used for compression in *pydicom* it's always treated as being lossy in
order to simplify its usage.

**Lossless compression**

As with RLE and JPEG-LS, performing lossless compression is straightforward::

    >>> from pydicom import examples
    >>> from pydicom.uid import JPEG2000Lossless
    >>> ds = examples.ct
    >>> ds.compress(JPEG2000Lossless)

For RGB pixel data, JPEG 2000 can perform multiple component transformation
(MCT) during the encoding process, which should improve the compression efficiency.
This can be enabled or disabled by setting an appropriate *Photometric Interpretation*
prior to compression:

* ``"RGB"`` to disable MCT
* ``"YBR_RCT"`` to enable MCT for *JPEG 2000 Lossless*
* ``"YBR_ICT"`` to enable MCT for *JPEG 2000*

.. code-block:: python

    >>> from pydicom import examples
    >>> from pydicom.uid import JPEG2000Lossless
    >>> ds = examples.rgb_color
    >>> ds.PhotometricInterpretation
    "RGB"
    >>> ds.compress(JPEG2000Lossless)  # No MCT applied
    >>> len(ds.PixelData)
    334412
    >>> ds = examples.rgb_color
    >>> ds.PhotometricInterpretation = "YBR_RCT"
    >>> ds.compress(JPEG2000Lossless)  # MCT applied
    >>> len(ds.PixelData)
    152342

**Lossy compression**

Lossy compression with *JPEG 2000* is both more and less complicated then JPEG-LS;
you don't have to worry about the pixel values for signed integers, but specifying
the image quality is less intuitive.

.. warning::

    *pydicom* makes no recommendations for specifying the image quality for
    lossy encoding methods. Any examples of lossy encoding are for
    **illustration purposes only**.

.. code-block:: python

    >>> from pydicom import examples
    >>> from pydicom.uid import JPEG2000
    >>> ds = examples.ct
    >>> ds.compress(JPEG2000, j2k_cr=[5, 2])  # 2 quality layers

With JPEG 2000 image quality is specified with either the `j2k_cr` or `j2k_psnr`
parameters:

* `j2k_cr` is a ``list[float]`` of compression ratios to use for each quality layer
  and is directly related to OpenJPEG's `-r compression ratio
  <https://github.com/uclouvain/openjpeg/wiki/DocJ2KCodec>`_ option. There must
  be at least one layer and the minimum allowable compression ratio is ``1``. When
  using multiple layers they should be ordered in decreasing value from left to right.
* `j2k_psnr` is a ``list[float]`` of the peak signal-to-noise ratios (in dB) to use
  for each quality layer and is directly related to OpenJPEG's `-q quality
  <https://github.com/uclouvain/openjpeg/wiki/DocJ2KCodec>`_ option.
  There must be at least one layer and when using multiple layers they should
  be ordered in increasing value from left to right.

Choosing appropriate quality settings for *JPEG 2000* is far beyond the scope of this
tutorial, but whatever you end up selecting should be thoroughly tested with a
representative sample of expected pixel data.

More information on performing compression with JPEG 2000 can be found in
the :doc:`JPEG 2000 encoding guide</guides/encoding/jpeg_2k>`.


Encapsulating data compressed by third-party packages
.....................................................

You can also use *pydicom* with third-party compression packages to encapsulate
the compressed *Pixel Data*, provided they meet the requirements of the
corresponding transfer syntax. The :func:`~pydicom.encaps.encapsulate` or
:func:`~pydicom.encaps.encapsulate_extended` functions are used to encapsulate the
compressed data.

.. code-block:: python

    from pydicom import examples
    from pydicom.encaps import encapsulate, encapsulate_extended
    from pydicom.uid import JPEGBaseline8Bit

    # Fetch an example dataset
    ds = examples.ct

    # Use third-party package to compress
    # Let's assume it compresses to JPEG Baseline
    frames: list[bytes] = third_party_compression_func(...)

    # Set the *Transfer Syntax UID* appropriately
    ds.file_meta.TransferSyntaxUID = JPEGBaseline8Bit
    # For *Samples per Pixel* 1 the *Photometric Interpretation* is unchanged

    # Basic encapsulation
    ds.PixelData = encapsulate(frames)
    ds["PixelData"].VR = "OB"  # always for encapsulated pixel data
    ds.save_as("ct_compressed_basic.dcm")

    # Extended encapsulation
    result: tuple[bytes, bytes, bytes] = encapsulate_extended(frames)
    ds.PixelData = result[0]
    ds.ExtendedOffsetTable = result[1]
    ds.ExtendedOffsetTableLength = result[2]
    ds.save_as("ct_compressed_ext.dcm")


Decompression of *Pixel Data*
=============================

Datasets with a compressed *Transfer Syntax UID* can be decompressed with
:meth:`Dataset.decompress()<pydicom.dataset.Dataset.decompress>` or the
:func:`~pydicom.pixels.decompress` function.

.. code-block:: python

    >>> from pydicom import examples
    >>> ds = examples.jpeg2k
    >>> ds.decompress()

This will decompress the :class:`~pydicom.dataset.Dataset` in-place:

* The *Pixel Data* will be set using the uncompressed pixel data.
* The *Transfer Syntax UID* will be changed to *Explicit VR Little Endian*.
* The :dcm:`Image Pixel<part03/sect_C.7.6.3.html>` module elements will be updated
  as required to match the uncompressed pixel data.
* A new *SOP Instance UID* value will be also be generated, but this can
  be disabled by passing ``generate_instance_uid=False``.

Dataset decompression uses the same backend as accessing compressed *Pixel Data*,
so the same :doc:`customization options</guides/decoding/decoder_options>` of the decoding
process apply. For example, to use a :doc:`specific plugin</guides/plugin_table>`
you can pass its name via the `decoding_plugin` argument::

    >>> from pydicom import examples
    >>> ds = examples.jpeg2k
    >>> ds.decompress(decoding_plugin="pylibjpeg")

If the dataset's *Pixel Data* is in the YCbCr color space it will also be converted
to RGB by default. This can be disabled by passing ``as_rgb=False``::

    import numpy as np

    from pydicom import examples
    from pydicom.pixels import convert_color_space, pixel_array
    from pydicom.uid import JPEG2000Lossless

    # Original dataset in RGB
    ds = examples.rgb_color
    assert ds.PhotometricInterpretation == "RGB"

    # Convert to YCbCr and compress
    ybr = convert_color_space(ds.pixel_array, "RGB", "YBR_FULL")
    ds.PhotometricInterpretation = "YBR_FULL"
    ds.compress(JPEG2000Lossless, ybr)
    assert ds.PhotometricInterpretation == "YBR_FULL"

    # RGB reference - needed because converting RGB -> YBR -> RGB is lossy
    rgb = convert_color_space(ybr, "YBR_FULL", "RGB")

    # Decompress with conversion to RGB
    ds.decompress()
    assert ds.PhotometricInterpretation == "RGB"
    assert np.array_equal(rgb, pixel_array(ds, raw=True))

    # Decompress without conversion to RGB
    ds.PhotometricInterpretation = "YBR_FULL"
    ds.compress(JPEG2000Lossless, ybr)

    ds.decompress(as_rgb=False)
    assert ds.PhotometricInterpretation == "YBR_FULL"
    assert np.array_equal(ybr, pixel_array(ds, raw=True))

Conclusion
==========

In part 3 of this tutorial you've learned how to use *pydicom* to compress and decompress
datasets and how to encapsulate pixel data that has been compressed by third-party
packages. Having made it to the end of the pixel data tutorial you should now be
comfortable using *pydicom* to perform pixel data related tasks.
