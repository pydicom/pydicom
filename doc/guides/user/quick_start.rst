===================
pydicom quick start
===================

Welcome to the quick start guide for *pydicom*.

*pydicom* is an MIT licensed, open source `Python <https://www.python.org/>`_ library for
creating, reading, modifying and writing `DICOM <https://www.dicomstandard.org/>`_
:dcm:`Data Sets<part05/chapter_7.html>` (*datasets* for short) and
:dcm:`File-sets<part10/chapter_8.html>`. It can also convert
the imaging and waveform data in certain dataset types to a `NumPy <https://www.numpy.org>`_
`ndarray <https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html>`_ (and back again),
as long as suitable optional packages are :doc:`installed</guides/user/installation>`.

What is a DICOM dataset?
========================

A DICOM dataset represents an instance of a real world object, such as a single image slice from a CT
scan acquisition. Each dataset is made up of a collection of :dcm:`Data Elements
<part05/chapter_7.html#sect_7.1>`, with each Data Element representing an *attribute* of
the object. A Data Element is itself made of a unique identifier called the *Element Tag*,
has a format specifier called the *Value Representation* and contains the *Value* of the
attribute. The DICOM Standard groups Data Elements that describe related attributes
into *modules*.

In :dcm:`Part 3<part03/ps3.3.html>`, the DICOM Standard defines the many different types
of dataset, using something called an Information Object Definition (IOD). Each IOD contains
a table of optional (U) and mandatory (M) modules that a dataset must have in order to meet
that definition. This means you can use the IOD that corresponds to a given dataset to see
what Data Elements it should contain.

As an example, the :dcm:`CT Image IOD<part03/sect_A.3.html>` contains :dcm:`this table
<part03/sect_A.3.3.html>` listing the modules that are required for a dataset to be
considered a valid *CT Image* instance. This includes a
:dcm:`Patient<part03/sect_C.7.html#sect_C.7.1.1>` module, which contains patient
demographic attributes, a :dcm:`CT Image<part03/sect_C.8.2.html#sect_C.8.2.1>` module,
which describes the CT image data, as well as all the other mandatory modules.

If we look at :dcm:`the page<part03/sect_C.7.html#sect_C.7.1.1>` for the *Patient* module
we see that it contains a *Patient's Name* attribute, with a *Type* of 2. This means
that in any given *CT Image* dataset we should be able to find a *Patient's Name* Data
Element - although it may not have a useful value, as Type 2 means :dcm:`it must be present but
may have an empty value<part05/sect_7.4.3.html>`.

.. include:: /tutorials/_dataset_basics_content.rst


Accessing *Pixel Data*
======================

.. seealso::

    We have a separate and more in-depth :doc:`pixel data tutorial</tutorials/pixel_data/index>`
    that covers: conversion to an ``ndarray``, creation of new pixel data, and compressing and
    decompressing existing pixel data.

Many DICOM datasets have image or other image-like data available in the (7FE0,0010) *Pixel
Data* element. If present, the data will either be available as uncompressed raw binary data
or as an encapsulated and compressed image codestream, depending on the *Transfer Syntax UID*::

    >>> ds = examples.ct
    >>> ds.file_meta.TransferSyntaxUID.is_compressed
    False
    >>> ds = examples.jpeg2k
    >>> ds.file_meta.TransferSyntaxUID.is_compressed
    True

As :class:`bytes`
-----------------

For datasets with an uncompressed *Transfer Syntax UID*, accessing the image data is
simply a matter of accessing the *Pixel Data* value, which will return all frames
concatenated together as :class:`bytes`::

    >>> ds = examples.ct
    >>> pixel_data = ds.PixelData
    >>> type(pixel_data)
    <class 'bytes'>
    >>> len(pixel_data)
    32768

For datasets with a compressed *Transfer Syntax*, each frame of image data will have
been :dcm:`encapsulated<part05/sect_A.4.html>`, which must first be removed. In *pydicom*
this can be done with the :func:`~pydicom.encaps.get_frame` function or the
:func:`~pydicom.encaps.generate_frames` iterator to return or yield a frame of compressed
image data as :class:`bytes`::

    >>> from pydicom.encaps import get_frame
    >>> ds = examples.jpeg2k
    >>> len(ds.PixelData)
    152326
    >>> nr_frames = ds.get("NumberOfFrames", 1)  # Number Of Frames is Type 3
    >>> frame = get_frame(ds.PixelData, 0, number_of_frames=nr_frames)
    >>> len(frame)
    152294

As a NumPy :class:`~numpy.ndarray`
----------------------------------

.. currentmodule:: pydicom.dataset

.. note::

    Converting uncompressed *Pixel Data* to an :class:`~numpy.ndarray` requires installing
    `NumPy <https://www.numpy.org>`_, and converting compressed *Pixel Data* may
    require installing other packages. See :doc:`this page</guides/plugin_table>`
    for a list of supported transfer syntaxes and the packages required to decompress
    them.

There are three main methods for converting *Pixel Data* to an :class:`~numpy.ndarray`,
depending on your use case:

1. Using the :attr:`Dataset.pixel_array<Dataset.pixel_array>` property, in conjunction
   with :meth:`Dataset.pixel_array_options()<Dataset.pixel_array_options>`.
2. Using the :func:`~pydicom.pixels.pixel_array` and :func:`~pydicom.pixels.iter_pixels`
   functions.
3. Using :meth:`Decoder.as_array()<pydicom.pixels.decoders.base.Decoder.as_array>` and
   :meth:`Decoder.iter_array()<pydicom.pixels.decoders.base.Decoder.iter_array>`instance methods.

With :attr:`Dataset.pixel_array<Dataset.pixel_array>`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The most convenient way to return the entire pixel data as an :class:`~numpy.ndarray`
is with the :attr:`Dataset.pixel_array<Dataset.pixel_array>` property::

    >>> from pydicom import examples
    >>> ds = examples.ybr_color
    >>> arr = ds.pixel_array
    >>> arr.shape
    (30, 240, 320, 3)


This will load the entire pixel data into memory and convert it to a ``ndarray``. By default,
it will also convert any pixel data in the :wiki:`YCbCr<YCbCr>` color space to RGB using
the :func:`~pydicom.pixels.convert_color_space` function. Customization of the conversion
process can be done through :meth:`Dataset.pixel_array_options()<Dataset.pixel_array_options>`.

.. code-block:: python

    >>> ds.pixel_array_options(index=0)  # Convert only the first frame
    >>> arr = ds.pixel_array  # still reads all frames into memory
    >>> arr.shape
    (240, 320, 3)

The main drawbacks of :attr:`Dataset.pixel_array<Dataset.pixel_array>` are:

* It requires loading the entire *Pixel Data* into memory.
* The returned ``ndarray`` lacks any descriptive metadata.
* The conversion can only be customised using a second function.


.. currentmodule:: pydicom.pixels

With :func:`~pixel_array` and :func:`~iter_pixels`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :func:`~pixel_array` and :func:`~iter_pixels` behave in much the same way as
:attr:`Dataset.pixel_array<pydicom.dataset.Dataset.pixel_array>`, only without the need
for a second function to control the conversion process::

    >>> from pydicom.pixels import pixel_array
    >>> arr = pixel_array(ds, index=0)  # reads all frames into memory
    >>> arr.shape
    (240, 320, 3)

If you're concerned about memory usage then both functions can be used with the path to
the dataset instead. This will reduce the amount of *Pixel Data* read into memory to the
minimum required::

    >>> path = examples.get_path("ybr_color")
    >>> arr = pixel_array(path, index=0)   # reads only a single frame into memory

If you need the elements from the dataset's :dcm:`Image Pixel<part03/sect_C.7.6.3.html>`
module in order to perform any required image processing operations (such as windowing
and rescale), you can pass an empty ``Dataset`` via the `ds_out` parameter, which will
be populated by the group ``0x0028`` elements::

    >>> from pydicom.dataset import Dataset
    >>> ds = Dataset()
    >>> arr = pixel_array(path, index=0, ds_out=ds)
    >>> ds.Rows, ds.Columns
    (240, 320)

The main drawback of :func:`~pixel_array` and :func:`~iter_pixels` is that the
returned ``ndarray`` lacks any descriptive metadata.

.. currentmodule:: pydicom.pixels.decoders.base

With :meth:`Decoder.as_array()<Decoder.as_array>` and :meth:`Decoder.iter_array()<Decoder.iter_array>`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. warning::

    Do not use the :class:`~Decoder` class directly, instead use the class instance
    returned by the :func:`~pydicom.pixels.get_decoder` function.

Finally, if you need metadata describing the returned ``ndarray`` then you can use the
:meth:`Decoder.as_array()<Decoder.as_array>` and :meth:`Decoder.iter_array()
<Decoder.iter_array>` methods for the :class:`~Decoder` class instance returned by
:func:`~pydicom.pixels.get_decoder`::

    >>> from pydicom.pixels import get_decoder
    >>> ds = examples.ybr_color
    >>> decoder = get_decoder(ds.file_meta.TransferSyntaxUID)
    >>> arr, meta = decoder.as_array(ds, index=0)
    >>> meta["photometric_interpretation"]
    'RGB'
    >>> meta["number_of_frames"]
    1

The main drawback of using the :class:`~Decoder` methods in the manner shown above is
that the entire *Pixel Data* will be read into memory. However, this doesn't necessarily
have to be the case; the :func:`~pydicom.pixels.pixel_array` and
:func:`~pydicom.pixels.iter_pixels` functions use those same methods to perform
memory-efficient decoding. If you need both image metadata and memory efficiency,
take a look at the source code for those functions to see how to implement it for yourself.
