=============================================
*Pixel Data* - Part 2: Creation of pixel data
=============================================

.. currentmodule:: pydicom

In part 1 of this tutorial you learned how to :doc:`access the pixel data
</tutorials/pixel_data/introduction>` as either the raw :class:`bytes` or a NumPy
:class:`~numpy.ndarray`. In this part we'll be creating pixel data from
scratch and adding it to a :class:`~pydicom.dataset.Dataset`. We'll be creating
uncompressed datasets with the following types of *Pixel Data*:

* Grayscale with 8-bit unsigned integers
* Multi-frame RGB with 8-bit unsigned integers
* Grayscale with 12-bit signed integers
* Grayscale with 32-bit floats (for *Float Pixel Data*)


**Prerequisites**

Installing using pip:

.. code-block:: bash

    python -m pip install -U pydicom numpy matplotlib pylibjpeg[all]

Installing on conda:

.. code-block:: bash

    conda install numpy matplotlib
    conda install -c conda-forge pydicom
    pip install pylibjpeg[all]


Creating *Pixel Data*
---------------------

We'll be using NumPy to create an array containing the pixel data and converting
it to little-endian ordered :class:`bytes` using :meth:`ndarray.tobytes()
<numpy.ndarray.tobytes>`. This is the function we'll be using to create the array::

    import numpy as np

    def draw_circle(shape: tuple[int, int], dtype: str, value: int) -> np.ndarray:
        """Return an ndarray containing a circle."""
        (rows, columns), radius = shape, min(shape) // 2

        x0, y0 = columns // 2, rows // 2
        x = np.linspace(0, columns, columns)
        y = np.linspace(0, rows, rows)[:, None]

        # Create a boolean array where values inside the radius are True
        arr = (x - x0)**2 + (y - y0)**2 <= radius**2

        # Convert to the required `dtype` and set the maximum `value`
        return arr.astype(dtype) * value


The datasets we'll be creating don't meet the requirements of any DICOM
:dcm:`IOD<part03/chapter_A.html>` and so aren't conformant DICOM SOP instances, but
they're sufficient to demonstrate how to create and add pixel data to a
:class:`~pydicom.dataset.Dataset` using *pydicom*. To create pixel data for an
actual dataset you should check the requirements of the specific IOD you're working
with, as many IODs place restrictions on the allowed values for elements such
as *Bits Stored*, *Photometric Interpretation* and others.

Grayscale with 8-bit unsigned integers
......................................

The first example uses a single frame of grayscale *Pixel Data* with 8-bit unsigned integers:

* For 8-bit pixel values *Bits Stored* is ``8``
* *Bits Allocated* must be a multiple of 8 and not less than *Bits Stored*
* For unsigned integers *Pixel Representation* must be ``0``
* For 8-bit unsigned integers all pixel values must be in the `closed interval
  <https://en.wikipedia.org/wiki/Interval_(mathematics)>`_ [0,  2\ :sup:`8` - 1]
* For pixel data that uses a single sample per pixel, *Samples per Pixel* is ``1``
* The *Photometric Interpretation* should be appropriate for a single sample per pixel
* If *Bits Allocated* is <= 8 then *Pixel Data* uses a VR of **OB**

The :dcm:`VR<part05/sect_6.2.html>` for *Pixel Data* may be **OB** or **OW** depending
on the value of *Bits Allocated*. *pydicom* will set this automatically when
writing the :class:`~pydicom.dataset.Dataset` to file as long as *Bits Allocated* has
been set, but for completeness we'll be setting it manually.

The example has two different sets of *Pixel Data*; one with an even number of bytes
and one with an odd number. The :dcm:`DICOM Standard<part05/chapter_8.html>` requires
odd length *Pixel Data* have trailing padding sufficient to make it an even length,
so the latter case demonstrates how to do so.

Because we'll be using NumPy to create the data we need an array with a :class:`~numpy.dtype`
appropriate for our chosen pixel data properties. For unsigned 8-bit integers
the obvious choice is ``uint8`` as it can contain the values with the minimum
amount of memory usage and can be converted directly to a suitable *Pixel Data*
:class:`bytes` value with :meth:`ndarray.tobytes()<numpy.ndarray.tobytes>`.
If instead we were to use something like ``uint16`` we would double the memory usage
and require either setting ``ds.BitsAllocated = 16`` (and roughly doubling the
final size of the dataset) or keeping *Bits Stored* as ``8`` and stripping out the
unused bytes with ``ds.PixelData == arr.tobytes()[1::2]``.

.. code-block:: python

    import matplotlib.pyplot as plt

    from pydicom import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian

    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds.BitsAllocated = 8  # 8-bit containers
    ds.BitsStored = 8  # 8-bits used
    ds.HighBit = ds.BitsStored - 1
    ds.PixelRepresentation = 0  # unsigned

    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"

    ## Even number of bytes
    # Create a 480 x 320, 8-bit unsigned array
    arr = draw_circle((320, 480), "uint8", 255)
    assert arr.size % 2 == 0

    # No padding needed
    ds.PixelData = arr.tobytes()
    ds["PixelData"].VR = "OB"
    ds.Rows = arr.shape[0]  # 320 pixels
    ds.Columns = arr.shape[1]  # 480 pixels

    plt.imshow(ds.pixel_array)
    plt.show()

    ## Odd number of bytes
    # Create a 31 x 63, 8-bit unsigned array
    arr = draw_circle((63, 31), "uint8", 255)
    assert arr.size % 2 == 1

    # Trailing padding required to make the length an even number of bytes
    ds.PixelData = b"".join((arr.tobytes(), b"\x00"))
    ds["PixelData"].VR = "OB"
    ds.Rows = arr.shape[0]
    ds.Columns = arr.shape[1]

    plt.imshow(ds.pixel_array)
    plt.show()


**Experimentation**

Modify the example to use the following and see what effects they have on the
displayed images:

* Set *Bits Allocated* and *Bits Stored* to ``16`` and ``ds.Columns = arr.shape[1] // 2``
* Set ``ds.Rows = arr.shape[1]`` and ``ds.Columns = arr.shape[0]``


Multi-frame RGB with 8-bit unsigned integers
............................................

The second example uses multi-frame RGB *Pixel Data* with 8-bit unsigned integers:

* *Samples per Pixel* has changed to ``3``, because there are 3 channels; R, G and B.
* *Photometric Interpretation* has changed to ``"RGB"`` to match the image type
* *Planar Configuration* has been added as it's required when *Samples per Pixel* > 1
* *Number of Frames* has been added as it's required when there are multiple frames

The *Planar Configuration* value is set as ``0``, which means each pixel is encoded
separately then all the encoded pixels are concatenated together. This matches how
:meth:`ndarray.tobytes()<numpy.ndarray.tobytes>` will encode an array that's ordered as
(rows, columns, samples) or (frames, rows, columns, samples).

.. code-block:: python

    import matplotlib.pyplot as plt

    from pydicom import Dataset, FileMetaDataset
    from pydicom.pixels import iter_pixels
    from pydicom.uid import ExplicitVRLittleEndian

    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds.BitsAllocated = 8  # 8-bit containers
    ds.BitsStored = 8  # 8-bits used
    ds.HighBit = ds.BitsStored - 1
    ds.PixelRepresentation = 0  # unsigned

    ds.SamplesPerPixel = 3
    ds.PhotometricInterpretation = "RGB"
    ds.PlanarConfiguration = 0
    ds.NumberOfFrames = 2

    # Create 2 frames of 480 x 320 x 3, 8-bit unsigned array
    arr = np.empty((2, 320, 480, 3), dtype="uint8")
    # Frame 1
    arr[0, ..., 0] = draw_circle((320, 480), "uint8", 255)
    arr[0, ..., 1] = draw_circle((320, 480), "uint8", 127)
    arr[0, ..., 2] = draw_circle((320, 480), "uint8", 0)

    # Frame 2
    arr[1, ..., 0] = draw_circle((320, 480), "uint8", 0)
    arr[1, ..., 1] = draw_circle((320, 480), "uint8", 127)
    arr[1, ..., 2] = draw_circle((320, 480), "uint8", 255)

    ds.PixelData = b"".join((arr.tobytes(), b"\x00")) if arr.size % 2 else arr.tobytes()
    ds["PixelData"].VR = "OB"
    ds.Rows = arr.shape[1]
    ds.Columns = arr.shape[2]

    # Display the frames
    im = plt.imshow(np.zeros((ds.Rows, ds.Columns, 3), dtype="uint8"))
    for frame in iter_pixels(ds):
        im.set_data(frame)
        plt.pause(1)


**Experimentation**

* A *Planar Configuration* value of ``1`` means each color channel is encoded
  separately and then the results concatenated together. Try setting
  ``ds.PlanarConfiguration = 1`` and seeing what effect it has.
* By default *pydicom* will :doc:`return any extra frames</guides/decoding/decoder_options>`
  it finds in the *Pixel Data*. Set ``ds.NumberOfFrames = 1`` and see what effect it has,
  then pass ``allow_excess_frames=False`` to :func:`~pydicom.pixels.iter_pixels` and compare
  the results.


Grayscale with 12-bit signed integers
.....................................

The final *Pixel Data* example uses a single channel of 12-bit signed integers:

* For 12-bit pixel values *Bits Stored* is ``12`` and *Bits Allocated* should be at least ``16``
* For signed integers *Pixel Representation* must be ``1``
* For 12-bit signed integers all pixels must have values in the `closed interval
  <https://en.wikipedia.org/wiki/Interval_(mathematics)>`_ [-2\ :sup:`11`, 2\ :sup:`11` - 1]
* If *Bits Allocated* is > 8 then *Pixel Data* uses a VR of **OW**

We need a :class:`~numpy.dtype` sufficient for containing 12-bit integers, so
to minimize memory usage we'll go with ``int16`` and use a *Bits Allocated* value
of ``16`` to match.

.. code-block:: python

    import matplotlib.pyplot as plt

    from pydicom import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian

    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds.BitsAllocated = 16  # 16-bits allocated
    ds.BitsStored = 12  # 12-bits used; interval is [-2048, 2047]
    ds.HighBit = ds.BitsStored - 1
    ds.PixelRepresentation = 1  # signed

    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"

    # Create a 480 x 320, 16-bit signed array
    arr = draw_circle((320, 480), "int16", -2048)

    ds.PixelData = arr.tobytes()
    ds["PixelData"].VR = "OW"
    ds.Rows = arr.shape[0]
    ds.Columns = arr.shape[1]

    plt.imshow(ds.pixel_array)
    plt.show()


**Experimentation**

Set *Pixel Representation* to 0 and see what effect it has on the value of the
pixels in the circle.


Creating *Float Pixel Data* and *Double Float Pixel Data*
---------------------------------------------------------

The creation of *Float Pixel Data* or *Double Float Pixel Data* is very similar to
that of *Pixel Data*, the main differences being:

* *Bits Allocated* and *Bits Stored* are always 32 for *Float Pixel Data* and 64
  for *Double Float Pixel Data*
* The *Pixel Representation* element should not be present
* The VR doesn't need to be set manually

+---------------------------+--------+------------------+---------------+-----------------------+
| Element                   | VR     | *Bits Allocated* | *Bits Stored* | :class:`~numpy.dtype` |
+===========================+========+==================+===============+=======================+
| *Float Pixel Data*        | **OF** | 32               | 32            | ``float32``           |
+---------------------------+--------+------------------+---------------+-----------------------+
| *Double Float Pixel Data* | **OD** | 64               | 64            | ``float64``           |
+---------------------------+--------+------------------+---------------+-----------------------+

The example below demonstrates creating *Float Pixel Data*::

    from pydicom import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian

    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds.BitsAllocated = 32
    ds.BitsStored = 32
    ds.HighBit = ds.BitsStored - 1
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"

    # Create a 480 x 320, 32-bit float array
    arr = draw_circle((320, 480), "float32", 1024.58)

    ds.FloatPixelData = arr.tobytes()
    ds.Rows = arr.shape[0]
    ds.Columns = arr.shape[1]


Conclusion and next steps
-------------------------

In part 2 of this tutorial you've learned how to create and add a variety of different pixel
data to a :class:`~pydicom.dataset.Dataset` using an :class:`~numpy.ndarray`. In the final
part you'll learn how to :doc:`compress and decompress datasets
</tutorials/pixel_data/compressing>` containing pixel data.
