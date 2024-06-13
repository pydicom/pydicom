=================================================
*Pixel Data* - Part 1: Introduction and accessing
=================================================

.. currentmodule:: pydicom

This is part 1 of the tutorial on using *pydicom* with DICOM *Pixel Data*. It covers:

* An introduction to DICOM pixel data
* Converting pixel data to a NumPy :class:`~numpy.ndarray`
* Customizing the conversion process

It's assumed that you're already familiar with the :doc:`dataset basics
<../dataset_basics>`.


**Prerequisites**

Installing using pip:

.. code-block:: bash

    python -m pip install -U pydicom numpy matplotlib pylibjpeg[all]

Installing on conda:

.. code-block:: bash

    conda install numpy matplotlib
    conda install -c conda-forge pydicom
    pip install pylibjpeg[all]


Introduction
------------

Many DICOM SOP classes contain bulk pixel data, which typically represents medical
imagery or 2D slices of a 3D volume. This data is most commonly found in
the *Pixel Data* element, however it may be in *Float Pixel Data* or *Double Float
Pixel Data* instead, depending on the SOP class. The table below lists these
possible pixel data containing elements, although it's important to note that
only one may be present in any given dataset.

+-------------+---------------------+----------------------+------------------+
| Tag         | Description         | Keyword              | VR               |
+=============+=====================+======================+==================+
| (7FE0,0008) | *Float Pixel Data*  | FloatPixelData       | **OF**           |
+-------------+---------------------+----------------------+------------------+
| (7FE0,0009) | *Double Pixel Data* | DoubleFloatPixelData | **OD**           |
+-------------+---------------------+----------------------+------------------+
| (7FE0,0010) | *Pixel Data*        | PixelData            | **OB** or **OW** |
+-------------+---------------------+----------------------+------------------+

All three elements use **O*** :dcm:`VRs<part05/sect_6.2.html>` (such as **OB** and
**OD**), which in *pydicom* are :doc:`stored as</guides/element_value_types>`
(and should be set using) :class:`bytes`::

    >>> from pydicom import examples
    >>> ds = examples.jpeg2k
    >>> ds.group_dataset(0x7FE0)
    (7FE0,0010) Pixel Data                          OB: Array of 152326 elements
    >>> ds.PixelData[:50] # doctest: +ELLIPSIS
    b'\xfe\xff\x00\xe0\x00\x00\x00\x00\xfe\xff\x00\xe0\x00\x00\x01\x00\xffO\xffQ...

If the dataset's been written using the :dcm:`DICOM File Format<part10/chapter_7.html>`
it should have a *Transfer Syntax UID* element which describes how the pixel data
is encoded and whether it's undergone compression::

    >>> tsyntax = ds.file_meta.TransferSyntaxUID
    >>> tsyntax.name
    'JPEG 2000 Image Compression (Lossless Only)'
    >>> tsyntax.is_compressed
    True

In the example above the *Transfer Syntax UID* indicates that the pixel data has
been compressed using the :dcm:`JPEG 2000 <part05/sect_A.4.4.html>` compression method.
Other things to keep in mind with compressed transfer syntaxes are:

* Only datasets that use the *Pixel Data* element may be compressed
* Each frame of pixel data is compressed separately
* The compressed frames are then :func:`encapsulated<pydicom.encaps.encapsulate>`
  and the encapsulated data used to set the *Pixel Data* value

To access the encapsulated frames you can use :func:`~pydicom.encaps.get_frame`
or the :func:`~pydicom.encaps.generate_frames` iterator::

    >>> from pydicom.encaps import get_frame
    >>> frame = get_frame(ds.PixelData, 0, number_of_frames=1)
    >>> print(len(frame))
    152294

The next example uses an uncompressed *Transfer Syntax UID*::

    >>> ds = examples.ct
    >>> tsyntax = ds.file_meta.TransferSyntaxUID
    >>> tsyntax.name
    'Explicit VR Little Endian'
    >>> tsyntax.is_compressed
    False

The pixel data in this dataset uses `little-endian byte ordering
<https://en.wikipedia.org/wiki/Endianness>`_ and is uncompressed. Uncompressed
transfer syntaxes never use encapsulation and may use any one of the
three pixel data elements, although *Pixel Data* is the most common.

A dataset with pixel data should always contain group ``0x0028`` :dcm:`Image Pixel
<part03/sect_C.7.6.3.html>` module elements, which are needed to properly interpret
the encoded pixel data byte stream::

    >>> ds.group_dataset(0x0028)
    (0028,0002) Samples per Pixel                   US: 1
    (0028,0004) Photometric Interpretation          CS: 'MONOCHROME2'
    (0028,0010) Rows                                US: 128
    (0028,0011) Columns                             US: 128
    (0028,0030) Pixel Spacing                       DS: [0.661468, 0.661468]
    (0028,0100) Bits Allocated                      US: 16
    (0028,0101) Bits Stored                         US: 16
    (0028,0102) High Bit                            US: 15
    (0028,0103) Pixel Representation                US: 1
    ...

An explanation of what these elements represent can be found in the
:doc:`glossary</guides/glossary>`, but briefly, the above indicates that this
dataset contains a single grayscale image with dimensions 128 x 128 and that each
pixel should be interpreted as a 2-byte signed integer.


Converting to an :class:`~numpy.ndarray`
----------------------------------------

Properly interpreting all the possible variations of a dataset's pixel data requires
a lot of specific domain knowledge, not just of DICOM but also the various
JPEG compression schemes. For this reason *pydicom* offers a number of methods
for converting the pixel data to a NumPy :class:`~numpy.ndarray`, the most high-level
of which are the :func:`~pydicom.pixels.pixel_array` and :func:`~pydicom.pixels.iter_pixels`
functions::

    import matplotlib.pyplot as plt

    from pydicom import examples
    from pydicom.pixels import pixel_array

    # Get an example dataset as a FileDataset instance
    ds = examples.ct

    # Convert the pixel data to an ndarray
    arr = pixel_array(ds)
    assert arr.shape == (128, 128)
    assert str(arr.dtype) == "int16"

    # Display the pixel data using matplotlib
    plt.imshow(arr, cmap="gray")
    plt.show()

This will convert the entire pixel data to an :class:`~numpy.ndarray` before using
`matplotlib <https://matplotlib.org/>`_ to display it. If the dataset has multiple
frames but you're only interested in a particular one, then you can use the `index` parameter
to return it::

    from pydicom import examples
    from pydicom.pixels import pixel_array

    # Get an example multi-frame dataset
    ds = examples.rt_dose
    assert ds.NumberOfFrames == '15'

    # Return all frames
    arr = pixel_array(ds)
    assert arr.shape == (15, 10, 10)

    # Return only the first frame
    arr = pixel_array(ds, index=0)
    assert arr.shape == (10, 10)

:func:`~pydicom.pixels.iter_pixels` can be used to iterate through either all
the available frames or those specified by the `indices` parameter::

    from pydicom import examples
    from pydicom.pixels import iter_pixels

    # Iterate through all frames
    for arr in iter_pixels(examples.rt_dose):
        assert arr.shape == (10, 10)

    # Iterate through the first 3 even frames
    for arr in iter_pixels(examples.rt_dose, indices=[1, 3, 5]):
        assert arr.shape == (10, 10)

Controlling decoding
....................

The default decoding options for :func:`~pydicom.pixels.pixel_array` and
:func:`~pydicom.pixels.iter_pixels` have been chosen to return the pixel data in
its most commonly used form; for multi-sample data this means RGB is returned
by default. Datasets with pixel data in `YCbCr <https://en.wikipedia.org/wiki/YCbCr>`_
color space are converted using :func:`~pydicom.pixels.convert_color_space` prior
to the array being returned. If you'd like to skip this conversion and return the
data as found in the dataset you can pass ``raw=True``::

    import matplotlib.pyplot as plt

    from pydicom import examples
    from pydicom.pixels import pixel_array

    ds = examples.ybr_color
    assert ds.PhotometricInterpretation == "YBR_FULL_422"

    ybr = pixel_array(ds, index=0, raw=True)
    rgb = pixel_array(ds, index=0)

    fig, (im1, im2) = plt.subplots(1, 2)
    im1.imshow(ybr)
    im1.set_title("Original (in YCbCr)")
    im2.imshow(rgb)
    im2.set_title("Converted (in RGB)")
    plt.show()

Further customization of the returned :class:`~numpy.ndarray` is possible by
passing one or more :doc:`decoding options</guides/decoding/decoder_options>` to
:func:`~pydicom.pixels.pixel_array` and :func:`~pydicom.pixels.iter_pixels`.


Compressed transfer syntaxes
............................

When converting datasets with a compressed transfer syntax, one or more additional
packages are needed to perform the actual decompression (via their corresponding decoding
plugins). By default, all available plugins will be tried and the first successful
one will have its results returned::

    from pydicom import examples
    from pydicom.pixels import pixel_array

    ds = examples.jpeg2k

    # Returns the results from the first successful decoding plugin
    arr = pixel_array(ds)

If no plugins are available for the given transfer syntax due to missing dependencies
you'll get an exception:

.. code-block:: pytb

    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File ".../pydicom/pixels/utils.py", line 1386, in pixel_array
        return decoder.as_array(
               ^^^^^^^^^^^^^^^^^
      File ".../pydicom/pixels/decoders/base.py", line 971, in as_array
        self._validate_plugins(decoding_plugin),
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File ".../pydicom/pixels/common.py", line 249, in _validate_plugins
        raise RuntimeError(
    RuntimeError: Unable to decompress 'JPEG 2000 Image Compression (Lossless Only)' pixel data because all plugins are missing dependencies:
    	gdcm - requires gdcm>=3.0.10
    	pylibjpeg - requires pylibjpeg>=2.0 and pylibjpeg-openjpeg>=2.0
    	pillow - requires numpy and pillow>=10.0

While the resulting :class:`~numpy.ndarray` for lossless compression methods should
be identical no matter which plugin is used, there may be slight differences for lossy
compression methods. To ensure consistency you can use the `decoding_plugin` argument
to use the specified :doc:`decompression plugin</guides/plugin_table>`::

    from pydicom import examples
    from pydicom.pixels import pixel_array

    ds = examples.jpeg2k

    # Return the results from the 'pylibjpeg' decoding plugin
    arr = pixel_array(ds, decoding_plugin="pylibjpeg")

And of course if the specified plugin isn't available you'll get an exception::

    >>> from pydicom import examples
    >>> from pydicom.pixels import pixel_array
    >>> pixel_array(examples.jpeg2k, decoding_plugin="pillow")
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File ".../pydicom/pixels/utils.py", line 1386, in pixel_array
        return decoder.as_array(
               ^^^^^^^^^^^^^^^^^
      File ".../pydicom/pixels/decoders/base.py", line 971, in as_array
        self._validate_plugins(decoding_plugin),
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File ".../pydicom/pixels/common.py", line 230, in _validate_plugins
        raise RuntimeError(
    RuntimeError: Unable to decompress 'JPEG 2000 Image Compression (Lossless Only)' pixel data because the specified plugin is missing dependencies:
        pillow - requires numpy and pillow>=10.0


Minimizing memory usage
.......................

Sometimes a dataset's pixel data may be very large due to it having a large number
of frames and you'd like to avoid having the entire thing read into memory.
By passing the path to the dataset (as :class:`str` or :class:`pathlib.Path`) to
:func:`~pydicom.pixels.pixel_array` only the :dcm:`Image Pixel
<part03/sect_C.7.6.3.html>` module elements and the minimum amount of required
pixel data will be loaded::

    from pydicom import examples
    from pydicom.pixels import pixel_array

    # Get the path to the 'examples.rt_dose' dataset
    path = examples.get_path("rt_dose")

    # Return the first frame of the pixel data
    arr = pixel_array(path, index=0)

The same is true for :func:`~pydicom.pixels.iter_pixels`::

    import matplotlib.pyplot as plt
    import numpy as np

    from pydicom import examples
    from pydicom.pixels import iter_pixels

    # Get the path to the 'examples.ybr_color' dataset
    path = examples.get_path("ybr_color")

    # Create an empty ndarray and use it to initialize the display
    im = plt.imshow(np.zeros((ds.Rows, ds.Columns), dtype="u1"))

    # Iterate through the frames and update the display
    for frame in iter_pixels(path):
        im.set_data(frame)
        plt.pause(0.033)

If you're supplying a path to :func:`~pydicom.pixels.pixel_array`
or :func:`~pydicom.pixels.iter_pixels` and you need access to the :dcm:`Image Pixel
<part03/sect_C.7.6.3.html>` elements to perform image processing operations on
the array (such as :func:`rescale<pydicom.pixels.apply_rescale>` or
:func:`windowing<pydicom.pixels.apply_windowing>`) you can access them by passing
an empty :class:`~pydicom.dataset.Dataset` instance via the `ds_out` argument,
or alternatively by using :func:`~pydicom.filereader.dcmread` with
``stop_before_pixels=True``::

    from pydicom import Dataset, examples
    from pydicom.pixels import pixel_array, apply_rescale

    # Get the path to the 'examples.ct' dataset
    path = examples.get_path("ct")

    ds = Dataset()
    arr = pixel_array(path, ds_out=ds)

    assert ds.RescaleIntercept == "-1024.0"
    assert ds.RescaleSlope == "1.0"

    # Convert raw CT values to Hounsfield units
    hu = apply_rescale(arr, ds)


Converting to an :class:`~numpy.ndarray` with metadata
------------------------------------------------------

While :func:`~pydicom.pixels.pixel_array` and :func:`~pydicom.pixels.iter_pixels`
should cover most use cases, you may want more information about the returned
:class:`~numpy.ndarray`, such as what color space it's in. The :meth:`Decoder.as_array()
<pydicom.pixels.decoders.base.Decoder.as_array>` and :meth:`Decoder.iter_array()
<pydicom.pixels.decoders.base.Decoder.iter_array>` methods provide mid-level access
to *pydicom's* pixel data decoding functionality while still handling most of the complexity
of conversion to an array. More importantly, they return or yield a tuple of
(:class:`~numpy.ndarray`, :class:`dict`), where the :class:`dict` contains metadata
describing the corresponding :class:`~numpy.ndarray`.

.. warning::

    The :class:`~pydicom.pixels.decoders.base.Decoder` class should not be used
    directly, instead use the class instance returned by :func:`~pydicom.pixels.get_decoder`.

.. code-block:: python

    from pydicom import examples
    from pydicom.pixels import get_decoder

    ds = examples.ybr_color
    assert ds.PhotometricInterpretation == "YBR_FULL_422"

    # Get the 'Decoder' instance required to decode the dataset's pixel data
    decoder = get_decoder(ds.file_meta.TransferSyntaxUID)

    # Converts the pixel data to an ndarray in the original color space
    arr, meta = decoder.as_array(ds, raw=True, index=0)
    assert (meta["rows"], meta["columns"], meta["samples_per_pixel"]) == arr.shape
    assert meta["photometric_interpretation"] == "YBR_FULL_422"

    # Converts the pixel data to an ndarray in RGB color space
    arr, meta = decoder.as_array(ds, index=0)
    assert meta["photometric_interpretation"] == "RGB"

This is especially useful for non-conformant datasets where the :dcm:`Image Pixel
<part03/sect_C.7.6.3.html>` module elements have values that don't match the
actual pixel data (such as *Number of Frames* or *Photometric Interpretation*).


Conclusion and next steps
-------------------------

In part 1 of this tutorial you've been introduced to DICOM's pixel data and learned how to
use *pydicom* to access it, convert it to an :class:`~numpy.ndarray` and how to
control the conversion process. In the next part you'll learn how to
:doc:`create your own pixel data from scratch</tutorials/pixel_data/creation>`.
