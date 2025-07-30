===================
pydicom quick start
===================

Welcome to the quick start guide for *pydicom*.

*pydicom* is an MIT licensed, open source `Python <https://www.python.org/>`_ library for
creating, reading, modifying and writing `DICOM <https://www.dicomstandard.org/>`_
:dcm:`Data Sets<part05/chapter_7.html>` (*datasets* for short) and
:dcm:`File-sets<part10/chapter_8.html>`. It can also convert
the imaging and waveform data in certain dataset types to a `NumPy <https://www.numpy.org>`_
``ndarray`` (and back again), as long as suitable optional packages are :doc:`installed
</guides/user/installation>`.

What is a DICOM dataset?
========================

A DICOM dataset represents an instance of a real world object, such as a single image slice from
a CT scan acquisition. Each dataset is made up of a collection of :dcm:`Data Elements
<part05/chapter_7.html#sect_7.1>`, with each Data Element representing an *attribute* of
the object. A Data Element is itself made of a unique identifier called the *Element Tag*,
has a format specifier called the *Value Representation* and contains the *Value* of the
attribute. The DICOM Standard groups Data Elements that describe related attributes
into *modules*.

In :dcm:`Part 3<part03/ps3.3.html>`, the DICOM Standard defines the many different types
of dataset using something called an Information Object Definition (IOD). Each IOD contains
a table of optional (U) and mandatory (M) modules that a dataset must have in order to meet
that definition. This means you can use the IOD that corresponds to a given dataset to
determine which Data Elements it should contain.

As an example, the :dcm:`CT Image IOD<part03/sect_A.3.html>` contains :dcm:`this table
<part03/sect_A.3.3.html>` with the modules that are required for a dataset to be
considered a valid *CT Image* instance. This includes the *Patient* module, which
contains patient demographic information. If we look at :dcm:`the Patient module
<part03/sect_C.7.html#sect_C.7.1.1>` itself, we see that it contains
attributes for the *Patient's Name*, *Patient ID* and *Patient's Birth Date*, all of
which are considered *Type* 2.

Type 2 attributes :dcm:`must be present, but may have an empty value
<part05/sect_7.4.3.html>`, so in any given *CT Image* dataset we should be able to find
three Data Elements corresponding to those attributes, albeit with no guarantee
they'll have a useful value.

.. include:: /tutorials/_dataset_basics_content.rst


Accessing *Pixel Data*
======================

.. seealso::

    We have a separate and more in-depth :doc:`pixel data tutorial</tutorials/pixel_data/index>`
    that also covers creation of new pixel data and compressing and decompressing existing
    pixel data.

Many DICOM datasets have image and image-like data available in the (7FE0,0010) *Pixel
Data* element. If present, the data will either be available as uncompressed raw binary data
or as an encapsulated and compressed image codestream, depending on the *Transfer Syntax UID*::

    >>> ds = examples.ct
    >>> ds.file_meta.TransferSyntaxUID.is_compressed  # raw binary
    False
    >>> ds = examples.jpeg2k
    >>> ds.file_meta.TransferSyntaxUID.is_compressed  # encapsulated codestreams
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
been :dcm:`encapsulated<part05/sect_A.4.html>`, which must be reversed. In *pydicom*
this can be done with the :func:`~pydicom.encaps.get_frame` function or the
:func:`~pydicom.encaps.generate_frames` iterator to return or yield a frame of compressed
image data as :class:`bytes`::

    >>> from pydicom.encaps import get_frame
    >>> ds = examples.jpeg2k
    >>> len(ds.PixelData)
    152326
    >>> nr_frames = ds.get("NumberOfFrames", 1)  # Number Of Frames may not be present
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
2. Using the :func:`~pydicom.pixels.pixel_array` or :func:`~pydicom.pixels.iter_pixels`
   functions.
3. Using the :meth:`Decoder.as_array()<pydicom.pixels.decoders.base.Decoder.as_array>` or
   :meth:`Decoder.iter_array()<pydicom.pixels.decoders.base.Decoder.iter_array>` instance
   methods.

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
* The ``ndarray`` is kept as an attribute of the dataset, taking up memory when it might
  not need to do so.
* The returned ``ndarray`` lacks any descriptive metadata.
* The conversion can only be customized using a second function.


.. currentmodule:: pydicom.pixels

With :func:`~pixel_array` and :func:`~iter_pixels`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :func:`~pixel_array` and :func:`~iter_pixels` functions convert the pixel data data
to an ``ndarray`` directly::

    >>> from pydicom.pixels import pixel_array
    >>> arr = pixel_array(ds, index=0)  # reads all frames into memory
    >>> arr.shape
    (240, 320, 3)

If you're concerned about memory usage, both functions can be used with the path to
the dataset instead. This will reduce the amount of *Pixel Data* read into memory to the
minimum required::

    >>> path = examples.get_path("ybr_color")
    >>> arr = pixel_array(path, index=0)   # reads only a single frame into memory

If you need the elements from the dataset's :dcm:`Image Pixel<part03/sect_C.7.6.3.html>`
module in order to perform any required image processing operations (such as
:func:`rescale<pydicom.pixels.apply_rescale>` and :func:`windowing<pydicom.pixels.apply_windowing>`),
you can pass an empty ``Dataset`` via the `ds_out` parameter, which will be populated by the
group ``0x0028`` elements::

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

Finally, if you need metadata describing the returned ``ndarray``, you can use the
:meth:`Decoder.as_array()<Decoder.as_array>` and :meth:`Decoder.iter_array()
<Decoder.iter_array>` methods for the ``Decoder`` class instance returned by
:func:`~pydicom.pixels.get_decoder`::

    >>> from pydicom.pixels import get_decoder
    >>> ds = examples.ybr_color
    >>> decoder = get_decoder(ds.file_meta.TransferSyntaxUID)
    >>> arr, meta = decoder.as_array(ds, index=0)
    >>> meta["photometric_interpretation"]
    'RGB'
    >>> meta["number_of_frames"]
    1

The main drawback of using the ``Decoder`` methods in the manner shown above is
that the entire *Pixel Data* will be read into memory. However, this doesn't necessarily
have to be the case; the :func:`~pydicom.pixels.pixel_array` and
:func:`~pydicom.pixels.iter_pixels` functions use those same methods to perform
memory-efficient decoding. If you need both image metadata and memory efficiency,
take a look at the source code for those functions to see how you can implement this yourself.


Loading a File-set
==================

.. currentmodule:: pydicom.fileset

.. seealso::

    We have a separate and more in-depth :doc:`File-set tutorial</tutorials/filesets>`
    that also covers creating and modifying File-sets.

A File-set is a collection of (usually) related datasets that have been written to file and share
a common naming space. They're identifiable by a ``DICOMDIR`` file located in their root
directory, which is used to summarize the File-set's contents. While the DICOMDIR file can be
read using :func:`~pydicom.filereader.dcmread` like any other DICOM dataset, we recommend that
you use the :class:`~pydicom.fileset.FileSet` class to manage the DICOMDIR and related File-set
instead.

.. warning::

    The DICOMDIR dataset contains a series of records that are referenced to each other by
    their file offsets, which makes it very easy to 'break' a DICOMDIR dataset, even by
    changing something seemingly innocuous like the (0004,1130) *File-set ID*. This is why we
    recommend using :class:`~pydicom.fileset.FileSet` to manage any changes.

.. code-block:: python

    >>> from pydicom import examples
    >>> from pydicom.fileset import FileSet
    >>> path = examples.get_path("dicomdir")  # The path to the example File-set
    >>> fs = FileSet(path)

A summary of the File-set's contents is shown when printing::

    >>> print(fs)
    DICOM File-set
      Root directory: .../pydicom/data/test_files/dicomdirtests
      File-set ID: PYDICOM_TEST
      File-set UID: 1.2.276.0.7230010.3.1.4.0.31906.1359940846.78187
      Descriptor file ID: (no value available)
      Descriptor file character set: (no value available)
      Changes staged for write(): DICOMDIR update, directory structure update

      Managed instances:
        PATIENT: PatientID='77654033', PatientName='Doe^Archibald'
          STUDY: StudyDate=20010101, StudyTime=000000, StudyDescription='XR C Spine Comp Min 4 Views'
            SERIES: Modality=CR, SeriesNumber=1
              IMAGE: 1 SOP Instance
            SERIES: Modality=CR, SeriesNumber=2
              IMAGE: 1 SOP Instance
            SERIES: Modality=CR, SeriesNumber=3
              IMAGE: 1 SOP Instance
          STUDY: StudyDate=19950903, StudyTime=173032, StudyDescription='CT, HEAD/BRAIN WO CONTRAST'
            SERIES: Modality=CT, SeriesNumber=2
              IMAGE: 4 SOP Instances
        PATIENT: PatientID='98890234', PatientName='Doe^Peter'
          STUDY: StudyDate=20010101, StudyTime=000000
            SERIES: Modality=CT, SeriesNumber=4
              IMAGE: 2 SOP Instances
            SERIES: Modality=CT, SeriesNumber=5
              IMAGE: 5 SOP Instances
          ...

You can search the File-set with the :meth:`~FileSet.find_values` method to
return a list of element values found in the DICOMDIR's records::

    >>> fs.find_values("PatientID")
    ['77654033', '98890234']

The search can be expanded to the File-set's managed instances (its datasets), by passing
``load=True``, at the cost of a longer search time due to having to read and decode the
corresponding files::

    >>> fs.find_values("PhotometricInterpretation")
    []
    >>> fs.find_values("PhotometricInterpretation", load=True)
    ['MONOCHROME1', 'MONOCHROME2']

The File-set can also be searched to find instances matching a query using the
:meth:`~FileSet.find` method, which returns a list of :class:`~FileInstance` that
can be read and decoded using :meth:`FileInstance.load` to return them as a
:class:`~pydicom.dataset.FileDataset`::

    >>> matches = fs.find(PatientID="77654033")
    >>> len(matches)
    7
    >>> ds = matches[0].load()
    >>> ds.PatientName
    'Doe^Archibald'

:meth:`~FileSet.find` also supports the use of the `load` parameter::

    >>> len(fs.find(PhotometricInterpretation='MONOCHROME1'))
    0
    >>> len(fs.find(PhotometricInterpretation='MONOCHROME1', load=True))
    3
