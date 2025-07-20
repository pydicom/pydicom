
:html_theme.sidebar_secondary.remove: true


=======
pydicom
=======

An easy to use Python package for creating, reading, modifying and writing DICOM files,
with optional support for converting compressed and uncompressed *Pixel Data* to
`NumPy <https://www.numpy.org>`_
`ndarrays <https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html>`_ (and back again).

.. grid:: 2
    :gutter: 2

    .. grid-item-card:: Quick start
        :columns: 6

        | Guide: :doc:`Installation<guides/user/installation>`
        | Tutorial: :doc:`Dataset basics: read, access, modify, write</tutorials/dataset_basics>`
        | Reference: :doc:`What Python type to use for each VR<guides/element_value_types>`
        | Guide: :doc:`A DICOM primer<guides/dicom>`
        | Examples: A | B | C | D

    .. grid-item-card:: User guide
        :columns: 6

        | :doc:`Get started</guides/user/installation>`
        | :doc:`Fundamentals</guides/user/installation>`
        | :doc:`Pixel Data</guides/user/installation>`
        | :doc:`Overlays and waveforms</guides/user/installation>`
        | :doc:`Extras</guides/user/installation>`

    .. grid-item-card:: Pixel Data
        :columns: 12

        | Tutorial: :doc:`Introduction & accessing</tutorials/pixel_data/introduction>` |
          :doc:`Creating new Pixel Data</tutorials/pixel_data/creation>` |
          :doc:`Compression and decompression</tutorials/pixel_data/compressing>`
        | Reference: Supported transfer syntaxes and plugin information for *Pixel Data*
          :ref:`compression <guide_encoding_plugins>` and
          :ref:`decompression <guide_decoding_plugins>`
        | Guide: *Pixel Data* compression using :doc:`RLE Lossless</guides/encoding/rle_lossless>` |
          :doc:`JPEG-LS</guides/encoding/jpeg_ls>` |
          :doc:`JPEG 2000</guides/encoding/jpeg_2k>` |
          :doc:`Deflated Image</guides/encoding/defl_image>`
        | Examples: A | B | C | D | and more...

    .. grid-item-card:: Examples
        :columns: 6

        | Tutorial: :doc:`DICOM File-sets and DICOMDIR</tutorials/filesets>`
        | Tutorial: :doc:`Waveform decoding and encoding</tutorials/waveforms>`
        | Guide: :doc:`Command line utilities</guides/cli/cli_guide>`

    .. grid-item-card:: Extras
        :columns: 6

        | Tutorial: :doc:`DICOM File-sets and DICOMDIR</tutorials/filesets>`
        | Tutorial: :doc:`Waveform decoding and encoding</tutorials/waveforms>`
        | Guide: :doc:`Command line utilities</guides/cli/cli_guide>`


User Guide
==========

The

.. toctree::
   :maxdepth: 2

   guides/user/index


Tutorials and guides
====================

.. toctree::
   :maxdepth: 1

   tutorials/index
   guides/index


Examples
========

A set of examples illustrating the use of the different core elements.

.. toctree::
   :maxdepth: 2

   auto_examples/index

Utilities
=========

Some CLI utilities

.. toctree::
   :maxdepth: 2

   guides/cli/cli_guide


Reference
=========

Documentation for *pydicom's* public functions, classes and other objects.

.. toctree::
   :maxdepth: 1

   reference/index


Releases
========

.. toctree::
   :maxdepth: 1

   release_notes/index
